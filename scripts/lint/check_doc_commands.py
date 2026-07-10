#!/usr/bin/env python3
"""Check contributor docs for direct commands that should use Make targets."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts import REPO_ROOT
from scripts.lint.make_targets import (
    extract_markdown_code_snippets,
    load_makefile_targets,
)

DEFAULT_DOC_PATHS = (
    Path("README.md"),
    Path("CLAUDE.md"),
    Path(".github/CONTRIBUTING.md"),
    Path(".github/pull_request_template.md"),
    Path("docs/operations.md"),
)


@dataclass(frozen=True)
class CommandRule:
    """One direct-command pattern and its Make target replacement."""

    pattern: re.Pattern[str]
    target: str
    requires_full_snippet_match: bool = False


COMMAND_RULES = (
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+test:coverage)\s*$"),
        "coverage-js",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+install\s+--package-lock-only)\s*$"),
        "lock-node",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+format)\s*$"),
        "fmt-prettier",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+format:check)\s*$"),
        "format-prettier-check",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+dead-code|knip)\s*$"),
        "dead-code-js",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:(?:\.venv/bin/)?vulture|python(?:3(?:\.\d+)?)?\s+-m\s+vulture)\s*$"),
        "dead-code-py",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:\.venv/bin/)?ruff\s+format\s+--check\s*\.\s*$"),
        "format-py-check",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"\b(?:python(?:3(?:\.\d+)?)?\s+-m\s+pytest|(?:\.venv/bin/)?pytest)\b"),
        "test-py",
        requires_full_snippet_match=False,
    ),
    CommandRule(re.compile(r"\b(?:npm\s+run\s+test|node\s+--test)\b"), "test-js"),
    CommandRule(
        re.compile(r"^\s*(?:\.venv/bin/)?ruff\s+(?:check\s+--fix|format)\s*$"),
        "fmt-py",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:\.venv/bin/)?ruff(?:\s+check)?\s*$"),
        "lint-py",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+lint:js)\s*$"),
        "lint-js",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+lint:js\s+--\s+--fix)\s*$"),
        "fmt-js",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+lint:css)\s*$"),
        "lint-css",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+lint:css\s+--\s+--fix)\s*$"),
        "fmt-css",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:npm\s+run\s+lint:workflows|actionlint)\s*$"),
        "lint-workflows",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*(?:yamllint)\s*$"),
        "lint-yaml",
        requires_full_snippet_match=True,
    ),
    CommandRule(re.compile(r"\b(?:pip-audit|npm\s+audit)\b"), "security"),
    CommandRule(
        re.compile(r"^\s*playwright\s+install\s+chromium\s+--with-deps\s*$"),
        "setup-ci",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*playwright\s+install\s+chromium\s*$"),
        "setup-all",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*python(?:3(?:\.\d+)?)?\s+scripts/lint/check_editorconfig\.py\s*$"),
        "editorconfig-check",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*python(?:3(?:\.\d+)?)?\s+scripts/lint/align_tables\.py\s*$"),
        "align-tables",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*python(?:3(?:\.\d+)?)?\s+scripts/build/generate_thumbnails\.py\s*$"),
        "thumbnails",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*python(?:3(?:\.\d+)?)?\s+scripts/build/generate_index\.py\s*$"),
        "index",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*python(?:3(?:\.\d+)?)?\s+scripts/build/prepare_site\.py\s*$"),
        "site",
        requires_full_snippet_match=True,
    ),
    CommandRule(
        re.compile(r"^\s*python(?:3(?:\.\d+)?)?\s+scripts/build/scaffold_artifact\.py\s*$"),
        "new",
        requires_full_snippet_match=True,
    ),
    CommandRule(re.compile(r"^\s*gh\s+pr\s+create\s*$"), "pr-create", True),
    CommandRule(re.compile(r"^\s*gh\s+pr\s+list\s*$"), "pr-list", True),
    CommandRule(re.compile(r"^\s*gh\s+pr\s+checks\s+--watch\s*$"), "pr-checks", True),
    CommandRule(re.compile(r"^\s*gh\s+pr\s+checks\s*$"), "pr-status", True),
    CommandRule(re.compile(r"^\s*gh\s+pr\s+diff\s*$"), "pr-diff", True),
    CommandRule(re.compile(r"^\s*gh\s+pr\s+view\s+--comments\s*$"), "pr-comments", True),
    CommandRule(re.compile(r"^\s*gh\s+run\s+list\s*$"), "ci-runs", True),
    CommandRule(re.compile(r"^\s*gh\s+run\s+watch\s*$"), "ci-watch", True),
    CommandRule(re.compile(r"^\s*gh\s+issue\s+list\s*$"), "issues", True),
    CommandRule(re.compile(r"^\s*git\s+diff\s+--cached\s*$"), "diff-staged", True),
    CommandRule(re.compile(r"^\s*git\s+diff\s*$"), "diff", True),
    CommandRule(re.compile(r"^\s*git\s+log\s*$"), "log", True),
)
COMMAND_SEPARATOR_PATTERN = re.compile(r"\s*(?:&&|\|\||;)\s*")
INSTRUCTION_WORDS_PATTERN = (
    r"run|use|rerun|execute|invoke|trigger|open|bootstrap|install|"
    r"scaffold|validate|regenerate|refresh|serve|verify|add|list|show|"
    r"watch|merge|close|reply|comment"
)
CLAUSE_SEPARATOR_PATTERN = re.compile(
    rf"(?:[.;!?]\s*|,\s*(?=(?:instead|then|but)\b|(?:{INSTRUCTION_WORDS_PATTERN})\b))",
    re.IGNORECASE,
)
CHECKLIST_PREFIX_PATTERN = re.compile(r"^\s*[-*]\s+\[[ xX]\]\s*$")
ORDERED_PREFIX_PATTERN = re.compile(r"^\s*\d+\.\s*$")
PLAIN_BULLET_PREFIX_PATTERN = re.compile(r"^\s*[-*]\s*$")
INSTRUCTION_PREFIX_PATTERN = re.compile(
    rf"\b(?:{INSTRUCTION_WORDS_PATTERN})\b",
    re.IGNORECASE,
)
NEGATION_PREFIX_PATTERN = re.compile(r"\b(?:never|do not|don't|avoid)\b", re.IGNORECASE)


def iter_default_paths(root: Path | None = None) -> list[Path]:
    """Return the contributor-facing docs covered by command lint."""
    workspace_root = root or REPO_ROOT
    return [
        workspace_root / relative_path
        for relative_path in DEFAULT_DOC_PATHS
        if (workspace_root / relative_path).is_file()
    ]


def find_replacement_targets(snippet: str, known_targets: set[str]) -> list[str]:
    """Return all matching Make targets for a direct command snippet."""
    seen: set[str] = set()
    targets: list[str] = []
    for segment in COMMAND_SEPARATOR_PATTERN.split(snippet):
        segment = segment.strip()
        if not segment:
            continue

        full_matches: list[str] = []
        partial_matches: list[str] = []
        for rule in COMMAND_RULES:
            if rule.target not in known_targets:
                continue

            matched = (
                rule.pattern.fullmatch(segment)
                if rule.requires_full_snippet_match
                else rule.pattern.search(segment)
            )
            if not matched:
                continue

            if rule.requires_full_snippet_match:
                full_matches.append(rule.target)
            else:
                partial_matches.append(rule.target)

        for target in full_matches or partial_matches:
            if target in seen:
                continue
            seen.add(target)
            targets.append(target)
    return targets


def _snippet_is_actionable(line: str, snippet: str) -> bool:
    """Return whether one inline snippet is presented as a command to run."""
    marker = f"`{snippet}`"
    if marker not in line:
        return not line.lstrip().startswith("#")

    prefix, suffix = line.split(marker, 1)
    local_prefix = CLAUSE_SEPARATOR_PATTERN.split(prefix)[-1]
    if NEGATION_PREFIX_PATTERN.search(local_prefix):
        return False
    if CHECKLIST_PREFIX_PATTERN.match(prefix):
        return True
    if ORDERED_PREFIX_PATTERN.match(prefix):
        return True
    if PLAIN_BULLET_PREFIX_PATTERN.match(prefix):
        stripped_suffix = suffix.lstrip()
        return stripped_suffix.startswith(("(", "if ", "when ", "before ", "to ", "for "))
    return bool(INSTRUCTION_PREFIX_PATTERN.search(local_prefix))


def check_file(path: Path, known_targets: set[str], root: Path | None = None) -> list[str]:
    """Return direct-command violations for one contributor-facing doc."""
    workspace_root = root or REPO_ROOT
    relative_path = path.relative_to(workspace_root).as_posix()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    violations: list[str] = []
    for snippet in extract_markdown_code_snippets(text):
        line = lines[snippet.line_number - 1]
        if not _snippet_is_actionable(line, snippet.text):
            continue
        for target in find_replacement_targets(snippet.text, known_targets):
            violations.append(
                f"{relative_path}:{snippet.line_number}: "
                f"use `make {target}` instead of `{snippet.text}`"
            )
    return violations


def run_check(paths: list[Path] | None = None, root: Path | None = None) -> list[str]:
    """Run contributor-doc command lint and return all violations."""
    workspace_root = root or REPO_ROOT
    known_targets = load_makefile_targets(workspace_root / "Makefile")
    candidate_paths = paths if paths is not None else iter_default_paths(workspace_root)
    violations: list[str] = []
    for path in candidate_paths:
        violations.extend(check_file(path, known_targets, root=workspace_root))
    return violations


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the contributor-doc command checker."""
    parser = argparse.ArgumentParser(
        description="Check contributor-facing docs for direct commands with Make equivalents."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional repository-relative markdown files to check",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    args = parse_args(argv)
    workspace_root = REPO_ROOT

    if not args.paths:
        candidate_paths = iter_default_paths(workspace_root)
    else:
        candidate_paths = []
        for raw_path in args.paths:
            resolved_path = workspace_root / raw_path
            if not resolved_path.is_file():
                print(f"  {raw_path}: path does not exist or is not a file")
                return 1
            candidate_paths.append(resolved_path)

    violations = run_check(paths=candidate_paths, root=workspace_root)
    if not violations:
        print(f"Command lint passed for {len(candidate_paths)} file(s)")
        return 0

    print("Command lint failed:")
    for violation in violations:
        print(violation)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
