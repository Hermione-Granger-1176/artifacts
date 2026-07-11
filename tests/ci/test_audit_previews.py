from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

import scripts.ci.audit_previews as audit_previews
import scripts.ci.workflow_helpers as workflow_helpers

if TYPE_CHECKING:
    from collections.abc import Callable


def _fake_api(responses: dict[str, object]) -> Callable[..., object]:
    """Return a run_gh_api_json stand-in that replays keyed responses."""

    def fake(endpoint: str, *, description: str, required_permission: str | None = None) -> object:
        del description, required_permission
        return responses[endpoint]

    return fake


def test_list_preview_dir_names_returns_tree_directories() -> None:
    """List preview dir names returns tree directories."""
    responses = {
        "repos/o/r/git/trees/gh-pages": {
            "tree": [
                "skip-non-dict-entry",
                {"path": "pr-preview", "type": "tree", "sha": "deadbeef"},
                {"path": "index.html", "type": "blob"},
            ]
        },
        "repos/o/r/git/trees/deadbeef": {
            "tree": [
                {"path": "pr-12", "type": "tree"},
                {"path": "pr-7", "type": "tree"},
                {"path": "README", "type": "blob"},
                {"path": 123, "type": "tree"},
            ]
        },
    }

    names = audit_previews.list_preview_dir_names(
        "o/r", "gh-pages", run_gh_api_json_fn=_fake_api(responses)
    )
    assert names == ["pr-12", "pr-7"]


def test_list_preview_dir_names_returns_empty_without_preview_root() -> None:
    """List preview dir names returns empty without preview root."""
    responses = {
        "repos/o/r/git/trees/gh-pages": {
            "tree": [
                {"path": "index.html", "type": "blob"},
                {"path": "pr-preview", "type": "blob"},
            ]
        },
    }

    names = audit_previews.list_preview_dir_names(
        "o/r", "gh-pages", run_gh_api_json_fn=_fake_api(responses)
    )
    assert names == []


def test_list_preview_dir_names_rejects_non_string_sha() -> None:
    """List preview dir names rejects non string sha."""
    responses = {
        "repos/o/r/git/trees/gh-pages": {
            "tree": [{"path": "pr-preview", "type": "tree", "sha": 123}]
        },
    }

    with pytest.raises(RuntimeError, match="missing a sha"):
        audit_previews.list_preview_dir_names(
            "o/r", "gh-pages", run_gh_api_json_fn=_fake_api(responses)
        )


def test_tree_entries_reject_malformed_payloads() -> None:
    """Tree entries reject malformed payloads."""
    with pytest.raises(RuntimeError, match="must be a JSON object"):
        audit_previews.list_preview_dir_names(
            "o/r", "gh-pages", run_gh_api_json_fn=_fake_api({"repos/o/r/git/trees/gh-pages": []})
        )
    with pytest.raises(RuntimeError, match="must include a tree array"):
        audit_previews.list_preview_dir_names(
            "o/r",
            "gh-pages",
            run_gh_api_json_fn=_fake_api({"repos/o/r/git/trees/gh-pages": {"tree": "nope"}}),
        )


def test_tree_entries_reject_truncated_listing() -> None:
    """A truncated tree listing fails the audit rather than auditing a partial set."""
    responses = {
        "repos/o/r/git/trees/gh-pages": {
            "truncated": True,
            "tree": [{"path": "pr-preview", "type": "tree", "sha": "deadbeef"}],
        },
    }

    with pytest.raises(RuntimeError, match="truncated"):
        audit_previews.list_preview_dir_names(
            "o/r", "gh-pages", run_gh_api_json_fn=_fake_api(responses)
        )


def test_tree_entries_allow_untruncated_and_absent_truncated_key() -> None:
    """An explicit falsy or absent ``truncated`` key still passes."""
    responses = {
        "repos/o/r/git/trees/gh-pages": {
            "truncated": False,
            "tree": [{"path": "pr-preview", "type": "tree", "sha": "deadbeef"}],
        },
        "repos/o/r/git/trees/deadbeef": {
            "tree": [{"path": "pr-7", "type": "tree"}],
        },
    }

    names = audit_previews.list_preview_dir_names(
        "o/r", "gh-pages", run_gh_api_json_fn=_fake_api(responses)
    )
    assert names == ["pr-7"]


def test_list_open_pr_numbers_collects_integer_numbers() -> None:
    """List open pr numbers collects integer numbers."""
    responses = {
        "repos/o/r/pulls?state=open&per_page=100&page=1": [
            {"number": 12},
            {"number": 7},
            {"missing": "number"},
            {"number": "x"},
            "not-a-dict",
        ]
    }

    numbers = audit_previews.list_open_pr_numbers("o/r", run_gh_api_json_fn=_fake_api(responses))
    assert numbers == {12, 7}


def test_list_open_pr_numbers_paginates_until_short_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """List open pr numbers follows every page until a short page ends it."""
    monkeypatch.setattr(audit_previews, "_PULLS_PER_PAGE", 2)
    responses = {
        "repos/o/r/pulls?state=open&per_page=2&page=1": [{"number": 1}, {"number": 2}],
        "repos/o/r/pulls?state=open&per_page=2&page=2": [{"number": 3}, {"number": 4}],
        "repos/o/r/pulls?state=open&per_page=2&page=3": [{"number": 5}],
    }

    numbers = audit_previews.list_open_pr_numbers("o/r", run_gh_api_json_fn=_fake_api(responses))
    assert numbers == {1, 2, 3, 4, 5}


def test_list_open_pr_numbers_stops_on_empty_trailing_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """List open pr numbers stops when a full page is followed by an empty page."""
    monkeypatch.setattr(audit_previews, "_PULLS_PER_PAGE", 2)
    responses = {
        "repos/o/r/pulls?state=open&per_page=2&page=1": [{"number": 1}, {"number": 2}],
        "repos/o/r/pulls?state=open&per_page=2&page=2": [],
    }

    numbers = audit_previews.list_open_pr_numbers("o/r", run_gh_api_json_fn=_fake_api(responses))
    assert numbers == {1, 2}


def test_list_open_pr_numbers_handles_empty_first_page() -> None:
    """List open pr numbers returns an empty set when the first page is empty."""
    responses = {"repos/o/r/pulls?state=open&per_page=100&page=1": []}
    numbers = audit_previews.list_open_pr_numbers("o/r", run_gh_api_json_fn=_fake_api(responses))
    assert numbers == set()


def test_list_open_pr_numbers_rejects_non_array() -> None:
    """List open pr numbers rejects non array."""
    responses = {"repos/o/r/pulls?state=open&per_page=100&page=1": {}}
    with pytest.raises(RuntimeError, match="must be a JSON array"):
        audit_previews.list_open_pr_numbers("o/r", run_gh_api_json_fn=_fake_api(responses))


def test_find_stale_previews_reports_only_unmatched_pr_dirs() -> None:
    """Find stale previews reports only unmatched pr dirs."""
    stale = audit_previews.find_stale_previews(["pr-12", "pr-7", "not-a-preview", "pr-3"], {12, 7})
    assert stale == ["pr-3"]


def test_audit_previews_raises_when_previews_are_stale() -> None:
    """Audit previews raises when previews are stale."""
    responses = {
        "repos/o/r/git/trees/gh-pages": {
            "tree": [{"path": "pr-preview", "type": "tree", "sha": "s"}]
        },
        "repos/o/r/git/trees/s": {
            "tree": [{"path": "pr-9", "type": "tree"}, {"path": "pr-4", "type": "tree"}]
        },
        "repos/o/r/pulls?state=open&per_page=100&page=1": [{"number": 9}],
    }

    with pytest.raises(ValueError, match="Stale PR preview directories") as exc_info:
        audit_previews.audit_previews(repo="o/r", run_gh_api_json_fn=_fake_api(responses))

    message = str(exc_info.value)
    assert "pr-4" in message
    assert "gh-pages" in message


def test_audit_previews_returns_live_previews_when_clean() -> None:
    """Audit previews returns live previews when clean."""
    responses = {
        "repos/o/r/git/trees/gh-pages": {
            "tree": [{"path": "pr-preview", "type": "tree", "sha": "s"}]
        },
        "repos/o/r/git/trees/s": {
            "tree": [{"path": "pr-9", "type": "tree"}, {"path": "pr-4", "type": "tree"}]
        },
        "repos/o/r/pulls?state=open&per_page=100&page=1": [{"number": 9}, {"number": 4}],
    }

    previews = audit_previews.audit_previews(
        repo="o/r", pages_branch="gh-pages", run_gh_api_json_fn=_fake_api(responses)
    )
    assert previews == ["pr-9", "pr-4"]


def test_workflow_helpers_audit_previews_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Workflow helpers audit previews delegates to the module with the shared api."""
    captured: dict[str, object] = {}

    def fake_audit_previews(
        *, repo: str, pages_branch: str, run_gh_api_json_fn: object
    ) -> list[str]:
        captured["repo"] = repo
        captured["pages_branch"] = pages_branch
        captured["run_gh_api_json_fn"] = run_gh_api_json_fn
        return ["pr-9"]

    monkeypatch.setattr(workflow_helpers._audit_previews, "audit_previews", fake_audit_previews)

    assert workflow_helpers.audit_previews(repo="o/r", pages_branch="gh-pages") == ["pr-9"]
    assert captured["repo"] == "o/r"
    assert captured["pages_branch"] == "gh-pages"
    assert captured["run_gh_api_json_fn"] is workflow_helpers._run_gh_api_json


def test_main_audit_previews_prints_open_previews(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main audit previews prints open previews."""
    monkeypatch.setattr(
        workflow_helpers,
        "audit_previews",
        lambda **_kwargs: ["pr-9", "pr-4"],
    )

    exit_code = workflow_helpers.main(
        ["audit-previews", "--repo", "o/r", "--pages-branch", "gh-pages"]
    )

    assert exit_code == 0
    # The output is sorted regardless of the API response ordering.
    assert json.loads(capsys.readouterr().out) == {"open-previews": ["pr-4", "pr-9"]}
