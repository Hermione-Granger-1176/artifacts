from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from scripts.gh import cli, pr_review, pr_watch
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
