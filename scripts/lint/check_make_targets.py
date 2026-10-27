"""Check every Make target reference in the repository against the Makefile.

References are read from documentation, CI shell, and source code, since a
reference to a renamed target is a bug wherever it lives.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from scripts import REPO_ROOT
from scripts.lint import (
    add_paths_argument,
    check_each_path,
    print_failures,
    requested_or_default_paths,
)
from scripts.lint import resolve_requested_paths as _resolve_repo_paths
from scripts.lint.make_targets import (
    MAKEFILE_PATH,
    extract_path_make_references,
    find_shell_control_flow,
    iter_reference_files,
    load_makefile_targets,
    makefile_sources,
    snippet_extractor,
)

if TYPE_CHECKING:
    from pathlib import Path


def resolve_requested_paths(raw_paths: list[str], root: Path) -> tuple[list[Path], list[str]]:
    """Resolve safe repository-relative scannable paths and return validation errors."""
    return _resolve_repo_paths(
        raw_paths,
        root,
        accepts=lambda relative: snippet_extractor(relative) is not None,
        rejection="path must be Markdown, YAML under .github, or non-test Python or JavaScript",
    )


def check_file(path: Path, known_targets: set[str], root: Path) -> list[str]:
    """Return unknown Make target references for one file."""
    relative_path = path.relative_to(root).as_posix()
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        return [f"{relative_path}: not valid UTF-8 text ({exc.reason})"]

    return [
        f"{relative_path}:{reference.line_number}: unknown Make target `{reference.target}`"
        for reference in extract_path_make_references(path.relative_to(root), text)
        if reference.target not in known_targets
    ]


def run_check(paths: list[Path] | None = None, root: Path | None = None) -> list[str]:
    """Run the Make target reference check and return all violations."""
    workspace_root = root or REPO_ROOT
    known_targets = load_makefile_targets(workspace_root / "Makefile")
    candidate_paths = paths if paths is not None else iter_reference_files(workspace_root)
    return check_each_path(
        candidate_paths,
        workspace_root,
        resolve_requested_paths,
        lambda path: check_file(path, known_targets, workspace_root),
    )


def run_control_flow_check(makefile_path: Path | None = None) -> list[str]:
    """Return recipe lines that begin raw shell control flow in the Makefile.

    This runs on the Makefile and its group files rather than on the reference
    files, so it happens once regardless of which paths were requested.
    """
    path = makefile_path or MAKEFILE_PATH
    return [
        f"{source.relative_to(path.parent).as_posix()}:{violation.line_number}: "
        f"recipe for `{violation.target}` begins raw shell control flow "
        f"(`{violation.keyword}`); move the logic into scripts/ "
        "or add the target to CONTROL_FLOW_ALLOWLIST with a reason"
        for source in makefile_sources(path)
        for violation in find_shell_control_flow(source.read_text(encoding="utf-8"))
    ]


FAILURE_HEADER = "Make target check failed:"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the Make target reference checker."""
    parser = argparse.ArgumentParser(
        description="Check make <target> references against the Makefile."
    )
    add_paths_argument(parser, "Optional repository-relative files to check")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    args = parse_args(argv)
    workspace_root = REPO_ROOT

    candidate_paths = requested_or_default_paths(
        args.paths,
        workspace_root,
        default_paths=iter_reference_files,
        resolve=resolve_requested_paths,
        failure_header=FAILURE_HEADER,
    )
    if candidate_paths is None:
        return 1

    violations = run_check(paths=candidate_paths, root=workspace_root)
    violations.extend(run_control_flow_check(workspace_root / "Makefile"))
    if not violations:
        print(
            "Make target check passed for "
            f"{len(candidate_paths)} file(s) against {MAKEFILE_PATH.name}"
        )
        return 0

    print_failures(FAILURE_HEADER, violations)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
