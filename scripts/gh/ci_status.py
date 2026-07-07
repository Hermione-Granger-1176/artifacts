"""CI run inspection: find the current branch's latest run and its failures.

Replaces the manual ``gh run list`` -> ``gh run view --log-failed`` dance with
a single command that prints only what is needed to triage a red run.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import gh_runner
from .gh_runner import GhError, RunFunction

_RUN_FIELDS = "databaseId,status,conclusion,workflowName,headBranch,url"


@dataclass(frozen=True)
class RunInfo:
    """Summary of a single workflow run."""

    run_id: int
    status: str
    conclusion: str
    workflow: str
    branch: str
    url: str


def latest_run(branch: str | None = None, *, run_fn: RunFunction | None = None) -> RunInfo:
    """Return the most recent workflow run for ``branch`` (current when omitted)."""
    branch = branch or gh_runner.current_branch(run_fn=run_fn)
    runs = gh_runner.gh_json(
        ["run", "list", "--branch", branch, "--limit", "1", "--json", _RUN_FIELDS],
        run_fn=run_fn,
    )
    if not runs:
        raise GhError(f"No workflow runs found for branch {branch!r}.")
    run = runs[0]
    return RunInfo(
        run_id=int(run["databaseId"]),
        status=str(run.get("status") or ""),
        conclusion=str(run.get("conclusion") or ""),
        workflow=str(run.get("workflowName") or ""),
        branch=str(run.get("headBranch") or branch),
        url=str(run.get("url") or ""),
    )


def failed_step_logs(run_id: int, *, run_fn: RunFunction | None = None) -> str:
    """Return the logs of only the failed steps for ``run_id``."""
    return gh_runner.run_gh(
        ["run", "view", str(run_id), "--log-failed"],
        run_fn=run_fn,
        timeout=gh_runner.LOG_TIMEOUT,
    ).rstrip()


def failure_digest(
    run_id: int | None = None,
    *,
    branch: str | None = None,
    run_fn: RunFunction | None = None,
) -> str:
    """Return a compact digest of the failed steps for a run.

    When ``run_id`` is omitted, the current branch's latest run is used.
    Succeeded or still-running runs return a short status line instead of logs.
    """
    if run_id is None:
        info = latest_run(branch, run_fn=run_fn)
        header = (
            f"Run {info.run_id} [{info.status}/{info.conclusion or 'pending'}] "
            f"{info.workflow} ({info.branch})\n{info.url}"
        )
        if info.conclusion == "success":
            return f"{header}\n\nRun succeeded; no failures."
        if info.status != "completed":
            return f"{header}\n\nRun is {info.status}; no failed-step logs yet."
        run_id = info.run_id
    else:
        header = f"Run {run_id}"

    logs = failed_step_logs(run_id, run_fn=run_fn)
    return f"{header}\n\n{logs or '(no failed-step logs returned)'}"
