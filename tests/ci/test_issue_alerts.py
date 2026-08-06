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
    with pytest.raises(ValueError, match="Unsupported alert state: 'bogus'"):
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
    with pytest.raises(ValueError, match="Unsupported alert state: 'bogus'"):
        issue_alerts.build_alert_body(state="bogus", run_url="https://example.test/run")


def test_issue_payloads_by_title_filters_non_matching_issues_and_prs() -> None:
    """Issue payloads by title filters non matching issues and prs."""
    payload = [
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

    assert matches == [payload[0]]


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
            "repos/owner/repo/issues/7/comments",
            "POST",
            [("body", "Updated body")],
            "commenting on alert issue Artifact alert for owner/repo",
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
    with pytest.raises(RuntimeError, match="Matched issue number must be a positive integer"):
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
    with pytest.raises(RuntimeError, match="Matched issue number must be a positive integer"):
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


@pytest.mark.parametrize(
    ("run_url", "message"),
    [
        ("", "must not be empty"),
        ("http://github.com/o/r/actions/runs/1", "https URL"),
        ("https://github.com/o/r/actions/1", "Actions run"),
    ],
)
def test_build_alert_body_rejects_unusable_run_urls(run_url: str, message: str) -> None:
    """Alert bodies do not record malformed or misleading run links."""
    with pytest.raises(ValueError, match=message):
        issue_alerts.build_alert_body(state="open", run_url=run_url)


def test_issue_payloads_by_title_scopes_query_to_labels() -> None:
    """Issue lookup includes the supplied labels in the bounded API query."""
    captured: dict[str, object] = {}

    def fake_json(endpoint: str, **_kwargs: object) -> object:
        captured["endpoint"] = endpoint
        return []

    assert (
        issue_alerts.issue_payloads_by_title(
            "owner/repo",
            "Alert",
            labels=["ops", "ci", "ops"],
            run_gh_api_json_fn=fake_json,
        )
        == []
    )
    assert captured["endpoint"] == "repos/owner/repo/issues?state=open&per_page=100&labels=ops,ci"


def test_issue_payloads_by_title_rejects_a_capped_result() -> None:
    """A capped response cannot safely prove that an alert issue is absent."""
    payload = [{"number": number, "title": "Other"} for number in range(100)]

    with pytest.raises(RuntimeError, match="may be truncated"):
        issue_alerts.issue_payloads_by_title(
            "owner/repo",
            "Alert",
            run_gh_api_json_fn=lambda *_args, **_kwargs: payload,
        )


def test_issue_payloads_by_title_rejects_malformed_entries() -> None:
    """A malformed issue entry fails closed instead of being ignored."""
    with pytest.raises(RuntimeError, match="entries must be JSON objects"):
        issue_alerts.issue_payloads_by_title(
            "owner/repo",
            "Alert",
            run_gh_api_json_fn=lambda *_args, **_kwargs: ["not an issue"],
        )


def test_issue_payloads_by_title_prefers_the_oldest_duplicate() -> None:
    """Duplicate alert issues converge on the oldest matching issue."""
    payload = [
        {"number": 12, "title": "Alert", "html_url": "https://example/12"},
        {"number": 4, "title": "Alert", "html_url": "https://example/4"},
    ]

    matches = issue_alerts.issue_payloads_by_title(
        "owner/repo",
        "Alert",
        run_gh_api_json_fn=lambda *_args, **_kwargs: payload,
    )

    assert [match["number"] for match in matches] == [4, 12]


def test_sync_alert_issue_rejects_empty_create_url() -> None:
    """Creating an alert without a returned URL is an operational failure."""
    with pytest.raises(RuntimeError, match="returned no URL"):
        issue_alerts.sync_alert_issue(
            repo="owner/repo",
            title="Alert",
            body="Failure",
            labels=["ci"],
            should_exist=True,
            issue_payloads_by_title_fn=lambda *_args, **_kwargs: [],
            run_gh_api_form_fn=lambda *_args, **_kwargs: "",
        )


@pytest.mark.parametrize("field", ["repo", "title"])
def test_sync_alert_issue_rejects_flag_like_identifiers(field: str) -> None:
    """Structured alert identifiers cannot be passed as option-looking values."""
    values = {
        "repo": "-owner/repo",
        "title": "-Alert",
        "body": "Failure",
        "labels": ["ci"],
    }

    with pytest.raises(ValueError, match="must not start"):
        issue_alerts.sync_alert_issue(
            repo=values["repo"] if field == "repo" else "owner/repo",
            title=values["title"] if field == "title" else "Alert",
            body="Failure",
            labels=["ci"],
            should_exist=True,
            issue_payloads_by_title_fn=lambda *_args, **_kwargs: [],
            run_gh_api_form_fn=lambda *_args, **_kwargs: "url",
        )
