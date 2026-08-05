#!/usr/bin/env python3
"""Align markdown table pipes so columns line up visually.

Reads markdown files, finds table blocks (consecutive lines containing pipes),
and pads each cell so that pipe characters are vertically aligned.

Usage:
    python scripts/lint/align_tables.py [FILE ...]

When called with no arguments, processes all .md files in the repository.
Pass one or more file paths to process only those files.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from scripts import REPO_ROOT

SEPARATOR_PATTERN = re.compile(r"^[\s|:*-]+$")


def is_table_line(line: str) -> bool:
    """Return True if the line looks like a markdown table row."""
    stripped = line.strip()
    return "|" in stripped and stripped.startswith("|") and stripped.endswith("|")


def split_cells(line: str) -> list[str]:
    """Split a table row into cell contents, stripping the outer pipes."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def is_separator_row(cells: list[str]) -> bool:
    """Return True if every cell matches the --- separator pattern."""
    return all(SEPARATOR_PATTERN.match(cell) for cell in cells)


def build_separator(widths: list[int], original_cells: list[str]) -> str:
    """Rebuild a separator row preserving colon alignment markers."""
    parts = []
    for width, raw_cell in zip(widths, original_cells, strict=True):
        cell = raw_cell.strip()
        left_colon = cell.startswith(":")
        right_colon = cell.endswith(":")
        parts.append(
            (":" if left_colon else "")
            + "-" * (width - int(left_colon) - int(right_colon))
            + (":" if right_colon else "")
        )
    return "| " + " | ".join(parts) + " |"


def align_table(lines: list[str]) -> list[str]:
    """Align a block of table lines so pipe characters are vertically aligned."""
    rows = [split_cells(line) for line in lines]
    col_count = max(len(row) for row in rows)
    rows = [row + [""] * (col_count - len(row)) for row in rows]
    content_rows = [row for row in rows if not is_separator_row(row)]

    widths = [
        max(3, max((len(row[col]) for row in content_rows), default=0)) for col in range(col_count)
    ]

    return [
        build_separator(widths, row)
        if is_separator_row(row)
        else "| " + " | ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)) + " |"
        for row in rows
    ]


def process_file(path: Path) -> bool:
    """Align all tables in a markdown file. Return True if the file changed."""
    text = path.read_text(encoding="utf-8")
    aligned_text = align_document(text)
    if aligned_text == text:
        return False
    path.write_text(aligned_text, encoding="utf-8")
    return True


def align_document(text: str) -> str:
    """Return Markdown text with every table aligned without writing a file."""
    lines = text.split("\n")

    output: list[str] = []
    table_block: list[str] = []
    in_code_fence = False

    def flush_block() -> None:
        if not table_block:
            return
        aligned = align_table(table_block)
        output.extend(aligned)
        table_block.clear()

    for line in lines:
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence

        if not in_code_fence and is_table_line(line):
            table_block.append(line)
        else:
            flush_block()
            output.append(line)

    flush_block()
    return "\n".join(output)


def find_markdown_files() -> list[Path]:
    """Find all .md files in the repository, excluding hidden dirs and _site."""
    excluded = {"node_modules", ".venv", "_site", ".git", ".pytest_cache"}
    return sorted(
        p
        for p in REPO_ROOT.rglob("*.md")
        if not any(
            part.startswith(".") or part in excluded for part in p.relative_to(REPO_ROOT).parts
        )
    )


def main() -> None:
    """Entry point: align tables in the given files or all repo .md files."""
    arguments = sys.argv[1:]
    check_only = "--check" in arguments
    files = [Path(arg) for arg in arguments if arg != "--check"]
    files = files or find_markdown_files()

    changed_count = 0
    for path in files:
        if not path.exists():
            print(f"Skipping {path} (not found)")
            continue
        original = path.read_text(encoding="utf-8") if check_only else ""
        changed = align_document(original) != original if check_only else process_file(path)
        if changed:
            changed_count += 1
            print(
                f"Table alignment needed in {path}" if check_only else f"Aligned tables in {path}"
            )

    if changed_count == 0:
        print("No tables needed alignment")
    elif check_only:
        print(f"Table alignment needed in {changed_count} file(s)")
        raise SystemExit(1)
    else:
        print(f"Aligned tables in {changed_count} file(s)")


if __name__ == "__main__":  # pragma: no cover
    main()
