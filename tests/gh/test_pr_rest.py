from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from scripts.gh import pr_rest
from scripts.gh.gh_runner import GhError
from tests.gh.gh_test_support import FakeGh, has, json_response, rest, sandbox_routes

PULL = {
    "number": 7,
    "title": "Add thing",
    "state": "open",
    "merged": False,
    "html_url": "https://example/pull/7",
    "head": {"sha": "abc123"},
}


def _runner(*routes: tuple[Callable[[list[str]], bool], Any]) -> FakeGh:
    """Build a sandbox runner with the given REST routes."""
    return FakeGh([*sandbox_routes(), *routes])


def test_pull_state_reports_merged_open_and_closed() -> None:
    """A merged PR reads MERGED regardless of its closed state."""
    assert pr_rest.pull_state({"state": "closed", "merged": True}) == "MERGED"
    assert pr_rest.pull_state({"state": "open"}) == "OPEN"
    assert pr_rest.pull_state({"state": "closed"}) == "CLOSED"
    assert pr_rest.pull_state({}) == ""


def test_head_sha_requires_a_head_commit() -> None:
    """A pull request without a head commit is a clear error."""
    assert pr_rest.head_sha(PULL) == "abc123"
    for pull in ({}, {"head": "x"}, {"head": {"sha": ""}}):
        with pytest.raises(GhError, match="no head commit"):
            pr_rest.head_sha(pull)


def test_pull_request_rejects_a_non_object() -> None:
    """A list where the pull request should be is a shape error."""
    runner = _runner((rest("GET", "repos/o/r/pulls/7"), json_response([])))

    with pytest.raises(GhError, match="Unexpected pull request response shape for PR 7"):
        pr_rest.pull_request("o/r", 7, run_fn=runner)


def _rollup_runner(runs: list[object], statuses: object) -> FakeGh:
    """Build a runner serving check runs and commit statuses for ``abc123``."""
    return _runner(
        (
            rest("GET", "repos/o/r/commits/abc123/check-runs"),
            json_response({"total_count": len(runs), "check_runs": runs}),
        ),
        (rest("GET", "repos/o/r/commits/abc123/status"), json_response(statuses)),
    )


def test_status_check_rollup_matches_the_gh_shape() -> None:
    """Check runs and commit statuses become upper-case rollup entries."""
    runs = [
        {
            "name": "lint",
            "status": "completed",
            "conclusion": "success",
            "details_url": "https://example/lint",
            "started_at": "2026-01-01T00:00:00Z",
            "completed_at": "2026-01-01T00:01:05Z",
        },
        {"name": "test", "status": "in_progress", "conclusion": None, "html_url": "https://h"},
    ]
    statuses = {"state": "pending", "statuses": [{"context": "ci/x", "state": "success"}]}

    rollup = pr_rest.status_check_rollup("o/r", "abc123", run_fn=_rollup_runner(runs, statuses))

    assert rollup == [
        {
            "name": "lint",
            "status": "COMPLETED",
            "conclusion": "SUCCESS",
            "detailsUrl": "https://example/lint",
            "startedAt": "2026-01-01T00:00:00Z",
            "completedAt": "2026-01-01T00:01:05Z",
        },
        {
            "name": "test",
            "status": "IN_PROGRESS",
            "conclusion": "",
            "detailsUrl": "https://h",
            "startedAt": None,
            "completedAt": None,
        },
        {"context": "ci/x", "state": "SUCCESS", "targetUrl": ""},
    ]


def test_status_check_rollup_keeps_the_newest_run_of_each_name() -> None:
    """A re-run replaces the older run of the same name, wherever it appears in the list."""
    runs = [
        {"id": 2, "name": "lint", "status": "completed", "conclusion": "success"},
        {"id": 1, "name": "lint", "status": "completed", "conclusion": "failure"},
        {"id": 3, "name": "test", "status": "completed", "conclusion": "failure"},
        {"id": 4, "name": "test", "status": "completed", "conclusion": "success"},
        {"name": "docs", "status": "completed", "conclusion": "skipped"},
    ]
    runner = _rollup_runner(runs, {"statuses": []})

    rollup = pr_rest.status_check_rollup("o/r", "abc123", run_fn=runner)

    assert [(entry["name"], entry["conclusion"]) for entry in rollup] == [
        ("lint", "SUCCESS"),
        ("test", "SUCCESS"),
        ("docs", "SKIPPED"),
    ]


def test_status_check_rollup_keeps_same_named_checks_from_separate_suites() -> None:
    """A passing check in one suite never hides a failing check of the same name in another."""
    runs = [
        {"id": 5, "name": "lint", "check_suite": {"id": 20}, "conclusion": "success"},
        {"id": 4, "name": "lint", "check_suite": {"id": 10}, "conclusion": "failure"},
        {"id": 3, "name": "lint", "check_suite": {"id": 10}, "conclusion": "success"},
    ]
    runner = _rollup_runner(runs, {"statuses": []})

    rollup = pr_rest.status_check_rollup("o/r", "abc123", run_fn=runner)

    assert [(entry["name"], entry["conclusion"]) for entry in rollup] == [
        ("lint", "SUCCESS"),
        ("lint", "FAILURE"),
    ]


def test_status_check_rollup_reads_every_page_of_statuses() -> None:
    """A failing status on the second page still reaches the rollup."""
    first = [{"context": f"ok-{index}", "state": "success"} for index in range(100)]
    runner = _runner(
        (rest("GET", "repos/o/r/commits/abc123/check-runs"), json_response({"check_runs": []})),
        (has("repos/o/r/commits/abc123/status", "page=1"), json_response({"statuses": first})),
        (
            has("repos/o/r/commits/abc123/status", "page=2"),
            json_response({"statuses": [{"context": "deploy", "state": "failure"}]}),
        ),
    )

    rollup = pr_rest.status_check_rollup("o/r", "abc123", run_fn=runner)

    assert len(rollup) == 101
    assert rollup[-1] == {"context": "deploy", "state": "FAILURE", "targetUrl": ""}


def test_status_check_rollup_ignores_the_combined_pending_state() -> None:
    """A commit with no statuses adds nothing, although the combined state reads pending."""
    runner = _rollup_runner([], {"state": "pending", "statuses": []})

    assert pr_rest.status_check_rollup("o/r", "abc123", run_fn=runner) == []


@pytest.mark.parametrize(
    "statuses",
    ["not an object", {"state": "pending"}, {"statuses": ["not an object"]}],
)
def test_status_check_rollup_rejects_malformed_statuses(statuses: object) -> None:
    """A combined-status response of the wrong shape is a GhError."""
    with pytest.raises(GhError, match="status"):
        pr_rest.status_check_rollup("o/r", "abc123", run_fn=_rollup_runner([], statuses))


def test_reviews_normalize_to_the_gh_shape() -> None:
    """Reviews use node ids, bot-free logins, and upper-case states."""
    runner = _runner(
        (
            rest("GET", "repos/o/r/pulls/7/reviews"),
            json_response(
                [
                    {
                        "id": 1,
                        "node_id": "PRR_x",
                        "user": {"login": "copilot-pull-request-reviewer[bot]"},
                        "submitted_at": "2026-01-01T00:00:00Z",
                        "body": None,
                        "state": "commented",
                    },
                    {"id": 2, "user": None, "state": "APPROVED"},
                ]
            ),
        )
    )

    assert pr_rest.reviews("o/r", 7, run_fn=runner) == [
        {
            "id": "PRR_x",
            "author": {"login": "copilot-pull-request-reviewer"},
            "submittedAt": "2026-01-01T00:00:00Z",
            "body": "",
            "state": "COMMENTED",
        },
        {"id": "2", "author": None, "submittedAt": None, "body": "", "state": "APPROVED"},
    ]


def test_pr_view_supplies_only_requested_fields() -> None:
    """Each requested field is built, and unrequested lookups are skipped."""
    runner = _runner(
        (rest("GET", "repos/o/r/pulls/7"), json_response(PULL)),
        (rest("GET", "repos/o/r/pulls/7/reviews"), json_response([])),
    )

    view = pr_rest.pr_view(7, ["number", "title", "state", "url", "reviews"], run_fn=runner)

    assert view == {
        "number": 7,
        "title": "Add thing",
        "state": "OPEN",
        "url": "https://example/pull/7",
        "reviews": [],
    }
    assert not any("check-runs" in part for call in runner.calls for part in call)


def test_pr_view_includes_the_rollup_when_requested() -> None:
    """The check rollup is resolved through the head commit."""
    runner = _runner(
        (rest("GET", "repos/o/r/pulls/7"), json_response(PULL)),
        (rest("GET", "repos/o/r/commits/abc123/check-runs"), json_response({"check_runs": []})),
        (rest("GET", "repos/o/r/commits/abc123/status"), json_response({"statuses": []})),
    )

    assert pr_rest.pr_view(7, ["statusCheckRollup"], run_fn=runner) == {"statusCheckRollup": []}


def test_pr_view_rejects_an_unsupported_field() -> None:
    """Asking for a field the REST path cannot build is explicit."""
    runner = _runner((rest("GET", "repos/o/r/pulls/7"), json_response(PULL)))

    with pytest.raises(GhError, match="cannot supply the labels field"):
        pr_rest.pr_view(7, ["labels"], run_fn=runner)
