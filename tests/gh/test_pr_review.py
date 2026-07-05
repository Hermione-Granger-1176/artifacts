from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from scripts.gh import cli, gh_runner, pr_review
from scripts.gh.gh_runner import GhError

if TYPE_CHECKING:
    from collections.abc import Sequence


def completed_process(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Create a subprocess result for injected runners."""
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeGh:
    """A dispatching fake subprocess runner that records its calls."""

    def __init__(self, routes: list[tuple[Callable[[list[str]], bool], Any]]) -> None:
        self.routes = routes
        self.calls: list[list[str]] = []

    def __call__(
        self, cmd: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Return the response whose predicate matches, or fail the test."""
        command = list(cmd)
        self.calls.append(command)
        for predicate, response in self.routes:
            if predicate(command):
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected command: {command}")


def has(*needles: str) -> Callable[[list[str]], bool]:
    """Build a predicate matching commands that contain all needles as arguments."""
    return lambda cmd: all(needle in cmd for needle in needles)


def _query_arg(cmd: list[str]) -> str:
    """Return the ``query=`` argument from a gh graphql command."""
    return next(part for part in cmd if part.startswith("query="))


THREADS_PAYLOAD = {
    "data": {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "PRRT_open1",
                            "isResolved": False,
                            "path": "src/foo.py",
                            "line": 42,
                            "comments": {
                                "nodes": [
                                    {
                                        "body": "Please rename this\nsecond line",
                                        "url": "https://example/1",
                                        "author": {"login": "reviewer"},
                                    }
                                ]
                            },
                        },
                        {
                            "id": "PRRT_done1",
                            "isResolved": True,
                            "path": "src/bar.py",
                            "line": None,
                            "comments": {"nodes": []},
                        },
                    ],
                }
            }
        }
    }
}


def _comments_page(
    thread_id: str,
    comment_nodes: list[dict[str, Any]],
    *,
    threads_next: bool = False,
    threads_cursor: str | None = None,
    comments_next: bool = False,
    comments_cursor: str | None = None,
) -> dict[str, Any]:
    """Build one ``reviewThreads`` page response for the comments query."""
    return {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {
                            "hasNextPage": threads_next,
                            "endCursor": threads_cursor,
                        },
                        "nodes": [
                            {
                                "id": thread_id,
                                "comments": {
                                    "pageInfo": {
                                        "hasNextPage": comments_next,
                                        "endCursor": comments_cursor,
                                    },
                                    "nodes": comment_nodes,
                                },
                            }
                        ],
                    }
                }
            }
        }
    }


COMMENTS_PAYLOAD = _comments_page(
    "PRRT_a",
    [
        {
            "id": "PRRC_first",
            "body": "Original review note\nsecond line",
            "url": "https://example/c1",
            "author": {"login": "reviewer"},
        },
        {
            "id": "PRRC_reply",
            "body": "Fixed it",
            "url": "https://example/c2",
            "author": None,
        },
    ],
)


def test_parse_threads_maps_fields() -> None:
    """Map a GraphQL payload into ReviewThread objects."""
    threads = pr_review.parse_threads(THREADS_PAYLOAD["data"])

    assert [thread.thread_id for thread in threads] == ["PRRT_open1", "PRRT_done1"]
    first = threads[0]
    assert first.state == "open"
    assert first.author == "reviewer"
    assert first.body.startswith("Please rename")
    assert threads[1].state == "resolved"
    assert threads[1].author == "unknown"


def _threads_page(
    thread_id: str, *, has_next: bool, end_cursor: str | None = None
) -> dict[str, Any]:
    """Build a one-node reviewThreads page with the given pagination state."""
    return {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "pageInfo": {"hasNextPage": has_next, "endCursor": end_cursor},
                    "nodes": [
                        {
                            "id": thread_id,
                            "isResolved": False,
                            "path": "f.py",
                            "line": 1,
                            "comments": {
                                "nodes": [
                                    {"body": "x", "url": "u", "author": {"login": "r"}}
                                ]
                            },
                        }
                    ],
                }
            }
        }
    }


def test_list_threads_follows_pagination() -> None:
    """list_threads pages through reviewThreads until hasNextPage is false."""
    pages = iter(
        [
            _threads_page("PRRT_a", has_next=True, end_cursor="CURSOR1"),
            _threads_page("PRRT_b", has_next=False),
        ]
    )
    calls: list[list[str]] = []

    def runner(
        cmd: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        command = list(cmd)
        calls.append(command)
        if has("repo", "view")(command):
            return completed_process(0, json.dumps({"nameWithOwner": "o/r"}))
        if has("graphql")(command):
            return completed_process(0, json.dumps({"data": next(pages)}))
        raise AssertionError(command)

    threads = pr_review.list_threads(7, include_resolved=True, run_fn=runner)

    assert [thread.thread_id for thread in threads] == ["PRRT_a", "PRRT_b"]
    # The second page request carries the first page's endCursor.
    graphql_calls = [command for command in calls if has("graphql")(command)]
    assert len(graphql_calls) == 2
    assert any("after=CURSOR1" in command for command in graphql_calls)


def test_parse_threads_raises_on_missing_pull_request() -> None:
    """A null/absent repository or pull request raises a clear GhError."""
    for payload in ({}, {"repository": None}, {"repository": {"pullRequest": None}}):
        with pytest.raises(GhError):
            pr_review.parse_threads(payload)


def test_list_threads_filters_resolved_by_default() -> None:
    """Drop resolved threads unless include_resolved is set."""
    runner = FakeGh(
        [
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("graphql"), completed_process(0, json.dumps(THREADS_PAYLOAD))),
        ]
    )

    open_only = pr_review.list_threads(7, run_fn=runner)
    everything = pr_review.list_threads(7, include_resolved=True, run_fn=runner)

    assert [thread.thread_id for thread in open_only] == ["PRRT_open1"]
    assert len(everything) == 2


def test_format_threads_is_greppable() -> None:
    """Render each open thread with its id and state."""
    threads = pr_review.parse_threads(THREADS_PAYLOAD["data"])
    text = pr_review.format_threads(threads)

    assert "thread=PRRT_open1" in text
    assert "state=open" in text
    assert "src/foo.py:42" in text
    assert "second line" not in text  # only the first body line is shown


def test_format_threads_empty() -> None:
    """Report when there are no matching threads."""
    assert pr_review.format_threads([]) == "No matching review threads."


def test_reply_uses_thread_id_without_database_id() -> None:
    """Reply via addPullRequestReviewThreadReply keyed on the thread id."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    pr_review.reply_to_thread("PRRT_open1", "Fixed", run_fn=runner)

    (cmd,) = runner.calls
    assert "addPullRequestReviewThreadReply" in _query_arg(cmd)
    assert "thread=PRRT_open1" in cmd
    assert "body=Fixed" in cmd


def test_graphql_serializes_variables_by_type() -> None:
    """Bools become JSON true/false via -F, ints stay typed, strings use -f."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    gh_runner.graphql(
        "query($flag: Boolean!, $count: Int!, $name: String!) { x }",
        variables={"flag": True, "count": 3, "name": "abc"},
        run_fn=runner,
    )

    (cmd,) = runner.calls
    assert "flag=true" in cmd  # not Python's "True"
    assert "count=3" in cmd
    assert "name=abc" in cmd
    # The bool and int are typed (-F); the string is plain (-f).
    assert cmd[cmd.index("flag=true") - 1] == "-F"
    assert cmd[cmd.index("name=abc") - 1] == "-f"


def test_address_replies_then_resolves() -> None:
    """Address a thread by replying first and resolving second."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    pr_review.address_thread("PRRT_open1", "done", run_fn=runner)

    mutations = [_query_arg(cmd) for cmd in runner.calls]
    assert "addPullRequestReviewThreadReply" in mutations[0]
    assert "resolveReviewThread" in mutations[1]


def test_address_short_circuits_when_reply_fails() -> None:
    """Do not resolve a thread if the reply failed."""
    runner = FakeGh([(has("graphql"), completed_process(1, "", "boom"))])

    with pytest.raises(GhError):
        pr_review.address_thread("PRRT_open1", "done", run_fn=runner)

    assert len(runner.calls) == 1  # reply attempted, resolve skipped


def test_pr_summary_includes_meta_and_threads() -> None:
    """Summaries show PR state, a checks tally, and open threads."""
    meta = {
        "number": 7,
        "title": "Add feature",
        "state": "OPEN",
        "url": "https://example/pr/7",
        "statusCheckRollup": [{"conclusion": "SUCCESS"}, {"conclusion": "FAILURE"}],
    }
    runner = FakeGh(
        [
            (has("pr", "view"), completed_process(0, json.dumps(meta))),
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("graphql"), completed_process(0, json.dumps(THREADS_PAYLOAD))),
        ]
    )

    text = pr_review.pr_summary(7, run_fn=runner)

    assert "PR #7 [OPEN] Add feature" in text
    assert "1 failure" in text and "1 success" in text
    assert "open review threads: 1" in text
    assert "thread=PRRT_open1" in text


def test_resolve_repo_falls_back_to_remote() -> None:
    """Parse owner/name from the git remote when gh repo view fails."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (has("remote"), completed_process(0, "git@github.com:octo/Hello.git\n")),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"


def test_resolve_repo_handles_ssh_remote_with_port() -> None:
    """An SSH remote URL with an explicit port still yields owner/name."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (
                has("remote"),
                completed_process(0, "ssh://git@github.com:22/octo/Hello.git\n"),
            ),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"


def test_resolve_repo_ignores_non_github_remote() -> None:
    """Do not treat a non-GitHub origin path as a GitHub owner/name slug."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (
                has("remote"),
                completed_process(0, "https://gitlab.example/octo/Hello.git\n"),
            ),
        ]
    )

    with pytest.raises(GhError):
        gh_runner.resolve_repo(run_fn=runner)


def test_resolve_repo_ignores_github_lookalike_host() -> None:
    """Reject origins whose host merely contains github.com as a substring."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (
                has("remote"),
                completed_process(0, "https://github.com.evil/octo/Hello.git\n"),
            ),
        ]
    )

    with pytest.raises(GhError):
        gh_runner.resolve_repo(run_fn=runner)


def test_resolve_repo_falls_back_when_key_missing() -> None:
    """A repo-view payload without nameWithOwner still falls back to the remote."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(0, json.dumps({}))),
            (has("remote"), completed_process(0, "git@github.com:octo/Hello.git\n")),
        ]
    )

    assert gh_runner.resolve_repo(run_fn=runner) == "octo/Hello"


def test_resolve_repo_raises_when_unresolvable() -> None:
    """Raise a clear error when neither source yields a slug."""
    runner = FakeGh(
        [
            (has("repo", "view"), completed_process(1, "", "no repo")),
            (has("remote"), completed_process(1, "", "no remote")),
        ]
    )

    with pytest.raises(GhError):
        gh_runner.resolve_repo(run_fn=runner)


def test_current_pr_number_parses_gh_output() -> None:
    """Read the PR number for the current branch."""
    runner = FakeGh(
        [(has("pr", "view"), completed_process(0, json.dumps({"number": 19})))]
    )

    assert gh_runner.current_pr_number(run_fn=runner) == 19


def test_current_pr_number_raises_without_pr() -> None:
    """Raise a friendly error when the branch has no PR."""
    runner = FakeGh(
        [(has("pr", "view"), completed_process(1, "", "no pull requests found"))]
    )

    with pytest.raises(GhError):
        gh_runner.current_pr_number(run_fn=runner)


def test_main_requires_body_for_reply() -> None:
    """Reject a reply that is missing a body via argparse."""
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["reply", "--thread", "PRRT_x"])

    assert excinfo.value.code == 2


def test_main_list_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list command emits JSON when asked."""
    thread = pr_review.ReviewThread("PRRT_x", "open", "f.py", 1, "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_threads", lambda *_a, **_k: [thread])

    exit_code = cli.main(["list", "--json"])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured[0]["thread_id"] == "PRRT_x"


def test_list_comments_flattens_all_thread_comments() -> None:
    """list_comments returns every comment across threads, missing author included."""
    runner = FakeGh(
        [
            (
                has("repo", "view"),
                completed_process(0, json.dumps({"nameWithOwner": "o/r"})),
            ),
            (has("graphql"), completed_process(0, json.dumps(COMMENTS_PAYLOAD))),
        ]
    )

    comments = pr_review.list_comments(7, run_fn=runner)

    assert [comment.comment_id for comment in comments] == ["PRRC_first", "PRRC_reply"]
    assert comments[0].author == "reviewer"
    assert comments[1].author == "unknown"  # null author falls back


def test_list_comments_paginates_threads_and_comments() -> None:
    """list_comments pages both reviewThreads and a thread's overflow comments."""
    thread_comments_page = {
        "data": {
            "node": {
                "comments": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {
                            "id": "PRRC_a2",
                            "body": "more",
                            "url": "u",
                            "author": {"login": "r"},
                        }
                    ],
                }
            }
        }
    }
    pages = iter(
        [
            _comments_page(
                "PRRT_a",
                [
                    {
                        "id": "PRRC_a1",
                        "body": "first",
                        "url": "u",
                        "author": {"login": "r"},
                    }
                ],
                threads_next=True,
                threads_cursor="TCUR",
                comments_next=True,
                comments_cursor="CCUR",
            ),
            thread_comments_page,
            _comments_page(
                "PRRT_b",
                [
                    {
                        "id": "PRRC_b1",
                        "body": "second",
                        "url": "u",
                        "author": {"login": "r"},
                    }
                ],
            ),
        ]
    )
    calls: list[list[str]] = []

    def runner(
        cmd: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        command = list(cmd)
        calls.append(command)
        if has("repo", "view")(command):
            return completed_process(0, json.dumps({"nameWithOwner": "o/r"}))
        if has("graphql")(command):
            return completed_process(0, json.dumps(next(pages)))
        raise AssertionError(command)

    comments = pr_review.list_comments(7, run_fn=runner)

    assert [comment.comment_id for comment in comments] == [
        "PRRC_a1",
        "PRRC_a2",
        "PRRC_b1",
    ]
    graphql_calls = [command for command in calls if has("graphql")(command)]
    assert len(graphql_calls) == 3
    assert any(
        "after=CCUR" in command for command in graphql_calls
    )  # comment pagination
    assert any(
        "after=TCUR" in command for command in graphql_calls
    )  # thread pagination


def test_format_comments_shows_first_line_only() -> None:
    """Rendering is one greppable line per comment, first body line only."""
    comment = pr_review.ReviewComment(
        "PRRC_first", "reviewer", "Note here\nsecond line", "u"
    )

    text = pr_review.format_comments([comment])

    assert text == "comment=PRRC_first  @reviewer: Note here"


def test_format_comments_empty() -> None:
    """An empty comment list renders a friendly placeholder."""
    assert pr_review.format_comments([]) == "No review comments."


def test_delete_review_comment_uses_mutation_without_retry() -> None:
    """Deletion keys off the comment node id via deletePullRequestReviewComment."""
    runner = FakeGh([(has("graphql"), completed_process(0, json.dumps({"data": {}})))])

    pr_review.delete_review_comment("PRRC_reply", run_fn=runner)

    (cmd,) = runner.calls
    assert "deletePullRequestReviewComment" in _query_arg(cmd)
    assert "comment=PRRC_reply" in cmd


def test_main_list_comments_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list-comments command emits JSON when asked."""
    comment = pr_review.ReviewComment("PRRC_x", "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_comments", lambda *_a, **_k: [comment])

    exit_code = cli.main(["list-comments", "--json"])

    captured = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert captured[0]["comment_id"] == "PRRC_x"


def test_main_delete_comment_invokes_helper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The delete-comment command deletes by node id and confirms."""
    deleted: list[str] = []
    monkeypatch.setattr(
        pr_review, "delete_review_comment", lambda comment: deleted.append(comment)
    )

    exit_code = cli.main(["delete-comment", "--comment", "PRRC_x"])

    assert exit_code == 0
    assert deleted == ["PRRC_x"]
    assert "Deleted PRRC_x" in capsys.readouterr().out


def test_main_list_prints_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list command prints formatted text by default."""
    thread = pr_review.ReviewThread("PRRT_x", "open", "f.py", 1, "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_threads", lambda *_a, **_k: [thread])

    exit_code = cli.main(["list"])

    assert exit_code == 0
    assert "thread=PRRT_x" in capsys.readouterr().out


def test_main_reply_reads_body_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The reply command accepts body text from a file."""
    body_file = tmp_path / "reply.md"
    body_file.write_text("Fixed with detail", encoding="utf-8")
    replies: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pr_review,
        "reply_to_thread",
        lambda thread, body: replies.append((thread, body)),
    )

    exit_code = cli.main(["reply", "--thread", "PRRT_x", "--body-file", str(body_file)])

    assert exit_code == 0
    assert replies == [("PRRT_x", "Fixed with detail")]
    assert "Replied to PRRT_x" in capsys.readouterr().out


def test_main_resolve_invokes_helper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The resolve command resolves by thread id and confirms."""
    resolved: list[str] = []
    monkeypatch.setattr(pr_review, "resolve_thread", resolved.append)

    exit_code = cli.main(["resolve", "--thread", "PRRT_x"])

    assert exit_code == 0
    assert resolved == ["PRRT_x"]
    assert "Resolved PRRT_x" in capsys.readouterr().out


def test_main_address_invokes_helper(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The address command replies and resolves through the helper."""
    addressed: list[tuple[str, str]] = []
    monkeypatch.setattr(
        pr_review,
        "address_thread",
        lambda thread, body: addressed.append((thread, body)),
    )

    exit_code = cli.main(["address", "--thread", "PRRT_x", "--body", "Fixed now"])

    assert exit_code == 0
    assert addressed == [("PRRT_x", "Fixed now")]
    assert "Replied to and resolved PRRT_x" in capsys.readouterr().out


def test_main_list_comments_prints_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The list-comments command prints formatted text by default."""
    comment = pr_review.ReviewComment("PRRC_x", "me", "hi", "u")
    monkeypatch.setattr(pr_review, "list_comments", lambda *_a, **_k: [comment])

    exit_code = cli.main(["list-comments"])

    assert exit_code == 0
    assert "comment=PRRC_x" in capsys.readouterr().out


def test_main_summary_prints_overview(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The summary command prints the PR overview."""
    monkeypatch.setattr(pr_review, "pr_summary", lambda pr: f"summary {pr}")

    exit_code = cli.main(["summary", "--pr", "7"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "summary 7"


def test_main_ci_failures_prints_digest(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The ci-failures command prints the failed-step digest."""
    monkeypatch.setattr(cli.ci_status, "failure_digest", lambda run: f"run {run}")

    exit_code = cli.main(["ci-failures", "--run", "99"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "run 99"


def test_rollup_summary_empty() -> None:
    """An empty check rollup is rendered as none."""
    assert pr_review._rollup_summary([]) == "none"


def test_owner_name_rejects_invalid_slug(monkeypatch: pytest.MonkeyPatch) -> None:
    """The owner/name splitter rejects a malformed slug."""
    monkeypatch.setattr(gh_runner, "resolve_repo", lambda **_kwargs: "owner/")

    with pytest.raises(GhError):
        pr_review._owner_name()
