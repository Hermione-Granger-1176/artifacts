from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from scripts.gh import issue_commands
from scripts.gh.gh_runner import GhError
from tests.gh.gh_test_support import (
    FakeGh,
    completed_process,
    has,
    json_response,
    rest,
    sandbox_routes,
)

if TYPE_CHECKING:
    from collections.abc import Callable

Route = tuple["Callable[[list[str]], bool]", Any]

ISSUE = {
    "number": 5,
    "title": "Broken: the thing!",
    "state": "open",
    "html_url": "https://example/issues/5",
    "body": "Details",
    "user": {"login": "octo"},
    "labels": [{"name": "bug"}, {"name": "CI"}],
    "assignees": [{"login": "dev1"}],
    "milestone": {"title": "v1"},
}


class Recorder:
    """A runner that records every command with its options and returns one result."""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Record the call and succeed."""
        self.calls.append((list(cmd), dict(kwargs)))
        return completed_process(0)


def _sandbox(*routes: Route) -> FakeGh:
    """Build a runner for a sandbox that blocks GraphQL, with extra routes."""
    return FakeGh([*sandbox_routes(), *routes])


def _issue_route(issue: dict[str, Any] | None = None) -> Route:
    """Route serving issue 5's REST object."""
    return (rest("GET", "repos/o/r/issues/5"), json_response(issue or ISSUE))


# --- primary path ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("call", "expected", "stdin"),
    [
        (
            lambda r: issue_commands.list_issues(run_fn=r),
            ["gh", "issue", "list"],
            None,
        ),
        (
            lambda r: issue_commands.list_issues(
                state="all",
                labels="bug",
                assignees=["dev", "@me"],
                author="octo",
                limit=5,
                search="is:open crash",
                run_fn=r,
            ),
            [
                "gh",
                "issue",
                "list",
                "--state",
                "all",
                "--label",
                "bug",
                "--assignee",
                "dev",
                "--assignee",
                "@me",
                "--author",
                "octo",
                "--limit",
                "5",
                "--search",
                "is:open crash",
            ],
            None,
        ),
        (
            lambda r: issue_commands.view_issue(5, run_fn=r),
            ["gh", "issue", "view", "5", "--comments"],
            None,
        ),
        (
            lambda r: issue_commands.create_issue(
                "T", "Body", labels="bug,ci", assignee="@me", run_fn=r
            ),
            [
                "gh",
                "issue",
                "create",
                "--title",
                "T",
                "--label",
                "bug,ci",
                "--assignee",
                "@me",
                "--body-file",
                "-",
            ],
            "Body",
        ),
        (
            lambda r: issue_commands.create_issue("T", "Body", run_fn=r),
            ["gh", "issue", "create", "--title", "T", "--body-file", "-"],
            "Body",
        ),
        (
            lambda r: issue_commands.comment_issue(5, "Hi", run_fn=r),
            ["gh", "issue", "comment", "5", "--body-file", "-"],
            "Hi",
        ),
        (
            lambda r: issue_commands.edit_issue(5, title="T", body="B", run_fn=r),
            ["gh", "issue", "edit", "5", "--title", "T", "--body-file", "-"],
            "B",
        ),
        (
            lambda r: issue_commands.edit_issue(5, title="T", run_fn=r),
            ["gh", "issue", "edit", "5", "--title", "T"],
            None,
        ),
        (
            lambda r: issue_commands.label_issue(5, "bug,ci", run_fn=r),
            ["gh", "issue", "edit", "5", "--add-label", "bug,ci"],
            None,
        ),
        (
            lambda r: issue_commands.label_issue(5, "bug", remove=True, run_fn=r),
            ["gh", "issue", "edit", "5", "--remove-label", "bug"],
            None,
        ),
        (
            lambda r: issue_commands.assign_issue(5, users="a,b", mine=True, run_fn=r),
            [
                "gh",
                "issue",
                "edit",
                "5",
                "--add-assignee",
                "@me",
                "--add-assignee",
                "a,b",
            ],
            None,
        ),
        (
            lambda r: issue_commands.assign_issue(5, mine=True, remove=True, run_fn=r),
            ["gh", "issue", "edit", "5", "--remove-assignee", "@me"],
            None,
        ),
        (
            lambda r: issue_commands.close_issue(5, reason="not planned", comment="Why", run_fn=r),
            ["gh", "issue", "close", "5", "--reason", "not planned", "--comment", "Why"],
            None,
        ),
        (
            lambda r: issue_commands.close_issue(5, run_fn=r),
            ["gh", "issue", "close", "5"],
            None,
        ),
        (
            lambda r: issue_commands.reopen_issue(5, comment="Back", run_fn=r),
            ["gh", "issue", "reopen", "5", "--comment", "Back"],
            None,
        ),
        (
            lambda r: issue_commands.reopen_issue(5, run_fn=r),
            ["gh", "issue", "reopen", "5"],
            None,
        ),
        (
            lambda r: issue_commands.develop_issue(5, base="dev", name="fix-5", run_fn=r),
            ["gh", "issue", "develop", "5", "--checkout", "--base", "dev", "--name", "fix-5"],
            None,
        ),
        (
            lambda r: issue_commands.develop_issue(5, run_fn=r),
            ["gh", "issue", "develop", "5", "--checkout"],
            None,
        ),
    ],
)
def test_gh_is_the_primary_path(
    call: Callable[[Recorder], int], expected: list[str], stdin: str | None
) -> None:
    """On a machine with GraphQL, each command runs the same gh invocation as before."""
    recorder = Recorder()

    assert call(recorder) == 0

    cmd, options = recorder.calls[0]
    assert cmd == expected
    assert options.get("input") == stdin
    assert len(recorder.calls) == 1


def test_edit_requires_a_title_or_body() -> None:
    """An edit that changes nothing is rejected."""
    with pytest.raises(GhError, match="Provide a title or body"):
        issue_commands.edit_issue(5, run_fn=Recorder())


# --- REST fallback --------------------------------------------------------------------------


def test_list_fallback_filters_out_pull_requests(capsys: pytest.CaptureFixture[str]) -> None:
    """The repository issue list is used, minus entries that are really PRs."""
    runner = _sandbox(
        (
            rest(
                "GET",
                "repos/o/r/issues",
                "state=open",
                "labels=bug,ci",
                "assignee=dev",
                "creator=octo",
            ),
            json_response(
                [
                    {"number": 1, "state": "open", "title": "A", "labels": [{"name": "bug"}]},
                    {"number": 2, "state": "open", "title": "PR", "pull_request": {}},
                    {"number": 3, "state": "open", "title": "C", "labels": None},
                ]
            ),
        )
    )

    code = issue_commands.list_issues(
        labels="bug, ci", assignees=["dev"], author="octo", run_fn=runner
    )

    assert code == 0
    assert capsys.readouterr().out.splitlines() == ["1\tOPEN\tA\tbug", "3\tOPEN\tC\t"]


def test_list_fallback_resolves_me_and_honors_state_and_limit() -> None:
    """@me becomes the authenticated login, and state and limit reach the request."""
    runner = _sandbox(
        (rest("GET", "user"), json_response({"login": "me-login"})),
        (
            rest("GET", "repos/o/r/issues", "state=closed", "assignee=me-login", "per_page=2"),
            json_response([]),
        ),
    )

    issue_commands.list_issues(state="closed", assignees=["@me"], limit=2, run_fn=runner)


def test_list_fallback_reports_an_empty_result(capsys: pytest.CaptureFixture[str]) -> None:
    """No matches are reported on standard error."""
    runner = _sandbox((rest("GET", "repos/o/r/issues"), json_response([])))

    issue_commands.list_issues(run_fn=runner)

    assert "No issues match your search in o/r" in capsys.readouterr().err


def test_list_fallback_uses_the_search_endpoint_for_search_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Search text and the filters become one search query."""
    runner = _sandbox(
        (
            rest(
                "GET",
                "search/issues",
                'q=repo:o/r is:issue is:closed label:"bug" label:"ci" assignee:@me '
                "author:octo crash",
                "sort=created",
            ),
            json_response({"items": [{"number": 9, "state": "closed", "title": "Crash"}]}),
        )
    )

    issue_commands.list_issues(
        state="closed",
        labels="bug,ci",
        assignees=["@me"],
        author="octo",
        search="crash",
        run_fn=runner,
    )

    assert capsys.readouterr().out.splitlines() == ["9\tCLOSED\tCrash\t"]


def test_search_query_omits_the_state_for_all_issues() -> None:
    """state=all adds no state qualifier, and plain defaults mean open issues."""
    assert issue_commands._search_query("o/r", "all", None, None, None, "x") == (
        "repo:o/r is:issue x"
    )
    assert issue_commands._search_query("o/r", None, None, None, None, "x") == (
        "repo:o/r is:issue is:open x"
    )


def test_login_rejects_an_unresolvable_me() -> None:
    """@me must resolve to a login."""
    runner = _sandbox((rest("GET", "user"), json_response({})))

    with pytest.raises(GhError, match="Could not resolve @me"):
        issue_commands._login("@me", run_fn=runner)


def test_view_fallback_prints_the_issue_and_comments(capsys: pytest.CaptureFixture[str]) -> None:
    """Metadata, body, and comments are printed."""
    runner = _sandbox(
        _issue_route(),
        (
            rest("GET", "repos/o/r/issues/5/comments"),
            json_response([{"user": {"login": "a"}, "body": "hi"}, {"user": None, "body": None}]),
        ),
    )

    assert issue_commands.view_issue(5, run_fn=runner) == 0

    out = capsys.readouterr().out
    assert "Broken: the thing! #5" in out
    assert "state: OPEN" in out
    assert "author: @octo" in out
    assert "labels: bug, CI" in out
    assert "assignees: dev1" in out
    assert "milestone: v1" in out
    assert "Details" in out
    assert "comment by @a\nhi" in out
    assert "comment by @unknown" in out


def test_view_fallback_handles_a_sparse_issue(capsys: pytest.CaptureFixture[str]) -> None:
    """Missing labels, assignees, milestone, and body print as none."""
    sparse = {"number": 6, "title": "T", "state": "closed", "html_url": "u"}
    runner = _sandbox(
        (rest("GET", "repos/o/r/issues/6"), json_response(sparse)),
        (rest("GET", "repos/o/r/issues/6/comments"), json_response([])),
    )

    issue_commands.view_issue(6, run_fn=runner)

    out = capsys.readouterr().out
    assert "author: @unknown" in out
    assert "labels: none" in out
    assert "assignees: none" in out
    assert "milestone: none" in out


def test_create_fallback_posts_labels_and_assignees(capsys: pytest.CaptureFixture[str]) -> None:
    """Title, body, labels, and the resolved assignee go in one POST."""
    runner = _sandbox(
        (rest("GET", "user"), json_response({"login": "me-login"})),
        (
            rest(
                "POST",
                "repos/o/r/issues",
                "title=T",
                "body=Body",
                "labels[]=bug",
                "labels[]=ci",
                "assignees[]=me-login",
            ),
            json_response({"html_url": "https://example/issues/9"}),
        ),
    )

    issue_commands.create_issue("T", "Body", labels="bug,ci", assignee="@me", run_fn=runner)

    assert capsys.readouterr().out.strip() == "https://example/issues/9"


def test_create_fallback_without_labels_or_assignee() -> None:
    """Only the title and body are sent when nothing else was asked for."""
    runner = _sandbox((rest("POST", "repos/o/r/issues", "title=T"), json_response({})))

    issue_commands.create_issue("T", "Body", run_fn=runner)

    assert not any(part.startswith(("labels[]", "assignees[]")) for part in runner.calls[-1])


def test_comment_fallback_posts_to_the_issue(capsys: pytest.CaptureFixture[str]) -> None:
    """The comment is posted and its URL printed."""
    runner = _sandbox(
        (
            rest("POST", "repos/o/r/issues/5/comments", "body=Hi"),
            json_response({"html_url": "https://example/issues/5#c1"}),
        )
    )

    issue_commands.comment_issue(5, "Hi", run_fn=runner)

    assert capsys.readouterr().out.strip() == "https://example/issues/5#c1"


def test_edit_fallback_patches_title_and_body() -> None:
    """Title and body are sent in one PATCH."""
    runner = _sandbox((rest("PATCH", "repos/o/r/issues/5", "title=T", "body=B"), json_response({})))

    issue_commands.edit_issue(5, title="T", body="B", run_fn=runner)


def test_edit_fallback_with_only_a_title_sends_no_body() -> None:
    """A title-only edit patches just the title."""
    runner = _sandbox((rest("PATCH", "repos/o/r/issues/5", "title=T"), json_response({})))

    issue_commands.edit_issue(5, title="T", run_fn=runner)

    assert not any(part.startswith("body=") for part in runner.calls[-1])


def test_edit_fallback_with_only_a_body_sends_no_title() -> None:
    """A body-only edit patches just the body."""
    runner = _sandbox((rest("PATCH", "repos/o/r/issues/5", "body=B"), json_response({})))

    issue_commands.edit_issue(5, body="B", run_fn=runner)

    assert not any(part.startswith("title=") for part in runner.calls[-1])


def test_label_fallback_adds_labels() -> None:
    """Labels are posted as an array."""
    runner = _sandbox(
        (
            rest("POST", "repos/o/r/issues/5/labels", "labels[]=bug", "labels[]=ci"),
            json_response([]),
        )
    )

    assert issue_commands.label_issue(5, "bug,ci", run_fn=runner) == 0


def test_unlabel_fallback_removes_only_labels_the_issue_has() -> None:
    """A label the issue does not carry is skipped, and names are URL-encoded."""
    labelled = {**ISSUE, "labels": [{"name": "bug"}, {"name": "needs work"}]}
    runner = _sandbox(
        _issue_route(labelled),
        (rest("DELETE", "repos/o/r/issues/5/labels/needs%20work"), json_response([])),
    )

    issue_commands.label_issue(5, "Needs Work,missing", remove=True, run_fn=runner)

    deletes = [call[4] for call in runner.calls if call[2:4] == ["--method", "DELETE"]]
    assert deletes == ["repos/o/r/issues/5/labels/needs%20work"]


def test_labels_of_tolerates_an_unlabelled_issue() -> None:
    """An issue without labels yields an empty list."""
    assert issue_commands._labels_of({}) == []


def test_assign_fallback_posts_assignees_including_me() -> None:
    """Users and @me are combined into one assignees array."""
    runner = _sandbox(
        (rest("GET", "user"), json_response({"login": "me-login"})),
        (
            rest(
                "POST",
                "repos/o/r/issues/5/assignees",
                "assignees[]=me-login",
                "assignees[]=a",
                "assignees[]=b",
            ),
            json_response({}),
        ),
    )

    issue_commands.assign_issue(5, users="a,b", mine=True, run_fn=runner)


def test_unassign_fallback_deletes_assignees() -> None:
    """Removing assignees uses DELETE with the assignees array."""
    runner = _sandbox(
        (rest("DELETE", "repos/o/r/issues/5/assignees", "assignees[]=a"), json_response({}))
    )

    issue_commands.assign_issue(5, users="a", remove=True, run_fn=runner)


def test_close_fallback_comments_then_closes_with_a_reason() -> None:
    """The comment is posted first, then the issue is closed with a normalized reason."""
    runner = _sandbox(
        (rest("POST", "repos/o/r/issues/5/comments", "body=Why"), json_response({})),
        (
            rest("PATCH", "repos/o/r/issues/5", "state=closed", "state_reason=not_planned"),
            json_response({}),
        ),
    )

    assert issue_commands.close_issue(5, reason="Not Planned", comment="Why", run_fn=runner) == 0

    assert [call[3] for call in runner.calls if call[:2] == ["gh", "api"]] == ["POST", "PATCH"]


def test_close_fallback_without_extras_only_patches() -> None:
    """A plain close sends no comment and no reason."""
    runner = _sandbox((rest("PATCH", "repos/o/r/issues/5", "state=closed"), json_response({})))

    issue_commands.close_issue(5, run_fn=runner)

    assert not any(part.startswith("state_reason") for part in runner.calls[-1])


def test_reopen_fallback_reopens_with_a_comment() -> None:
    """Reopening posts the optional comment and sets the state to open."""
    runner = _sandbox(
        (rest("POST", "repos/o/r/issues/5/comments", "body=Back"), json_response({})),
        (rest("PATCH", "repos/o/r/issues/5", "state=open"), json_response({})),
    )

    assert issue_commands.reopen_issue(5, comment="Back", run_fn=runner) == 0


def test_develop_fallback_creates_an_unlinked_branch(capsys: pytest.CaptureFixture[str]) -> None:
    """The branch is created locally from the default branch, with a not-linked note."""
    runner = _sandbox(
        _issue_route(),
        (rest("GET", "repos/o/r"), json_response({"default_branch": "main"})),
        (has("fetch"), completed_process(0)),
        (has("checkout"), completed_process(0)),
    )

    assert issue_commands.develop_issue(5, run_fn=runner) == 0

    assert ["git", "fetch", "origin", "main"] in runner.calls
    assert runner.calls[-1] == [
        "git",
        "checkout",
        "-b",
        "5-broken-the-thing",
        "--no-track",
        "origin/main",
    ]
    assert "not linked to issue #5" in capsys.readouterr().err


def test_develop_fallback_honors_base_and_name() -> None:
    """An explicit base and branch name skip the lookups."""
    runner = _sandbox((has("fetch"), completed_process(0)), (has("checkout"), completed_process(0)))

    issue_commands.develop_issue(5, base="dev", name="my-branch", run_fn=runner)

    assert runner.calls[-1][-3:] == ["my-branch", "--no-track", "origin/dev"]


def test_develop_fallback_names_a_branch_after_an_untitled_issue() -> None:
    """A title with no usable characters leaves just the issue number."""
    runner = _sandbox(
        (rest("GET", "repos/o/r/issues/5"), json_response({"title": "!!!"})),
        (has("fetch"), completed_process(0)),
        (has("checkout"), completed_process(0)),
    )

    issue_commands.develop_issue(5, base="dev", run_fn=runner)

    assert runner.calls[-1][3] == "5"
