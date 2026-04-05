import argparse
import json
import os
import re
import sys
import time

import colorama
from colorama import Fore, Style
from deep_translator import GoogleTranslator

colorama.init(autoreset=True)


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES_DIR = os.path.join(BASE_DIR, "src", "locales")
EN_FILE = os.path.join(LOCALES_DIR, "en.json")


DEFAULT_LANGS = {
    "he": "iw",
    "ru": "ru",
    "es": "es",
    "fr": "fr",
    "de": "de",
    "ar": "ar",
    "it": "it",
    "pt": "pt",
    "tr": "tr",
    "id": "id",
    "fa": "fa",
    "hi": "hi",
    "uk": "uk",
    "pl": "pl",
    "nl": "nl",
    "zh": "zh-CN",
    "ja": "ja",
    "ko": "ko",
}


class LocaleManager:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.en_data: dict[str, str] = {}
        self.load_en()

    def load_en(self):
        """Load and sort en.json as source of truth."""
        if not os.path.exists(EN_FILE):
            print(f"{Fore.RED}Error: en.json not found at {EN_FILE}")
            sys.exit(1)

        with open(EN_FILE, encoding="utf-8") as f:
            data = json.load(f)

        self.en_data = dict(sorted(data.items()))

    def save_json(self, path: str, data: dict[str, str]):
        """Save JSON with consistent formatting."""

        final_data = {k: data[k] for k in self.en_data if k in data}

        with open(path, "w", encoding="utf-8") as f:
            json.dump(final_data, f, ensure_ascii=False, indent=2)

    def get_locale_path(self, lang: str) -> str:
        return os.path.join(LOCALES_DIR, f"{lang}.json")

    def load_locale(self, lang: str) -> dict[str, str]:
        path = self.get_locale_path(lang)
        if not os.path.exists(path):
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            if self.verbose:
                print(f"{Fore.YELLOW}Warning: Could not load {lang}.json ({e})")
            return {}


class SmartTranslator:
    def __init__(self, target_lang_code: str):
        self.target_code = target_lang_code
        self.translator = GoogleTranslator(source="en", target=target_lang_code)

    def protect_placeholders(self, text: str) -> tuple[str, dict[str, str]]:
        """Hardened placeholder protection using double-bracketed tokens."""

        placeholders = re.findall(r"\{[^{}]+\}", text)
        ph_map = {}
        temp_text = text
        for i, p in enumerate(placeholders):
            token = f"[[--T_PH_{i}--]]"
            ph_map[token] = p
            temp_text = temp_text.replace(p, token)
        return temp_text, ph_map

    def restore_placeholders(self, text: str, ph_map: dict[str, str]) -> str:
        """Restore protected placeholders and clean up common translator artifacts."""
        if not text:
            return text
        for token, original in ph_map.items():
            inner = token.strip(" []-")
            pattern = re.compile(rf"\[\[\s*-*\s*{re.escape(inner)}\s*-*\s*\]\]", re.IGNORECASE)
            text = pattern.sub(original, text)

        for original in ph_map.values():
            text = text.replace(f"{original}_", original)
            text = text.replace(f"{original} ", original + " ")

        return text.strip()

    def translate_batch(self, texts: list[str]) -> list[str] | None:
        """Batch translation with separator validation."""
        if not texts:
            return []

        protected_pairs = [self.protect_placeholders(t) for t in texts]
        payload = " |§| ".join([p[0] for p in protected_pairs])

        try:
            translated_blob = self.translator.translate(payload)

            translated_list = [t.strip() for t in translated_blob.split("|§|")]

            if len(translated_list) != len(texts):
                return None

            return [
                self.restore_placeholders(t, protected_pairs[i][1])
                for i, t in enumerate(translated_list)
            ]
        except Exception:
            return None


def render_progress_bar(
    current: int, total: int, prefix: str = "PROGRESS", status: str = "", length: int = 40
):
    """Renders a sleek, global progress bar."""
    percent = (current / total) if total > 0 else 1.0
    filled_len = int(length * percent)

    bar = "█" * filled_len + "▒" * (length - filled_len)

    color = Fore.CYAN if percent < 1.0 else Fore.GREEN
    prefix_fmt = f"{Fore.WHITE}{Style.BRIGHT}{prefix:<10}"
    status_fmt = f"{Fore.YELLOW}{status:<15}"

    sys.stdout.write(
        f"\r  {prefix_fmt} {color}{bar} {int(percent * 100):>3}% ({current}/{total}) | {status_fmt}"
    )
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Advanced Locale Translation Tool")
    parser.add_argument("--langs", help="Target languages (he,ru,etc.)", type=str)
    parser.add_argument("--sort", action="store_true", help="Only sort files and sync keys")
    parser.add_argument(
        "--check", action="store_true", help="Check for differences without translating"
    )
    parser.add_argument(
        "--force", action="store_true", help="Force re-translation of existing keys"
    )
    parser.add_argument(
        "--keys", help="Specific keys to force translate (comma-separated)", type=str
    )
    parser.add_argument("--verbose", action="store_true", help="Detailed logging")
    args = parser.parse_args()

    mgr = LocaleManager(args.verbose)
    target_langs = args.langs.split(",") if args.langs else DEFAULT_LANGS.keys()

    print(f"{Fore.CYAN}{Style.BRIGHT}Locale Manager v2.0")
    print(f"{Fore.WHITE}Master: {EN_FILE} ({len(mgr.en_data)} keys)")

    if args.sort:
        mgr.save_json(EN_FILE, mgr.en_data)
        print(f"{Fore.GREEN}✓ en.json sorted and saved.\n")

    force_keys = args.keys.split(",") if args.keys else []

    work_plan = []
    total_to_translate = 0

    if not args.sort:
        print(f"{Fore.WHITE}Scanning locales for updates...")
        for lang_name in target_langs:
            lang_code = DEFAULT_LANGS.get(lang_name, lang_name)
            data = mgr.load_locale(lang_name)

            missing = [k for k in mgr.en_data if k not in data or args.force or k in force_keys]
            extra = [k for k in data if k not in mgr.en_data]

            if missing or extra:
                work_plan.append(
                    {
                        "name": lang_name,
                        "code": lang_code,
                        "path": mgr.get_locale_path(lang_name),
                        "data": data,
                        "missing": missing,
                        "extra": extra,
                    }
                )
                total_to_translate += len(missing)

    if not work_plan and not args.sort:
        print(f"{Fore.GREEN}✓ All locales are already up to date.")
        return

    if args.check:
        for job in work_plan:
            print(f"\n{Fore.BLUE}➤ {job['name'].upper()} ({job['path']})")
            if job["extra"]:
                print(f"  {Fore.RED}× Found {len(job['extra'])} extra keys.")
            if job["missing"]:
                print(f"  {Fore.YELLOW}∆ Found {len(job['missing'])} keys needing translation.")
        return

    global_done = 0

    for job in work_plan:
        lang_name = job["name"]
        data = job["data"]
        missing = job["missing"]
        extra = job["extra"]

        for k in extra:
            del data[k]

        if missing:
            translator = SmartTranslator(job["code"])
            to_translate = [mgr.en_data[k] for k in missing]
            results = []

            chunk_size = 20
            for i in range(0, len(to_translate), chunk_size):
                chunk = to_translate[i : i + chunk_size]

                render_progress_bar(
                    global_done + i,
                    total_to_translate,
                    prefix="PROGRESS",
                    status=f"Translating {lang_name.upper()}",
                )

                batch = translator.translate_batch(chunk)
                if batch:
                    results.extend(batch)
                else:
                    for t in chunk:
                        p_text, p_map = translator.protect_placeholders(t)
                        try:
                            res = translator.translator.translate(p_text)
                            results.append(translator.restore_placeholders(res, p_map))
                        except Exception:
                            results.append(t)

                time.sleep(0.4)

            for i, k in enumerate(missing):
                data[k] = results[i]

            global_done += len(missing)

        mgr.save_json(job["path"], data)

    if total_to_translate > 0:
        render_progress_bar(
            total_to_translate, total_to_translate, prefix="COMPLETE", status="All Synchronized"
        )
        print(
            f"\n\n{Fore.GREEN}{Style.BRIGHT}✓ Translation and synchronization successfully completed."
        )
    elif work_plan:
        print(f"\n{Fore.GREEN}✓ Synchronized extra keys and sorted locales.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Fore.RED}🛑 Translation aborted by user.")
        sys.exit(1)
