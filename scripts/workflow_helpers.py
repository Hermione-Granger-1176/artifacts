#!/usr/bin/env python3
"""
Workflow Helpers

Provides small command-line helpers for GitHub Actions workflows so trust-boundary
decisions and artifact validation live in tested Python instead of inline shell.

Usage:
    python scripts/workflow_helpers.py app-token-policy --event-name pull_request \
        --head-repo-fork false --pr-author login
    python scripts/workflow_helpers.py read-lock-metadata --root .artifacts/lock-refresh
    python scripts/workflow_helpers.py validate-lock-artifact --root .artifacts/lock-refresh
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

LOCK_ARTIFACT_FILES = {
    "pr-number": Path(".artifacts/pr-number.txt"),
    "head-sha": Path(".artifacts/head-sha.txt"),
    "head-ref": Path(".artifacts/head-ref.txt"),
}

LOCK_ARTIFACT_REQUIRED_FILES = {
    "requirements": Path("locks/requirements.lock"),
    "requirements-dev": Path("locks/requirements-dev.lock"),
    **LOCK_ARTIFACT_FILES,
}


def _parse_bool(value: str) -> bool:
    """Parse a GitHub-style boolean string."""
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")


def app_token_allowed(*, event_name: str, head_repo_fork: bool, pr_author: str) -> bool:
    """Return whether a workflow run may mint the GitHub App token."""
    if event_name != "pull_request":
        return True
    if head_repo_fork:
        return False
    return pr_author != "dependabot[bot]"


def read_lock_refresh_metadata(root: Path) -> dict[str, str]:
    """Read required lock-refresh metadata values from a downloaded artifact tree."""
    return {
        key: (root / relative_path).read_text(encoding="utf-8").strip()
        for key, relative_path in LOCK_ARTIFACT_FILES.items()
    }


def validate_lock_refresh_artifact(root: Path) -> None:
    """Fail if a downloaded lock-refresh artifact tree contains unsafe paths."""
    for walk_root, dirnames, filenames in os.walk(root, followlinks=False):
        for name in [*dirnames, *filenames]:
            path = Path(walk_root) / name
            if path.is_symlink():
                raise ValueError(f"Refusing artifact containing symlink: {path}")
        dirnames[:] = [
            name for name in dirnames if not (Path(walk_root) / name).is_symlink()
        ]

    for relative_path in LOCK_ARTIFACT_REQUIRED_FILES.values():
        path = root / relative_path
        if not path.is_file():
            raise ValueError(
                f"Required artifact file missing or not a regular file: {path}"
            )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workflow helper commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    policy_parser = subparsers.add_parser(
        "app-token-policy", help="Determine whether app-token actions are allowed"
    )
    policy_parser.add_argument("--event-name", required=True)
    policy_parser.add_argument("--head-repo-fork", required=True)
    policy_parser.add_argument("--pr-author", default="")

    metadata_parser = subparsers.add_parser(
        "read-lock-metadata", help="Read lock refresh metadata from an artifact tree"
    )
    metadata_parser.add_argument("--root", required=True)

    artifact_parser = subparsers.add_parser(
        "validate-lock-artifact", help="Validate a downloaded lock refresh artifact"
    )
    artifact_parser.add_argument("--root", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)

    if args.command == "app-token-policy":
        allowed = app_token_allowed(
            event_name=args.event_name,
            head_repo_fork=_parse_bool(args.head_repo_fork),
            pr_author=args.pr_author,
        )
        print(f"allowed={'true' if allowed else 'false'}")
        return 0

    root = Path(args.root)

    if args.command == "read-lock-metadata":
        print(json.dumps(read_lock_refresh_metadata(root), sort_keys=True))
        return 0

    if args.command == "validate-lock-artifact":
        validate_lock_refresh_artifact(root)
        return 0

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
