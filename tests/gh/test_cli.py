from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from scripts.gh import cli, pr_review
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
