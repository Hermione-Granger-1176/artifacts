from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from scripts.gh import gh_runner, pr_commands
from scripts.gh.gh_runner import GhError
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

PULL = {
    "number": 7,
    "title": "Add thing",
    "state": "open",
    "html_url": "https://example/pull/7",
    "body": "Body text",
    "head": {"ref": "feature", "sha": "abc", "repo": {"full_name": "o/r"}},
    "base": {"repo": {"default_branch": "main"}},
    "mergeable_state": "clean",
}


class Recorder:
    """A runner that records every command with its options and returns one result."""

    def __init__(self, result: subprocess.CompletedProcess[str] | None = None) -> None:
        self.result = result or completed_process(0)
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Record the call and return the canned result."""
        self.calls.append((list(cmd), dict(kwargs)))
        return self.result


def _sandbox(*routes: Route) -> FakeGh:
    """Build a runner for a sandbox that blocks GraphQL, with extra routes."""
    return FakeGh([*sandbox_routes(), *routes])


def _pushed(cmd: list[str]) -> bool:
    """Match the ``git rev-parse HEAD`` call that reads the local head commit."""
    return cmd[-2:] == ["rev-parse", "HEAD"]


def _branch_lookup(cmd: list[str]) -> bool:
    """Match the REST read of a branch on GitHub."""
    return cmd[:4] == ["gh", "api", "--method", "GET"] and cmd[4].startswith("repos/o/r/branches/")


def _create_sandbox(*routes: Route, remote: Any = None) -> FakeGh:
    """Build a sandbox runner where the branch on GitHub matches local HEAD ``abc``."""
    branch = json_response({"commit": {"sha": "abc"}}) if remote is None else remote
    return _sandbox((_pushed, completed_process(0, "abc\n")), (_branch_lookup, branch), *routes)


def _pr_routes() -> list[Route]:
    """Routes that resolve the current branch ``feature`` to open PR 7."""
    return [
        (has("rev-parse"), completed_process(0, "feature\n")),
        (rest("GET", "repos/o/r/pulls", "head=o:feature"), json_response([{"number": 7}])),
    ]


def _pull_route(pull: dict[str, Any] | None = None) -> Route:
    """Route serving PR 7's REST object."""
    return (rest("GET", "repos/o/r/pulls/7"), json_response(pull or PULL))


def _checks_routes(runs: list[dict[str, Any]], statuses: list[dict[str, Any]]) -> list[Route]:
    """Routes serving the checks and statuses on commit ``abc``."""
    return [
        _pull_route(),
        (rest("GET", "repos/o/r/commits/abc/check-runs"), json_response({"check_runs": runs})),
        (rest("GET", "repos/o/r/commits/abc/status"), json_response({"statuses": statuses})),
    ]


def _run(
    name: str, conclusion: str | None = "success", status: str = "completed"
) -> dict[str, Any]:
    """Build one REST check run."""
    return {"name": name, "status": status, "conclusion": conclusion, "details_url": f"u/{name}"}


# --- primary path: the exact gh command the Makefile used to run -----------------------------


@pytest.mark.parametrize(
    ("call", "expected"),
    [
        (lambda r: pr_commands.list_prs(run_fn=r), ["gh", "pr", "list"]),
        (lambda r: pr_commands.pr_checks_status(run_fn=r), ["gh", "pr", "checks"]),
        (lambda r: pr_commands.pr_checks_status(7, run_fn=r), ["gh", "pr", "checks", "7"]),
        (
            lambda r: pr_commands.watch_pr_checks(7, run_fn=r),
            ["gh", "pr", "checks", "7", "--watch", "--fail-fast"],
        ),
        (lambda r: pr_commands.show_diff(run_fn=r), ["gh", "pr", "diff"]),
        (lambda r: pr_commands.checkout_pr(7, run_fn=r), ["gh", "pr", "checkout", "7"]),
        (lambda r: pr_commands.view_comments(7, run_fn=r), ["gh", "pr", "view", "7", "--comments"]),
        (
            lambda r: pr_commands.merge_pr(run_fn=r),
            ["gh", "pr", "merge", "--squash", "--delete-branch"],
        ),
        (
            lambda r: pr_commands.merge_pr(7, admin=True, run_fn=r),
            ["gh", "pr", "merge", "7", "--squash", "--delete-branch", "--admin"],
        ),
        (
            lambda r: pr_commands.add_reviewers("a,b", 7, run_fn=r),
            ["gh", "pr", "edit", "7", "--add-reviewer", "a,b"],
        ),
        (
            lambda r: pr_commands.add_labels("bug", run_fn=r),
            ["gh", "pr", "edit", "--add-label", "bug"],
        ),
        (
            lambda r: pr_commands.close_pr(7, run_fn=r),
            ["gh", "pr", "close", "7", "--delete-branch"],
        ),
        (lambda r: pr_commands.create_pr(run_fn=r), ["gh", "pr", "create", "--fill"]),
        (
            lambda r: pr_commands.create_pr(base="dev", run_fn=r),
            ["gh", "pr", "create", "--fill", "--base", "dev"],
        ),
    ],
)
def test_gh_is_the_primary_path(call: Callable[[Recorder], int], expected: list[str]) -> None:
    """On a machine with GraphQL, each command runs the same gh invocation as before."""
    recorder = Recorder()

    assert call(recorder) == 0

    assert [cmd for cmd, _ in recorder.calls] == [expected]


def test_primary_path_returns_the_gh_exit_code() -> None:
    """A failing check keeps its exit code so the target still fails."""
    assert pr_commands.pr_checks_status(run_fn=Recorder(completed_process(1))) == 1


def test_create_with_a_title_pipes_the_body_to_gh() -> None:
    """An explicit title sends the body on standard input via --body-file -."""
    recorder = Recorder()

    pr_commands.create_pr(title="T", base="dev", body="Body", run_fn=recorder)

    cmd, options = recorder.calls[0]
    assert cmd == ["gh", "pr", "create", "--base", "dev", "--title", "T", "--body-file", "-"]
    assert options["input"] == "Body"


# --- REST fallback --------------------------------------------------------------------------


def _compare(endpoint: str, *messages: str) -> Route:
    """Route serving a compare response whose commits carry ``messages``, oldest first."""
    commits = [{"commit": {"message": message}} for message in messages]
    return (rest("GET", endpoint), json_response({"commits": commits}))


def test_create_fallback_fills_from_a_single_commit() -> None:
    """One commit supplies the title and body, like gh pr create --fill."""
    runner = _create_sandbox(
        (rest("GET", "repos/o/r"), json_response({"default_branch": "main"})),
        (has("rev-parse"), completed_process(0, "feature\n")),
        _compare("repos/o/r/compare/main...feature", "Fix thing\n\nLonger body\n"),
        (
            rest("POST", "repos/o/r/pulls", "title=Fix thing", "head=feature", "base=main"),
            json_response({"html_url": "https://example/pull/9"}),
        ),
    )

    assert pr_commands.create_pr(run_fn=runner) == 0

    assert "body=Longer body" in runner.calls[-1]
    assert not any("log" in call for call in runner.calls)


def test_create_fallback_summarizes_several_commits(capsys: pytest.CaptureFixture[str]) -> None:
    """Several commits give the branch name as title and the subjects as a list."""
    runner = _create_sandbox(
        (has("rev-parse"), completed_process(0, "fix-the_thing\n")),
        _compare("repos/o/r/compare/dev...fix-the_thing", "One", "Two\n\nbody"),
        (
            rest("POST", "repos/o/r/pulls", "title=Fix the thing", "body=- One\n- Two", "base=dev"),
            json_response({"html_url": "https://example/pull/9"}),
        ),
    )

    pr_commands.create_pr(base="dev", run_fn=runner)

    assert capsys.readouterr().out.strip() == "https://example/pull/9"


def test_create_fallback_compares_a_fork_head_against_the_selected_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With GH_REPO on upstream, the text comes from upstream's base and the fork's branch."""
    monkeypatch.setenv("GH_REPO", "org/project")
    runner = FakeGh(
        [
            *sandbox_routes("alice/project"),
            (_pushed, completed_process(0, "abc\n")),
            (has("rev-parse"), completed_process(0, "fix#1\n")),
            (
                rest("GET", "repos/alice/project/branches/fix%231"),
                json_response({"commit": {"sha": "abc"}}),
            ),
            _compare("repos/org/project/compare/main...alice:fix%231", "Subject only"),
            (
                rest("POST", "repos/org/project/pulls", "title=Subject only", "body="),
                json_response({"html_url": "https://example/pull/9"}),
            ),
        ]
    )

    assert pr_commands.create_pr(base="main", run_fn=runner) == 0


def test_create_fallback_rejects_a_branch_with_no_commits() -> None:
    """Nothing ahead of the base cannot be filled."""
    runner = _create_sandbox(
        (has("rev-parse"), completed_process(0, "feature\n")),
        (rest("GET", "repos/o/r/compare/dev...feature"), json_response({"commits": []})),
    )

    with pytest.raises(GhError, match="No commits on feature ahead of dev"):
        pr_commands.create_pr(base="dev", run_fn=runner)


@pytest.mark.parametrize(
    ("remote", "message"),
    [
        (completed_process(1, "", "Branch not found (HTTP 404)"), "is not on GitHub"),
        (json_response({"commit": {"sha": "old"}}), "does not match your local HEAD"),
    ],
)
def test_create_fallback_requires_the_pushed_head(
    remote: subprocess.CompletedProcess[str], message: str
) -> None:
    """An unpushed or outdated branch on GitHub stops the PR before it opens."""
    runner = _create_sandbox((has("rev-parse"), completed_process(0, "fix#1\n")), remote=remote)

    with pytest.raises(GhError, match=message):
        pr_commands.create_pr(title="T", base="dev", run_fn=runner)

    assert any(call[4:5] == ["repos/o/r/branches/fix%231"] for call in runner.calls)
    assert not any("POST" in call for call in runner.calls)


def test_create_fallback_refuses_a_detached_head() -> None:
    """A detached HEAD has no branch to open a PR from, so no push advice is given."""
    runner = _create_sandbox((has("rev-parse"), completed_process(0, "HEAD\n")))

    with pytest.raises(GhError, match="HEAD is detached"):
        pr_commands.create_pr(title="T", base="dev", run_fn=runner)


def test_create_fallback_keeps_the_real_error_of_a_failed_branch_lookup() -> None:
    """Only a 404 means unpushed. A permission error surfaces as itself."""
    runner = _create_sandbox(
        (has("rev-parse"), completed_process(0, "feature\n")),
        remote=completed_process(1, "", "Resource not accessible by integration (HTTP 403)"),
    )

    with pytest.raises(GhError, match="was refused") as caught:
        pr_commands.create_pr(title="T", base="dev", run_fn=runner)

    assert "make push" not in str(caught.value)


def test_create_fallback_with_a_title_uses_the_given_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An explicit title and body are sent as given, and a non-object reply is tolerated."""
    runner = _create_sandbox(
        (has("rev-parse"), completed_process(0, "feature\n")),
        (rest("POST", "repos/o/r/pulls", "title=T", "body=B", "base=dev"), json_response([])),
    )

    pr_commands.create_pr(title="T", base="dev", body="B", run_fn=runner)

    assert capsys.readouterr().out.strip() == "Created pull request"


def test_list_fallback_prints_open_pull_requests(capsys: pytest.CaptureFixture[str]) -> None:
    """Open PRs print as number, title, branch, and state."""
    runner = _sandbox(
        (
            rest("GET", "repos/o/r/pulls", "state=open"),
            json_response(
                [
                    {"number": 7, "title": "A", "head": {"ref": "a"}},
                    {"number": 8, "title": "B", "head": None, "draft": True},
                ]
            ),
        )
    )

    assert pr_commands.list_prs(run_fn=runner) == 0

    assert capsys.readouterr().out.splitlines() == ["7\tA\ta\tOPEN", "8\tB\t\tDRAFT"]


def test_list_fallback_reports_no_open_pull_requests(capsys: pytest.CaptureFixture[str]) -> None:
    """An empty list says so on standard error."""
    runner = _sandbox((rest("GET", "repos/o/r/pulls"), json_response([])))

    pr_commands.list_prs(run_fn=runner)

    assert "No open pull requests in o/r" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("runs", "statuses", "code"),
    [
        ([_run("lint"), _run("t", "neutral"), _run("s", "skipped")], [], 0),
        ([_run("lint")], [{"context": "ci", "state": "success"}], 0),
        ([_run("lint"), _run("t", "failure")], [], 1),
        ([_run("t", "cancelled")], [], 1),
        ([_run("lint"), _run("t", None, "in_progress")], [], 8),
        ([_run("lint")], [{"context": "ci", "state": "pending"}], 8),
        ([_run("lint")], [{"context": "ci", "state": "expected"}], 8),
        ([_run("lint")], [{"context": "ci", "state": "failure"}], 1),
    ],
)
def test_status_fallback_uses_gh_checks_exit_codes(
    runs: list[dict[str, Any]], statuses: list[dict[str, Any]], code: int
) -> None:
    """Exit 0 when all pass, 1 when any fail or cancel, 8 while pending."""
    runner = _sandbox(*_checks_routes(runs, statuses))

    assert pr_commands.pr_checks_status(7, run_fn=runner) == code


def test_status_fallback_prints_a_table_with_elapsed_time(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Rows are tab separated: name, bucket, elapsed, URL."""
    timed = {
        **_run("lint"),
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:01:05Z",
    }
    quick = {
        **_run("fast"),
        "started_at": "2026-01-01T00:00:00Z",
        "completed_at": "2026-01-01T00:00:09Z",
    }
    runner = _sandbox(*_checks_routes([timed, quick], [{"context": "ci", "state": "success"}]))

    pr_commands.pr_checks_status(7, run_fn=runner)

    assert capsys.readouterr().out.splitlines() == [
        "lint\tpass\t1m5s\tu/lint",
        "fast\tpass\t9s\tu/fast",
        "ci\tpass\t\t",
    ]


def test_status_fallback_reports_a_pr_with_no_checks(capsys: pytest.CaptureFixture[str]) -> None:
    """No checks is reported on standard error with a failing exit code."""
    runner = _sandbox(*_pr_routes(), *_checks_routes([], []))

    assert pr_commands.pr_checks_status(run_fn=runner) == 1
    assert "no checks reported on PR #7" in capsys.readouterr().err


def test_watch_fallback_returns_when_checks_finish() -> None:
    """A finished set of checks ends the watch with their exit code."""
    runner = _sandbox(*_checks_routes([_run("lint")], []))
    sleeps: list[float] = []

    assert pr_commands.watch_pr_checks(7, run_fn=runner, sleep_fn=sleeps.append) == 0
    assert sleeps == []


def test_watch_fallback_polls_until_pending_checks_finish(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Pending or not-yet-registered checks keep the watch polling at the interval."""
    states = iter([[], [_run("lint", None, "queued")], [_run("lint")]])
    sleeps: list[float] = []

    def runner(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Serve a different check set on each poll."""
        if cmd[:2] in (["gh", "repo"], ["gh", "pr"]):
            return graphql_blocked()
        if cmd[0] == "git":
            return completed_process(0, "https://github.com/o/r.git\n")
        if cmd[4] == "repos/o/r/pulls/7":
            return json_response(PULL)
        if cmd[4].endswith("check-runs"):
            return json_response({"check_runs": next(states)})
        return json_response({"statuses": []})

    code = pr_commands.watch_pr_checks(7, interval=3, run_fn=runner, sleep_fn=sleeps.append)

    assert code == 0
    assert sleeps == [3, 3]
    assert "Waiting on 1 pending check(s) on PR #7" in capsys.readouterr().err


def test_watch_fallback_fails_fast_on_a_failed_check() -> None:
    """A failure ends the watch even while other checks are still running."""
    runner = _sandbox(*_checks_routes([_run("t", "failure"), _run("u", None, "queued")], []))

    assert pr_commands.watch_pr_checks(7, run_fn=runner, sleep_fn=lambda _s: None) == 1


def test_watch_fallback_gives_up_after_max_polls() -> None:
    """A check that never finishes ends in an error instead of waiting forever."""
    runner = _sandbox(*_checks_routes([_run("t", None, "queued")], []))
    sleeps: list[float] = []

    with pytest.raises(GhError, match="did not finish after 2 polls"):
        pr_commands.watch_pr_checks(
            7, max_polls=2, interval=1, run_fn=runner, sleep_fn=sleeps.append
        )

    assert sleeps == [1]


def test_watch_fallback_sleeps_with_the_real_clock_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without an injected sleeper the watch waits with time.sleep."""
    waits: list[float] = []
    monkeypatch.setattr(pr_commands.time, "sleep", waits.append)
    runner = _sandbox(*_checks_routes([_run("t", None, "queued")], []))

    with pytest.raises(GhError):
        pr_commands.watch_pr_checks(7, max_polls=2, interval=4, run_fn=runner)

    assert waits == [4]


def test_elapsed_is_blank_when_a_check_has_not_finished() -> None:
    """Missing or unparseable timestamps give an empty elapsed time."""
    assert pr_commands._elapsed(None, None) == ""
    assert pr_commands._elapsed("2026-01-01T00:00:00Z", "later") == ""


def test_diff_fallback_requests_the_diff_media_type(capsys: pytest.CaptureFixture[str]) -> None:
    """The raw diff is printed using the diff Accept header."""
    runner = _sandbox(
        (
            rest("GET", "repos/o/r/pulls/7", "Accept: application/vnd.github.diff"),
            completed_process(0, "diff --git a/x b/x\n"),
        )
    )

    assert pr_commands.show_diff(7, run_fn=runner) == 0

    assert capsys.readouterr().out == "diff --git a/x b/x\n"


def test_checkout_fallback_refuses_when_gh_repo_is_not_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PR numbers are per repository, so origin's pull/<n>/head would be a different PR."""
    monkeypatch.setenv("GH_REPO", "org/project")
    runner = FakeGh(sandbox_routes("alice/project"))

    with pytest.raises(GhError, match="Cannot check out PR #7: GH_REPO selects org/project"):
        pr_commands.checkout_pr(7, run_fn=runner)

    assert not any("fetch" in call for call in runner.calls)


def test_create_fallback_checks_a_fork_branch_and_qualifies_its_head(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With GH_REPO on upstream, the push check reads the fork and the head names its owner."""
    monkeypatch.setenv("GH_REPO", "org/project")
    runner = FakeGh(
        [
            *sandbox_routes("alice/project"),
            (_pushed, completed_process(0, "abc\n")),
            (has("rev-parse"), completed_process(0, "feature\n")),
            (
                rest("GET", "repos/alice/project/branches/feature"),
                json_response({"commit": {"sha": "abc"}}),
            ),
            (
                rest("POST", "repos/org/project/pulls", "head=alice:feature", "base=main"),
                json_response({"html_url": "https://example/pull/9"}),
            ),
        ]
    )

    assert pr_commands.create_pr(title="T", base="main", run_fn=runner) == 0


def test_checkout_fallback_prefixes_a_fork_branch_and_records_its_pr() -> None:
    """A fork's main checks out as alice/main, so local main is never fast-forwarded."""
    head = {"ref": "main", "sha": "abc", "repo": {"full_name": "alice/r"}}
    runner = _sandbox(
        _pull_route({**PULL, "head": head}),
        (has("--verify"), completed_process(1, "", "")),
        (has("fetch"), completed_process(0)),
        (has("checkout"), completed_process(0)),
    )

    assert pr_commands.checkout_pr(7, run_fn=runner) == 0

    assert ["git", "fetch", "origin", "pull/7/head:alice/main"] in runner.calls
    assert ["git", "checkout", "main"] not in runner.calls
    assert runner.calls[-1] == ["git", "config", "branch.alice/main.gh-pr-number", "7"]


def test_checkout_fallback_creates_a_new_local_branch() -> None:
    """A branch that does not exist locally is fetched from the PR ref and checked out."""
    runner = _sandbox(
        _pull_route(),
        (has("--verify"), completed_process(1, "", "")),
        (has("fetch"), completed_process(0)),
        (has("checkout"), completed_process(0)),
    )

    assert pr_commands.checkout_pr(7, run_fn=runner) == 0

    assert ["git", "fetch", "origin", "pull/7/head:feature"] in runner.calls
    assert runner.calls[-2] == ["git", "checkout", "feature"]
    assert runner.calls[-1] == ["git", "config", "branch.feature.gh-pr-number", "7"]


def test_checkout_fallback_fast_forwards_an_existing_branch() -> None:
    """An existing local branch is updated with a fast-forward merge."""
    runner = _sandbox(
        _pull_route(),
        (has("--verify"), completed_process(0, "abc\n")),
        (has("fetch"), completed_process(0)),
        (has("checkout"), completed_process(0)),
        (has("merge"), completed_process(0)),
    )

    pr_commands.checkout_pr(7, run_fn=runner)

    assert ["git", "fetch", "origin", "pull/7/head"] in runner.calls
    assert runner.calls[-2] == ["git", "merge", "--ff-only", "FETCH_HEAD"]


def test_checkout_fallback_requires_a_head_branch() -> None:
    """A PR object without a head branch cannot be checked out."""
    runner = _sandbox(_pull_route({"head": None}))

    with pytest.raises(GhError, match="no head branch"):
        pr_commands.checkout_pr(7, run_fn=runner)


def test_view_fallback_shows_body_comments_and_review_summaries(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The fallback prints the PR, its comments, and non-empty review bodies."""
    runner = _sandbox(
        _pull_route(),
        (
            rest("GET", "repos/o/r/issues/7/comments"),
            json_response([{"user": {"login": "a"}, "body": "hi"}, {"user": None, "body": None}]),
        ),
        (
            rest("GET", "repos/o/r/pulls/7/reviews"),
            json_response(
                [
                    {"user": {"login": "copilot[bot]"}, "body": "Overview", "state": "COMMENTED"},
                    {"user": None, "body": "", "state": "APPROVED"},
                    {"user": None, "body": "Anon", "state": "APPROVED"},
                ]
            ),
        ),
    )

    assert pr_commands.view_comments(7, run_fn=runner) == 0

    out = capsys.readouterr().out
    assert "Add thing #7" in out
    assert "state: OPEN" in out
    assert "Body text" in out
    assert "comment by @a\nhi" in out
    assert "comment by @unknown" in out
    assert "review by @copilot [COMMENTED]\nOverview" in out
    assert "review by @unknown [APPROVED]\nAnon" in out


def test_view_fallback_omits_an_empty_body(capsys: pytest.CaptureFixture[str]) -> None:
    """A PR without a description prints no blank body section."""
    runner = _sandbox(
        _pull_route({**PULL, "body": None}),
        (rest("GET", "repos/o/r/issues/7/comments"), json_response([])),
        (rest("GET", "repos/o/r/pulls/7/reviews"), json_response([])),
    )

    pr_commands.view_comments(7, run_fn=runner)

    assert "Body text" not in capsys.readouterr().out


def test_merge_fallback_squashes_and_deletes_the_branch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An admin merge squashes past a blocked PR and then deletes the same-repository branch."""
    runner = _sandbox(
        _pull_route({**PULL, "mergeable_state": "blocked"}),
        (
            rest("PUT", "repos/o/r/pulls/7/merge", "merge_method=squash", "sha=abc"),
            json_response({}),
        ),
        (rest("DELETE", "repos/o/r/git/refs/heads/feature"), completed_process(0, "")),
    )

    assert pr_commands.merge_pr(7, admin=True, run_fn=runner) == 0

    assert "Squashed and merged pull request #7" in capsys.readouterr().out
    assert runner.calls[-1][4] == "repos/o/r/git/refs/heads/feature"


@pytest.mark.parametrize(
    "head",
    [
        {"ref": "feature", "sha": "abc", "repo": {"full_name": "fork/r"}},
        {"ref": "main", "sha": "abc", "repo": {"full_name": "o/r"}},
        {"sha": "abc", "repo": {"full_name": "o/r"}},
    ],
)
def test_merge_fallback_keeps_forked_default_and_unnamed_branches(head: dict[str, Any]) -> None:
    """Only a non-default branch in this repository is deleted."""
    runner = _sandbox(
        _pull_route({**PULL, "head": head}),
        (rest("PUT", "repos/o/r/pulls/7/merge"), json_response({})),
    )

    assert pr_commands.merge_pr(7, run_fn=runner) == 0

    assert not any("DELETE" in call for call in runner.calls)


def test_merge_fallback_only_warns_when_the_branch_delete_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The merge already happened, so a failed branch delete is a warning."""
    runner = _sandbox(
        _pull_route(),
        (rest("PUT", "repos/o/r/pulls/7/merge"), json_response({})),
        (
            rest("DELETE", "repos/o/r/git/refs/heads/feature"),
            completed_process(1, "", "Reference does not exist (HTTP 422)"),
        ),
    )

    assert pr_commands.merge_pr(7, run_fn=runner) == 0

    assert "Could not delete branch feature" in capsys.readouterr().err


@pytest.mark.parametrize("state", ["blocked", "unknown", "dirty", None])
def test_merge_fallback_refuses_a_pr_branch_protection_blocks(state: str | None) -> None:
    """Without admin, a blocked or not yet computed merge state never reaches the merge call."""
    runner = _sandbox(_pull_route({**PULL, "mergeable_state": state}))

    with pytest.raises(GhError, match=f"not ready to merge \\(mergeable_state: {state}\\)"):
        pr_commands.merge_pr(7, run_fn=runner)

    assert not any("PUT" in call for call in runner.calls)


def test_merge_fallback_encodes_the_branch_it_deletes() -> None:
    """A branch name with URL syntax stays in the ref path instead of becoming a fragment."""
    head = {"ref": "fix/a#1", "sha": "abc", "repo": {"full_name": "o/r"}}
    runner = _sandbox(
        _pull_route({**PULL, "head": head}),
        (rest("PUT", "repos/o/r/pulls/7/merge"), json_response({})),
        (rest("DELETE", "repos/o/r/git/refs/heads/fix/a%231"), completed_process(0, "")),
    )

    assert pr_commands.merge_pr(7, run_fn=runner) == 0

    assert runner.calls[-1][4] == "repos/o/r/git/refs/heads/fix/a%231"


def test_merge_fallback_surfaces_a_rejected_merge() -> None:
    """A refused merge (for example a failing required check) is an error."""
    runner = _sandbox(
        _pull_route(),
        (
            rest("PUT", "repos/o/r/pulls/7/merge"),
            completed_process(1, "", "Not mergeable (HTTP 405)"),
        ),
    )

    with pytest.raises(GhError, match="Not mergeable"):
        pr_commands.merge_pr(7, run_fn=runner)


def test_reviewers_fallback_posts_a_reviewer_list(capsys: pytest.CaptureFixture[str]) -> None:
    """Comma-separated users become the reviewers array."""
    runner = _sandbox(
        (
            rest("POST", "repos/o/r/pulls/7/requested_reviewers", "reviewers[]=a", "reviewers[]=b"),
            json_response({}),
        )
    )

    assert pr_commands.add_reviewers("a, b", 7, run_fn=runner) == 0

    assert "Requested review on PR #7 from a, b" in capsys.readouterr().out


def test_reviewers_fallback_sends_teams_as_team_reviewers() -> None:
    """An org/team entry becomes a team slug, separate from user logins."""
    runner = _sandbox(
        (
            rest(
                "POST",
                "repos/o/r/pulls/7/requested_reviewers",
                "reviewers[]=a",
                "team_reviewers[]=core",
            ),
            json_response({}),
        )
    )

    pr_commands.add_reviewers("a,o/core", 7, run_fn=runner)

    assert "reviewers[]=o/core" not in runner.calls[-1]


def test_labels_fallback_posts_a_label_list(capsys: pytest.CaptureFixture[str]) -> None:
    """Comma-separated labels become the labels array on the issues endpoint."""
    runner = _sandbox(
        (
            rest("POST", "repos/o/r/issues/7/labels", "labels[]=bug", "labels[]=ci"),
            json_response([]),
        )
    )

    assert pr_commands.add_labels("bug,ci", 7, run_fn=runner) == 0

    assert "Added labels to PR #7: bug,ci" in capsys.readouterr().out


def test_close_fallback_closes_and_deletes_the_branch(capsys: pytest.CaptureFixture[str]) -> None:
    """Closing patches the state and removes the branch."""
    runner = _sandbox(
        _pull_route(),
        (rest("PATCH", "repos/o/r/pulls/7", "state=closed"), json_response({})),
        (rest("DELETE", "repos/o/r/git/refs/heads/feature"), completed_process(0, "")),
    )

    assert pr_commands.close_pr(7, run_fn=runner) == 0

    assert "Closed pull request #7" in capsys.readouterr().out


def test_fallback_defaults_to_the_current_pr() -> None:
    """Without a number the REST path targets the branch's open PR."""
    runner = _sandbox(
        *_pr_routes(),
        (rest("POST", "repos/o/r/issues/7/labels"), json_response([])),
    )

    pr_commands.add_labels("bug", run_fn=runner)


def test_fallback_errors_are_not_retried_against_graphql() -> None:
    """When the REST fallback fails, the error surfaces and GraphQL is not retried."""
    runner = _sandbox(
        (rest("GET", "repos/o/r/pulls"), completed_process(1, "", "Not Found (HTTP 404)"))
    )

    with pytest.raises(GhError, match="Not Found"):
        pr_commands.list_prs(run_fn=runner)

    assert sum(call[:2] == ["gh", "pr"] for call in runner.calls) == 1
    assert gh_runner.graphql_unavailable()
