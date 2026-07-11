from __future__ import annotations

import pytest

from scripts.ci import issue_alerts


def test_alert_should_exist_maps_states_to_lifecycle() -> None:
    """Alert should exist maps states to lifecycle."""
    assert issue_alerts.alert_should_exist("open") is True
    assert issue_alerts.alert_should_exist("setup-failure") is True
    assert issue_alerts.alert_should_exist("close") is False


def test_alert_should_exist_rejects_unknown_state() -> None:
    """Alert should exist rejects unknown state."""
    with pytest.raises(ValueError, match="Unsupported alert state: bogus"):
        issue_alerts.alert_should_exist("bogus")


def test_build_alert_body_renders_each_state_with_run_url() -> None:
    """Build alert body renders each state with run url."""
    run_url = "https://github.com/owner/repo/actions/runs/9"

    open_body = issue_alerts.build_alert_body(state="open", run_url=run_url)
    assert open_body.startswith("Scheduled checks behind this alert are failing.")
    assert f"Workflow run: {run_url}" in open_body

    close_body = issue_alerts.build_alert_body(state="close", run_url=run_url)
    assert close_body.startswith("Scheduled checks behind this alert are passing again.")
    assert f"Workflow run: {run_url}" in close_body

    setup_body = issue_alerts.build_alert_body(state="setup-failure", run_url=run_url)
    assert "failed before its checks could report a status" in setup_body
    assert f"Workflow run: {run_url}" in setup_body


def test_build_alert_body_appends_detail_when_given() -> None:
    """Build alert body appends detail when given."""
    body = issue_alerts.build_alert_body(
        state="open",
        run_url="https://github.com/owner/repo/actions/runs/9",
        detail="Published URL: https://example.test/",
    )
    assert body.endswith("\n\nPublished URL: https://example.test/")


def test_build_alert_body_rejects_unknown_state() -> None:
    """Build alert body rejects unknown state."""
    with pytest.raises(ValueError, match="Unsupported alert state: bogus"):
        issue_alerts.build_alert_body(state="bogus", run_url="https://example.test/run")


def test_issue_payloads_by_title_filters_non_matching_issues_and_prs() -> None:
    """Issue payloads by title filters non matching issues and prs."""
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
        run_gh_api_json_fn=lambda *_args, **_kwargs: payload,
    )

    assert matches == [payload[1]]


def test_issue_payloads_by_title_rejects_non_array_payloads() -> None:
    """Issue payloads by title rejects non array payloads."""
    with pytest.raises(RuntimeError, match="Issues response must be a JSON array"):
        issue_alerts.issue_payloads_by_title(
            "owner/repo",
            "Alert",
            run_gh_api_json_fn=lambda *_args, **_kwargs: {"invalid": True},
        )


def test_sync_alert_issue_creates_new_issue_when_missing() -> None:
    """Sync alert issue creates new issue when missing."""
    create_calls = []

    def fake_run_gh_api_form(
        endpoint: str,
        *,
        method: str,
        fields,
        description: str,
        jq_expr: str = "",
        **_kwargs: object,
    ) -> str:
        create_calls.append((endpoint, method, fields, description, jq_expr))
        return "https://github.com/owner/repo/issues/11"

    issue_url = issue_alerts.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Something broke",
        labels=["ci", "ops"],
        should_exist=True,
        issue_payloads_by_title_fn=lambda *_args, **_kwargs: [],
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
    """Sync alert issue updates existing issue when present."""
    update_calls = []

    def fake_run_gh_api_form(
        endpoint: str,
        *,
        method: str,
        fields,
        description: str,
        jq_expr: str = "",
        **_kwargs: object,
    ) -> str:
        update_calls.append((endpoint, method, fields, description, jq_expr))
        return ""

    issue_url = issue_alerts.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Updated body",
        labels=["ci"],
        should_exist=True,
        issue_payloads_by_title_fn=lambda *_args, **_kwargs: [
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
    """Sync alert issue closes existing issue when no longer needed."""
    close_calls = []

    def fake_run_gh_api_form(
        endpoint: str,
        *,
        method: str,
        fields,
        description: str,
        jq_expr: str = "",
        **_kwargs: object,
    ) -> str:
        close_calls.append((endpoint, method, fields, description, jq_expr))
        return ""

    issue_url = issue_alerts.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Resolved",
        labels=["ci"],
        should_exist=False,
        issue_payloads_by_title_fn=lambda *_args, **_kwargs: [
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
    """Sync alert issue rejects non integer issue number on update."""
    with pytest.raises(RuntimeError, match="Matched issue number must be an integer"):
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Updated body",
            labels=["ci"],
            should_exist=True,
            issue_payloads_by_title_fn=lambda *_args, **_kwargs: [{"number": "7"}],
            run_gh_api_form_fn=lambda *_args, **_kwargs: "",
        )


def test_sync_alert_issue_rejects_missing_html_url_on_update() -> None:
    """Sync alert issue rejects missing html url on update."""
    with pytest.raises(RuntimeError, match="Matched issue html_url must be a non-empty string"):
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Updated body",
            labels=["ci"],
            should_exist=True,
            issue_payloads_by_title_fn=lambda *_args, **_kwargs: [{"number": 7, "html_url": ""}],
            run_gh_api_form_fn=lambda *_args, **_kwargs: "",
        )


def test_sync_alert_issue_rejects_non_integer_issue_number_on_close() -> None:
    """Sync alert issue rejects non integer issue number on close."""
    with pytest.raises(RuntimeError, match="Matched issue number must be an integer"):
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Resolved",
            labels=["ci"],
            should_exist=False,
            issue_payloads_by_title_fn=lambda *_args, **_kwargs: [{"number": "7"}],
            run_gh_api_form_fn=lambda *_args, **_kwargs: "",
        )


def test_sync_alert_issue_returns_empty_when_no_open_issue_to_close() -> None:
    """Sync alert issue returns empty when no open issue to close."""
    assert (
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Artifact alert",
            body="Resolved",
            labels=["ci"],
            should_exist=False,
            issue_payloads_by_title_fn=lambda *_args, **_kwargs: [],
            run_gh_api_form_fn=lambda endpoint, **_kwargs: endpoint,
        )
        == ""
    )
