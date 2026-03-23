#!/usr/bin/env python3
"""Check covered repository files against supported .editorconfig rules."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EDITORCONFIG_FILE = REPO_ROOT / ".editorconfig"
SKIP_DIRECTORIES = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "_site",
    "build",
    "dist",
    "node_modules",
}
BINARY_SUFFIXES = {
    ".avif",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
}


@dataclass(frozen=True)
class EditorConfigSection:
    """One ordered .editorconfig section and its assigned properties."""

    pattern: str
    properties: dict[str, str]


def parse_editorconfig(content: str) -> list[EditorConfigSection]:
    """Parse ordered sections from .editorconfig content."""
    sections: list[EditorConfigSection] = []
    current_pattern: str | None = None
    current_properties: dict[str, str] = {}

    def flush_current_section() -> None:
        if current_pattern is None:
            return
        sections.append(EditorConfigSection(current_pattern, dict(current_properties)))

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue

        if line.startswith("[") and line.endswith("]"):
            flush_current_section()
            current_pattern = line[1:-1].strip()
            current_properties = {}
            continue

        if current_pattern is None or "=" not in line:
            continue

        key, value = line.split("=", 1)
        current_properties[key.strip()] = value.strip()

    flush_current_section()

    return sections


def load_editorconfig(path: Path | None = None) -> list[EditorConfigSection]:
    """Load and parse the repository .editorconfig file."""
    config_path = path or EDITORCONFIG_FILE
    return parse_editorconfig(config_path.read_text(encoding="utf-8"))


def resolve_settings(
    sections: list[EditorConfigSection], relative_path: str
) -> dict[str, str]:
    """Resolve effective settings for one repository-relative path."""
    settings: dict[str, str] = {}
    for section in sections:
        if not fnmatch.fnmatchcase(relative_path, section.pattern):
            continue
        for key, value in section.properties.items():
            if value == "unset":
                settings.pop(key, None)
            else:
                settings[key] = value
    return settings


def should_check_file(sections: list[EditorConfigSection], relative_path: str) -> bool:
    """Return whether a path is covered by explicit .editorconfig patterns."""
    if relative_path == ".editorconfig":
        return True
    return any(
        section.pattern != "*" and fnmatch.fnmatchcase(relative_path, section.pattern)
        for section in sections
    )


def iter_workspace_files(root: Path | None = None) -> list[Path]:
    """Return repository files while skipping configured cache, build, and dependency directories."""
    workspace_root = root or REPO_ROOT
    return [
        path
        for path in sorted(workspace_root.rglob("*"))
        if path.is_file()
        and not any(
            part in SKIP_DIRECTORIES for part in path.relative_to(workspace_root).parts
        )
    ]


def _decode_text_file(path: Path) -> str | None:
    """Return UTF-8 text for text files, None for binary files, or raise decode errors."""
    raw = path.read_bytes()
    if path.suffix.lower() in BINARY_SUFFIXES or b"\0" in raw:
        return None
    return raw.decode("utf-8")


def _leading_whitespace(line: str) -> str:
    """Return the leading whitespace prefix for one line."""
    return line[: len(line) - len(line.lstrip(" \t"))]


def check_file(path: Path, relative_path: str, settings: dict[str, str]) -> list[str]:
    """Return all supported EditorConfig violations for one file."""
    try:
        text = _decode_text_file(path)
    except UnicodeDecodeError as exc:
        return [f"{relative_path}: not valid UTF-8 text ({exc.reason})"]

    if text is None:
        return []

    violations: list[str] = []
    if settings.get("end_of_line") == "lf" and "\r" in text:
        violations.append(f"{relative_path}: expected LF line endings")

    insert_final_newline = settings.get("insert_final_newline")
    has_final_newline = text.endswith("\n")
    match insert_final_newline:
        case "true" if text and not has_final_newline:
            violations.append(f"{relative_path}: missing final newline")
        case "false" if has_final_newline:
            violations.append(f"{relative_path}: unexpected final newline")

    lines = text.splitlines()
    trim_trailing_whitespace = settings.get("trim_trailing_whitespace") == "true"
    indent_style = settings.get("indent_style")

    for line_number, line in enumerate(lines, start=1):
        if trim_trailing_whitespace and line.rstrip(" \t") != line:
            violations.append(f"{relative_path}:{line_number}: trailing whitespace")

        if not line:
            continue

        leading = _leading_whitespace(line)
        match indent_style:
            case "space" if "\t" in leading:
                violations.append(
                    f"{relative_path}:{line_number}: tab used for indentation"
                )
            case "tab" if leading and not leading.startswith("\t"):
                violations.append(
                    f"{relative_path}:{line_number}: spaces used for indentation"
                )

    return violations


def run_check(paths: list[Path] | None = None, root: Path | None = None) -> list[str]:
    """Run supported EditorConfig checks for covered paths and return violations."""
    workspace_root = root or REPO_ROOT
    sections = load_editorconfig(workspace_root / ".editorconfig")
    candidate_paths = (
        paths if paths is not None else iter_workspace_files(workspace_root)
    )

    violations: list[str] = []
    for path in candidate_paths:
        relative_path = path.relative_to(workspace_root).as_posix()
        if not should_check_file(sections, relative_path):
            continue
        settings = resolve_settings(sections, relative_path)
        violations.extend(check_file(path, relative_path, settings))
    return violations


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the editorconfig checker."""
    parser = argparse.ArgumentParser(
        description="Check covered repository files against supported .editorconfig rules."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional repository-relative file paths to check",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    args = parse_args(argv)
    workspace_root = REPO_ROOT
    sections = load_editorconfig(workspace_root / ".editorconfig")

    if not args.paths:
        candidate_paths = iter_workspace_files(workspace_root)
    else:
        resolved_paths = []
        for raw in args.paths:
            resolved = workspace_root / raw
            if not resolved.is_file():
                print(f"  {raw}: path does not exist or is not a file")
                return 1
            resolved_paths.append(resolved)
        candidate_paths = resolved_paths

    checked_paths = [
        path
        for path in candidate_paths
        if should_check_file(sections, path.relative_to(workspace_root).as_posix())
    ]
    violations = run_check(paths=checked_paths, root=workspace_root)

    if not violations:
        print(f"EditorConfig check passed for {len(checked_paths)} file(s)")
        return 0

    print("EditorConfig check failed:")
    for violation in violations:
        print(violation)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
