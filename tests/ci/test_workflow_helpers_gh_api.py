from __future__ import annotations

import subprocess

import pytest

import scripts.ci.workflow_helpers as workflow_helpers
import scripts.lib.gh_api as gh_api
from scripts.lib import gh_policy
from tests.ci.workflow_helpers_test_support import FakeSubprocessResult


def test_is_retryable_gh_api_failure_matches_expected_cases() -> None:
    """Is retryable gh api failure matches expected cases."""
    assert gh_api.is_retryable_gh_api_failure("503 Service Unavailable")
    assert gh_api.is_retryable_gh_api_failure("timed out while calling API")
    assert gh_api.is_retryable_gh_api_failure("network error")
    assert not gh_api.is_retryable_gh_api_failure("404 Not Found")
    # Rate limits must never be treated as retryable; they fail fast instead.
    assert not gh_api.is_retryable_gh_api_failure("API rate limit exceeded (HTTP 429)")
    assert not gh_api.is_retryable_gh_api_failure("You have exceeded a secondary rate limit")


def test_is_rate_limited_gh_api_failure_matches_variants() -> None:
    """Is rate limited gh api failure matches variants."""
    assert gh_api.is_rate_limited_gh_api_failure("API rate limit exceeded")
    assert gh_api.is_rate_limited_gh_api_failure("gh: something failed (HTTP 429)")
    assert gh_api.is_rate_limited_gh_api_failure("You have exceeded a secondary rate limit")
    assert gh_api.is_rate_limited_gh_api_failure("triggered abuse detection")
    assert gh_api.is_rate_limited_gh_api_failure("content submitted too quickly")
    assert not gh_api.is_rate_limited_gh_api_failure("503 Service Unavailable")
    assert not gh_api.is_rate_limited_gh_api_failure("404 Not Found")


def test_run_gh_api_fails_fast_on_rate_limit_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api fails fast on rate limit without retry."""
    calls = 0
    sleep_calls: list[float] = []

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        nonlocal calls
        calls += 1
        result = FakeSubprocessResult(returncode=1)
        result.stderr = "gh: API rate limit exceeded (HTTP 429)"
        return result

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    monkeypatch.setattr(workflow_helpers.time, "sleep", sleep_calls.append)

    with pytest.raises(RuntimeError, match="GitHub rate limit hit"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo/pulls/1/files",
            paginate=["--paginate"],
            jq_expr=".[].filename",
            description="listing changed files for pull_request owner/repo",
        )

    # A single attempt, no backoff sleeps: the limit window must reset first.
    assert calls == 1
    assert sleep_calls == []


def test_run_gh_api_rate_limit_skips_permission_enrichment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api rate limit skips permission enrichment."""

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        result = FakeSubprocessResult(returncode=1)
        result.stderr = "gh: API rate limit exceeded (HTTP 403)"
        return result

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        workflow_helpers._run_gh_api(
            "repos/owner/repo",
            paginate=[],
            jq_expr=".",
            description="reading repository metadata for owner/repo",
            required_permission="metadata: read",
        )

    message = str(exc_info.value)
    assert "GitHub rate limit hit" in message
    assert "metadata: read" not in message
    assert "likely lacks" not in message


def test_run_gh_api_retries_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api retries transient failures."""
    calls = 0
    sleep_calls: list[float] = []

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        nonlocal calls
        calls += 1
        if calls == 1:
            result = FakeSubprocessResult(returncode=1)
            result.stderr = "503 Service Unavailable"
            return result
        return FakeSubprocessResult("apps/demo/index.html\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    monkeypatch.setattr(workflow_helpers.time, "sleep", sleep_calls.append)
    monkeypatch.setattr(gh_policy, "retry_backoff_seconds", lambda attempt: attempt + 1.25)

    stdout = workflow_helpers._run_gh_api(
        "repos/owner/repo/pulls/1/files",
        paginate=["--paginate"],
        jq_expr=".[].filename",
        description="listing changed files for pull_request owner/repo",
    )

    assert stdout == "apps/demo/index.html\n"
    assert calls == 2
    assert sleep_calls == [1.25]


def test_run_gh_api_retries_timeout_then_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api retries timeout then fails."""
    sleep_calls: list[float] = []

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        raise subprocess.TimeoutExpired(["gh", "api"], 15)

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    monkeypatch.setattr(workflow_helpers.time, "sleep", sleep_calls.append)
    monkeypatch.setattr(gh_policy, "retry_backoff_seconds", lambda attempt: attempt + 1.25)

    with pytest.raises(RuntimeError, match="timed out"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo/commits/abc123",
            paginate=[],
            jq_expr=".files[].filename",
            description="listing changed files for push owner/repo",
        )

    assert sleep_calls == [1.25, 2.25]


def test_run_gh_api_fails_fast_for_non_retryable_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api fails fast for non retryable errors."""

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
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
    """Run gh api uses final fallback when attempts disabled."""
    monkeypatch.setattr(workflow_helpers._gh_api, "GH_API_MAX_ATTEMPTS", 0)

    with pytest.raises(RuntimeError, match="unknown error"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo/commits/abc123",
            paginate=[],
            jq_expr=".files[].filename",
            description="listing changed files for push owner/repo",
        )


def test_run_gh_api_json_parses_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run gh api json parses payload."""
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *_args, **_kwargs: '{"ok": true}',
    )

    assert workflow_helpers._run_gh_api_json(
        "repos/owner/repo", description="reading repository metadata"
    ) == {"ok": True}


def test_run_gh_api_json_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run gh api json rejects invalid json."""
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *_args, **_kwargs: "not-json",
    )

    with pytest.raises(RuntimeError, match="returned invalid JSON"):
        workflow_helpers._run_gh_api_json(
            "repos/owner/repo", description="reading repository metadata"
        )


def test_run_gh_api_enriches_403_with_required_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api enriches 403 with required permission."""

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        result = FakeSubprocessResult(returncode=1)
        result.stderr = "HTTP 403: Resource not accessible by integration"
        return result

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="'administration: read'"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo/branches/main/protection",
            paginate=[],
            jq_expr=".",
            description="reading branch protection for owner/repo:main",
            required_permission="administration: read",
        )


def test_run_gh_api_hints_generic_on_403_without_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api hints generic on 403 without permission."""

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        result = FakeSubprocessResult(returncode=1)
        result.stderr = "gh: Resource not accessible by integration (HTTP 403)"
        return result

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="Token likely lacks required permission"):
        workflow_helpers._run_gh_api(
            "repos/owner/repo",
            paginate=[],
            jq_expr=".",
            description="reading repository metadata for owner/repo",
        )


def test_run_gh_api_does_not_enrich_non_403_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api does not enrich non 403 errors."""

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        result = FakeSubprocessResult(returncode=1)
        result.stderr = "404 Not Found"
        return result

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        workflow_helpers._run_gh_api(
            "repos/owner/repo/branches/main/protection",
            paginate=[],
            jq_expr=".",
            description="reading branch protection for owner/repo:main",
            required_permission="administration: read",
        )

    message = str(exc_info.value)
    assert "404 Not Found" in message
    assert "administration: read" not in message
    assert "likely lacks" not in message


def test_run_gh_api_does_not_misdiagnose_rate_limit_403(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api does not misdiagnose rate limit 403."""

    def fake_run(*_args: object, **_kwargs: object) -> FakeSubprocessResult:
        result = FakeSubprocessResult(returncode=1)
        result.stderr = "gh: API rate limit exceeded (HTTP 403)"
        return result

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as exc_info:
        workflow_helpers._run_gh_api(
            "repos/owner/repo",
            paginate=[],
            jq_expr=".",
            description="reading repository metadata for owner/repo",
            required_permission="metadata: read",
        )

    message = str(exc_info.value)
    assert "API rate limit exceeded" in message
    assert "metadata: read" not in message
    assert "likely lacks" not in message


def test_is_forbidden_gh_api_failure_matches_variants() -> None:
    """Is forbidden gh api failure matches variants."""
    assert gh_api.is_forbidden_gh_api_failure("Resource not accessible by integration")
    assert gh_api.is_forbidden_gh_api_failure("resource NOT accessible BY integration")
    assert gh_api.is_forbidden_gh_api_failure(
        "gh: Resource not accessible by integration (HTTP 403)"
    )
    assert not gh_api.is_forbidden_gh_api_failure("gh: API rate limit exceeded (HTTP 403)")
    assert not gh_api.is_forbidden_gh_api_failure(
        "gh: You have exceeded a secondary rate limit (HTTP 403)"
    )
    assert not gh_api.is_forbidden_gh_api_failure(
        "gh: Resource protected by organization SAML enforcement (HTTP 403)"
    )
    assert not gh_api.is_forbidden_gh_api_failure("HTTP 403: denied")
    assert not gh_api.is_forbidden_gh_api_failure("4030 requests queued")
    assert not gh_api.is_forbidden_gh_api_failure("404 Not Found")
    assert not gh_api.is_forbidden_gh_api_failure("500 Internal Server Error")


def test_run_gh_api_form_posts_fields_with_shared_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api form posts fields with shared helper."""
    captured = {}

    def fake_run_gh_api_form(
        endpoint: str,
        *,
        method: str,
        fields: list[tuple[str, str]],
        description: str,
        jq_expr: str = "",
        max_attempts: int,
        timeout_seconds: float,
        required_permission: str | None = None,
        **_kwargs: object,
    ) -> str:
        captured["endpoint"] = endpoint
        captured["method"] = method
        captured["fields"] = fields
        captured["description"] = description
        captured["jq_expr"] = jq_expr
        captured["max_attempts"] = max_attempts
        captured["timeout_seconds"] = timeout_seconds
        captured["required_permission"] = required_permission
        return "https://example.com/issues/1"

    monkeypatch.setattr(workflow_helpers._gh_api, "run_gh_api_form", fake_run_gh_api_form)

    result = workflow_helpers._run_gh_api_form(
        "repos/owner/repo/issues",
        method="POST",
        fields=[("title", "Alert"), ("labels[]", "ci")],
        description="creating alert issue",
        jq_expr=".html_url",
        required_permission="issues: write",
    )

    assert result == "https://example.com/issues/1"
    assert captured == {
        "endpoint": "repos/owner/repo/issues",
        "method": "POST",
        "fields": [("title", "Alert"), ("labels[]", "ci")],
        "description": "creating alert issue",
        "jq_expr": ".html_url",
        "max_attempts": gh_api.GH_API_MAX_ATTEMPTS,
        "timeout_seconds": gh_api.GH_API_TIMEOUT_SECONDS,
        "required_permission": "issues: write",
    }


def test_run_gh_api_form_escapes_leading_at_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api form escapes leading at values."""
    captured = {}

    def fake_run_gh_command(
        command: list[str],
        **_kwargs: object,
    ) -> str:
        captured["command"] = command
        return "ok"

    monkeypatch.setattr(workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command)

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
    """Low level run gh api form appends jq expression."""
    captured = {}

    def fake_run_gh_command(
        command: list[str],
        **_kwargs: object,
    ) -> str:
        captured["command"] = command
        return "ok"

    monkeypatch.setattr(workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command)

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
    """Run gh api form omits jq when not requested."""
    captured = {}

    def fake_run_gh_command(
        command: list[str],
        **_kwargs: object,
    ) -> str:
        captured["command"] = command
        return "ok"

    monkeypatch.setattr(workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command)

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


def test_run_gh_api_form_forwards_required_permission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api form forwards required permission."""
    captured = {}

    def fake_run_gh_command(
        _command: list[str],
        *,
        required_permission: str | None = None,
        **_kwargs: object,
    ) -> str:
        captured["required_permission"] = required_permission
        return "ok"

    monkeypatch.setattr(workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command)

    workflow_helpers._gh_api.run_gh_api_form(
        "repos/owner/repo/issues",
        method="POST",
        fields=[("title", "Alert")],
        description="creating alert issue",
        required_permission="issues: write",
    )

    assert captured["required_permission"] == "issues: write"


def test_run_gh_api_form_passes_custom_subprocess_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run gh api form passes custom subprocess module."""
    captured = {}
    fake_subprocess_module = object()

    def fake_run_gh_command(
        _command: list[str],
        *,
        subprocess_module,
        **_kwargs: object,
    ) -> str:
        captured["subprocess_module"] = subprocess_module
        return "ok"

    monkeypatch.setattr(workflow_helpers._gh_api, "_run_gh_command", fake_run_gh_command)

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
    """Sync alert issue delegates to issue alerts module."""
    captured = {}

    def fake_sync_alert_issue(**kwargs) -> str:
        captured.update(kwargs)
        return "https://github.com/owner/repo/issues/7"

    monkeypatch.setattr(workflow_helpers._issue_alerts, "sync_alert_issue", fake_sync_alert_issue)

    issue_url = workflow_helpers.sync_alert_issue(
        repo="owner/repo",
        title="Artifact alert",
        body="Updated body",
        labels=["ci"],
        should_exist=True,
    )

    assert issue_url == "https://github.com/owner/repo/issues/7"
    assert captured["repo"] == "owner/repo"
    assert captured["title"] == "Artifact alert"
    assert captured["body"] == "Updated body"
    assert captured["labels"] == ["ci"]
    assert captured["should_exist"] is True
    assert captured["issue_payloads_by_title_fn"] is workflow_helpers._issue_payloads_by_title
    assert captured["run_gh_api_form_fn"] is workflow_helpers._run_gh_api_form


def test_issue_payloads_by_title_delegates_to_issue_alerts_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Issue payloads by title delegates to issue alerts module."""
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

    assert workflow_helpers._issue_payloads_by_title("owner/repo", "Alert") == [{"number": 1}]
    assert captured["repo"] == "owner/repo"
    assert captured["title"] == "Alert"
    assert captured["run_gh_api_json_fn"] is workflow_helpers._run_gh_api_json
