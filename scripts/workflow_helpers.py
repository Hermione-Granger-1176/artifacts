#!/usr/bin/env python3
"""Provide small command-line helpers for GitHub Actions workflows.

Provides small command-line helpers for GitHub Actions workflows so trust-boundary
decisions and artifact validation live in tested Python instead of inline shell.

Usage:
    python scripts/workflow_helpers.py app-token-policy --event-name pull_request \
        --head-repo-fork false --pr-author login
    python scripts/workflow_helpers.py read-lock-metadata --root .artifacts/lock-refresh
    python scripts/workflow_helpers.py validate-lock-artifact --root .artifacts/lock-refresh
    python scripts/workflow_helpers.py invalidate-thumbnails --event-name pull_request \
        --repo owner/repo --pr-number 42
    python scripts/workflow_helpers.py check-fallback --result-url https://github.com/...
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from itertools import chain
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

BOOL_LOOKUP = {
    "true": True,
    "1": True,
    "yes": True,
    "false": False,
    "0": False,
    "no": False,
}


def _parse_bool(value: str) -> bool:
    """Parse a GitHub-style boolean string."""
    normalized = value.strip().lower()
    try:
        return BOOL_LOOKUP[normalized]
    except KeyError as exc:
        raise ValueError(f"Invalid boolean value: {value}") from exc


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
        for name in chain(dirnames, filenames):
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


def invalidate_thumbnails(
    *, event_name: str, repo: str, pr_number: str, commit_sha: str
) -> list[str]:
    """Delete thumbnail.webp for apps whose index.html changed in a PR or push."""
    if event_name == "pull_request":
        endpoint = f"repos/{repo}/pulls/{pr_number}/files"
        paginate = ["--paginate"]
        jq_expr = ".[].filename"
    else:
        endpoint = f"repos/{repo}/commits/{commit_sha}"
        paginate = []
        jq_expr = ".files[].filename"

    result = subprocess.run(
        ["gh", "api", endpoint, *paginate, "--jq", jq_expr],
        capture_output=True,
        text=True,
        check=True,
    )
    invalidated = []
    for line in result.stdout.splitlines():
        filename = line.strip()
        if not filename:
            continue
        parts = Path(filename).parts
        if not (len(parts) == 3 and parts[0] == "apps" and parts[2] == "index.html"):
            continue
        thumb = Path(parts[0]) / parts[1] / "thumbnail.webp"
        if not thumb.exists():
            continue
        thumb.unlink()
        invalidated.append(str(thumb))
        print(f"Invalidating {thumb} ({filename} changed)")
    return invalidated


def check_fallback(result_url: str) -> bool:
    """Return True when the verified-commit result URL points to a pull request."""
    return "/pull/" in result_url


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

    thumb_parser = subparsers.add_parser(
        "invalidate-thumbnails",
        help="Delete stale thumbnails for apps with changed index.html",
    )
    thumb_parser.add_argument("--event-name", required=True)
    thumb_parser.add_argument("--repo", required=True)
    thumb_parser.add_argument("--pr-number", default="")
    thumb_parser.add_argument("--commit-sha", default="")

    fallback_parser = subparsers.add_parser(
        "check-fallback",
        help="Check if a verified-commit result URL is a fallback PR",
    )
    fallback_parser.add_argument("--result-url", required=True)

    return parser


def _handle_app_token_policy(args: argparse.Namespace) -> int:
    """Print whether GitHub App token actions are allowed for the current event."""
    allowed = app_token_allowed(
        event_name=args.event_name,
        head_repo_fork=_parse_bool(args.head_repo_fork),
        pr_author=args.pr_author,
    )
    print(f"allowed={'true' if allowed else 'false'}")
    return 0


def _handle_read_lock_metadata(args: argparse.Namespace) -> int:
    """Print lock refresh metadata as JSON."""
    root = Path(args.root)
    print(json.dumps(read_lock_refresh_metadata(root), sort_keys=True))
    return 0


def _handle_validate_lock_artifact(args: argparse.Namespace) -> int:
    """Validate a downloaded lock refresh artifact tree."""
    validate_lock_refresh_artifact(Path(args.root))
    return 0


def _handle_invalidate_thumbnails(args: argparse.Namespace) -> int:
    """Print invalidated thumbnail paths, or a no-op message."""
    invalidated = invalidate_thumbnails(
        event_name=args.event_name,
        repo=args.repo,
        pr_number=args.pr_number,
        commit_sha=args.commit_sha,
    )
    if not invalidated:
        print("No thumbnails invalidated")
    return 0


def _handle_check_fallback(args: argparse.Namespace) -> int:
    """Print whether the verified-commit result is a fallback PR."""
    is_fallback = check_fallback(args.result_url)
    print(f"fallback={'true' if is_fallback else 'false'}")
    return 0


COMMAND_HANDLERS = {
    "app-token-policy": _handle_app_token_policy,
    "read-lock-metadata": _handle_read_lock_metadata,
    "validate-lock-artifact": _handle_validate_lock_artifact,
    "invalidate-thumbnails": _handle_invalidate_thumbnails,
    "check-fallback": _handle_check_fallback,
}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except (ValueError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
