from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from scripts.gh import gh_runner, pr_review
from scripts.gh.gh_runner import GhError, GhRateLimitError
from scripts.lib import gh_policy
from tests.gh.gh_test_support import (
    FakeGh,
    completed_process,
    graphql_blocked,
    has,
    json_response,
    rest,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

Route = tuple["Callable[[list[str]], bool]", Any]

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


def test_run_uses_the_shared_retry_policy(
    monkeypatch: pytest.MonkeyPatch, _no_sleep: list[float]
) -> None:
    """The CLI wrapper delegates its retry delay to the shared policy."""
    seen_attempts: list[int] = []
    monkeypatch.setattr(
        gh_policy,
        "retry_backoff_seconds",
        lambda attempt: seen_attempts.append(attempt) or 1.25,
    )
    runner = SequenceRunner(
        [completed_process(1, "", "Server Error (HTTP 502)"), completed_process(0, "ok")]
    )

    assert gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=1) == "ok"
    assert seen_attempts == [0]
    assert _no_sleep == [1.25]


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


def test_run_names_the_missing_permission_without_retrying() -> None:
    """A forbidden response fails immediately with an actionable message."""
    runner = SequenceRunner(
        [
            completed_process(1, "", "Resource not accessible by integration"),
            completed_process(0, "unused"),
        ]
    )

    with pytest.raises(GhError, match="missing a permission or scope") as excinfo:
        gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=5)

    assert not isinstance(excinfo.value, GhRateLimitError)
    assert runner.calls == 1


def test_run_reports_the_exit_code_when_the_command_says_nothing() -> None:
    """A silent non-zero exit still yields an actionable message."""
    runner = SequenceRunner([completed_process(3, "", "")])

    with pytest.raises(GhError, match=r"no output \(exit code 3\)"):
        gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=0)


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


def test_current_pr_number_masks_only_not_found() -> None:
    """Genuine not-found errors become the friendly no-PR message."""
    runner = FakeGh(
        [
            (
                has("pr", "view"),
                completed_process(1, "", "no pull requests found for branch x"),
            )
        ]
    )

    with pytest.raises(GhError, match="No pull request found"):
        gh_runner.current_pr_number(run_fn=runner)


def test_current_pr_number_passes_through_real_errors() -> None:
    """Auth/binary failures are not masked as a missing PR."""
    runner = FakeGh([(has("pr", "view"), completed_process(1, "", "GraphQL: 401 Unauthorized"))])

    with pytest.raises(GhError) as exc:
        gh_runner.current_pr_number(run_fn=runner)
    assert "No pull request found" not in str(exc.value)


def test_current_pr_number_passes_through_dns_errors() -> None:
    """A 'could not resolve host' network error is not masked as a missing PR."""
    runner = FakeGh(
        [
            (
                has("pr", "view"),
                completed_process(1, "", "could not resolve host: github.com"),
            )
        ]
    )

    with pytest.raises(GhError) as exc:
        gh_runner.current_pr_number(run_fn=runner)
    assert "No pull request found" not in str(exc.value)


def test_graphql_unavailable_is_distinct_unretried_and_remembered(_no_sleep: list[float]) -> None:
    """A blocked GraphQL endpoint raises its own error once and is never retried."""
    runner = SequenceRunner([graphql_blocked()])

    with pytest.raises(gh_runner.GhGraphqlUnavailableError, match="GraphQL is unavailable"):
        gh_runner.run_gh(["pr", "view"], run_fn=runner, retries=2)

    assert runner.calls == 1
    assert _no_sleep == []
    assert gh_runner.graphql_unavailable()


def test_remembered_verdict_skips_the_graphql_subprocess() -> None:
    """Once GraphQL is known to be blocked, graphql() fails without running gh."""
    runner = SequenceRunner([graphql_blocked()])
    with pytest.raises(gh_runner.GhGraphqlUnavailableError):
        gh_runner.graphql("query { viewer { login } }", run_fn=runner)

    with pytest.raises(gh_runner.GhGraphqlUnavailableError):
        gh_runner.graphql("query { viewer { login } }", run_fn=runner)

    assert runner.calls == 1


def test_reset_forgets_the_graphql_verdict() -> None:
    """Resetting the verdict lets GraphQL be tried again."""
    with pytest.raises(gh_runner.GhGraphqlUnavailableError):
        gh_runner.run_gh(["pr", "view"], run_fn=SequenceRunner([graphql_blocked()]))
    gh_runner.reset_graphql_availability()

    assert not gh_runner.graphql_unavailable()


@pytest.mark.parametrize(
    "stderr",
    ["HTTP 403: Forbidden", "Resource not accessible by integration (HTTP 403)"],
)
def test_other_forbidden_responses_do_not_mark_graphql_unavailable(stderr: str) -> None:
    """An ordinary 403 stays a plain error and never triggers a REST fallback."""
    called: list[str] = []
    runner = SequenceRunner([completed_process(1, "", stderr)])

    with pytest.raises(GhError) as exc:
        gh_runner.with_rest_fallback(
            lambda: gh_runner.run_gh(["pr", "view"], run_fn=runner),
            lambda: called.append("rest") or "rest",
        )

    assert not isinstance(exc.value, gh_runner.GhGraphqlUnavailableError)
    assert called == []
    assert not gh_runner.graphql_unavailable()


def test_rate_limits_do_not_trigger_the_rest_fallback() -> None:
    """A rate limit from the primary path propagates instead of switching to REST."""
    runner = SequenceRunner([completed_process(1, "", "API rate limit exceeded (HTTP 429)")])

    with pytest.raises(GhRateLimitError):
        gh_runner.with_rest_fallback(
            lambda: gh_runner.run_gh(["pr", "view"], run_fn=runner),
            lambda: pytest.fail("the fallback must not run"),
        )


def test_with_rest_fallback_uses_primary_when_graphql_works() -> None:
    """On a normal machine only the primary path runs."""
    assert gh_runner.with_rest_fallback(lambda: "graphql", lambda: pytest.fail("no")) == "graphql"


def test_with_rest_fallback_switches_once_and_then_skips_primary() -> None:
    """The first blocked call falls back, and later calls go straight to REST."""
    primary_calls: list[str] = []

    def primary() -> str:
        """Fail like a blocked GraphQL call."""
        primary_calls.append("graphql")
        raise gh_runner.GhGraphqlUnavailableError("blocked")

    assert gh_runner.with_rest_fallback(primary, lambda: "rest") == "rest"
    assert primary_calls == ["graphql"]


def test_with_rest_fallback_skips_primary_after_a_remembered_verdict() -> None:
    """A verdict recorded by an earlier gh call routes later calls to REST directly."""
    with pytest.raises(gh_runner.GhGraphqlUnavailableError):
        gh_runner.run_gh(["pr", "view"], run_fn=SequenceRunner([graphql_blocked()]))

    result = gh_runner.with_rest_fallback(lambda: pytest.fail("no GraphQL"), lambda: "rest")

    assert result == "rest"


def test_with_rest_fallback_surfaces_a_failing_fallback() -> None:
    """A fallback error propagates; it is not retried against GraphQL."""

    def primary() -> str:
        """Fail like a blocked GraphQL call."""
        raise gh_runner.GhGraphqlUnavailableError("blocked")

    def fallback() -> str:
        """Fail like a REST call."""
        raise GhError("rest failed")

    with pytest.raises(GhError, match="rest failed"):
        gh_runner.with_rest_fallback(primary, fallback)


def test_passthrough_returns_the_exit_code_and_replays_stderr(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Passthrough keeps stdout on the terminal, returns the code, and replays stderr."""
    seen: list[dict[str, object]] = []

    def runner(_cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Record the options and fail like a pending-checks run."""
        seen.append(dict(kwargs))
        return completed_process(8, "", "checks pending\n")

    code = gh_runner.run_gh_passthrough(["pr", "checks"], run_fn=runner)

    assert code == 8
    assert capsys.readouterr().err == "checks pending\n"
    assert seen == [{"stderr": subprocess.PIPE, "text": True}]


def test_passthrough_pipes_stdin_text_and_stays_quiet_on_success(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Supplied text is piped to gh, and a clean run prints nothing itself."""
    seen: list[dict[str, object]] = []

    def runner(_cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Record the options."""
        seen.append(dict(kwargs))
        return completed_process(0)

    assert gh_runner.run_gh_passthrough(["issue", "create"], run_fn=runner, stdin_text="body") == 0

    assert seen[0]["input"] == "body"
    assert capsys.readouterr().err == ""


def test_passthrough_detects_the_graphql_verdict() -> None:
    """A blocked GraphQL run raises the distinct error instead of printing its stderr."""
    runner = SequenceRunner([graphql_blocked()])

    with pytest.raises(gh_runner.GhGraphqlUnavailableError):
        gh_runner.run_gh_passthrough(["pr", "list"], run_fn=runner)

    assert gh_runner.graphql_unavailable()


def test_passthrough_does_not_fall_back_on_other_failures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Any other failure is reported as gh reported it, with its exit code."""
    runner = SequenceRunner([completed_process(1, "", "HTTP 403: Forbidden")])

    assert gh_runner.run_gh_passthrough(["pr", "list"], run_fn=runner) == 1
    assert "Forbidden" in capsys.readouterr().err
    assert not gh_runner.graphql_unavailable()


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (FileNotFoundError("gh"), "Command not found"),
        (PermissionError("denied"), "Failed to run gh pr"),
    ],
)
def test_passthrough_reports_a_gh_that_cannot_start(error: OSError, message: str) -> None:
    """A missing or unrunnable gh binary is a GhError."""
    with pytest.raises(GhError, match=message):
        gh_runner.run_gh_passthrough(["pr", "list"], run_fn=SequenceRunner([error]))


def test_gh_or_rest_prefers_the_gh_command() -> None:
    """The REST fallback is not used when gh succeeds."""
    runner = SequenceRunner([completed_process(0)])

    assert gh_runner.gh_or_rest(["pr", "list"], lambda: pytest.fail("no"), run_fn=runner) == 0


def test_gh_or_rest_falls_back_when_graphql_is_blocked() -> None:
    """A blocked gh command is replaced by the REST fallback's exit code."""
    runner = SequenceRunner([graphql_blocked()])

    assert gh_runner.gh_or_rest(["pr", "list"], lambda: 3, run_fn=runner) == 3


def test_graphql_field_arguments_cover_every_value_type() -> None:
    """Typed values use -F, strings use -f, and lists repeat a key[] field."""
    assert gh_runner._field_args("n", 3) == ["-F", "n=3"]
    assert gh_runner._field_args("flag", True) == ["-F", "flag=true"]
    assert gh_runner._field_args("name", "x") == ["-f", "name=x"]
    assert gh_runner._field_args("labels", ["a", "b"]) == [
        "-f",
        "labels[]=a",
        "-f",
        "labels[]=b",
    ]
    assert gh_runner._field_args("labels", []) == []


def test_rest_builds_a_get_with_query_fields_and_retries() -> None:
    """GET calls pass fields and headers and retry transient failures."""
    runner = SequenceRunner(
        [completed_process(1, "", "HTTP 502"), completed_process(0, json.dumps({"ok": True}))]
    )

    out = gh_runner.rest_text(
        "repos/o/n/pulls",
        fields={"state": "open", "per_page": 5},
        headers=["Accept: x"],
        run_fn=runner,
    )

    assert json.loads(out) == {"ok": True}
    assert runner.calls == 2


def test_rest_command_vector_for_a_mutation_is_not_retried() -> None:
    """Mutations send fields with an explicit method and never retry."""
    runner = FakeGh(
        [(rest("POST", "repos/o/n/issues", "title=T"), completed_process(1, "", "HTTP 502"))]
    )

    with pytest.raises(GhError):
        gh_runner.rest("repos/o/n/issues", method="POST", fields={"title": "T"}, run_fn=runner)

    assert runner.calls == [
        ["gh", "api", "--method", "POST", "repos/o/n/issues", "--input", "-", "title=T"]
    ]


def test_rest_sends_mutation_fields_as_a_json_body_on_stdin() -> None:
    """A mutation body travels on stdin, so its size never hits the argument limit."""
    seen: dict[str, object] = {}

    def runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen["cmd"] = cmd
        seen["input"] = kwargs.get("input")
        return completed_process(0, "{}")

    body = "\u4e2d" * 50_000
    gh_runner.rest(
        "repos/o/n/issues/1/comments",
        method="POST",
        fields={"body": body, "draft": True, "labels": ["a"]},
        run_fn=runner,
    )

    assert seen["cmd"][2:] == ["--method", "POST", "repos/o/n/issues/1/comments", "--input", "-"]
    assert json.loads(str(seen["input"])) == {"body": body, "draft": True, "labels": ["a"]}


def test_rest_sends_a_field_free_mutation_without_a_body() -> None:
    """A mutation with no fields, such as a DELETE, reads nothing from stdin."""
    runner = FakeGh([(rest("DELETE", "repos/o/n/git/refs/heads/x"), completed_process(0))])

    assert gh_runner.rest("repos/o/n/git/refs/heads/x", method="DELETE", run_fn=runner) is None
    assert runner.calls == [["gh", "api", "--method", "DELETE", "repos/o/n/git/refs/heads/x"]]


def test_rest_parses_json_and_treats_an_empty_body_as_none() -> None:
    """REST returns parsed JSON, or None for a body-less success such as a 204."""
    assert gh_runner.rest("x", run_fn=SequenceRunner([json_response({"a": 1})])) == {"a": 1}
    assert gh_runner.rest("x", run_fn=SequenceRunner([completed_process(0, "  \n")])) is None


def test_rest_rejects_invalid_json() -> None:
    """A non-JSON body is a GhError naming the endpoint."""
    with pytest.raises(GhError, match="gh api repos/o/n returned invalid JSON"):
        gh_runner.rest("repos/o/n", run_fn=SequenceRunner([completed_process(0, "not json")]))


def test_rest_pages_follows_full_pages_until_a_short_one() -> None:
    """Paging continues while a page is full and stops at the first short page."""
    first = [{"id": index} for index in range(100)]
    runner = FakeGh(
        [
            (has("page=1"), json_response(first)),
            (has("page=2"), json_response([{"id": 100}])),
        ]
    )

    items = gh_runner.rest_pages("repos/o/n/pulls", run_fn=runner)

    assert len(items) == 101
    assert len(runner.calls) == 2


def test_rest_pages_reads_envelopes_and_caps_at_the_limit() -> None:
    """An items key unwraps an envelope and the limit truncates the result."""
    payload = {"check_runs": [{"id": 1}, {"id": 2}, {"id": 3}]}
    runner = FakeGh([(has("per_page=2"), json_response({"check_runs": payload["check_runs"][:2]}))])

    items = gh_runner.rest_pages("c", items_key="check_runs", limit=2, run_fn=runner)

    assert items == [{"id": 1}, {"id": 2}]
    assert len(runner.calls) == 1


def test_rest_pages_skips_rejected_items_without_counting_them() -> None:
    """Items the filter rejects do not count toward the limit, so paging continues."""
    runner = FakeGh(
        [
            (has("page=1"), json_response([{"id": 1, "pull_request": {}}, {"id": 2}])),
            (has("page=2"), json_response([{"id": 3}, {"id": 4, "pull_request": {}}])),
        ]
    )

    items = gh_runner.rest_pages(
        "issues", limit=2, accept=lambda item: "pull_request" not in item, run_fn=runner
    )

    assert [item["id"] for item in items] == [2, 3]


@pytest.mark.parametrize("payload", [{"not": "a list"}, ["not an object"]])
def test_rest_pages_rejects_unexpected_shapes(payload: object) -> None:
    """A non-list page, or a list of non-objects, is a GhError."""
    with pytest.raises(GhError, match="Unexpected list response shape"):
        gh_runner.rest_pages("x", run_fn=SequenceRunner([json_response(payload)]))


def test_default_branch_reads_the_repository() -> None:
    """The default branch comes from the repository object."""
    runner = FakeGh([(rest("GET", "repos/o/n"), json_response({"default_branch": "main"}))])

    assert gh_runner.default_branch("o/n", run_fn=runner) == "main"


def test_default_branch_rejects_a_missing_name() -> None:
    """A repository response without a default branch is a GhError."""
    runner = FakeGh([(rest("GET", "repos/o/n"), json_response({}))])

    with pytest.raises(GhError, match="default branch"):
        gh_runner.default_branch("o/n", run_fn=runner)


def test_split_list_trims_and_drops_empties() -> None:
    """Comma-separated options split into trimmed, non-empty items."""
    assert gh_runner.split_list(" a, ,b ,") == ["a", "b"]


def test_resolve_repo_skips_gh_repo_view_once_graphql_is_blocked() -> None:
    """With GraphQL known to be blocked, the repo comes from the git remote alone."""
    runner = FakeGh(
        [
            (has("repo", "view"), graphql_blocked()),
            (has("remote"), completed_process(0, "https://github.com/octo/Hello.git\n")),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"
    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"

    assert sum("repo" in call and "view" in call for call in runner.calls) == 1


@pytest.mark.parametrize(
    "value", ["octo/Other", "github.com/octo/Other", "https://github.com/octo/Other/"]
)
def test_resolve_repo_honors_gh_repo(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """GH_REPO picks the repository before gh or the git remote is asked."""
    monkeypatch.setenv("GH_REPO", value)
    runner = FakeGh([])

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Other"
    assert runner.calls == []


@pytest.mark.parametrize("value", ["ghe.example.com/octo/Other", "octo", "a/b/c/d"])
def test_resolve_repo_rejects_an_unsupported_gh_repo(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A GH_REPO this helper cannot address fails instead of falling back to the remote."""
    monkeypatch.setenv("GH_REPO", value)

    with pytest.raises(GhError, match=r"is not an owner/name on github\.com"):
        gh_runner.resolve_repo(run_fn=FakeGh([]))


def _branch_runner(open_pulls: object, closed_pulls: object = ()) -> FakeGh:
    """Build a runner for a blocked ``gh pr view`` on branch ``feature`` of ``octo/Hello``."""
    return FakeGh(
        [
            (has("pr", "view"), graphql_blocked()),
            (has("repo", "view"), graphql_blocked()),
            (has("remote"), completed_process(0, "git@github.com:octo/Hello.git\n")),
            (has("rev-parse"), completed_process(0, "feature\n")),
            (has("config", "--get"), completed_process(1)),
            (
                rest("GET", "repos/octo/Hello/pulls", "head=octo:feature", "state=open"),
                json_response(open_pulls),
            ),
            (
                rest("GET", "repos/octo/Hello/pulls", "head=octo:feature", "state=closed"),
                json_response(closed_pulls),
            ),
        ]
    )


def test_current_pr_number_falls_back_to_the_branch_lookup() -> None:
    """A blocked gh pr view is replaced by a pulls lookup on the current branch."""
    assert gh_runner.current_pr_number(run_fn=_branch_runner([{"number": 42}])) == 42


def test_current_pr_number_fallback_prefers_an_open_pr_then_the_newest_closed_one() -> None:
    """An open PR wins, and a merged branch still finds its newest closed PR."""
    closed = [{"number": 9, "state": "closed"}, {"number": 8, "state": "closed"}]

    assert gh_runner.current_pr_number(run_fn=_branch_runner([], closed)) == 9


def test_current_pr_number_fallback_open_query_wins_over_closed_pulls() -> None:
    """The open query is answered first, so a closed PR is never even requested."""
    runner = _branch_runner([{"number": 7, "state": "open"}], [{"number": 9}])

    assert gh_runner.current_pr_number(run_fn=runner) == 7
    assert not any("state=closed" in call for call in runner.calls)


def test_current_pr_number_fallback_qualifies_a_fork_branch_with_its_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With GH_REPO on upstream, the branch lookup names origin's owner as the head owner."""
    monkeypatch.setenv("GH_REPO", "org/project")
    runner = FakeGh(
        [
            (has("pr", "view"), graphql_blocked()),
            (has("remote"), completed_process(0, "git@github.com:alice/project.git\n")),
            (has("rev-parse"), completed_process(0, "feature\n")),
            (has("config", "--get"), completed_process(1)),
            (
                rest("GET", "repos/org/project/pulls", "head=alice:feature", "state=open"),
                json_response([{"number": 5, "state": "open"}]),
            ),
        ]
    )

    assert gh_runner.current_pr_number(run_fn=runner) == 5


def _recorded_runner(number: str, repo: str | None) -> FakeGh:
    """Build a runner whose branch has a recorded PR number and, optionally, repository."""
    return FakeGh(
        [
            (has("pr", "view"), graphql_blocked()),
            (has("remote"), completed_process(0, "git@github.com:alice/project.git\n")),
            (has("rev-parse"), completed_process(0, "alice/feature\n")),
            (
                has("config", "--get", "branch.alice/feature.gh-pr-number"),
                completed_process(0, f"{number}\n"),
            ),
            (
                has("config", "--get", "branch.alice/feature.gh-pr-repo"),
                completed_process(0, f"{repo}\n") if repo else completed_process(1),
            ),
            (
                rest("GET", "repos/alice/project/pulls/12"),
                json_response({"number": 12, "state": "open"}),
            ),
            (
                rest("GET", "repos/alice/project/pulls", "head=alice:alice/feature", "state=open"),
                json_response([{"number": 99, "state": "open"}]),
            ),
        ]
    )


def test_current_pr_number_fallback_uses_the_pr_a_checkout_recorded() -> None:
    """A fork PR checked out through REST is found by its recorded number, not a head lookup."""
    runner = _recorded_runner("12", "alice/project")

    assert gh_runner.current_pr_number(run_fn=runner) == 12
    assert not any("head=alice:alice/feature" in call for call in runner.calls)


def _closed_recorded_runner(*routes: Route) -> FakeGh:
    """Build a runner whose recorded PR 12 on ``alice/project`` is closed (a fork PR from bob)."""
    return FakeGh(
        [
            (has("pr", "view"), graphql_blocked()),
            (has("remote"), completed_process(0, "git@github.com:alice/project.git\n")),
            (has("rev-parse"), completed_process(0, "bob/feature\n")),
            (
                has("config", "--get", "branch.bob/feature.gh-pr-number"),
                completed_process(0, "12\n"),
            ),
            (
                has("config", "--get", "branch.bob/feature.gh-pr-repo"),
                completed_process(0, "alice/project\n"),
            ),
            (
                rest("GET", "repos/alice/project/pulls/12"),
                json_response(
                    {
                        "number": 12,
                        "state": "closed",
                        "head": {"ref": "feature", "label": "bob:feature", "repo": None},
                    }
                ),
            ),
            *routes,
        ]
    )


def test_current_pr_number_fallback_replaces_a_closed_recorded_pr_with_an_open_one() -> None:
    """A reused branch finds its new PR, looked up by the recorded PR's own head."""
    runner = _closed_recorded_runner(
        (
            rest("GET", "repos/alice/project/pulls", "head=bob:feature", "state=open"),
            json_response([{"number": 20}]),
        )
    )

    assert gh_runner.current_pr_number(run_fn=runner) == 20


def test_current_pr_number_fallback_reads_the_head_owner_from_the_recorded_repo() -> None:
    """The head repository's owner login is preferred over the label."""
    runner = FakeGh(
        [
            (has("pr", "view"), graphql_blocked()),
            (has("remote"), completed_process(0, "git@github.com:alice/project.git\n")),
            (has("rev-parse"), completed_process(0, "carol/feature\n")),
            (
                has("config", "--get", "branch.carol/feature.gh-pr-number"),
                completed_process(0, "12\n"),
            ),
            (
                has("config", "--get", "branch.carol/feature.gh-pr-repo"),
                completed_process(0, "alice/project\n"),
            ),
            (
                rest("GET", "repos/alice/project/pulls/12"),
                json_response(
                    {
                        "state": "closed",
                        "head": {"ref": "feature", "repo": {"owner": {"login": "carol"}}},
                    }
                ),
            ),
            (
                rest("GET", "repos/alice/project/pulls", "head=carol:feature", "state=open"),
                json_response([{"number": 21}]),
            ),
        ]
    )

    assert gh_runner.current_pr_number(run_fn=runner) == 21


def test_current_pr_number_fallback_keeps_a_closed_recorded_pr_without_another() -> None:
    """Like gh pr view, a closed recorded PR still counts when nothing newer exists."""
    runner = _closed_recorded_runner(
        (rest("GET", "repos/alice/project/pulls"), json_response([])),
    )

    assert gh_runner.current_pr_number(run_fn=runner) == 12


def test_current_pr_number_fallback_compares_the_recorded_repo_case_insensitively() -> None:
    """A recorded repository with different capitalization still matches."""
    runner = _recorded_runner("12", "Alice/Project")

    assert gh_runner.current_pr_number(run_fn=runner) == 12


def test_current_pr_number_fallback_ignores_a_number_recorded_for_another_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A different GH_REPO means the recorded number belongs to another repository."""
    monkeypatch.setenv("GH_REPO", "org/other")
    runner = _recorded_runner("12", "alice/project")
    runner.routes.append(
        (
            rest("GET", "repos/org/other/pulls", "head=alice:alice/feature", "state=open"),
            json_response([{"number": 31, "state": "open"}]),
        )
    )

    assert gh_runner.current_pr_number(run_fn=runner) == 31


def test_current_pr_number_fallback_ignores_a_number_recorded_without_a_repo() -> None:
    """A number with no recorded repository cannot be trusted and is looked up instead."""
    assert gh_runner.current_pr_number(run_fn=_recorded_runner("12", None)) == 99


def test_current_pr_number_fallback_ignores_a_malformed_recorded_number() -> None:
    """A recorded value that is not a number falls back to the head lookup."""
    runner = _branch_runner([{"number": 42}])
    runner.routes.insert(0, (has("config", "--get"), completed_process(0, "x\n")))

    assert gh_runner.current_pr_number(run_fn=runner) == 42


def test_current_pr_number_fallback_reports_no_open_pr() -> None:
    """No open PR for the branch gives the same friendly error as the gh path."""
    with pytest.raises(GhError, match="No pull request found"):
        gh_runner.current_pr_number(run_fn=_branch_runner([]))


def test_current_pr_number_fallback_rejects_a_malformed_entry() -> None:
    """A pulls entry without a usable number is a clear error."""
    with pytest.raises(GhError, match="Could not read PR number from the pull request list"):
        gh_runner.current_pr_number(run_fn=_branch_runner([{"number": "x"}]))


def test_run_stdin_text_is_piped_to_the_command() -> None:
    """stdin_text reaches the subprocess as its input."""
    inputs: list[object] = []

    def runner(_cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Record the piped input."""
        inputs.append(kwargs.get("input"))
        return completed_process(0, "ok")

    assert gh_runner.run_gh(["issue", "comment"], run_fn=runner, stdin_text="hi") == "ok"
    assert inputs == ["hi"]


def test_resolve_repo_falls_back_when_repo_view_is_not_an_object() -> None:
    """A non-object ``gh repo view`` payload falls back to the git remote."""
    runner = FakeGh(
        [
            (has("repo", "view"), json_response([])),
            (has("remote"), completed_process(0, "git@github.com:octo/Hello.git\n")),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"


def test_same_repo_ignores_case() -> None:
    """GitHub treats owner/name slugs as case-insensitive."""
    assert gh_runner.same_repo("octo/hello", "octo/Hello")
    assert not gh_runner.same_repo("octo/hello", "octo/other")


def test_require_checkout_repo_refuses_an_unidentifiable_origin() -> None:
    """A non-GitHub origin cannot hold the selected repository's PRs and branches."""
    runner = FakeGh([(has("remote"), completed_process(0, "https://gitlab.com/o/r.git\n"))])

    with pytest.raises(GhError, match="Cannot check out PR #1: origin is not a GitHub repository"):
        gh_runner.require_checkout_repo("o/r", "check out PR #1", run_fn=runner)


def test_require_checkout_repo_accepts_a_slug_that_differs_only_in_case() -> None:
    """Origin naming octo/hello satisfies a GH_REPO of octo/Hello."""
    runner = FakeGh([(has("remote"), completed_process(0, "git@github.com:octo/hello.git\n"))])

    gh_runner.require_checkout_repo("octo/Hello", "check out PR #1", run_fn=runner)
