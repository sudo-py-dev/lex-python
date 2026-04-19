"""Locale translation tool using Rich for beautiful CLI output."""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

from deep_translator import GoogleTranslator
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

console = Console()

BASE_DIR = Path(__file__).parent.parent
LOCALES_DIR = BASE_DIR / "src" / "locales"
EN_FILE = LOCALES_DIR / "en.json"

DEFAULT_LANGS: dict[str, str] = {
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
    "hi": "hi",
    "uk": "uk",
    "pl": "pl",
    "nl": "nl",
    "zh": "zh-CN",
    "ja": "ja",
    "ko": "ko",
}

PLACEHOLDER_PATTERN = re.compile(r"\{[^{}]+\}")
PLACEHOLDER_TOKEN = "[[--T_PH_{}--]]"
PLACEHOLDER_RESTORE = re.compile(r"\[\[\s*-*\s*T_PH_(\d+)\s*-*\s*\]\]")

TECHNICAL_PATTERNS = [
    re.compile(r"^[A-Z_]+$"),
    re.compile(r"<.*?>"),
    re.compile(r"^IDENTITY:"),
    re.compile(r"^\d+ (MB|GB|KB|week|day|month|year)s?$"),
    re.compile(r"\{time:.*?\}"),
    re.compile(r"^https?://"),
    re.compile(r"^[a-z0-9_\-\.]+\.[a-z]{2,4}(/.*)?$"),
]

EXCLUDED_FILES = {"__init__.py", "i18n.py", "config.py", "prompts.py"}
CHUNK_SIZE = 20


class LocaleManager:
    """Manages locale files and operations."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.en_data: dict[str, str] = {}
        self.load_en()

    def load_en(self) -> None:
        """Load and validate en.json as source of truth."""
        if not EN_FILE.exists():
            console.print(f"[red]Error: en.json not found at {EN_FILE}")
            sys.exit(1)

        with open(EN_FILE, encoding="utf-8") as f:
            self.en_data = dict(sorted(json.load(f).items()))

    def save_json(self, path: Path, data: dict[str, str]) -> None:
        """Save JSON with consistent formatting, preserving key order from en.json."""
        ordered = {k: data[k] for k in self.en_data if k in data}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ordered, f, ensure_ascii=False, indent=2)
            f.write("\n")

    def get_locale_path(self, lang: str) -> Path:
        return LOCALES_DIR / f"{lang}.json"

    def load_locale(self, lang: str) -> dict[str, str]:
        path = self.get_locale_path(lang)
        if not path.exists():
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            if self.verbose:
                console.print(f"[yellow]Warning: Could not load {lang}.json ({e})")
            return {}


class Translator:
    """Handles text translation with placeholder protection."""

    SEPARATOR = " |§| "

    def __init__(self, target_lang: str) -> None:
        self.target = target_lang
        self._translator = GoogleTranslator(source="en", target=target_lang)

    def _protect(self, text: str) -> tuple[str, dict[str, str]]:
        """Protect placeholders with temporary tokens."""
        placeholders = PLACEHOLDER_PATTERN.findall(text)
        mapping: dict[str, str] = {}
        result = text
        for i, ph in enumerate(placeholders):
            token = PLACEHOLDER_TOKEN.format(i)
            mapping[token] = ph
            result = result.replace(ph, token, 1)
        return result, mapping

    def _restore(self, text: str, mapping: dict[str, str]) -> str:
        """Restore placeholders and clean artifacts."""
        if not text:
            return text

        def replace_token(match: re.Match) -> str:
            idx = match.group(1)
            return mapping.get(PLACEHOLDER_TOKEN.format(idx), match.group(0)) or match.group(0)

        result = PLACEHOLDER_RESTORE.sub(replace_token, text)

        for original in mapping.values():
            result = result.replace(f"{original}_", original)
            result = result.replace(f"{original} ", original + " ")

        return result.strip()

    def translate_batch(self, texts: list[str]) -> list[str] | None:
        """Translate multiple texts, preserving placeholders."""
        if not texts:
            return []

        protected = [self._protect(t) for t in texts]
        payload = self.SEPARATOR.join(p[0] for p in protected)

        try:
            translated = self._translator.translate(payload)
            parts = [t.strip() for t in translated.split(self.SEPARATOR.strip())]

            if len(parts) != len(texts):
                return None

            return [self._restore(parts[i], protected[i][1]) for i in range(len(parts))]
        except Exception:
            return None

    def translate_single(self, text: str) -> str:
        """Translate single text with fallback."""
        protected, mapping = self._protect(text)
        try:
            return self._restore(self._translator.translate(protected), mapping)
        except Exception:
            return text


class StringScanner(ast.NodeVisitor):
    """AST scanner to find unlocalized strings."""

    def __init__(self, en_keys: set[str], en_values: set[str], content: str, rel_path: str):
        self.en_keys = en_keys
        self.en_values = en_values
        self.content = content
        self.rel_path = rel_path
        self.lines = content.splitlines()
        self.found: list[tuple[int, str]] = []
        self._in_logger = False
        self._in_fstring = False

    def _is_logger(self, node: ast.Call) -> bool:
        """Check if node is a logger call."""
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            return node.func.value.id in ("logger", "log") and node.func.attr in (
                "debug",
                "info",
                "warning",
                "error",
                "exception",
                "critical",
                "trace",
                "success",
            )
        return isinstance(node.func, ast.Name) and node.func.id in (
            "debug",
            "info",
            "warning",
            "error",
            "exception",
            "trace",
            "success",
        )

    def _should_skip_string(self, val: str, line_no: int) -> bool:
        """Check if a string should be skipped."""
        if len(val) < 5 or " " not in val:
            return True
        if val in self.en_keys or val in self.en_values:
            return True
        if val.isupper() and "_" in val:
            return True
        if any(p.search(val) for p in TECHNICAL_PATTERNS):
            return True

        if 0 < line_no <= len(self.lines):
            line = self.lines[line_no - 1].strip()
            if any(x in line.lower() for x in ["print(", "raise ", "filters.command"]):
                return True
            if line.startswith(("import ", "from ", '"""', "'''")):
                return True

        return False

    def visit_Call(self, node: ast.Call) -> None:
        old = self._in_logger
        if self._is_logger(node):
            self._in_logger = True
        self.generic_visit(node)
        self._in_logger = old

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        if self._in_logger:
            return

        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                val = value.value.strip()
                if self._should_skip_string(val, getattr(value, "lineno", 0)):
                    continue

                line_no = getattr(value, "lineno", 0)
                self.found.append((line_no, val[:60] + "..." if len(val) > 60 else val))

        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if not isinstance(node.value, str) or self._in_logger:
            return

        val = node.value.strip()
        if self._should_skip_string(val, getattr(node, "lineno", 0)):
            return

        line_no = getattr(node, "lineno", 0)
        self.found.append((line_no, val[:60] + "..." if len(val) > 60 else val))


def scan_unlocalized(mgr: LocaleManager) -> int:
    """Scan for hardcoded strings that should be localized."""
    console.print(Panel("[cyan]Scanning for unlocalized strings in src/...", title="Scan"))

    en_keys = set(mgr.en_data.keys())
    en_values = set(mgr.en_data.values())
    total = 0

    for path in (BASE_DIR / "src").rglob("*.py"):
        if path.name in EXCLUDED_FILES:
            continue

        rel = path.relative_to(BASE_DIR)
        try:
            content = path.read_text(encoding="utf-8")
            tree = ast.parse(content)
        except Exception as e:
            if mgr.verbose:
                console.print(f"[red]Error parsing {rel}: {e}")
            continue

        scanner = StringScanner(en_keys, en_values, content, str(rel))
        scanner.visit(tree)

        for line_no, text in scanner.found:
            console.print(f"  [yellow][{rel}:{line_no}][/] [white]{text!r}")
            total += 1

    if total == 0:
        console.print("[green]✓ No unlocalized strings found.")
    else:
        console.print(f"\n[magenta]Found {total} potential unlocalized strings.")
    return total


def find_unused_keys(mgr: LocaleManager) -> list[str]:
    """Find keys in en.json not used in source code."""
    console.print(Panel("[cyan]Scanning for unused localization keys...", title="Unused Keys"))

    unused: list[str] = []
    all_content = ""

    for path in (BASE_DIR / "src").rglob("*.py"):
        try:
            all_content += path.read_text(encoding="utf-8") + "\n"
        except Exception:
            continue

    for key in mgr.en_data:
        pattern = rf"(['\"]){re.escape(key)}\1"
        if not re.search(pattern, all_content):
            unused.append(key)

    if not unused:
        console.print("[green]✓ All keys are in use.")
    else:
        console.print(f"[red]Found {len(unused)} potentially unused keys:")
        for key in unused:
            console.print(f"  [yellow]- {key}")

    return unused


def build_work_plan(
    mgr: LocaleManager,
    target_langs: list[str],
    force: bool = False,
    force_keys: set[str] | None = None,
    prune_only: bool = False,
) -> list[dict]:
    """Build translation work plan for target languages."""
    plan = []

    for lang in target_langs:
        lang_code = DEFAULT_LANGS.get(lang, lang)
        data = mgr.load_locale(lang)

        missing = [
            k for k in mgr.en_data if k not in data or force or (force_keys and k in force_keys)
        ]
        extra = [k for k in data if k not in mgr.en_data]

        if prune_only:
            missing = []

        if missing or extra:
            plan.append(
                {
                    "name": lang,
                    "code": lang_code,
                    "path": mgr.get_locale_path(lang),
                    "data": data,
                    "missing": missing,
                    "extra": extra,
                    "is_new": not mgr.get_locale_path(lang).exists(),
                }
            )

    return plan


def translate_job(mgr: LocaleManager, job: dict, progress: Progress, task_id: int) -> None:
    """Execute translation for a single language job."""
    data = job["data"]
    missing = job["missing"]

    for k in job["extra"]:
        del data[k]

    if not missing:
        if job["extra"]:
            console.print(f"[red]➤ {job['name'].upper()}: Pruned {len(job['extra'])} extra keys.")
        mgr.save_json(job["path"], data)
        return

    translator = Translator(job["code"])
    to_translate = [mgr.en_data[k] for k in missing]
    results: list[str] = []

    for i in range(0, len(to_translate), CHUNK_SIZE):
        chunk = to_translate[i : i + CHUNK_SIZE]
        progress.update(
            task_id, advance=0, description=f"[cyan]Translating {job['name'].upper()}[/]"
        )

        batch = translator.translate_batch(chunk)
        if batch:
            results.extend(batch)
        else:
            for text in chunk:
                results.append(translator.translate_single(text))

        progress.update(task_id, advance=len(chunk))
    for i, key in enumerate(missing):
        data[key] = results[i]

    mgr.save_json(job["path"], data)


def display_check_results(plan: list[dict]) -> None:
    """Display check mode results in a table."""
    table = Table(title="Translation Check Results")
    table.add_column("Language", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Missing", style="yellow")
    table.add_column("Extra", style="red")

    for job in plan:
        status = "[yellow]Needs Update" if job["missing"] else "[green]OK"
        table.add_row(
            job["name"].upper(),
            status,
            str(len(job["missing"])),
            str(len(job["extra"])),
        )

    console.print(table)


def display_stats(mgr: LocaleManager, target_langs: list[str]) -> None:
    """Display translation coverage statistics for all locales."""
    table = Table(title="Translation Statistics")
    table.add_column("Language", style="cyan")
    table.add_column("Keys", style="white", justify="right")
    table.add_column("Coverage", style="green", justify="right")
    table.add_column("Missing", style="yellow", justify="right")
    table.add_column("Extra", style="red", justify="right")
    table.add_column("Status", style="white")

    total_keys = len(mgr.en_data)

    for lang in sorted(target_langs):
        data = mgr.load_locale(lang)
        present = len([k for k in mgr.en_data if k in data])
        missing = len([k for k in mgr.en_data if k not in data])
        extra = len([k for k in data if k not in mgr.en_data])

        coverage = (present / total_keys * 100) if total_keys > 0 else 0
        coverage_str = f"{coverage:.1f}%"

        if coverage >= 100:
            status = "[green]✓ Complete"
        elif coverage >= 75:
            status = "[yellow]Partial"
        elif coverage > 0:
            status = "[red]Incomplete"
        else:
            status = "[dim]Empty"

        table.add_row(
            lang.upper(),
            str(len(data)),
            coverage_str,
            str(missing),
            str(extra),
            status,
        )

    console.print(table)
    console.print(f"\n[dim]Total keys in en.json: {total_keys}")


def sort_all_locales(mgr: LocaleManager, target_langs: list[str], dry_run: bool = False) -> None:
    """Sort all locale files to match en.json key order."""
    sorted_count = 0

    for lang in target_langs:
        path = mgr.get_locale_path(lang)
        if not path.exists():
            continue

        data = mgr.load_locale(lang)
        if not data:
            continue

        expected_order = [k for k in mgr.en_data if k in data]
        current_order = [k for k in data if k in mgr.en_data]

        if current_order != expected_order or any(k not in mgr.en_data for k in data):
            if not dry_run:
                mgr.save_json(path, data)
            sorted_count += 1
            action = "[dry-run] Would sort" if dry_run else "Sorted"
            console.print(f"  [green]✓ {action} {lang}.json")

    if sorted_count == 0:
        console.print("  [green]✓ All locales already sorted.")
    else:
        action = "would be" if dry_run else "have been"
        console.print(f"\n[green]✓ {sorted_count} locale file(s) {action} sorted.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Locale Translation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--langs", help="Target languages (comma-separated, e.g., he,ru,es)")
    parser.add_argument(
        "--sort", action="store_true", help="Sort all locale files to match en.json key order"
    )
    parser.add_argument(
        "--check", action="store_true", help="Check differences without translating"
    )
    parser.add_argument("--force", action="store_true", help="Force re-translation of all keys")
    parser.add_argument("--keys", help="Specific keys to force translate (comma-separated)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")
    parser.add_argument("--scan", action="store_true", help="Scan for unlocalized strings")
    parser.add_argument("--unused", action="store_true", help="Find unused keys")
    parser.add_argument(
        "--prune", action="store_true", help="Only prune extra keys, no translation"
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="Show translation statistics for all locales"
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true", help="Preview changes without modifying files"
    )
    parser.add_argument("--create", help="Create new locale file(s) for specified language(s)")
    args = parser.parse_args()

    mgr = LocaleManager(args.verbose)

    if args.list:
        all_langs = sorted([f.stem for f in LOCALES_DIR.glob("*.json") if f.name != "en.json"])
        display_stats(mgr, all_langs or list(DEFAULT_LANGS.keys()))
        return

    if args.create:
        new_langs = [lang.strip() for lang in args.create.split(",")]
        created = 0
        for lang in new_langs:
            path = mgr.get_locale_path(lang)
            if path.exists():
                console.print(f"  [yellow]⚠ {lang}.json already exists, skipping.")
                continue
            if not args.dry_run:
                path.write_text("{}\n", encoding="utf-8")
                created += 1
            console.print(f"  [green]✓ {'Would create' if args.dry_run else 'Created'} {lang}.json")
        if created > 0:
            console.print(
                f"\n[green]✓ {created} new locale file(s) {'would be ' if args.dry_run else ''}ready for translation."
            )
        return

    if args.scan:
        scan_unlocalized(mgr)
        return

    if args.unused:
        find_unused_keys(mgr)
        return

    if args.langs:
        target_langs = [lang.strip() for lang in args.langs.split(",")]
    else:
        target_langs = [f.stem for f in LOCALES_DIR.glob("*.json") if f.name != "en.json"] or list(
            DEFAULT_LANGS.keys()
        )

    if args.list:
        display_stats(mgr, target_langs)
        return
    console.print(
        Panel(
            f"[bold blue]Locale Translation Tool[/]\n"
            f"[white]Master: {EN_FILE}[/] ([cyan]{len(mgr.en_data)} keys[/])",
            title="Translate",
        )
    )

    if args.sort:
        if args.dry_run:
            console.print("[cyan]Dry-run mode - no files will be modified.\n")
        console.print("[bold]Sorting all locale files...")
        sort_all_locales(mgr, target_langs, args.dry_run)
        return

    force_keys = set(args.keys.split(",")) if args.keys else set()
    plan = build_work_plan(mgr, target_langs, args.force, force_keys, args.prune)

    if not plan:
        console.print("[green]✓ All locales are already up to date.")
        return

    if args.check:
        display_check_results(plan)
        return
    if args.dry_run:
        console.print("[cyan]Dry-run mode - no files will be modified.\n")
        display_check_results(plan)
        return

    total_missing = sum(len(j["missing"]) for j in plan)

    if total_missing == 0 and any(j["extra"] for j in plan):
        for job in plan:
            data = job["data"]
            for k in job["extra"]:
                del data[k]
            mgr.save_json(job["path"], data)
            console.print(f"[green]✓ {job['name'].upper()}: Pruned {len(job['extra'])} extra keys.")
        return

    progress_cols = [
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style="green", finished_style="green"),
        TaskProgressColumn(),
    ]

    with Progress(*progress_cols, console=console, transient=True) as progress:
        task_id = progress.add_task("[cyan]Translating...", total=total_missing)

        for job in plan:
            translate_job(mgr, job, progress, task_id)

    table = Table(title="Translation Summary")
    table.add_column("Language", style="cyan")
    table.add_column("Translated", style="green")
    table.add_column("Pruned", style="red")
    table.add_column("Status", style="white")

    for job in plan:
        status = "[green]✓ Created" if job.get("is_new") else "[green]✓ Updated"
        table.add_row(
            job["name"].upper(),
            str(len(job["missing"])),
            str(len(job["extra"])),
            status,
        )

    console.print(table)
    console.print("[bold green]✓ Translation completed successfully!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[bold red]🛑 Translation aborted by user.")
        sys.exit(1)
