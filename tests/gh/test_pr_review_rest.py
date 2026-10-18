"""REST fallback behavior of the review-thread operations when GraphQL is blocked."""

from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from scripts.gh import cli, gh_runner, pr_review
from scripts.gh.gh_runner import GhError, GhRateLimitError
from tests.gh.gh_test_support import (
    FakeGh,
    completed_process,
    graphql_blocked,
    has,
    json_response,
    rest,
    sandbox_routes,
)

if TYPE_CHECKING:
    from collections.abc import Callable

Route = tuple["Callable[[list[str]], bool]", Any]

THREADS = [
    {"resolved": False, "outdated": False, "path": "a.py", "line": 4, "comment_ids": [11, 12]},
    {"resolved": True, "outdated": True, "path": "b.py", "line": None, "comment_ids": [21]},
]
COMMENTS = [
    {
        "id": 11,
        "node_id": "PRRC_11",
        "body": "Rename this\nplease",
        "html_url": "https://example/pull/7#discussion_r11",
        "user": {"login": "reviewer"},
    },
    {"id": 12, "body": "Done", "html_url": "u12", "user": {"login": "author"}},
    {"id": 21, "body": "Old", "html_url": "u21", "user": None},
]


def _sandbox(*routes: Route) -> FakeGh:
    """Build a runner for a sandbox that blocks GraphQL, with extra REST routes."""
    return FakeGh([*sandbox_routes(), *routes])


def _pr_routes() -> list[Route]:
    """Routes that resolve the current branch ``feature`` to open PR 7."""
    return [
        (has("rev-parse"), completed_process(0, "feature\n")),
        (rest("GET", "repos/o/r/pulls", "head=o:feature"), json_response([{"number": 7}])),
    ]


def _thread_routes(threads: object = THREADS, comments: object = COMMENTS) -> list[Route]:
    """Routes serving the REST thread and comment lists for PR 7."""
    return [
        (rest("GET", "repos/o/r/pulls/7/ccr/review_threads"), json_response(threads)),
        (rest("GET", "repos/o/r/pulls/7/comments"), json_response(comments)),
    ]


def test_list_threads_falls_back_to_rest_with_numeric_thread_ids() -> None:
    """Threads come from the REST route, identified by their first comment id."""
    runner = _sandbox(*_thread_routes())

    threads = pr_review.list_threads(7, include_resolved=True, run_fn=runner)

    assert [(t.thread_id, t.state, t.path, t.line) for t in threads] == [
        ("11", "open", "a.py", 4),
        ("21", "resolved", "b.py", None),
    ]
    assert (threads[0].author, threads[0].body, threads[0].url) == (
        "reviewer",
        "Rename this\nplease",
        "https://example/pull/7#discussion_r11",
    )
    assert threads[1].author == "unknown"
    rendered = pr_review.format_threads(threads[:1])
    assert rendered.startswith("thread=11  state=open  path=a.py:4")


def test_list_threads_hides_resolved_threads_by_default() -> None:
    """The default listing keeps only open threads."""
    runner = _sandbox(*_thread_routes())

    assert [t.thread_id for t in pr_review.list_threads(7, run_fn=runner)] == ["11"]


def test_list_threads_remembers_the_blocked_verdict() -> None:
    """The first blocked call is remembered, so later calls skip GraphQL entirely."""
    runner = _sandbox(*_thread_routes())

    pr_review.list_threads(7, run_fn=runner)
    pr_review.list_threads(7, run_fn=runner)

    assert not any(call[:3] == ["gh", "api", "graphql"] for call in runner.calls)
    assert sum(call[:3] == ["gh", "repo", "view"] for call in runner.calls) == 1


def test_list_threads_resolves_the_current_pr_through_rest() -> None:
    """Without a PR number the current branch's PR is found through REST."""
    runner = _sandbox(*_pr_routes(), *_thread_routes())

    assert [t.thread_id for t in pr_review.list_threads(run_fn=runner)] == ["11"]


def test_list_threads_skips_the_comment_lookup_when_there_are_no_threads() -> None:
    """An empty thread list needs no comment fetch."""
    runner = _sandbox(
        (rest("GET", "repos/o/r/pulls/7/ccr/review_threads"), json_response([])),
    )

    assert pr_review.list_threads(7, include_resolved=True, run_fn=runner) == []


def test_list_threads_tolerates_a_thread_whose_comment_is_missing() -> None:
    """A thread whose first comment is not listed still renders, without author text."""
    runner = _sandbox(*_thread_routes(comments=[]))

    thread = pr_review.list_threads(7, include_resolved=True, run_fn=runner)[0]

    assert (thread.author, thread.body, thread.url) == ("unknown", "", "")


@pytest.mark.parametrize(
    ("threads", "comments", "message"),
    [
        ({"not": "a list"}, [], "Unexpected review threads shape"),
        (["x"], [], "no comment ids"),
        ([{"comment_ids": []}], [], "no comment ids"),
        (THREADS, [{"body": "no id"}], "has no id"),
    ],
)
def test_list_threads_rejects_malformed_rest_responses(
    threads: object, comments: object, message: str
) -> None:
    """Unexpected REST shapes surface as GhError."""
    runner = _sandbox(*_thread_routes(threads, comments))

    with pytest.raises(GhError, match=message):
        pr_review.list_threads(7, include_resolved=True, run_fn=runner)


def test_other_graphql_failures_do_not_fall_back_to_rest() -> None:
    """A plain 403 from GraphQL propagates; REST is never consulted."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(0, '{"nameWithOwner": "o/r"}')),
            (has("graphql"), completed_process(1, "", "HTTP 403: Forbidden")),
        ]
    )

    with pytest.raises(GhError, match="Forbidden"):
        pr_review.list_threads(7, run_fn=runner)

    assert not any("--method" in call for call in runner.calls)


def test_list_comments_falls_back_to_numeric_ids() -> None:
    """Every REST review comment is listed with its numeric id."""
    runner = _sandbox(*_thread_routes())

    comments = pr_review.list_comments(7, run_fn=runner)

    assert [c.comment_id for c in comments] == ["11", "12", "21"]
    assert comments[1].author == "author"
    assert (
        pr_review.format_comments(comments).splitlines()[0] == "comment=11  @reviewer: Rename this"
    )


def test_reply_to_numeric_thread_posts_a_rest_reply() -> None:
    """A numeric id replies through REST without trying GraphQL."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(0, '{"nameWithOwner": "o/r"}')),
            (
                rest("POST", "repos/o/r/pulls/7/comments/11/replies", "body=Fixed"),
                json_response({}),
            ),
        ]
    )

    pr_review.reply_to_thread("11", "Fixed", pr=7, run_fn=runner)

    assert not any("graphql" in call for call in runner.calls)


def test_reply_defaults_to_the_current_pr() -> None:
    """Without --pr a numeric reply targets the current branch's PR."""
    runner = _sandbox(
        *_pr_routes(),
        (rest("POST", "repos/o/r/pulls/7/comments/11/replies", "body=Hi"), json_response({})),
    )

    pr_review.reply_to_thread("11", "Hi", run_fn=runner)


def test_resolve_numeric_thread_uses_the_rest_thread_route_with_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A numeric id resolves through the ccr route, which is idempotent and retried."""
    monkeypatch.setattr(gh_runner, "_sleep", lambda _seconds: None)
    resolve_outcomes = iter([completed_process(1, "", "HTTP 502"), json_response({})])
    resolve_calls: list[list[str]] = []

    def runner(cmd: list[str], **_kwargs: object) -> Any:
        """Serve the repo lookup, and fail the first resolve transiently."""
        if cmd[:2] == ["git", "remote"]:
            return completed_process(0, "https://github.com/o/r.git\n")
        if cmd[0] == "git":
            return completed_process(1)
        if cmd[:2] == ["gh", "repo"]:
            return graphql_blocked()
        resolve_calls.append(cmd)
        return next(resolve_outcomes)

    pr_review.resolve_thread("11", pr=7, run_fn=runner)

    assert [call[4] for call in resolve_calls] == ["repos/o/r/pulls/7/ccr/comments/11/resolve"] * 2


def test_address_numeric_thread_replies_then_resolves() -> None:
    """Addressing a numeric thread posts the reply and then resolves it."""
    runner = _sandbox(
        (rest("POST", "repos/o/r/pulls/7/comments/11/replies"), json_response({})),
        (rest("POST", "repos/o/r/pulls/7/ccr/comments/11/resolve"), json_response({})),
    )

    pr_review.address_thread("11", "Done", pr=7, run_fn=runner)

    posts = [call[4] for call in runner.calls if call[2:4] == ["--method", "POST"]]
    assert posts == [
        "repos/o/r/pulls/7/comments/11/replies",
        "repos/o/r/pulls/7/ccr/comments/11/resolve",
    ]


@pytest.mark.parametrize(
    "operation",
    [
        lambda runner: pr_review.reply_to_thread("PRRT_x", "b", run_fn=runner),
        lambda runner: pr_review.resolve_thread("PRRT_x", run_fn=runner),
        lambda runner: pr_review.address_thread("PRRT_x", "b", run_fn=runner),
        lambda runner: pr_review.delete_review_comment("PRRC_x", run_fn=runner),
    ],
)
def test_node_ids_explain_the_numeric_route_when_graphql_is_blocked(
    operation: Callable[[FakeGh], None],
) -> None:
    """A GraphQL node id cannot be used here, and the error says what to use instead."""
    runner = _sandbox()

    with pytest.raises(GhError, match="numeric id"):
        operation(runner)


def test_delete_numeric_comment_uses_rest_delete() -> None:
    """A numeric comment id is deleted through REST without a PR number."""
    runner = _sandbox((rest("DELETE", "repos/o/r/pulls/comments/21"), completed_process(0, "")))

    pr_review.delete_review_comment("21", run_fn=runner)

    assert runner.calls[-1][:4] == ["gh", "api", "--method", "DELETE"]


def test_comment_on_pr_falls_back_to_an_issue_comment() -> None:
    """The REST path posts the PR-level comment on the issues endpoint."""
    runner = _sandbox(
        (rest("POST", "repos/o/r/issues/7/comments", "body=Hello"), json_response({})),
    )

    pr_review.comment_on_pr(7, "Hello", run_fn=runner)


def _summary_routes() -> list[Route]:
    """Routes serving PR 7's metadata, checks, and one open thread."""
    return [
        (
            rest("GET", "repos/o/r/pulls/7"),
            json_response(
                {
                    "number": 7,
                    "title": "T",
                    "state": "open",
                    "html_url": "https://example/pull/7",
                    "head": {"sha": "abc"},
                }
            ),
        ),
        (
            rest("GET", "repos/o/r/commits/abc/check-runs"),
            json_response(
                {"check_runs": [{"name": "lint", "status": "completed", "conclusion": "success"}]}
            ),
        ),
        (rest("GET", "repos/o/r/commits/abc/status"), json_response({"statuses": []})),
        *_thread_routes(),
    ]


def test_pr_summary_falls_back_to_rest() -> None:
    """The summary is built from REST metadata, checks, and threads."""
    text = pr_review.pr_summary(7, run_fn=_sandbox(*_summary_routes()))

    assert text.splitlines()[:4] == [
        "PR #7 [OPEN] T",
        "  https://example/pull/7",
        "  checks: 1 success",
        "  open review threads: 1",
    ]
    assert "thread=11" in text


def test_copilot_review_falls_back_to_the_bot_login() -> None:
    """The REST request names the Copilot bot, since @copilot is a gh shorthand."""
    runner = _sandbox(
        (
            rest(
                "POST",
                "repos/o/r/pulls/7/requested_reviewers",
                "reviewers[]=copilot-pull-request-reviewer[bot]",
            ),
            json_response({}),
        )
    )

    pr_review.request_copilot_review(7, run_fn=runner)


def test_copilot_review_fallback_failure_is_wrapped() -> None:
    """A failing REST request is reported as a failed Copilot request."""
    runner = _sandbox(
        (
            rest("POST", "repos/o/r/pulls/7/requested_reviewers"),
            completed_process(1, "", "Validation Failed (HTTP 422)"),
        )
    )

    with pytest.raises(GhError, match="Failed to request Copilot review on PR #7"):
        pr_review.request_copilot_review(7, run_fn=runner)


def test_copilot_review_fallback_rate_limit_is_not_wrapped() -> None:
    """A rate limit on the REST request keeps its own type."""
    runner = _sandbox(
        (
            rest("POST", "repos/o/r/pulls/7/requested_reviewers"),
            completed_process(1, "", "API rate limit exceeded"),
        )
    )

    with pytest.raises(GhRateLimitError):
        pr_review.request_copilot_review(7, run_fn=runner)


def _patch_route(*needles: str) -> Route:
    """Route for the PATCH that edits PR 7."""
    return (rest("PATCH", "repos/o/r/pulls/7", *needles), json_response({}))


def test_edit_pr_falls_back_to_a_patch_with_title_and_inline_body() -> None:
    """Title and inline body are sent in one PATCH."""
    runner = _sandbox(_patch_route("title=T", "body=B"))

    pr_review.edit_pr(7, title="T", body="B", run_fn=runner)


def test_edit_pr_falls_back_with_a_body_file(tmp_path: Path) -> None:
    """A body file is read by the fallback itself."""
    body_file = tmp_path / "body.md"
    body_file.write_text("from file", encoding="utf-8")
    runner = _sandbox(_patch_route("body=from file"))

    pr_review.edit_pr(7, body_file=str(body_file), run_fn=runner)


def test_edit_pr_fallback_reuses_the_stdin_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Standard input read for gh is still available to the fallback."""
    monkeypatch.setattr("sys.stdin", io.StringIO("piped"))
    runner = _sandbox(*_pr_routes(), _patch_route("body=piped"))

    pr_review.edit_pr(body_file="-", run_fn=runner)


def test_edit_pr_fallback_reports_an_unreadable_body_file() -> None:
    """A missing body file is a GhError naming the path."""
    runner = _sandbox()

    with pytest.raises(GhError, match=r"Could not read body file /missing/body.md"):
        pr_review.edit_pr(7, body_file="/missing/body.md", run_fn=runner)


def test_edit_pr_fallback_with_title_only_sends_no_body() -> None:
    """A title-only edit patches just the title."""
    runner = _sandbox(_patch_route("title=Only"))

    pr_review.edit_pr(7, title="Only", run_fn=runner)

    assert not any("body=" in part for part in runner.calls[-1])


def test_cli_reply_accepts_numeric_ids_and_a_pr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reply command passes --pr through for numeric thread ids."""
    seen: list[tuple[str, int | None]] = []
    monkeypatch.setattr(
        pr_review, "reply_to_thread", lambda thread, _body, pr=None: seen.append((thread, pr))
    )

    assert cli.main(["reply", "--thread", "11", "--pr", "7", "--body", "x"]) == 0

    assert seen == [("11", 7)]
    assert "Replied to 11" in capsys.readouterr().out


def test_list_threads_falls_back_when_the_graphql_call_itself_is_refused() -> None:
    """GraphQL is tried first and its refusal switches to REST for the rest of the run."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(0, '{"nameWithOwner": "o/r"}')),
            (lambda cmd: cmd[:3] == ["gh", "api", "graphql"], graphql_blocked()),
            (has("remote"), completed_process(0, "https://github.com/o/r.git\n")),
            *_thread_routes(),
        ]
    )

    assert [t.thread_id for t in pr_review.list_threads(7, run_fn=runner)] == ["11"]
    assert [t.thread_id for t in pr_review.list_threads(7, run_fn=runner)] == ["11"]
    assert sum(call[:3] == ["gh", "api", "graphql"] for call in runner.calls) == 1
