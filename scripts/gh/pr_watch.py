"""Poll a pull request until its checks settle and Copilot has reviewed it."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from . import gh_runner, pr_review
from .gh_runner import GhError, RunFunction

if TYPE_CHECKING:
    from collections.abc import Callable

_COPILOT_LOGIN = "copilot-pull-request-reviewer"
_PENDING_STATES = {"PENDING", "EXPECTED"}


@dataclass(frozen=True)
class PollStatus:
    """The current check and Copilot-review status for a pull request."""

    checks_settled: bool
    rollup_tally: str
    new_review_count: int


def default_since(pr: int, *, run_fn: RunFunction | None = None) -> str:
    """Return the committed date of the newest commit on ``pr``."""
    payload = gh_runner.gh_json(
        ["pr", "view", str(pr), "--json", "commits"],
        run_fn=run_fn,
    )
    if not isinstance(payload, dict):
        raise GhError(f"Unexpected PR view response shape for PR {pr}.")
    commits = payload.get("commits")
    if not isinstance(commits, list):
        raise GhError(f"Unexpected commits shape in PR view response for PR {pr}.")
    if not commits:
        raise GhError(f"PR {pr} has no commits in its PR view response.")
    commit = commits[-1]
    if not isinstance(commit, dict):
        raise GhError(f"Unexpected last commit shape in PR view response for PR {pr}.")
    committed_date = commit.get("committedDate")
    if not isinstance(committed_date, str):
        raise GhError(f"Last commit in PR {pr} is missing a string committedDate.")
    if not committed_date:
        raise GhError(f"Last commit in PR {pr} has an empty committedDate.")
    return committed_date


def _checks_settled(rollup: list[dict[str, Any]]) -> bool:
    """Return whether every check or status context in ``rollup`` has settled."""
    if not rollup:
        return False
    for check in rollup:
        if "status" in check:
            if check.get("status") != "COMPLETED":
                return False
        elif check.get("state") in _PENDING_STATES:
            return False
    return True


def _new_copilot_review_count(reviews: list[Any], since: str) -> int:
    """Count Copilot reviews submitted after ``since``."""
    count = 0
    for review in reviews:
        if not isinstance(review, dict):
            raise GhError("Unexpected review entry shape in PR view response.")
        author = review.get("author")
        if author is not None and not isinstance(author, dict):
            raise GhError("Unexpected review author shape in PR view response.")
        author = author or {}
        submitted_at = review.get("submittedAt")
        if (
            author.get("login") == _COPILOT_LOGIN
            and isinstance(submitted_at, str)
            and submitted_at > since
        ):
            count += 1
    return count


def poll_once(
    pr: int,
    since: str,
    *,
    checks_only: bool = False,
    run_fn: RunFunction | None = None,
) -> PollStatus:
    """Return one pull-request poll result for checks and fresh Copilot reviews."""
    payload = gh_runner.gh_json(
        ["pr", "view", str(pr), "--json", "statusCheckRollup,reviews"],
        run_fn=run_fn,
    )
    if not isinstance(payload, dict):
        raise GhError(f"Unexpected PR view response shape for PR {pr}.")
    rollup = payload.get("statusCheckRollup")
    if not isinstance(rollup, list):
        raise GhError(f"Unexpected statusCheckRollup shape in PR view response for PR {pr}.")
    reviews = payload.get("reviews")
    if not isinstance(reviews, list):
        raise GhError(f"Unexpected reviews shape in PR view response for PR {pr}.")
    rollup_tally = pr_review._rollup_summary(rollup)
    try:
        new_review_count = _new_copilot_review_count(reviews, since)
    except GhError:
        if not checks_only:
            raise
        new_review_count = 0
    return PollStatus(
        checks_settled=_checks_settled(rollup),
        rollup_tally=rollup_tally,
        new_review_count=new_review_count,
    )


def watch_pr(
    pr: int | None = None,
    since: str | None = None,
    *,
    interval: float = 45.0,
    max_polls: int = 40,
    checks_only: bool = False,
    run_fn: RunFunction | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> str:
    """Wait for settled checks and a fresh Copilot review, then report threads."""
    if max_polls < 1:
        raise GhError("max_polls must be at least 1.")
    pr = pr if pr is not None else gh_runner.current_pr_number(run_fn=run_fn)
    since = since if since is not None else default_since(pr, run_fn=run_fn)
    sleeper = sleep_fn or time.sleep

    for poll_count in range(1, max_polls + 1):
        status = poll_once(pr, since, checks_only=checks_only, run_fn=run_fn)
        if status.checks_settled and (checks_only or status.new_review_count > 0):
            break
        if poll_count < max_polls:
            sleeper(interval)
    else:
        raise GhError(
            f"PR #{pr} did not settle after {max_polls} polls: checks: {status.rollup_tally}; "
            f"new Copilot reviews since {since}: {status.new_review_count}."
        )

    threads = pr_review.list_threads(pr, run_fn=run_fn)
    return "\n".join(
        [
            f"PR #{pr} settled after {poll_count} poll(s)",
            f"checks: {status.rollup_tally}",
            f"new Copilot reviews since {since}: {status.new_review_count}",
            "",
            pr_review.format_threads(threads),
        ]
    )
