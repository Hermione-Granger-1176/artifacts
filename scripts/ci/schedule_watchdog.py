#!/usr/bin/env python3
"""Detect scheduled workflows that went stale or were auto-disabled.

GitHub disables a workflow's ``cron`` triggers after about 60 days without
repository activity, and a disabled schedule cannot open its own alert issue.
This watchdog runs from a push-triggered context (which GitHub never
auto-disables) and checks each scheduled workflow two ways:

- its workflow ``state`` is still ``active`` (an auto-disabled workflow reports
  ``disabled_inactivity``); and
- its most recent scheduled run is newer than the workflow's expected cadence
  plus a grace window, so a schedule that silently stopped firing is caught even
  while its state still reads active.

The CLI prints a report and exits non-zero when any workflow looks stale or
disabled, so the calling workflow can open, update, or close one alert issue
with the shared ``ci-alert-issue`` pattern.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from scripts.lib import gh_api

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

DAY_SECONDS = 86_400

# Maximum expected gap between scheduled runs for each workflow, derived from
# its cron expression. Keep these aligned with the crons in .github/workflows/.
SCHEDULED_WORKFLOW_CADENCES: dict[str, int] = {
    "live-site-smoke.yml": DAY_SECONDS,  # "17 6 * * *" daily
    "dependency-audit.yml": 7 * DAY_SECONDS,  # "0 6 * * 1" weekly
    "audit-repo-settings.yml": 7 * DAY_SECONDS,  # "23 8 * * 1" weekly
    "refresh-locks.yml": 7 * DAY_SECONDS,  # "0 12 * * 1" weekly
    "codeql.yml": 7 * DAY_SECONDS,  # "30 6 * * 1" weekly
    "update.yml": 7 * DAY_SECONDS,  # "23 4 * * 0" weekly full sweep
    "refresh-action-shas.yml": 31 * DAY_SECONDS,  # "0 3 1 * *" monthly
}

# Absorb runner backlog, delayed scheduling, and month-length variance so a
# healthy schedule is never reported as stale.
GRACE_SECONDS = 3 * DAY_SECONDS


@dataclass(frozen=True)
class WorkflowRecency:
    """The state and latest scheduled-run age for one workflow."""

    workflow_file: str
    state: str
    latest_run_at: datetime | None


def _require_dict(value: object, message: str) -> dict[str, object]:
    """Return ``value`` as a dict or raise a contextual error."""
    if not isinstance(value, dict):
        raise RuntimeError(message)
    return value


def _parse_timestamp(value: object) -> datetime | None:
    """Parse a GitHub ISO 8601 timestamp into an aware datetime, or None."""
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _latest_scheduled_run_at(payload: object) -> datetime | None:
    """Return the created_at of the newest scheduled run in a runs payload."""
    runs = _require_dict(payload, "workflow runs response must be a JSON object").get(
        "workflow_runs"
    )
    if not isinstance(runs, list) or not runs:
        return None
    first = runs[0]
    if not isinstance(first, dict):
        return None
    return _parse_timestamp(first.get("created_at"))


def fetch_workflow_recency(
    repo: str,
    workflow_file: str,
    *,
    run_gh_api_json_fn: Callable[..., object] = gh_api.run_gh_api_json,
) -> WorkflowRecency:
    """Fetch one workflow's active state and newest scheduled-run timestamp."""
    meta = _require_dict(
        run_gh_api_json_fn(
            f"repos/{repo}/actions/workflows/{workflow_file}",
            description=f"reading workflow metadata for {workflow_file}",
            required_permission="actions: read",
        ),
        f"workflow metadata for {workflow_file} must be a JSON object",
    )
    state = meta.get("state")
    if not isinstance(state, str):
        raise RuntimeError(f"workflow {workflow_file} metadata is missing a string state")

    runs_payload = run_gh_api_json_fn(
        f"repos/{repo}/actions/workflows/{workflow_file}/runs?event=schedule&per_page=1",
        description=f"reading scheduled runs for {workflow_file}",
        required_permission="actions: read",
    )
    return WorkflowRecency(
        workflow_file=workflow_file,
        state=state,
        latest_run_at=_latest_scheduled_run_at(runs_payload),
    )


def evaluate_recency(
    recency: WorkflowRecency, cadence_seconds: int, *, now: datetime
) -> str | None:
    """Return a problem description for one workflow, or None when healthy."""
    if recency.state != "active":
        return (
            f"{recency.workflow_file}: workflow state is {recency.state!r} "
            "(expected 'active'; an auto-disabled schedule cannot open its own alert)"
        )
    if recency.latest_run_at is None:
        # State is active but the API reports no scheduled runs. Treat this as a
        # soft signal rather than a hard failure so a freshly added schedule that
        # has not fired once does not raise a false alarm.
        return None
    age_seconds = (now - recency.latest_run_at).total_seconds()
    allowed_seconds = cadence_seconds + GRACE_SECONDS
    if age_seconds > allowed_seconds:
        return (
            f"{recency.workflow_file}: last scheduled run was "
            f"{age_seconds / DAY_SECONDS:.1f} days ago "
            f"(expected within {allowed_seconds / DAY_SECONDS:.1f} days)"
        )
    return None


def check_scheduled_workflows(
    *,
    repo: str,
    now: datetime | None = None,
    cadences: Mapping[str, int] = SCHEDULED_WORKFLOW_CADENCES,
    run_gh_api_json_fn: Callable[..., object] = gh_api.run_gh_api_json,
) -> list[str]:
    """Return one problem string per workflow that looks stale or disabled."""
    current_time = now or datetime.now(UTC)
    problems: list[str] = []
    for workflow_file, cadence_seconds in sorted(cadences.items()):
        recency = fetch_workflow_recency(repo, workflow_file, run_gh_api_json_fn=run_gh_api_json_fn)
        problem = evaluate_recency(recency, cadence_seconds, now=current_time)
        if problem is not None:
            problems.append(problem)
    return problems


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse CLI arguments for the schedule watchdog."""
    parser = argparse.ArgumentParser(description="Detect stale or disabled scheduled workflows")
    parser.add_argument("--repo", required=True, help="owner/name of the repository to check")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the watchdog and return a shell exit code (0 healthy, 1 stale)."""
    args = _parse_args(argv)
    problems = check_scheduled_workflows(repo=args.repo)
    if not problems:
        print("All scheduled workflows are active and recent")
        return 0

    print("Scheduled workflow watchdog found problems:")
    for problem in problems:
        print(f"- {problem}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except (RuntimeError, ValueError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
