from __future__ import annotations

import pytest

from scripts.gh import cli, pr_review


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
