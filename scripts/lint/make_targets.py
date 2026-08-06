"""Shared Markdown, workflow, source, and Makefile parsing for repository checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from scripts import REPO_ROOT
from scripts.lint import iter_lint_paths

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

MAKEFILE_PATH = REPO_ROOT / "Makefile"
MARKDOWN_SUFFIX = ".md"
SOURCE_SUFFIXES = frozenset({".py", ".mjs", ".js"})
WORKFLOW_SUFFIXES = frozenset({".yml", ".yaml"})
WORKFLOW_ROOT = ".github"
TEST_DIRECTORY_NAMES = frozenset({"tests", "test", "e2e", "__tests__"})
TARGET_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):(?!=)", re.MULTILINE)
GROUP_PATTERN = re.compile(
    r"^# ─── .+? @([A-Za-z][A-Za-z0-9_-]*) .*",
    re.MULTILINE,
)
MAKE_REFERENCE_PATTERN = re.compile(
    r"(?<![A-Za-z0-9_./$-])"
    r"(?:[A-Z_][A-Z0-9_]*=(?:\"[^\"]*\"|'[^']*'|[^\s\"']+)\s+)*"
    r"make\s+([A-Za-z][A-Za-z0-9_-]*)\b"
    r"(?![A-Za-z0-9_?*./:=+%-])"
)
INLINE_CODE_PATTERN = re.compile(r"`([^`\n]+)`")
RUN_KEY_PATTERN = re.compile(r"^(\s*)(-\s+)?run:\s*(.*)$")
BLOCK_SCALAR_PATTERN = re.compile(r"^[|>][+-]?\d*$")

# A recipe line begins raw shell control flow when, after its leading tab and any
# recipe prefix (@ - +), the first token is one of these keywords. ``$(if ...)``
# is a Make function, not shell, and never matches because the stripped line then
# begins with ``$``.
SHELL_CONTROL_FLOW_PATTERN = re.compile(r"^(?:if|for|while|case)\b")
RECIPE_PREFIX_PATTERN = re.compile(r"^[@\-+]+")

# Targets whose recipes may keep inline shell control flow. Every entry is
# argument assembly or git plumbing, not logic that belongs in scripts/, and the
# list is a ratchet: ``test_control_flow_allowlist_has_no_unused_entries`` fails
# if a target is fixed and left behind here.
#
# Several of these exist *because* of the free-text rule. An optional flag whose
# value is prose cannot be added with ``$(if $(COMMENT),--comment "$$COMMENT")``,
# since a Make conditional expands the value and would run ``$(shell ...)`` inside
# it. Testing in the recipe's shell is the only safe way to append the flag, so
# the branch is mandatory rather than lazy. See docs/development.md.
CONTROL_FLOW_ALLOWLIST = frozenset(
    {
        "coverage-js",  # optionally tee the JavaScript coverage report
        "commit",  # reject an interactive terminal before reading the required message
        "pr-create",  # TITLE selects --fill or an explicit title and body
        "pr-edit",  # choose whether to send a title, a body, or both
        "issue-edit",  # choose whether to send a title, a body, or both
        "issue-list",  # append the optional SEARCH value
        "issue-close",  # append the optional COMMENT value
        "issue-reopen",  # append the optional COMMENT value
    }
)


@dataclass(frozen=True)
class CodeSnippet:
    """One inline-code or fenced-code snippet extracted from Markdown."""

    line_number: int
    text: str
    column_start: int | None = field(default=None, compare=False)


@dataclass(frozen=True)
class MakeReference:
    """One ``make <target>`` reference found in documentation, shell, or source."""

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
    """Return Markdown paths while pruning ignored and symlinked directories."""
    workspace_root = root or REPO_ROOT
    return [
        path for path in iter_lint_paths(workspace_root) if path.suffix.lower() == MARKDOWN_SUFFIX
    ]


def extract_markdown_code_snippets(text: str) -> list[CodeSnippet]:
    """Extract inline-code and fenced-code snippets from Markdown text."""
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
            snippet = match.group(1)
            if snippet.strip():
                snippets.append(
                    CodeSnippet(
                        line_number=line_number,
                        text=snippet,
                        column_start=match.start(),
                    )
                )
    return snippets


def extract_source_code_snippets(text: str) -> list[CodeSnippet]:
    """Extract backticked spans from source comments, docstrings, and strings.

    Source files mix prose with commands, and an unquoted scan would read
    ordinary English such as "make sure" as a target reference. Backticks are
    the convention this repository already uses when naming a command inside a
    string, so they are what marks a span as a real reference.
    """
    snippets: list[CodeSnippet] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for match in INLINE_CODE_PATTERN.finditer(line):
            snippet = match.group(1)
            if snippet.strip():
                snippets.append(
                    CodeSnippet(
                        line_number=line_number,
                        text=snippet,
                        column_start=match.start(),
                    )
                )
    return snippets


def extract_workflow_run_snippets(text: str) -> list[CodeSnippet]:
    """Extract shell lines from ``run:`` values in any ``.github`` YAML file.

    The whole directory is scanned rather than an enumerated list of workflow
    and action paths, so a new kind of ``.github`` YAML that runs shell is
    covered the day it is added. Files without a ``run:`` key simply yield
    nothing.

    A ``run:`` value is shell, so every ``make`` word in it is a real
    invocation. These are the references that break CI silently when a target
    is renamed, which is why they are read directly rather than via backticks.
    """
    snippets: list[CodeSnippet] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = RUN_KEY_PATTERN.match(lines[index])
        index += 1
        if match is None:
            continue

        # Only the indicator decides the scalar style: YAML allows a trailing
        # comment after it, as in ``run: | # keep this shell in one step``.
        value = match.group(3).strip()
        indicator = value.split(maxsplit=1)[0] if value else ""
        if not BLOCK_SCALAR_PATTERN.match(indicator):
            if value:
                snippets.append(CodeSnippet(line_number=index, text=value))
            continue

        # The block ends at the first key indented no further than ``run:``
        # itself. In a `- run: |` step the sequence dash sits left of the key,
        # so sibling keys such as `shell:` and `env:` are more indented than
        # the line's leading whitespace and would otherwise be read as shell.
        key_indent = len(match.group(1)) + len(match.group(2) or "")
        while index < len(lines):
            body = lines[index]
            stripped = body.strip()
            if stripped and len(body) - len(body.lstrip()) <= key_indent:
                break
            if stripped:
                snippets.append(CodeSnippet(line_number=index + 1, text=stripped))
            index += 1
    return snippets


def is_test_path(relative_path: Path) -> bool:
    """Return whether a repository-relative path holds test code.

    Test files legitimately name targets that do not exist, as fixtures for
    the checkers themselves, so they are excluded from source scanning.
    """
    if any(part in TEST_DIRECTORY_NAMES for part in relative_path.parts):
        return True
    name = relative_path.name
    return name.startswith("test_") or ".test." in name or ".spec." in name


def snippet_extractor(relative_path: Path) -> Callable[[str], list[CodeSnippet]] | None:
    """Return the snippet extractor for a path, or ``None`` when unscanned."""
    suffix = relative_path.suffix.lower()
    if suffix == MARKDOWN_SUFFIX:
        return extract_markdown_code_snippets
    if is_test_path(relative_path):
        return None
    if suffix in WORKFLOW_SUFFIXES and relative_path.parts[:1] == (WORKFLOW_ROOT,):
        return extract_workflow_run_snippets
    if suffix in SOURCE_SUFFIXES:
        return extract_source_code_snippets
    return None


def iter_reference_files(root: Path) -> list[Path]:
    """Return every file whose ``make`` references are validated."""
    return [
        path
        for path in iter_lint_paths(root)
        if snippet_extractor(path.relative_to(root)) is not None
    ]


def extract_make_references(text: str) -> list[MakeReference]:
    """Extract documented ``make <target>`` references from Markdown code."""
    return _references_from_snippets(extract_markdown_code_snippets(text))


def extract_path_make_references(relative_path: Path, text: str) -> list[MakeReference]:
    """Extract ``make <target>`` references using the rule for the path's kind."""
    extractor = snippet_extractor(relative_path)
    if extractor is None:
        return []
    return _references_from_snippets(extractor(text))


def _references_from_snippets(snippets: list[CodeSnippet]) -> list[MakeReference]:
    """Return every ``make <target>`` reference found in extracted snippets."""
    references: list[MakeReference] = []
    for code_snippet in snippets:
        for match in MAKE_REFERENCE_PATTERN.finditer(code_snippet.text):
            references.append(
                MakeReference(
                    target=match.group(1),
                    line_number=code_snippet.line_number,
                    snippet=match.group(0).strip(),
                )
            )
    return references
