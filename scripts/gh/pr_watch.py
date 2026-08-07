"""Conservatively watch PR checks and an optionally requested Copilot review."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from . import gh_runner, pr_review
from .gh_runner import GhError, RunFunction

if TYPE_CHECKING:
    from collections.abc import Callable

_COPILOT_LOGIN = "copilot-pull-request-reviewer"
_PENDING_STATES = {"EXPECTED", "PENDING"}
_SUCCESSFUL_CHECK_OUTCOMES = {"NEUTRAL", "SKIPPED", "SUCCESS"}
# The latest artifacts PR exposed 31 status entries, including the conditional
# jobs reported as skipped. Keep that completeness floor project-specific while
# allowing callers to override it when the workflow surface changes.
DEFAULT_EXPECTED_CHECKS = 31
# Copilot writes "generated no comments" on a first review and "generated no new
# comments" on a re-review, so "new" has to be optional or a clean first pass is
# reported as unclassifiable.
_COMMENT_COUNT_PATTERN = re.compile(
    r"\bgenerated (?:(no(?: new)?)|(\d+)) comments?\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CopilotReview:
    """One validated Copilot pull-request review."""

    review_id: str
    submitted_at: datetime
    body: str
    generated_comment_count: int | None
    state: str = ""

    @property
    def is_explicitly_clean(self) -> bool:
        """Return whether the review reports nothing to address.

        Copilot review state is not evidence of a clean review. The review
        wording must say "generated no comments" on a first review or
        "generated no new comments" on a re-review. A numeric "generated 0
        comments" deliberately does not count, so unexpected wording fails
        closed.
        """
        match = _COMMENT_COUNT_PATTERN.search(self.body)
        return match is not None and match.group(1) is not None


@dataclass(frozen=True)
class PollStatus:
    """The current checks and fresh-review state for a pull request."""

    checks_settled: bool
    checks_successful: bool
    check_count: int
    rollup_tally: str
    fresh_review: CopilotReview | None


@dataclass(frozen=True)
class WatchBaseline:
    """Copilot review and thread ids seen before an explicit request.

    ``thread_ids`` deliberately includes resolved threads so that a thread
    resolved between polls is never mistaken for a newly generated one.
    """

    review_ids: frozenset[str]
    thread_ids: frozenset[str]


def _parse_timestamp(value: str, context: str) -> datetime:
    """Parse an ISO-8601 timestamp and require timezone information."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise GhError(f"{context} is not a valid ISO-8601 timestamp: {value!r}.") from exc
    if parsed.tzinfo is None:
        raise GhError(f"{context} must include timezone information: {value!r}.")
    return parsed


def _generated_comment_count(body: str) -> int | None:
    """Return the comment count from a Copilot overview, when recognized."""
    match = _COMMENT_COUNT_PATTERN.search(body)
    if match is None:
        return None
    if match.group(1) is not None:
        return 0
    return int(match.group(2))


def _copilot_reviews(reviews: object) -> tuple[CopilotReview, ...]:
    """Validate and return Copilot reviews from a PR view payload."""
    if not isinstance(reviews, list):
        raise GhError("Unexpected reviews shape in PR view response.")

    parsed: list[CopilotReview] = []
    for review in reviews:
        if not isinstance(review, dict):
            raise GhError("Unexpected review entry shape in PR view response.")
        author = review.get("author")
        if author is not None and not isinstance(author, dict):
            raise GhError("Unexpected review author shape in PR view response.")
        if not isinstance(author, dict) or author.get("login") != _COPILOT_LOGIN:
            continue

        review_id = review.get("id")
        if not isinstance(review_id, str) or not review_id.strip():
            raise GhError("A Copilot review is missing a non-empty string id.")
        submitted_at = review.get("submittedAt")
        if not isinstance(submitted_at, str) or not submitted_at:
            raise GhError("A Copilot review is missing a string submittedAt.")
        body = review.get("body")
        if not isinstance(body, str):
            raise GhError("A Copilot review is missing a string body.")
        state = review.get("state")
        if not isinstance(state, str):
            raise GhError("A Copilot review is missing a string state.")
        parsed.append(
            CopilotReview(
                review_id=review_id,
                submitted_at=_parse_timestamp(
                    submitted_at,
                    f"Copilot review {review_id} submittedAt",
                ),
                body=body,
                generated_comment_count=_generated_comment_count(body),
                state=state,
            )
        )
    return tuple(parsed)


def _review_payload(pr: int, *, run_fn: RunFunction | None = None) -> dict[str, object]:
    """Return the validated PR fields needed by the watcher."""
    payload = gh_runner.gh_json(
        ["pr", "view", str(pr), "--json", "statusCheckRollup,reviews"],
        run_fn=run_fn,
    )
    if not isinstance(payload, dict):
        raise GhError(f"Unexpected PR view response shape for PR {pr}.")
    return payload


def watch_baseline(pr: int, *, run_fn: RunFunction | None = None) -> WatchBaseline:
    """Capture existing Copilot reviews and every review thread before a request.

    Resolved threads are captured alongside open ones so that later polls only
    wait on threads the requested review actually created.
    """
    payload = _review_payload(pr, run_fn=run_fn)
    review_ids = frozenset(review.review_id for review in _copilot_reviews(payload.get("reviews")))
    thread_ids = frozenset(
        thread.thread_id
        for thread in pr_review.list_threads(pr, include_resolved=True, run_fn=run_fn)
    )
    return WatchBaseline(review_ids, thread_ids)


def _check_status(
    rollup: object,
    *,
    expected_checks: int,
) -> tuple[bool, bool, int, str]:
    """Return settled, successful, count, and summary for a check rollup."""
    if not isinstance(rollup, list):
        raise GhError("Unexpected statusCheckRollup shape in PR view response.")
    if expected_checks < 1:
        raise GhError("expected_checks must be at least 1.")

    settled = len(rollup) >= expected_checks
    successful = settled
    validated: list[dict[str, Any]] = []
    for entry in rollup:
        if not isinstance(entry, dict):
            raise GhError("Unexpected check entry shape in PR view response.")
        validated.append(entry)
        if "status" in entry:
            status = entry.get("status")
            if not isinstance(status, str):
                raise GhError("A check run is missing a string status.")
            if status != "COMPLETED":
                settled = False
                successful = False
                continue
            conclusion = entry.get("conclusion")
            if not isinstance(conclusion, str):
                raise GhError("A completed check run is missing a string conclusion.")
            if conclusion not in _SUCCESSFUL_CHECK_OUTCOMES:
                successful = False
            continue

        state = entry.get("state")
        if not isinstance(state, str):
            raise GhError("A status context is missing a string state.")
        if state in _PENDING_STATES:
            settled = False
            successful = False
        elif state != "SUCCESS":
            successful = False

    return settled, successful, len(validated), pr_review.rollup_summary(validated)


def poll_once(
    pr: int,
    baseline_ids: frozenset[str],
    *,
    expected_checks: int = DEFAULT_EXPECTED_CHECKS,
    checks_only: bool = False,
    run_fn: RunFunction | None = None,
) -> PollStatus:
    """Return one current poll result relative to a captured review baseline."""
    payload = _review_payload(pr, run_fn=run_fn)
    settled, successful, check_count, tally = _check_status(
        payload.get("statusCheckRollup"),
        expected_checks=expected_checks,
    )
    reviews = _copilot_reviews(payload.get("reviews"))
    fresh_reviews = tuple(review for review in reviews if review.review_id not in baseline_ids)
    fresh_review = (
        max(
            enumerate(fresh_reviews),
            key=lambda item: (item[1].submitted_at, item[0]),
        )[1]
        if fresh_reviews
        else None
    )
    if checks_only:
        fresh_review = None
    return PollStatus(
        checks_settled=settled,
        checks_successful=successful,
        check_count=check_count,
        rollup_tally=tally,
        fresh_review=fresh_review,
    )


def _review_summary(review: CopilotReview | None, *, requested: bool) -> str:
    """Return a compact classification for the latest fresh review."""
    if review is None:
        return "no new review yet" if requested else "not requested"
    if review.generated_comment_count is None:
        return "unrecognized Copilot overview"
    if review.is_explicitly_clean:
        return "generated no comments"
    return f"generated {review.generated_comment_count} comment(s)"


def _watch_report(
    *,
    pr: int,
    poll_count: int,
    status: PollStatus,
    threads: list[pr_review.ReviewThread],
    requested: bool,
) -> str:
    """Render the bounded final state from a completed watch."""
    merge_ready = (
        status.checks_successful
        and status.fresh_review is not None
        and status.fresh_review.is_explicitly_clean
        and not threads
    )
    return "\n".join(
        [
            f"PR #{pr} settled after {poll_count} poll(s)",
            f"checks: {status.rollup_tally} ({status.check_count} total)",
            f"latest Copilot review: {_review_summary(status.fresh_review, requested=requested)}",
            f"open review threads: {len(threads)}",
            f"merge ready: {'yes' if merge_ready else 'no'}",
            "",
            pr_review.format_threads(threads),
        ]
    )


def watch_pr(
    pr: int | None = None,
    *,
    interval: float = 45.0,
    max_polls: int = 40,
    expected_checks: int = DEFAULT_EXPECTED_CHECKS,
    checks_only: bool = False,
    request_copilot: bool = False,
    run_fn: RunFunction | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> str:
    """Wait for settled successful checks and the latest available Copilot review.

    Automatic PR review starts outside this command, so the default mode observes
    the latest available review without mutating reviewer state. Set
    ``request_copilot`` when the caller explicitly wants this command to capture a
    baseline and request a new review. With ``checks_only`` no Copilot review is
    requested or awaited.
    """
    if interval < 0:
        raise GhError("interval must not be negative.")
    if max_polls < 1:
        raise GhError("max_polls must be at least 1.")
    if expected_checks < 1:
        raise GhError("expected_checks must be at least 1.")

    pr = pr if pr is not None else gh_runner.current_pr_number(run_fn=run_fn)
    baseline = WatchBaseline(frozenset(), frozenset())
    if request_copilot and not checks_only:
        baseline = watch_baseline(pr, run_fn=run_fn)
        pr_review.request_copilot_review(pr, run_fn=run_fn)
    sleeper = sleep_fn or time.sleep
    threads: list[pr_review.ReviewThread] = []

    for poll_count in range(1, max_polls + 1):
        status = poll_once(
            pr,
            baseline.review_ids,
            expected_checks=expected_checks,
            checks_only=checks_only,
            run_fn=run_fn,
        )
        if status.checks_settled and not status.checks_successful:
            raise GhError(f"PR #{pr} checks settled unsuccessfully: {status.rollup_tally}.")

        ready_for_threads = status.checks_settled and (
            checks_only or status.fresh_review is not None
        )
        if ready_for_threads:
            all_threads = pr_review.list_threads(pr, include_resolved=True, run_fn=run_fn)
            review_count = (
                status.fresh_review.generated_comment_count
                if status.fresh_review is not None
                else 0
            )
            fresh_thread_count = sum(
                thread.thread_id not in baseline.thread_ids for thread in all_threads
            )
            waiting_for_threads = review_count is not None and review_count > fresh_thread_count
            if not waiting_for_threads:
                if (
                    status.fresh_review is not None
                    and status.fresh_review.generated_comment_count is None
                ):
                    raise GhError(
                        "The fresh Copilot review overview could not be classified; "
                        "inspect `make pr-review-comments` before merging."
                    )
                threads = [thread for thread in all_threads if thread.state == "open"]
                return _watch_report(
                    pr=pr,
                    poll_count=poll_count,
                    status=status,
                    threads=threads,
                    requested=not checks_only,
                )

        if poll_count < max_polls:
            sleeper(interval)

    raise GhError(
        f"PR #{pr} did not settle after {max_polls} polls: "
        f"checks: {status.rollup_tally} ({status.check_count} total); "
        f"latest Copilot review: "
        f"{_review_summary(status.fresh_review, requested=not checks_only)}."
    )
