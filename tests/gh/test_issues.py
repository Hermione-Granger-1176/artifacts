from __future__ import annotations

import json

import pytest

from scripts.gh import issues
from scripts.gh.gh_runner import GhError
from tests.gh.gh_test_support import FakeGh, completed_process, has


def _issue_runner(payload: dict[str, object]) -> FakeGh:
    """Build a fake gh runner that answers ``gh issue view`` with ``payload``."""
    return FakeGh([(has("issue", "view"), completed_process(0, json.dumps(payload)))])


def test_issue_summary_includes_meta_labels_and_recent_comments() -> None:
    """A full payload renders meta, labels, assignees, and only the last comments."""
    payload = {
        "number": 5,
        "title": "Broken thing",
        "state": "OPEN",
        "url": "https://example/issues/5",
        "author": {"login": "octocat"},
        "labels": [{"name": "bug"}, {"name": "ci"}],
        "assignees": [{"login": "dev1"}],
        "milestone": {"title": "v1"},
        "comments": [
            {"author": {"login": "a"}, "body": "oldest\nsecond line"},
            {"author": {"login": "b"}, "body": ""},
            {"author": None, "body": "no author here"},
            {"author": {"login": "c"}, "body": "newest"},
        ],
    }

    text = issues.issue_summary(5, run_fn=_issue_runner(payload))

    assert "Issue #5 [OPEN] Broken thing" in text
    assert "https://example/issues/5" in text
    assert "author: @octocat" in text
    assert "labels: bug, ci" in text
    assert "assignees: @dev1" in text
    assert "milestone: v1" in text
    assert "comments: 4" in text
    assert "recent comments:" in text
    # Only the last three comments are echoed, so the oldest is dropped.
    assert "oldest" not in text
    assert "@unknown: no author here" in text
    assert "@c: newest" in text


def test_issue_summary_handles_empty_optional_fields() -> None:
    """Null author, labels, assignees, milestone, and comments render as ``none``."""
    payload = {
        "number": 9,
        "title": "Empty",
        "state": "CLOSED",
        "url": "https://example/issues/9",
        "author": None,
        "labels": None,
        "assignees": None,
        "milestone": None,
        "comments": None,
    }

    text = issues.issue_summary(9, run_fn=_issue_runner(payload))

    assert "Issue #9 [CLOSED] Empty" in text
    assert "author: @unknown" in text
    assert "labels: none" in text
    assert "assignees: none" in text
    assert "milestone: none" in text
    assert "comments: 0" in text
    assert "recent comments:" not in text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("number", "5"),
        ("number", True),
        ("state", None),
        ("title", None),
        ("title", ""),
        ("url", None),
    ],
)
def test_issue_summary_rejects_invalid_required_fields(field: str, value: object) -> None:
    """Missing or malformed required metadata surfaces as a field-specific GhError."""
    payload: dict[str, object] = {
        "number": 5,
        "title": "Issue title",
        "state": "OPEN",
        "url": "https://example/issues/5",
    }
    payload[field] = value

    with pytest.raises(GhError, match=field):
        issues.issue_summary(5, run_fn=_issue_runner(payload))


def test_issue_summary_non_dict_payload_raises() -> None:
    """A non-mapping ``gh issue view`` payload surfaces as a GhError."""
    with pytest.raises(GhError):
        issues.issue_summary(1, run_fn=_issue_runner([1, 2]))  # type: ignore[arg-type]


def test_login_rejects_malformed_author() -> None:
    """A non-null, non-mapping author is a malformed shape."""
    with pytest.raises(GhError):
        issues._login("octocat")


def test_login_without_login_field_is_unknown() -> None:
    """An author object missing a login falls back to ``unknown``."""
    assert issues._login({}) == "unknown"


def test_names_skips_items_without_the_key() -> None:
    """Objects missing the requested key are skipped, not rendered blank."""
    assert issues._names([{"other": "x"}, {"name": "y"}], "name", "bad") == ["y"]


def test_names_rejects_non_list() -> None:
    """A non-null, non-list labels/assignees value is malformed."""
    with pytest.raises(GhError):
        issues._names({"name": "bug"}, "name", "bad")


def test_names_rejects_non_mapping_item() -> None:
    """A non-mapping entry inside the list is malformed."""
    with pytest.raises(GhError):
        issues._names([1], "name", "bad")


def test_milestone_title_variants() -> None:
    """Milestone rendering covers null, titled, and untitled objects, plus bad shapes."""
    assert issues._milestone_title(None) == "none"
    assert issues._milestone_title({"title": "v2"}) == "v2"
    assert issues._milestone_title({}) == "none"
    with pytest.raises(GhError):
        issues._milestone_title("v2")


def test_comment_list_rejects_non_list() -> None:
    """A non-null, non-list comments value is malformed."""
    with pytest.raises(GhError):
        issues._comment_list({"body": "x"})


def test_recent_comments_rejects_non_mapping_comment() -> None:
    """A non-mapping comment entry is malformed."""
    with pytest.raises(GhError):
        issues._recent_comments(["not a dict"])
