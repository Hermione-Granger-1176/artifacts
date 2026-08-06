"""Check every Make target reference in the repository against the Makefile.

References are read from documentation, CI shell, and source code, since a
reference to a renamed target is a bug wherever it lives.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts import REPO_ROOT
from scripts.lint import contains_symlink as _contains_symlink
from scripts.lint.make_targets import (
    MAKEFILE_PATH,
    extract_path_make_references,
    find_shell_control_flow,
    iter_reference_files,
    load_makefile_targets,
    snippet_extractor,
)


def resolve_requested_paths(raw_paths: list[str], root: Path) -> tuple[list[Path], list[str]]:
    """Resolve safe repository-relative scannable paths and return validation errors."""
    resolved_paths: list[Path] = []
    errors: list[str] = []
    resolved_root = root.resolve()

    for raw in raw_paths:
        relative = Path(raw)
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"{raw}: path must stay within the repository")
            continue
        if snippet_extractor(relative) is None:
            errors.append(
                f"{raw}: path must be Markdown, YAML under .github, "
                "or non-test Python or JavaScript"
            )
            continue

        candidate = root / relative
        if _contains_symlink(candidate, root):
            errors.append(f"{raw}: symbolic links are not supported")
            continue

        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            errors.append(f"{raw}: path does not exist")
            continue
        except OSError:
            errors.append(f"{raw}: path could not be accessed")
            continue

        try:
            resolved.relative_to(resolved_root)
        except ValueError:
            errors.append(f"{raw}: path resolves outside the repository")
            continue

        if not resolved.is_file():
            errors.append(f"{raw}: path does not exist or is not a file")
            continue
        resolved_paths.append(resolved)

    return resolved_paths, errors


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
    violations: list[str] = []

    for path in candidate_paths:
        try:
            relative_path = path.relative_to(workspace_root).as_posix()
        except ValueError:
            violations.append(f"{path}: path must stay within the repository")
            continue

        safe_paths, path_errors = resolve_requested_paths([relative_path], workspace_root)
        if path_errors:
            violations.extend(path_errors)
            continue
        violations.extend(check_file(safe_paths[0], known_targets, workspace_root))
    return violations


def run_control_flow_check(makefile_path: Path | None = None) -> list[str]:
    """Return recipe lines that begin raw shell control flow in the Makefile.

    This runs on the Makefile itself rather than on the reference files, so it
    happens once regardless of which paths were requested.
    """
    path = makefile_path or MAKEFILE_PATH
    return [
        f"{path.name}:{violation.line_number}: recipe for `{violation.target}` begins "
        f"raw shell control flow (`{violation.keyword}`); move the logic into scripts/ "
        "or add the target to CONTROL_FLOW_ALLOWLIST with a reason"
        for violation in find_shell_control_flow(path.read_text(encoding="utf-8"))
    ]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the Make target reference checker."""
    parser = argparse.ArgumentParser(
        description="Check make <target> references against the Makefile."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional repository-relative files to check",
    )
    return parser.parse_args(argv)


def print_failures(messages: list[str]) -> None:
    """Print Make target failures with consistent CI-friendly context."""
    print("Make target check failed:")
    for message in messages:
        print(f"  {message}")


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    args = parse_args(argv)
    workspace_root = REPO_ROOT

    if not args.paths:
        candidate_paths = iter_reference_files(workspace_root)
    else:
        candidate_paths, path_errors = resolve_requested_paths(args.paths, workspace_root)
        if path_errors:
            print_failures(path_errors)
            return 1

    violations = run_check(paths=candidate_paths, root=workspace_root)
    violations.extend(run_control_flow_check(workspace_root / "Makefile"))
    if not violations:
        print(
            "Make target check passed for "
            f"{len(candidate_paths)} file(s) against {MAKEFILE_PATH.name}"
        )
        return 0

    print_failures(violations)
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
