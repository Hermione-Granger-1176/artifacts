#!/usr/bin/env python3
"""Check documented Make target references against the repository Makefile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.lint.make_targets import (
    MAKEFILE_PATH,
    REPO_ROOT,
    extract_make_references,
    iter_markdown_files,
    load_makefile_targets,
)


def check_file(
    path: Path, known_targets: set[str], root: Path | None = None
) -> list[str]:
    """Return unknown documented Make target references for one file."""
    workspace_root = root or REPO_ROOT
    relative_path = path.relative_to(workspace_root).as_posix()
    text = path.read_text(encoding="utf-8")
    return [
        f"{relative_path}:{reference.line_number}: unknown Make target `{reference.target}`"
        for reference in extract_make_references(text)
        if reference.target not in known_targets
    ]


def run_check(paths: list[Path] | None = None, root: Path | None = None) -> list[str]:
    """Run the documented Make target check and return all violations."""
    workspace_root = root or REPO_ROOT
    known_targets = load_makefile_targets(workspace_root / "Makefile")
    candidate_paths = (
        paths if paths is not None else iter_markdown_files(workspace_root)
    )
    violations: list[str] = []
    for path in candidate_paths:
        violations.extend(check_file(path, known_targets, root=workspace_root))
    return violations


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the documented Make target checker."""
    parser = argparse.ArgumentParser(
        description="Check documented make <target> references against the Makefile."
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
        candidate_paths = iter_markdown_files(workspace_root)
    else:
        candidate_paths = []
        for raw_path in args.paths:
            resolved_path = (workspace_root / raw_path).resolve()
            if not resolved_path.is_relative_to(workspace_root.resolve()):
                print(f"  {raw_path}: path escapes workspace root")
                return 1
            if not resolved_path.is_file():
                print(f"  {raw_path}: path does not exist or is not a file")
                return 1
            candidate_paths.append(resolved_path)

    violations = run_check(paths=candidate_paths, root=workspace_root)
    if not violations:
        print(
            "Make target check passed for "
            f"{len(candidate_paths)} file(s) against {MAKEFILE_PATH.name}"
        )
        return 0

    print("Make target check failed:")
    for violation in violations:
        print(violation)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
