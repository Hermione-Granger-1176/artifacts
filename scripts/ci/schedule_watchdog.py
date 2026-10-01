#!/usr/bin/env python3
"""Detect disabled scheduled workflows without inferring health from run age.

The push-triggered watchdog checks GitHub's workflow state because a disabled
schedule cannot report its own failure. Smoke tests and other scheduled checks
own their result alerts. Delayed or missing runs do not imply a disabled workflow.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib import gh_api

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

EXIT_HEALTHY = 0
EXIT_PROBLEMS_FOUND = 1
EXIT_CHECK_FAILED = 2
GITHUB_OUTPUT_ENV = "GITHUB_OUTPUT"
CHECKED_OUTPUT = "checked"
WORKFLOW_ROOT = Path(__file__).resolve().parents[2] / ".github" / "workflows"


def scheduled_workflow_files(workflow_root: Path = WORKFLOW_ROOT) -> tuple[str, ...]:
    """Discover cron workflows from the repository's YAML files."""
    return tuple(
        path.name
        for path in sorted(workflow_root.iterdir())
        if path.is_file()
        and path.suffix in {".yml", ".yaml"}
        and re.search(r"^\s*-\s*cron:", path.read_text(encoding="utf-8"), re.MULTILINE)
    )


def fetch_workflow_state(
    repo: str,
    workflow_file: str,
    *,
    run_gh_api_json_fn: Callable[..., object] = gh_api.run_gh_api_json,
) -> str:
    """Read the workflow's enabled state, failing on unreadable API data."""
    meta = run_gh_api_json_fn(
        f"repos/{repo}/actions/workflows/{workflow_file}",
        description=f"reading workflow metadata for {workflow_file}",
        required_permission="actions: read",
    )
    if not isinstance(meta, dict):
        raise RuntimeError(f"workflow metadata for {workflow_file} must be a JSON object")
    state = meta.get("state")
    if not isinstance(state, str) or not state:
        raise RuntimeError(f"workflow {workflow_file} metadata is missing a string state")
    return state


def check_scheduled_workflows(
    *,
    repo: str,
    workflows: Iterable[str] | None = None,
    run_gh_api_json_fn: Callable[..., object] = gh_api.run_gh_api_json,
) -> list[str]:
    """Report non-active workflows, without reading or judging run history."""
    problems: list[str] = []
    for workflow_file in sorted(scheduled_workflow_files() if workflows is None else workflows):
        state = fetch_workflow_state(repo, workflow_file, run_gh_api_json_fn=run_gh_api_json_fn)
        if state != "active":
            problems.append(
                f"{workflow_file}: workflow state is {state!r} "
                "(expected 'active'; a disabled schedule cannot open its own alert)"
            )
    return problems


def report_checked(reached_verdict: bool, *, env: Mapping[str, str] | None = None) -> None:
    """Keep API failures distinct from disabled-workflow verdicts behind Make."""
    path = (os.environ if env is None else env).get(GITHUB_OUTPUT_ENV)
    if not path:
        return
    value = "true" if reached_verdict else "false"
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{CHECKED_OUTPUT}={value}\n")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse CLI arguments for the schedule watchdog."""
    parser = argparse.ArgumentParser(description="Detect disabled scheduled workflows")
    parser.add_argument("--repo", required=True, help="owner/name of the repository to check")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Check enabled states and report whether a verdict was reached."""
    args = _parse_args(argv)
    try:
        problems = check_scheduled_workflows(repo=args.repo)
    except (RuntimeError, ValueError, OSError) as exc:
        report_checked(False)
        print(f"Schedule watchdog could not complete its check: {exc}", file=sys.stderr)
        return EXIT_CHECK_FAILED

    report_checked(True)
    if not problems:
        print("All scheduled workflows are active")
        return EXIT_HEALTHY

    print("Scheduled workflow watchdog found disabled workflows:")
    for problem in problems:
        print(f"- {problem}")
    return EXIT_PROBLEMS_FOUND


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
