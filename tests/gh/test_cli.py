from __future__ import annotations

import argparse
import io
from pathlib import Path

import pytest

from scripts.gh import ci_status, cli, pr_review, pr_watch
from scripts.gh.ci_status import RunInfo
from scripts.gh.gh_runner import GhError

_SINCE = "2026-07-10T12:00:00Z"


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

    def watch_pr(pr: int | None, since: str | None, **kwargs: object) -> str:
        """Record the parsed watch arguments."""
        captured["pr"] = pr
        captured["since"] = since
        captured.update(kwargs)
        return "watch report"

    monkeypatch.setattr(pr_watch, "watch_pr", watch_pr)

    exit_code = cli.main(
        [
            "watch",
            "--pr",
            "9",
            "--since",
            _SINCE,
            "--interval",
            "2.5",
            "--max-polls",
            "3",
            "--checks-only",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "pr": 9,
        "since": _SINCE,
        "interval": 2.5,
        "max_polls": 3,
        "checks_only": True,
    }
    assert capsys.readouterr().out.strip() == "watch report"


def test_watch_subcommand_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """The watch command preserves omitted optional values for watch_pr."""
    captured: dict[str, object] = {}

    def watch_pr(pr: int | None, since: str | None, **kwargs: object) -> str:
        """Record the default watch arguments."""
        captured["pr"] = pr
        captured["since"] = since
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
        "since": None,
        "interval": 45.0,
        "max_polls": 40,
        "checks_only": False,
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
