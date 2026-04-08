from __future__ import annotations

import pytest

from scripts.ci import issue_alerts


def test_issue_payloads_by_title_filters_non_matching_issues_and_prs() -> None:
    payload = [
        "invalid",
        {
            "number": 1,
            "title": "Live site smoke check failed",
            "html_url": "https://example.com/1",
        },
        {
            "number": 2,
            "title": "Live site smoke check failed",
            "html_url": "https://example.com/2",
            "pull_request": {"url": "https://example.com/pr/2"},
        },
        {"number": 3, "title": "Different issue", "html_url": "https://example.com/3"},
    ]

    matches = issue_alerts.issue_payloads_by_title(
        "owner/repo",
        "Live site smoke check failed",
        run_gh_api_json_fn=lambda endpoint, description: payload,
    )

    assert matches == [payload[1]]


def test_issue_payloads_by_title_rejects_non_array_payloads() -> None:
    with pytest.raises(RuntimeError, match="Issues response must be a JSON array"):
        issue_alerts.issue_payloads_by_title(
            "owner/repo",
            "Alert",
            run_gh_api_json_fn=lambda endpoint, description: {"invalid": True},
        )


def test_sync_alert_issue_creates_new_issue_when_missing() -> None:
    create_calls = []

    def fake_run_gh_api_form(
        endpoint: str, *, method: str, fields, description: str, jq_expr: str = ""
    ) -> str:
        create_calls.append((endpoint, method, fields, description, jq_expr))
        return "https://github.com/owner/repo/issues/11"

    issue_url = issue_alerts.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Something broke",
        labels=["ci", "ops"],
        should_exist=True,
        issue_payloads_by_title_fn=lambda repo, title: [],
        run_gh_api_form_fn=fake_run_gh_api_form,
    )

    assert issue_url == "https://github.com/owner/repo/issues/11"
    assert create_calls == [
        (
            "repos/owner/repo/issues",
            "POST",
            [
                ("title", "Artifact alert"),
                ("body", "Something broke"),
                ("labels[]", "ci"),
                ("labels[]", "ops"),
            ],
            "creating alert issue Artifact alert for owner/repo",
            ".html_url",
        )
    ]


def test_sync_alert_issue_updates_existing_issue_when_present() -> None:
    update_calls = []

    def fake_run_gh_api_form(
        endpoint: str, *, method: str, fields, description: str, jq_expr: str = ""
    ) -> str:
        update_calls.append((endpoint, method, fields, description, jq_expr))
        return ""

    issue_url = issue_alerts.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Updated body",
        labels=["ci"],
        should_exist=True,
        issue_payloads_by_title_fn=lambda repo, title: [
            {"number": 7, "html_url": "https://github.com/owner/repo/issues/7"}
        ],
        run_gh_api_form_fn=fake_run_gh_api_form,
    )

    assert issue_url == "https://github.com/owner/repo/issues/7"
    assert update_calls == [
        (
            "repos/owner/repo/issues/7",
            "PATCH",
            [
                ("title", "Artifact alert"),
                ("body", "Updated body"),
                ("labels[]", "ci"),
            ],
            "updating alert issue Artifact alert for owner/repo",
            "",
        )
    ]


def test_sync_alert_issue_closes_existing_issue_when_no_longer_needed() -> None:
    close_calls = []

    def fake_run_gh_api_form(
        endpoint: str, *, method: str, fields, description: str, jq_expr: str = ""
    ) -> str:
        close_calls.append((endpoint, method, fields, description, jq_expr))
        return ""

    issue_url = issue_alerts.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Resolved",
        labels=["ci"],
        should_exist=False,
        issue_payloads_by_title_fn=lambda repo, title: [
            {"number": 7, "html_url": "https://github.com/owner/repo/issues/7"}
        ],
        run_gh_api_form_fn=fake_run_gh_api_form,
    )

    assert issue_url == ""
    assert close_calls == [
        (
            "repos/owner/repo/issues/7",
            "PATCH",
            [("state", "closed")],
            "closing alert issue Artifact alert for owner/repo",
            "",
        )
    ]


def test_sync_alert_issue_rejects_non_integer_issue_number_on_update() -> None:
    with pytest.raises(RuntimeError, match="Matched issue number must be an integer"):
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Updated body",
            labels=["ci"],
            should_exist=True,
            issue_payloads_by_title_fn=lambda repo, title: [{"number": "7"}],
            run_gh_api_form_fn=lambda **kwargs: "",
        )


def test_sync_alert_issue_rejects_missing_html_url_on_update() -> None:
    with pytest.raises(
        RuntimeError, match="Matched issue html_url must be a non-empty string"
    ):
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Updated body",
            labels=["ci"],
            should_exist=True,
            issue_payloads_by_title_fn=lambda repo, title: [
                {"number": 7, "html_url": ""}
            ],
            run_gh_api_form_fn=lambda endpoint, **kwargs: "",
        )


def test_sync_alert_issue_rejects_non_integer_issue_number_on_close() -> None:
    with pytest.raises(RuntimeError, match="Matched issue number must be an integer"):
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Resolved",
            labels=["ci"],
            should_exist=False,
            issue_payloads_by_title_fn=lambda repo, title: [{"number": "7"}],
            run_gh_api_form_fn=lambda **kwargs: "",
        )


def test_sync_alert_issue_returns_empty_when_no_open_issue_to_close() -> None:
    assert (
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Resolved",
            labels=["ci"],
            should_exist=False,
            issue_payloads_by_title_fn=lambda repo, title: [],
            run_gh_api_form_fn=lambda endpoint, **kwargs: endpoint,
        )
        == ""
    )
