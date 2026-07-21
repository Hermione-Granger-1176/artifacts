#!/usr/bin/env python3
"""Shared helpers for documented Make target linting."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scripts import REPO_ROOT
from scripts.lint import SKIP_DIRECTORIES

if TYPE_CHECKING:
    from pathlib import Path

MAKEFILE_PATH = REPO_ROOT / "Makefile"
TARGET_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?!=)", re.MULTILINE)
GROUP_PATTERN = re.compile(
    r"^# ─── .+? @([A-Za-z][A-Za-z0-9_-]*) .*",
    re.MULTILINE,
)
MAKE_REFERENCE_PATTERN = re.compile(
    r"(?:[A-Z_][A-Z0-9_]*=(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)\s+)*"
    r"make\s+([a-zA-Z][a-zA-Z0-9_-]*)\b"
)
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")

# A recipe line begins raw shell control flow when, after its leading tab and any
# recipe prefix (@ - +), the first token is one of these keywords. ``$(if ...)``
# is a Make function, not shell, and never matches because the stripped line then
# begins with ``$``.
SHELL_CONTROL_FLOW_PATTERN = re.compile(r"^(?:if|for|while|case)\b")
RECIPE_PREFIX_PATTERN = re.compile(r"^[@\-+]+")

# Targets whose recipes may keep inline shell control flow. coverage-js branches
# on COVERAGE_OUTPUT to optionally tee the coverage report; it is a doc-only
# target kept unchanged by design, so its single ``if`` is allowlisted here
# rather than pushed into scripts/.
CONTROL_FLOW_ALLOWLIST = frozenset({"coverage-js"})


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


@dataclass(frozen=True)
class ShellControlFlow:
    """One recipe line that begins a raw shell control-flow construct."""

    line_number: int
    target: str
    keyword: str
    text: str


def _scan_quote_state(text: str, quote: str | None) -> str | None:
    """Return the quote state after scanning ``text`` from ``quote``.

    Outside a quote, either ``'`` or ``"`` opens a quoted span. While inside a
    span only the matching quote character closes it, so the other quote is
    literal until then. Tracking this across backslash-continued recipe lines
    keeps control-flow keywords inside a quoted program body (for example the
    ``@awk '...'`` help blocks) from being read as shell control flow.
    """
    for char in text:
        if quote is None:
            if char in {"'", '"'}:
                quote = char
        elif char == quote:
            quote = None
    return quote


def find_shell_control_flow(
    content: str, *, allowlist: frozenset[str] = CONTROL_FLOW_ALLOWLIST
) -> list[ShellControlFlow]:
    """Return recipe lines that begin a raw shell control-flow construct.

    Only tab-indented recipe lines are considered. Lines inside ``define ...
    endef`` blocks, variable-assignment continuations, and quoted program bodies
    are ignored, and allowlisted targets are skipped, so future inline shell
    logic is pushed into ``scripts/`` instead.
    """
    violations: list[ShellControlFlow] = []
    in_define = False
    prev_continues = False
    logical_is_recipe = False
    quote: str | None = None
    current_target = ""

    for line_number, raw in enumerate(content.splitlines(), start=1):
        is_continuation = prev_continues
        prev_continues = raw.endswith("\\")

        if not is_continuation:
            quote = None
            stripped = raw.strip()
            if in_define:
                if stripped == "endef":
                    in_define = False
                logical_is_recipe = False
                continue
            if stripped == "define" or stripped.startswith("define "):
                in_define = True
                logical_is_recipe = False
                continue
            target_match = TARGET_PATTERN.match(raw)
            if target_match:
                current_target = target_match.group(1)
            logical_is_recipe = raw.startswith("\t")

        quote_at_start = quote
        quote = _scan_quote_state(raw, quote)

        if in_define or not logical_is_recipe or quote_at_start is not None:
            continue
        recipe_body = RECIPE_PREFIX_PATTERN.sub("", raw.lstrip("\t")).lstrip()
        keyword_match = SHELL_CONTROL_FLOW_PATTERN.match(recipe_body)
        if keyword_match is None or current_target in allowlist:
            continue
        violations.append(
            ShellControlFlow(
                line_number=line_number,
                target=current_target,
                keyword=keyword_match.group(0),
                text=recipe_body,
            )
        )

    return violations


def parse_makefile_targets(content: str) -> set[str]:
    """Return invokable target names declared in Makefile content."""
    targets = {
        match.group(1)
        for match in TARGET_PATTERN.finditer(content)
        if not match.group(1).startswith(".")
    }
    if re.search(r"^help-%:", content, re.MULTILINE):
        targets.update(f"help-{slug}" for slug in GROUP_PATTERN.findall(content))
    return targets


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
        if not any(part in SKIP_DIRECTORIES for part in path.relative_to(workspace_root).parts)
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
