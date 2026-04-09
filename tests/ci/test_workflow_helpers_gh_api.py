from __future__ import annotations

import subprocess

import pytest

import scripts.ci.workflow_helpers as workflow_helpers
import scripts.lib.gh_api as gh_api
from tests.ci.workflow_helpers_test_support import FakeSubprocessResult


def test_is_retryable_gh_api_failure_matches_expected_cases() -> None:
    assert gh_api.is_retryable_gh_api_failure("503 Service Unavailable")
    assert gh_api.is_retryable_gh_api_failure("timed out while calling API")
    assert gh_api.is_retryable_gh_api_failure("network error")
    assert not gh_api.is_retryable_gh_api_failure("404 Not Found")


def test_run_gh_api_retries_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    sleep_calls: list[float] = []

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            result = FakeSubprocessResult(returncode=1)
            result.stderr = "503 Service Unavailable"
            return result
        return FakeSubprocessResult("apps/demo/index.html\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    monkeypatch.setattr(workflow_helpers.time, "sleep", sleep_calls.append)

    stdout = workflow_helpers._run_gh_api(
        "repos/owner/repo/pulls/1/files",
        paginate=["--paginate"],
        jq_expr=".[].filename",
        description="listing changed files for pull_request owner/repo",
    )

    assert stdout == "apps/demo/index.html\n"
    assert calls == 2
    assert sleep_calls == [gh_api.GH_API_RETRY_DELAY_SECONDS]


def test_run_gh_api_retries_timeout_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_calls: list[float] = []

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        raise subprocess.TimeoutExpired(["gh", "api"], 15)

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    monkeypatch.setattr(workflow_helpers.time, "sleep", sleep_calls.append)

    with pytest.raises(RuntimeError, match="timed out"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo/commits/abc123",
            paginate=[],
            jq_expr=".files[].filename",
            description="listing changed files for push owner/repo",
        )

    assert sleep_calls == [
        gh_api.GH_API_RETRY_DELAY_SECONDS,
        gh_api.GH_API_RETRY_DELAY_SECONDS * 2,
    ]


def test_run_gh_api_fails_fast_for_non_retryable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        result = FakeSubprocessResult(returncode=1)
        result.stderr = "404 Not Found"
        return result

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="404 Not Found"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo/commits/abc123",
            paginate=[],
            jq_expr=".files[].filename",
            description="listing changed files for push owner/repo",
        )


def test_run_gh_api_uses_final_fallback_when_attempts_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(workflow_helpers._gh_api, "GH_API_MAX_ATTEMPTS", 0)

    with pytest.raises(RuntimeError, match="unknown error"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo/commits/abc123",
            paginate=[],
            jq_expr=".files[].filename",
            description="listing changed files for push owner/repo",
        )


def test_run_gh_api_json_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda endpoint, paginate, jq_expr, description: '{"ok": true}',
    )

    assert workflow_helpers._run_gh_api_json(
        "repos/owner/repo", description="reading repository metadata"
    ) == {"ok": True}


def test_run_gh_api_json_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda endpoint, paginate, jq_expr, description: "not-json",
    )

    with pytest.raises(RuntimeError, match="returned invalid JSON"):
        workflow_helpers._run_gh_api_json(
            "repos/owner/repo", description="reading repository metadata"
        )


def test_run_gh_api_form_posts_fields_with_shared_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_run_gh_api_form(
        endpoint: str,
        *,
        method: str,
        fields: list[tuple[str, str]],
        description: str,
        jq_expr: str = "",
        max_attempts: int,
        retry_delay_seconds: float,
        sleep_fn,
        timeout_seconds: float,
    ) -> str:
        captured["endpoint"] = endpoint
        captured["method"] = method
        captured["fields"] = fields
        captured["description"] = description
        captured["jq_expr"] = jq_expr
        captured["max_attempts"] = max_attempts
        captured["retry_delay_seconds"] = retry_delay_seconds
        captured["timeout_seconds"] = timeout_seconds
        return "https://example.com/issues/1"

    monkeypatch.setattr(
        workflow_helpers._gh_api, "run_gh_api_form", fake_run_gh_api_form
    )

    result = workflow_helpers._run_gh_api_form(
        "repos/owner/repo/issues",
        method="POST",
        fields=[("title", "Alert"), ("labels[]", "ci")],
        description="creating alert issue",
        jq_expr=".html_url",
    )

    assert result == "https://example.com/issues/1"
    assert captured == {
        "endpoint": "repos/owner/repo/issues",
        "method": "POST",
        "fields": [("title", "Alert"), ("labels[]", "ci")],
        "description": "creating alert issue",
        "jq_expr": ".html_url",
        "max_attempts": gh_api.GH_API_MAX_ATTEMPTS,
        "retry_delay_seconds": gh_api.GH_API_RETRY_DELAY_SECONDS,
        "timeout_seconds": gh_api.GH_API_TIMEOUT_SECONDS,
    }


def test_run_gh_api_form_escapes_leading_at_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_run_gh_command(
        command: list[str],
        *,
        description: str,
        max_attempts: int,
        retry_delay_seconds: float,
        sleep_fn,
        subprocess_module,
        timeout_seconds: float,
    ) -> str:
        captured["command"] = command
        return "ok"

    monkeypatch.setattr(
        workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command
    )

    result = workflow_helpers._gh_api.run_gh_api_form(
        "repos/owner/repo/issues",
        method="POST",
        fields=[("title", "@alert"), ("body", "body")],
        description="creating alert issue",
    )

    assert result == "ok"
    assert captured["command"] == [
        "gh",
        "api",
        "-X",
        "POST",
        "repos/owner/repo/issues",
        "-f",
        "title=\\@alert",
        "-f",
        "body=body",
    ]


def test_low_level_run_gh_api_form_appends_jq_expression(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_run_gh_command(
        command: list[str],
        *,
        description: str,
        max_attempts: int,
        retry_delay_seconds: float,
        sleep_fn,
        subprocess_module,
        timeout_seconds: float,
    ) -> str:
        captured["command"] = command
        return "ok"

    monkeypatch.setattr(
        workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command
    )

    result = workflow_helpers._gh_api.run_gh_api_form(
        "repos/owner/repo/issues",
        method="POST",
        fields=[("title", "Alert")],
        description="creating alert issue",
        jq_expr=".html_url",
    )

    assert result == "ok"
    assert captured["command"] == [
        "gh",
        "api",
        "-X",
        "POST",
        "repos/owner/repo/issues",
        "-f",
        "title=Alert",
        "--jq",
        ".html_url",
    ]


def test_run_gh_api_form_omits_jq_when_not_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_run_gh_command(
        command: list[str],
        *,
        description: str,
        max_attempts: int,
        retry_delay_seconds: float,
        sleep_fn,
        subprocess_module,
        timeout_seconds: float,
    ) -> str:
        captured["command"] = command
        return "ok"

    monkeypatch.setattr(
        workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command
    )

    result = workflow_helpers._gh_api.run_gh_api_form(
        "repos/owner/repo/issues/7",
        method="PATCH",
        fields=[("state", "closed")],
        description="closing alert issue",
    )

    assert result == "ok"
    assert captured["command"] == [
        "gh",
        "api",
        "-X",
        "PATCH",
        "repos/owner/repo/issues/7",
        "-f",
        "state=closed",
    ]


def test_run_gh_api_form_passes_custom_subprocess_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}
    fake_subprocess_module = object()

    def fake_run_gh_command(
        command: list[str],
        *,
        description: str,
        max_attempts: int,
        retry_delay_seconds: float,
        sleep_fn,
        subprocess_module,
        timeout_seconds: float,
    ) -> str:
        captured["subprocess_module"] = subprocess_module
        return "ok"

    monkeypatch.setattr(
        workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command
    )

    result = workflow_helpers._gh_api.run_gh_api_form(
        "repos/owner/repo/issues/7",
        method="PATCH",
        fields=[("state", "closed")],
        description="closing alert issue",
        subprocess_module=fake_subprocess_module,
    )

    assert result == "ok"
    assert captured["subprocess_module"] is fake_subprocess_module


def test_sync_alert_issue_delegates_to_issue_alerts_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_sync_alert_issue(**kwargs) -> str:
        captured.update(kwargs)
        return "https://github.com/owner/repo/issues/7"

    monkeypatch.setattr(
        workflow_helpers._issue_alerts, "sync_alert_issue", fake_sync_alert_issue
    )

    issue_url = workflow_helpers.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Updated body",
        labels=["ci"],
        issue_url="ignored",
        should_exist=True,
    )

    assert issue_url == "https://github.com/owner/repo/issues/7"
    assert captured["repo"] == "owner/repo"
    assert captured["title"] == "Artifact alert"
    assert captured["body"] == "Updated body"
    assert captured["labels"] == ["ci"]
    assert captured["should_exist"] is True
    assert (
        captured["issue_payloads_by_title_fn"]
        is workflow_helpers._issue_payloads_by_title
    )
    assert captured["run_gh_api_form_fn"] is workflow_helpers._run_gh_api_form


def test_issue_payloads_by_title_delegates_to_issue_alerts_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_issue_payloads_by_title(repo: str, title: str, *, run_gh_api_json_fn):
        captured["repo"] = repo
        captured["title"] = title
        captured["run_gh_api_json_fn"] = run_gh_api_json_fn
        return [{"number": 1}]

    monkeypatch.setattr(
        workflow_helpers._issue_alerts,
        "issue_payloads_by_title",
        fake_issue_payloads_by_title,
    )

    assert workflow_helpers._issue_payloads_by_title("owner/repo", "Alert") == [
        {"number": 1}
    ]
    assert captured["repo"] == "owner/repo"
    assert captured["title"] == "Alert"
    assert captured["run_gh_api_json_fn"] is workflow_helpers._run_gh_api_json
