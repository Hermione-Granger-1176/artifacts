from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING

import pytest

from scripts.gh import gh_runner, pr_review
from scripts.gh.gh_runner import GhError, GhRateLimitError
from tests.gh.test_pr_review import completed_process

if TYPE_CHECKING:
    from collections.abc import Sequence

REAL_SLEEP = gh_runner._sleep


class SequenceRunner:
    """A fake runner that yields a fixed sequence of results or exceptions."""

    def __init__(self, outcomes: Sequence[object]) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def __call__(self, _cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return (or raise) the next queued outcome and count the call."""
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        assert isinstance(outcome, subprocess.CompletedProcess)
        return outcome


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Replace backoff sleeps with a recorder so tests never actually wait."""
    waits: list[float] = []
    monkeypatch.setattr(gh_runner, "_sleep", waits.append)
    return waits


def test_classify_distinguishes_failure_kinds() -> None:
    """Rate-limit, transient, and fatal stderr are classified correctly."""
    assert gh_runner._classify("You have exceeded a secondary rate limit") == "rate_limit"
    assert gh_runner._classify("Server Error (HTTP 502)") == "transient"
    assert gh_runner._classify("Not Found (HTTP 404)") == "fatal"


def test_backoff_never_exceeds_cap() -> None:
    """Backoff stays within BACKOFF_CAP at every attempt, jitter included."""
    for attempt in range(10):
        assert gh_runner._backoff_seconds(attempt) <= gh_runner.BACKOFF_CAP


def test_sleep_delegates_to_time_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """The sleep wrapper delegates to time.sleep."""
    waits: list[float] = []
    monkeypatch.setattr(gh_runner.time, "sleep", waits.append)

    REAL_SLEEP(1.25)

    assert waits == [1.25]


def test_run_retries_transient_then_succeeds(_no_sleep: list[float]) -> None:
    """A transient 5xx is retried with backoff until it succeeds."""
    runner = SequenceRunner(
        [
            completed_process(1, "", "Server Error (HTTP 502)"),
            completed_process(1, "", "Bad gateway (HTTP 502)"),
            completed_process(0, "ok"),
        ]
    )

    out = gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=2)

    assert out == "ok"
    assert runner.calls == 3
    assert len(_no_sleep) == 2


def test_run_gives_up_after_exhausting_retries() -> None:
    """Transient failures raise GhError once retries are exhausted."""
    runner = SequenceRunner([completed_process(1, "", "(HTTP 503)")] * 3)

    with pytest.raises(GhError):
        gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=2)

    assert runner.calls == 3


def test_run_fails_fast_on_rate_limit() -> None:
    """Rate limits raise GhRateLimitError without any retry."""
    runner = SequenceRunner(
        [
            completed_process(1, "", "API rate limit exceeded for user"),
            completed_process(0, "unused"),
        ]
    )

    with pytest.raises(GhRateLimitError):
        gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=5)

    assert runner.calls == 1


def test_run_does_not_retry_fatal_errors() -> None:
    """A non-transient error (404) is not retried."""
    runner = SequenceRunner([completed_process(1, "", "Not Found (HTTP 404)")])

    with pytest.raises(GhError) as excinfo:
        gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=3)

    assert not isinstance(excinfo.value, GhRateLimitError)
    assert runner.calls == 1


def test_run_retries_timeouts() -> None:
    """A subprocess timeout is retried within the budget."""
    runner = SequenceRunner(
        [
            subprocess.TimeoutExpired(cmd=["gh"], timeout=30),
            completed_process(0, "ok"),
        ]
    )

    out = gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=1)

    assert out == "ok"
    assert runner.calls == 2


def test_run_timeout_message_after_exhaustion() -> None:
    """An exhausted timeout reports the budget in the error."""
    runner = SequenceRunner([subprocess.TimeoutExpired(cmd=["gh"], timeout=30)])

    with pytest.raises(GhError, match="timed out after 30s"):
        gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=0)


def test_run_reports_missing_command() -> None:
    """A missing executable reports a clear installation hint."""
    runner = SequenceRunner([FileNotFoundError("missing")])

    with pytest.raises(GhError, match="Command not found: gh"):
        gh_runner.run_gh(["pr", "view"], run_fn=runner)


def test_run_reports_os_error() -> None:
    """A local OSError is wrapped in GhError."""
    runner = SequenceRunner([OSError("boom")])

    with pytest.raises(GhError, match="Failed to run gh pr"):
        gh_runner.run_gh(["pr", "view"], run_fn=runner)


def test_reply_mutation_does_not_retry() -> None:
    """A reply is non-idempotent and must not retry on a transient error."""
    runner = SequenceRunner([completed_process(1, "", "(HTTP 502)")])

    with pytest.raises(GhError):
        pr_review.reply_to_thread("PRRT_x", "hi", run_fn=runner)

    assert runner.calls == 1


def test_resolve_mutation_retries() -> None:
    """Resolving is idempotent, so a transient error is retried."""
    runner = SequenceRunner(
        [
            completed_process(1, "", "(HTTP 502)"),
            completed_process(0, '{"data": {}}'),
        ]
    )

    pr_review.resolve_thread("PRRT_x", run_fn=runner)

    assert runner.calls == 2


def test_graphql_detects_rate_limit_in_200_body() -> None:
    """A 200 response carrying a RATE_LIMITED error raises GhRateLimitError."""
    errors = [{"type": "RATE_LIMITED", "message": "API rate limit exceeded"}]
    body = json.dumps({"data": None, "errors": errors})
    runner = SequenceRunner([completed_process(0, body)])

    with pytest.raises(GhRateLimitError):
        gh_runner.graphql("query { viewer { login } }", run_fn=runner)


def test_graphql_trusts_rate_limited_type_without_marker_text() -> None:
    """A RATE_LIMITED type is honored even if the message lacks marker words."""
    errors = [{"type": "RATE_LIMITED", "message": "Please slow down."}]
    body = json.dumps({"data": None, "errors": errors})
    runner = SequenceRunner([completed_process(0, body)])

    with pytest.raises(GhRateLimitError):
        gh_runner.graphql("query { viewer { login } }", run_fn=runner)


def test_graphql_reports_other_errors_as_gh_error() -> None:
    """Non-rate-limit GraphQL errors raise a plain GhError."""
    errors = [{"type": "NOT_FOUND", "message": "Could not resolve to a node."}]
    body = json.dumps({"data": None, "errors": errors})
    runner = SequenceRunner([completed_process(0, body)])

    with pytest.raises(GhError) as excinfo:
        gh_runner.graphql("query { viewer { login } }", run_fn=runner)
    assert not isinstance(excinfo.value, GhRateLimitError)


def test_gh_json_rejects_invalid_json() -> None:
    """Invalid JSON from gh becomes a GhError."""
    runner = SequenceRunner([completed_process(0, "not json")])

    with pytest.raises(GhError, match="invalid JSON"):
        gh_runner.gh_json(["pr", "view"], run_fn=runner)


def test_graphql_rejects_unexpected_shape() -> None:
    """GraphQL responses must be objects."""
    runner = SequenceRunner([completed_process(0, json.dumps([]))])

    with pytest.raises(GhError, match="Unexpected GraphQL response shape"):
        gh_runner.graphql("query { viewer { login } }", run_fn=runner)


def test_graphql_requires_data_key() -> None:
    """GraphQL responses without data are rejected."""
    runner = SequenceRunner([completed_process(0, json.dumps({}))])

    with pytest.raises(GhError, match="missing data"):
        gh_runner.graphql("query { viewer { login } }", run_fn=runner)


def test_repo_from_remote_rejects_short_github_path() -> None:
    """A GitHub remote must have owner and repo path segments."""
    runner = SequenceRunner([completed_process(0, "git@github.com:octo.git\n")])

    assert gh_runner._repo_from_remote(run_fn=runner) == ""


def test_current_pr_number_propagates_rate_limit() -> None:
    """Rate limits are not converted into a no-PR error."""
    runner = SequenceRunner([completed_process(1, "", "API rate limit exceeded")])

    with pytest.raises(GhRateLimitError):
        gh_runner.current_pr_number(run_fn=runner)


def test_current_pr_number_rejects_missing_number() -> None:
    """A malformed gh payload raises a clear PR-number error."""
    runner = SequenceRunner([completed_process(0, json.dumps({}))])

    with pytest.raises(GhError, match="Could not read PR number"):
        gh_runner.current_pr_number(run_fn=runner)
