import argparse
import re
import sys
from pathlib import Path

LANG_MAP = {
    "hash_line": [".py", ".sh", ".rb", ".yml", ".yaml", ".php", ".pl", ".r", ".tcl"],
    "c_style": [
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".c",
        ".cpp",
        ".cc",
        ".h",
        ".hpp",
        ".java",
        ".css",
        ".less",
        ".scss",
        ".go",
        ".rs",
        ".json",
        ".jsonc",
    ],
    "sql_style": [".sql"],
    "lua_style": [".lua"],
    "xml_style": [".html", ".xml", ".svg", ".xhtml"],
}


PATTERNS = {
    "string_single": r"'(?:[^'\\]|\\.)*'",
    "string_double": r'"(?:[^"\\]|\\.)*"',
    "string_triple_double": r'"""(?:[^"\\]|\\.)*"""',
    "string_triple_single": r"'''(?:[^'\\]|\\.)*'''",
    "hash_line": r"#.*$",
    "c_line": r"//.*$",
    "c_block": r"/\*[\s\S]*?\*/",
    "sql_line": r"--.*$",
    "lua_line": r"--.*$",
    "lua_block": r"--\[\[[\s\S]*?\]\]",
    "xml_block": r"<!--[\s\S]*?-->",
}


def get_pats_for_file(filepath: Path):
    ext = filepath.suffix.lower()

    group_found = False
    for group in LANG_MAP.values():
        if ext in group:
            group_found = True
            break

    if not group_found:
        return ""

    active_pats = []
    active_pats.extend([PATTERNS["string_double"], PATTERNS["string_single"]])

    if ext in LANG_MAP["hash_line"]:
        if ext == ".py":
            active_pats.extend([PATTERNS["string_triple_double"], PATTERNS["string_triple_single"]])
        active_pats.append(PATTERNS["hash_line"])

    elif ext in LANG_MAP["c_style"]:
        active_pats.extend([PATTERNS["c_line"], PATTERNS["c_block"]])

    elif ext in LANG_MAP["sql_style"]:
        active_pats.extend([PATTERNS["sql_line"], PATTERNS["c_block"]])

    elif ext in LANG_MAP["xml_style"]:
        active_pats.append(PATTERNS["xml_block"])

    elif ext in LANG_MAP["lua_style"]:
        active_pats.extend([PATTERNS["lua_line"], PATTERNS["lua_block"]])

    else:
        pass

    return "|".join(f"({p})" for p in active_pats)


def strip_comments(text: str, pattern: str):
    if not pattern:
        return text

    regex = re.compile(pattern, re.MULTILINE)

    def replacer(match):
        full_match = match.group(0)

        if full_match.startswith(("'''", '"""')):
            return full_match
        if full_match.startswith(("'", '"')):
            return full_match

        if full_match.startswith(("#", "//", "--", "/*", "<!--", "--[[", "--")):
            return ""

        return full_match

    return regex.sub(replacer, text)


def process_file(
    file_path: Path, dry_run: bool = False, verbose: bool = False, clean_empty: bool = False
):
    try:
        pattern = get_pats_for_file(file_path)
        if not pattern:
            if verbose:
                print(f"Skipping {file_path}: Unknown format")
            return

        with open(file_path, encoding="utf-8", errors="ignore") as f:
            content = f.read()

        new_content = strip_comments(content, pattern)

        lines = [line.rstrip() for line in new_content.splitlines()]

        if clean_empty:
            lines = [line for line in lines if line.strip()]
        else:
            new_lines = []
            empty_count = 0
            for line in lines:
                if not line.strip():
                    empty_count += 1
                else:
                    empty_count = 0

                if empty_count <= 2:
                    new_lines.append(line)
            lines = new_lines

        final_content = "\n".join(lines).strip() + "\n"

        if content != final_content:
            if not dry_run:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(final_content)
                print(f"✓ Cleaned: {file_path}")
            else:
                print(f"? Would clean: {file_path}")
        else:
            if verbose:
                print(f"• No changes: {file_path}")

    except Exception as e:
        print(f"Error processing {file_path}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Smart & Fast Comment Stripper")
    parser.add_argument("path", help="File or directory to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--verbose", action="store_true", help="Show all files")
    parser.add_argument(
        "--recursive", "-r", action="store_true", help="Process directories recursively"
    )
    parser.add_argument("--clean-empty", action="store_true", help="Remove all empty lines")
    args = parser.parse_args()

    target = Path(args.path)

    if target.is_file():
        process_file(target, args.dry_run, args.verbose, args.clean_empty)
    elif target.is_dir():
        pattern = "**/*" if args.recursive else "*"
        for f in target.glob(pattern):
            if f.is_file():
                process_file(f, args.dry_run, args.verbose, args.clean_empty)
    else:
        print(f"Error: {target} not found")
        sys.exit(1)


if __name__ == "__main__":
    main()
