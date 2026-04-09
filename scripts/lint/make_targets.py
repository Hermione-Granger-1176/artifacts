#!/usr/bin/env python3
"""Shared helpers for documented Make target linting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from scripts import REPO_ROOT
from scripts.lint import SKIP_DIRECTORIES

MAKEFILE_PATH = REPO_ROOT / "Makefile"
TARGET_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?!=)", re.MULTILINE)
MAKE_REFERENCE_PATTERN = re.compile(
    r"(?:[A-Z_][A-Z0-9_]*=(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)\s+)*"
    r"make\s+([a-zA-Z][a-zA-Z0-9_-]*)\b"
)
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")


@dataclass(frozen=True)
class CodeSnippet:
    """One inline-code or fenced-code snippet extracted from markdown."""

    line_number: int
    text: str


@dataclass(frozen=True)
class MakeReference:
    """One documented ``make <target>`` reference."""

    target: str
    line_number: int
    snippet: str


def parse_makefile_targets(content: str) -> set[str]:
    """Return invokable target names declared in Makefile content."""
    return {
        match.group(1)
        for match in TARGET_PATTERN.finditer(content)
        if not match.group(1).startswith(".")
    }


def load_makefile_targets(path: Path | None = None) -> set[str]:
    """Load target names from the repository Makefile."""
    makefile_path = path or MAKEFILE_PATH
    return parse_makefile_targets(makefile_path.read_text(encoding="utf-8"))


def iter_markdown_files(root: Path | None = None) -> list[Path]:
    """Return repository markdown files, skipping build and dependency folders."""
    workspace_root = root or REPO_ROOT
    return [
        path
        for path in sorted(workspace_root.rglob("*.md"))
        if not any(
            part in SKIP_DIRECTORIES for part in path.relative_to(workspace_root).parts
        )
    ]


def extract_markdown_code_snippets(text: str) -> list[CodeSnippet]:
    """Extract inline-code and fenced-code snippets from markdown text."""
    snippets: list[CodeSnippet] = []
    in_code_fence = False
    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.strip().startswith("```"):
            in_code_fence = not in_code_fence
            continue

        if in_code_fence:
            snippet = line.strip()
            if snippet and not snippet.startswith("#"):
                snippets.append(CodeSnippet(line_number=line_number, text=snippet))
            continue

        for match in INLINE_CODE_PATTERN.finditer(line):
            snippet = match.group(1).strip()
            if snippet:
                snippets.append(CodeSnippet(line_number=line_number, text=snippet))
    return snippets


def extract_make_references(text: str) -> list[MakeReference]:
    """Extract documented ``make <target>`` references from text."""
    references: list[MakeReference] = []
    for code_snippet in extract_markdown_code_snippets(text):
        for match in MAKE_REFERENCE_PATTERN.finditer(code_snippet.text):
            snippet = match.group(0).strip()
            references.append(
                MakeReference(
                    target=match.group(1),
                    line_number=code_snippet.line_number,
                    snippet=snippet,
                )
            )
    return references
