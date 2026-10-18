from __future__ import annotations

import argparse
import io
from pathlib import Path
from types import ModuleType

import pytest

from scripts.gh import (
    ci_status,
    cli,
    gh_runner,
    issue_commands,
    issues,
    pr_commands,
    pr_review,
    pr_watch,
)
from scripts.gh.ci_status import RunInfo
from scripts.gh.gh_runner import GhError


def test_copilot_review_subcommand_passes_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test copilot review subcommand passes pr."""
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        pr_review, "request_copilot_review", lambda pr: captured.setdefault("pr", pr)
    )
    assert cli.main(["copilot-review", "--pr", "9"]) == 0
    assert captured["pr"] == 9


def test_copilot_review_subcommand_defaults_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test copilot review subcommand defaults pr."""
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        pr_review,
        "request_copilot_review",
        lambda pr=None: captured.setdefault("pr", pr),
    )
    assert cli.main(["copilot-review"]) == 0
    assert captured["pr"] is None


def test_watch_subcommand_passes_options_and_prints_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The watch command dispatches every CLI option and prints its report."""
    captured: dict[str, object] = {}

    def watch_pr(pr: int | None, **kwargs: object) -> str:
        """Record the parsed watch arguments."""
        captured["pr"] = pr
        captured.update(kwargs)
        return "watch report"

    monkeypatch.setattr(pr_watch, "watch_pr", watch_pr)

    exit_code = cli.main(
        [
            "watch",
            "--pr",
            "9",
            "--interval",
            "2.5",
            "--max-polls",
            "3",
            "--expected-checks",
            "17",
            "--checks-only",
            "--request-copilot",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "pr": 9,
        "interval": 2.5,
        "max_polls": 3,
        "expected_checks": 17,
        "checks_only": True,
        "request_copilot": True,
    }
    assert capsys.readouterr().out.strip() == "watch report"


def test_watch_subcommand_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """The watch command preserves omitted optional values for watch_pr."""
    captured: dict[str, object] = {}

    def watch_pr(pr: int | None, **kwargs: object) -> str:
        """Record the default watch arguments."""
        captured["pr"] = pr
        captured.update(kwargs)
        return "report"

    monkeypatch.setattr(
        pr_watch,
        "watch_pr",
        watch_pr,
    )

    assert cli.main(["watch"]) == 0
    assert captured == {
        "pr": None,
        "interval": 45.0,
        "max_polls": 40,
        "expected_checks": pr_watch.DEFAULT_EXPECTED_CHECKS,
        "checks_only": False,
        "request_copilot": False,
    }


def test_edit_pr_subcommand_passes_title_and_body(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The edit-pr command forwards the PR number, title, and body."""
    captured: dict[str, object] = {}

    def edit_pr(pr: int | None = None, **kwargs: object) -> None:
        """Record the parsed edit-pr arguments."""
        captured["pr"] = pr
        captured.update(kwargs)

    monkeypatch.setattr(pr_review, "edit_pr", edit_pr)

    assert cli.main(["edit-pr", "--pr", "9", "--title", "New", "--body", "Body"]) == 0
    assert captured == {"pr": 9, "title": "New", "body": "Body", "body_file": None}
    assert capsys.readouterr().out.strip() == "Edited PR"


def test_edit_pr_subcommand_forwards_body_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """A --body-file is forwarded to edit_pr so gh reads it, not the CLI."""
    captured: dict[str, object] = {}
    monkeypatch.setattr(pr_review, "edit_pr", lambda _pr=None, **kwargs: captured.update(kwargs))

    assert cli.main(["edit-pr", "--body-file", "-"]) == 0
    assert captured == {"title": None, "body": None, "body_file": "-"}


def test_edit_pr_subcommand_title_only_omits_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Editing only the title passes no body through."""
    captured: dict[str, object] = {}
    monkeypatch.setattr(pr_review, "edit_pr", lambda _pr=None, **kwargs: captured.update(kwargs))

    assert cli.main(["edit-pr", "--title", "Only title"]) == 0
    assert captured == {"title": "Only title", "body": None, "body_file": None}


def test_comment_subcommand_posts_a_pr_comment(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The comment command forwards the PR number and body."""
    captured: dict[str, object] = {}

    def comment_on_pr(pr: int | None, body: str) -> None:
        """Record the parsed comment arguments."""
        captured.update(pr=pr, body=body)

    monkeypatch.setattr(pr_review, "comment_on_pr", comment_on_pr)

    assert cli.main(["comment", "--pr", "9", "--body", "Looks good"]) == 0
    assert captured == {"pr": 9, "body": "Looks good"}
    assert capsys.readouterr().out.strip() == "Commented on the PR"


def test_issue_summary_subcommand_prints_report(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The issue-summary command forwards the issue number and prints the report."""
    captured: dict[str, object] = {}

    def issue_summary(issue: int) -> str:
        """Record the parsed issue number."""
        captured["issue"] = issue
        return "issue report"

    monkeypatch.setattr(issues, "issue_summary", issue_summary)

    assert cli.main(["issue-summary", "--issue", "42"]) == 0
    assert captured["issue"] == 42
    assert "issue report" in capsys.readouterr().out


def test_issue_summary_subcommand_requires_issue() -> None:
    """Omitting --issue is a usage error."""
    with pytest.raises(SystemExit):
        cli.main(["issue-summary"])


def test_latest_run_id_subcommand_prints_run_id(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The latest-run-id command prints the newest run id for the branch."""
    monkeypatch.setattr(
        ci_status,
        "latest_run",
        lambda: RunInfo(
            run_id=4242,
            status="completed",
            conclusion="success",
            workflow="CI",
            branch="feature",
            url="https://example/run",
        ),
    )

    assert cli.main(["latest-run-id"]) == 0
    assert capsys.readouterr().out.strip() == "4242"


def test_body_text_missing_file_raises_gh_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test body text missing file raises gh error."""

    def _raise_os_error(*_args: object, **_kwargs: object) -> str:
        raise OSError("no such file")

    monkeypatch.setattr("scripts.gh.cli.Path.read_text", _raise_os_error)
    args = argparse.Namespace(body=None, body_file="missing.txt")
    with pytest.raises(GhError, match=r"Could not read --body-file missing.txt"):
        cli._body_text(args)


def test_body_text_dash_body_file_reads_stdin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A --body-file of ``-`` reads the body from stdin instead of a file."""
    monkeypatch.setattr("sys.stdin", io.StringIO("Fixed in abc123\n\n- detail line\n"))

    text = cli._body_text(argparse.Namespace(body=None, body_file="-"))

    assert text == "Fixed in abc123\n\n- detail line\n"


def test_body_text_empty_body_file_still_reads_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit empty --body-file path is handled as a file path, not a body."""
    seen: list[str] = []

    def _read_text(path: Path, *, encoding: str) -> str:
        seen.append(str(path))
        assert encoding == "utf-8"
        return "body"

    monkeypatch.setattr("scripts.gh.cli.Path.read_text", _read_text)

    text = cli._body_text(argparse.Namespace(body=None, body_file=""))

    assert text == "body"
    assert seen == ["."]


def test_check_commit_message_accepts_clean_message(
    tmp_path: Path,
) -> None:
    """A clean commit message file passes validation with exit code 0."""
    message_file = tmp_path / "msg.txt"
    message_file.write_text("Add a feature\n\n- detail\n", encoding="utf-8")

    assert cli.main(["check-commit-message", "--message-file", str(message_file)]) == 0


def test_check_commit_message_rejects_leaked_shell(tmp_path: Path) -> None:
    """A message with leaked shell text raises GhError."""
    message_file = tmp_path / "msg.txt"
    message_file.write_text("Subject\n\nEOF && make push 2>&1 | tail -3\n", encoding="utf-8")

    with pytest.raises(GhError, match="leaked shell text"):
        cli.main(["check-commit-message", "--message-file", str(message_file)])


def test_check_commit_message_reads_stdin(monkeypatch: pytest.MonkeyPatch) -> None:
    """A --message-file of ``-`` reads the message from stdin."""
    monkeypatch.setattr("sys.stdin", io.StringIO("Clean subject\n"))

    assert cli.main(["check-commit-message", "--message-file", "-"]) == 0


def test_check_commit_message_missing_file_raises(tmp_path: Path) -> None:
    """A missing message file surfaces a GhError."""
    missing = tmp_path / "nope.txt"

    with pytest.raises(GhError, match="Could not read --message-file"):
        cli.main(["check-commit-message", "--message-file", str(missing)])


def _spy(
    monkeypatch: pytest.MonkeyPatch, module: ModuleType, name: str, result: int = 0
) -> list[tuple[tuple[object, ...], dict[str, object]]]:
    """Replace ``module.name`` with a recorder that returns ``result``."""
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def record(*args: object, **kwargs: object) -> int:
        """Record the call."""
        calls.append((args, kwargs))
        return result

    monkeypatch.setattr(module, name, record)
    return calls


@pytest.mark.parametrize(
    ("argv", "function", "args", "kwargs"),
    [
        (["pr-list"], "list_prs", (), {}),
        (["pr-status"], "pr_checks_status", (None,), {}),
        (["pr-status", "--pr", "7"], "pr_checks_status", (7,), {}),
        (
            ["pr-checks", "--pr", "7", "--interval", "2", "--max-polls", "3"],
            "watch_pr_checks",
            (7,),
            {"interval": 2.0, "max_polls": 3},
        ),
        (
            ["pr-checks"],
            "watch_pr_checks",
            (None,),
            {
                "interval": pr_commands.CHECKS_INTERVAL_SECONDS,
                "max_polls": pr_commands.CHECKS_MAX_POLLS,
            },
        ),
        (["pr-diff"], "show_diff", (None,), {}),
        (["pr-checkout", "--pr", "7"], "checkout_pr", (7,), {}),
        (["pr-comments", "--pr", "7"], "view_comments", (7,), {}),
        (["pr-merge"], "merge_pr", (None,), {"admin": False}),
        (["pr-merge", "--pr", "7", "--admin"], "merge_pr", (7,), {"admin": True}),
        (["pr-reviewers", "--users", "a,b"], "add_reviewers", ("a,b", None), {}),
        (["pr-label", "--labels", "bug", "--pr", "7"], "add_labels", ("bug", 7), {}),
        (["pr-close", "--pr", "7"], "close_pr", (7,), {}),
        (["pr-create", "--base", "dev"], "create_pr", (), {"base": "dev"}),
        (
            ["pr-create", "--title", "T", "--body", "B"],
            "create_pr",
            (),
            {"title": "T", "base": None, "body": "B"},
        ),
        (
            ["pr-create", "--title", "T"],
            "create_pr",
            (),
            {"title": "T", "base": None, "body": ""},
        ),
    ],
)
def test_pr_subcommands_dispatch_to_pr_commands(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    function: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    """Each pr-* subcommand forwards its parsed options and returns the exit code."""
    calls = _spy(monkeypatch, pr_commands, function, result=3)

    assert cli.main(argv) == 3

    assert calls == [(args, kwargs)]


def test_pr_create_rejects_a_body_without_a_title() -> None:
    """A body only makes sense with a title; otherwise the text is filled from commits."""
    with pytest.raises(GhError, match="needs a --title"):
        cli.main(["pr-create", "--body", "B"])


def test_pr_create_reads_the_body_from_standard_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """--body-file - supplies the body text."""
    calls = _spy(monkeypatch, pr_commands, "create_pr")
    monkeypatch.setattr("sys.stdin", io.StringIO("from stdin"))

    assert cli.main(["pr-create", "--title", "T", "--body-file", "-"]) == 0

    assert calls == [((), {"title": "T", "base": None, "body": "from stdin"})]


@pytest.mark.parametrize(
    ("argv", "function", "args", "kwargs"),
    [
        (
            ["issue-list"],
            "list_issues",
            (),
            {
                "state": None,
                "labels": None,
                "assignees": None,
                "author": None,
                "limit": None,
                "search": None,
            },
        ),
        (
            [
                "issue-list",
                "--state",
                "all",
                "--label",
                "bug",
                "--assignee",
                "a",
                "--assignee",
                "@me",
                "--author",
                "o",
                "--limit",
                "5",
                "--search",
                "x",
            ],
            "list_issues",
            (),
            {
                "state": "all",
                "labels": "bug",
                "assignees": ["a", "@me"],
                "author": "o",
                "limit": 5,
                "search": "x",
            },
        ),
        (["issue-view", "--issue", "5"], "view_issue", (5,), {}),
        (
            ["issue-create", "--title", "T", "--labels", "bug", "--assignee", "@me", "--body", "B"],
            "create_issue",
            ("T", "B"),
            {"labels": "bug", "assignee": "@me"},
        ),
        (["issue-comment", "--issue", "5", "--body", "B"], "comment_issue", (5, "B"), {}),
        (
            ["issue-edit", "--issue", "5", "--title", "T", "--body", "B"],
            "edit_issue",
            (5,),
            {"title": "T", "body": "B"},
        ),
        (
            ["issue-edit", "--issue", "5", "--title", "T"],
            "edit_issue",
            (5,),
            {"title": "T", "body": None},
        ),
        (["issue-label", "--issue", "5", "--labels", "bug"], "label_issue", (5, "bug"), {}),
        (
            ["issue-unlabel", "--issue", "5", "--labels", "bug"],
            "label_issue",
            (5, "bug"),
            {"remove": True},
        ),
        (
            ["issue-assign", "--issue", "5", "--users", "a", "--mine"],
            "assign_issue",
            (5,),
            {"users": "a", "mine": True},
        ),
        (
            ["issue-unassign", "--issue", "5", "--users", "a"],
            "assign_issue",
            (5,),
            {"users": "a", "mine": False, "remove": True},
        ),
        (
            ["issue-close", "--issue", "5", "--reason", "completed", "--comment", "Done"],
            "close_issue",
            (5,),
            {"reason": "completed", "comment": "Done"},
        ),
        (["issue-reopen", "--issue", "5"], "reopen_issue", (5,), {"comment": None}),
        (
            ["issue-develop", "--issue", "5", "--base", "dev", "--name", "n"],
            "develop_issue",
            (5,),
            {"base": "dev", "name": "n"},
        ),
    ],
)
def test_issue_subcommands_dispatch_to_issue_commands(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    function: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    """Each issue-* subcommand forwards its parsed options and returns the exit code."""
    calls = _spy(monkeypatch, issue_commands, function, result=2)

    assert cli.main(argv) == 2

    assert calls == [(args, kwargs)]


def test_current_pr_subcommand_prints_the_number(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """current-pr prints just the number, for the Makefile's PR_NUM."""
    monkeypatch.setattr(gh_runner, "current_pr_number", lambda: 42)

    assert cli.main(["current-pr"]) == 0
    assert capsys.readouterr().out == "42\n"
