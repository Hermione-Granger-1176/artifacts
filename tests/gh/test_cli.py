from __future__ import annotations

import argparse

import pytest

from scripts.gh import cli, pr_review
from scripts.gh.gh_runner import GhError


def test_copilot_review_subcommand_passes_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        pr_review, "request_copilot_review", lambda pr: captured.setdefault("pr", pr)
    )
    assert cli.main(["copilot-review", "--pr", "9"]) == 0
    assert captured["pr"] == 9


def test_copilot_review_subcommand_defaults_pr(monkeypatch: pytest.MonkeyPatch) -> None:
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
    def _raise_os_error(*_args: object, **_kwargs: object) -> str:
        raise OSError("no such file")

    monkeypatch.setattr("scripts.gh.cli.Path.read_text", _raise_os_error)
    args = argparse.Namespace(body=None, body_file="missing.txt")
    with pytest.raises(GhError):
        cli._body_text(args)
