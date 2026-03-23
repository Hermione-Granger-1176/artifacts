from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import scripts.workflow_helpers as workflow_helpers


class FakeSubprocessResult:
    """Reusable fake for subprocess.run return values."""

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_bool_accepts_common_values() -> None:
    assert workflow_helpers._parse_bool("true") is True
    assert workflow_helpers._parse_bool("1") is True
    assert workflow_helpers._parse_bool("false") is False
    assert workflow_helpers._parse_bool("0") is False


def test_parse_bool_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="Invalid boolean value"):
        workflow_helpers._parse_bool("maybe")


def test_app_token_allowed_for_non_pull_request_events() -> None:
    assert workflow_helpers.app_token_allowed(
        event_name="push", head_repo_fork=False, pr_author="dependabot[bot]"
    )


def test_app_token_allowed_rejects_forks_and_dependabot_prs() -> None:
    assert (
        workflow_helpers.app_token_allowed(
            event_name="pull_request", head_repo_fork=True, pr_author="alice"
        )
        is False
    )
    assert (
        workflow_helpers.app_token_allowed(
            event_name="pull_request",
            head_repo_fork=False,
            pr_author="dependabot[bot]",
        )
        is False
    )
    assert (
        workflow_helpers.app_token_allowed(
            event_name="pull_request", head_repo_fork=False, pr_author="alice"
        )
        is True
    )


def test_read_lock_refresh_metadata_reads_required_values(tmp_path: Path) -> None:
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/pip/demo\n")

    assert workflow_helpers.read_lock_refresh_metadata(tmp_path) == {
        "head-ref": "dependabot/pip/demo",
        "head-sha": "abc123",
        "pr-number": "8",
    }


def test_validate_lock_refresh_artifact_accepts_expected_files(tmp_path: Path) -> None:
    write_text(tmp_path / "locks" / "requirements.lock", "pkg==1.0\n")
    write_text(tmp_path / "locks" / "requirements-dev.lock", "pkg==1.0\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/pip/demo\n")

    workflow_helpers.validate_lock_refresh_artifact(tmp_path)


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_validate_lock_refresh_artifact_rejects_symlinks(tmp_path: Path) -> None:
    write_text(tmp_path / "locks" / "requirements.lock", "pkg==1.0\n")
    write_text(tmp_path / "locks" / "requirements-dev.lock", "pkg==1.0\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/pip/demo\n")
    linked = tmp_path / "linked.txt"
    write_text(linked, "secret\n")
    (tmp_path / ".artifacts" / "escape.txt").symlink_to(linked)

    with pytest.raises(ValueError, match="Refusing artifact containing symlink"):
        workflow_helpers.validate_lock_refresh_artifact(tmp_path)


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_validate_lock_refresh_artifact_rejects_symlinked_directories(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "locks" / "requirements.lock", "pkg==1.0\n")
    write_text(tmp_path / "locks" / "requirements-dev.lock", "pkg==1.0\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/pip/demo\n")
    linked_dir = tmp_path / "linked-dir"
    linked_dir.mkdir()
    (tmp_path / ".artifacts" / "nested-link").symlink_to(
        linked_dir, target_is_directory=True
    )

    with pytest.raises(ValueError, match="Refusing artifact containing symlink"):
        workflow_helpers.validate_lock_refresh_artifact(tmp_path)


def test_validate_lock_refresh_artifact_rejects_missing_files(tmp_path: Path) -> None:
    write_text(tmp_path / "locks" / "requirements.lock", "pkg==1.0\n")

    with pytest.raises(
        ValueError, match="Required artifact file missing or not a regular file"
    ):
        workflow_helpers.validate_lock_refresh_artifact(tmp_path)


def test_main_app_token_policy_prints_allowed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = workflow_helpers.main(
        [
            "app-token-policy",
            "--event-name",
            "pull_request",
            "--head-repo-fork",
            "false",
            "--pr-author",
            "alice",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "allowed=true"


def test_main_read_lock_metadata_prints_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/pip/demo\n")

    exit_code = workflow_helpers.main(["read-lock-metadata", "--root", str(tmp_path)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "head-ref": "dependabot/pip/demo",
        "head-sha": "abc123",
        "pr-number": "8",
    }


def test_main_validate_lock_artifact_returns_zero(tmp_path: Path) -> None:
    write_text(tmp_path / "locks" / "requirements.lock", "pkg==1.0\n")
    write_text(tmp_path / "locks" / "requirements-dev.lock", "pkg==1.0\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/pip/demo\n")

    assert (
        workflow_helpers.main(["validate-lock-artifact", "--root", str(tmp_path)]) == 0
    )


def test_check_fallback_detects_pull_request_url() -> None:
    assert (
        workflow_helpers.check_fallback("https://github.com/owner/repo/pull/42") is True
    )


def test_check_fallback_detects_commit_url() -> None:
    assert (
        workflow_helpers.check_fallback("https://github.com/owner/repo/commit/abc123")
        is False
    )


def test_check_fallback_handles_empty_url() -> None:
    assert workflow_helpers.check_fallback("") is False


def test_invalidate_thumbnails_deletes_stale_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "apps" / "my-app"
    app_dir.mkdir(parents=True)
    thumb = app_dir / "thumbnail.webp"
    thumb.write_bytes(b"old")

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        return FakeSubprocessResult("apps/my-app/index.html\nREADME.md\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    result = workflow_helpers.invalidate_thumbnails(
        event_name="pull_request", repo="owner/repo", pr_number="1", commit_sha=""
    )
    assert result == ["apps/my-app/thumbnail.webp"]
    assert not thumb.exists()


def test_invalidate_thumbnails_uses_commits_api_for_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "apps" / "calculator"
    app_dir.mkdir(parents=True)
    thumb = app_dir / "thumbnail.webp"
    thumb.write_bytes(b"old")

    captured_cmd: list[object] = []

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        command = args[0] if args else []
        if isinstance(command, list):
            captured_cmd.extend(command)
        return FakeSubprocessResult("apps/calculator/index.html\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    workflow_helpers.invalidate_thumbnails(
        event_name="push", repo="owner/repo", pr_number="", commit_sha="abc123"
    )
    assert "repos/owner/repo/commits/abc123" in captured_cmd
    assert "--paginate" not in captured_cmd
    assert ".files[].filename" in captured_cmd
    assert not thumb.exists()


def test_invalidate_thumbnails_skips_blank_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        return FakeSubprocessResult("\n\nREADME.md\n\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    result = workflow_helpers.invalidate_thumbnails(
        event_name="push", repo="owner/repo", pr_number="", commit_sha="abc"
    )
    assert result == []


def test_invalidate_thumbnails_skips_non_index_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "apps" / "my-app"
    app_dir.mkdir(parents=True)
    thumb = app_dir / "thumbnail.webp"
    thumb.write_bytes(b"keep")

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        return FakeSubprocessResult("apps/my-app/styles.css\nREADME.md\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    result = workflow_helpers.invalidate_thumbnails(
        event_name="pull_request", repo="owner/repo", pr_number="1", commit_sha=""
    )
    assert result == []
    assert thumb.exists()


def test_invalidate_thumbnails_skips_missing_thumbnail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "apps" / "new-app"
    app_dir.mkdir(parents=True)

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        return FakeSubprocessResult("apps/new-app/index.html\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    result = workflow_helpers.invalidate_thumbnails(
        event_name="pull_request", repo="owner/repo", pr_number="1", commit_sha=""
    )
    assert result == []


def test_is_retryable_gh_api_failure_matches_expected_cases() -> None:
    assert workflow_helpers._is_retryable_gh_api_failure("503 Service Unavailable")
    assert workflow_helpers._is_retryable_gh_api_failure("timed out while calling API")
    assert workflow_helpers._is_retryable_gh_api_failure("network error")
    assert not workflow_helpers._is_retryable_gh_api_failure("404 Not Found")


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
    assert sleep_calls == [workflow_helpers.GH_API_RETRY_DELAY_SECONDS]


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
        workflow_helpers.GH_API_RETRY_DELAY_SECONDS,
        workflow_helpers.GH_API_RETRY_DELAY_SECONDS * 2,
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
    monkeypatch.setattr(workflow_helpers, "GH_API_MAX_ATTEMPTS", 0)

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


def test_collect_named_items_skips_non_lists_and_non_dict_entries() -> None:
    assert (
        workflow_helpers._collect_named_items({"variables": "invalid"}, "variables")
        == set()
    )
    assert workflow_helpers._collect_named_items(
        {"variables": ["bad", {"name": "APP_ID"}, {"name": 9}]}, "variables"
    ) == {"APP_ID"}


def test_extract_required_checks_handles_contexts_and_checks() -> None:
    assert workflow_helpers._extract_required_checks(
        {
            "required_status_checks": {
                "contexts": ["verify", "secret-scan"],
                "checks": [{"context": "dependency-review"}, {"context": 9}],
            }
        }
    ) == {"verify", "secret-scan", "dependency-review"}


def test_extract_required_checks_handles_missing_data() -> None:
    assert workflow_helpers._extract_required_checks(None) == set()
    assert workflow_helpers._extract_required_checks({}) == set()


def test_ruleset_targets_branch_detects_exact_refs() -> None:
    assert workflow_helpers._ruleset_targets_branch(
        {
            "target": "branch",
            "conditions": {"ref_name": {"include": ["main", "refs/heads/gh-pages"]}},
        },
        "gh-pages",
    )


def test_ruleset_targets_branch_rejects_non_matching_rulesets() -> None:
    assert (
        workflow_helpers._ruleset_targets_branch(
            {
                "target": "tag",
                "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            },
            "gh-pages",
        )
        is False
    )
    assert workflow_helpers._ruleset_targets_branch({}, "gh-pages") is False


def test_ruleset_targets_branch_rejects_malformed_conditions() -> None:
    assert (
        workflow_helpers._ruleset_targets_branch(
            {"target": "branch", "conditions": []}, "gh-pages"
        )
        is False
    )
    assert (
        workflow_helpers._ruleset_targets_branch(
            {"target": "branch", "conditions": {"ref_name": []}}, "gh-pages"
        )
        is False
    )
    assert (
        workflow_helpers._ruleset_targets_branch(
            {
                "target": "branch",
                "conditions": {"ref_name": {"include": "refs/heads/gh-pages"}},
            },
            "gh-pages",
        )
        is False
    )


def test_audit_repo_settings_returns_expected_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {"source": {"branch": "gh-pages", "path": "/"}},
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {
                "contexts": ["verify", "secret-scan", "dependency-review"]
            },
            "required_pull_request_reviews": {"required_approving_review_count": 1},
            "required_signatures": {"enabled": True},
            "required_linear_history": {"enabled": True},
            "required_conversation_resolution": {"enabled": True},
        },
        "repos/owner/repo/actions/variables": {
            "variables": [
                {"name": "APP_ID"},
                {"name": "ESCALATION_APP_ID"},
            ]
        },
        "repos/owner/repo/actions/secrets": {
            "secrets": [
                {"name": "APP_PRIVATE_KEY"},
                {"name": "ESCALATION_APP_PRIVATE_KEY"},
            ]
        },
        "repos/owner/repo/rulesets": [
            {
                "target": "branch",
                "conditions": {"ref_name": {"include": ["refs/heads/gh-pages"]}},
            }
        ],
    }

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    assert workflow_helpers.audit_repo_settings(repo="owner/repo") == {
        "default-branch": "main",
        "gh-pages-ruleset": True,
        "pages-branch": "gh-pages",
        "pages-path": "/",
        "required-checks": ["dependency-review", "secret-scan", "verify"],
    }


def test_audit_repo_settings_rejects_unexpected_response_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": [],
        "repos/owner/repo/pages": {"source": {"branch": "gh-pages", "path": "/"}},
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Repository metadata must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_pages_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": [],
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Pages settings must be a JSON object"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_protection_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {"source": {"branch": "gh-pages", "path": "/"}},
        "repos/owner/repo/branches/main/protection": [],
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        RuntimeError, match="Branch protection settings must be a JSON object"
    ):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_variables_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {"source": {"branch": "gh-pages", "path": "/"}},
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": [],
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        RuntimeError, match="Actions variables response must be a JSON object"
    ):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_secrets_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {"source": {"branch": "gh-pages", "path": "/"}},
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": [],
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        RuntimeError, match="Actions secrets response must be a JSON object"
    ):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_rejects_invalid_rulesets_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "main"},
        "repos/owner/repo/pages": {"source": {"branch": "gh-pages", "path": "/"}},
        "repos/owner/repo/branches/main/protection": {},
        "repos/owner/repo/actions/variables": {"variables": []},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": {},
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(RuntimeError, match="Rulesets response must be a JSON array"):
        workflow_helpers.audit_repo_settings(repo="owner/repo")


def test_audit_repo_settings_reports_configuration_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "repos/owner/repo": {"default_branch": "trunk"},
        "repos/owner/repo/pages": {"source": {"branch": "docs", "path": "/site"}},
        "repos/owner/repo/branches/main/protection": {
            "required_status_checks": {"contexts": ["verify"]},
            "required_pull_request_reviews": {"required_approving_review_count": 0},
            "required_signatures": {"enabled": False},
            "required_linear_history": {"enabled": False},
            "required_conversation_resolution": {"enabled": False},
        },
        "repos/owner/repo/actions/variables": {"variables": [{"name": "APP_ID"}]},
        "repos/owner/repo/actions/secrets": {"secrets": []},
        "repos/owner/repo/rulesets": [],
    }
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda endpoint, description: responses[endpoint],
    )

    with pytest.raises(
        ValueError, match="Repository settings audit failed"
    ) as exc_info:
        workflow_helpers.audit_repo_settings(repo="owner/repo")

    message = str(exc_info.value)
    assert "default branch is 'trunk' instead of 'main'" in message
    assert "Pages source branch is 'docs' instead of 'gh-pages'" in message
    assert "missing repository variables: ESCALATION_APP_ID" in message
    assert (
        "missing repository secrets: APP_PRIVATE_KEY, ESCALATION_APP_PRIVATE_KEY"
        in message
    )
    assert "no branch ruleset explicitly targets 'gh-pages'" in message


def test_main_check_fallback_prints_true(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = workflow_helpers.main(
        ["check-fallback", "--result-url", "https://github.com/o/r/pull/1"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "fallback=true"


def test_main_check_fallback_prints_false(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = workflow_helpers.main(
        ["check-fallback", "--result-url", "https://github.com/o/r/commit/abc"]
    )
    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "fallback=false"


def test_main_invalidate_thumbnails_returns_zero(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)

    def fake_run(*args: object, **kwargs: object) -> FakeSubprocessResult:
        return FakeSubprocessResult()

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    exit_code = workflow_helpers.main(
        [
            "invalidate-thumbnails",
            "--event-name",
            "push",
            "--repo",
            "owner/repo",
            "--commit-sha",
            "abc123",
        ]
    )
    assert exit_code == 0
    assert "No thumbnails invalidated" in capsys.readouterr().out


def test_main_rejects_unknown_command(monkeypatch: pytest.MonkeyPatch) -> None:
    import argparse

    fake_ns = argparse.Namespace(command="nonexistent")
    monkeypatch.setattr(
        workflow_helpers,
        "_build_parser",
        lambda: type("P", (), {"parse_args": lambda self, argv=None: fake_ns})(),
    )
    with pytest.raises(ValueError, match="Unsupported command"):
        workflow_helpers.main([])


def test_main_audit_repo_settings_prints_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        workflow_helpers,
        "audit_repo_settings",
        lambda repo, default_branch, pages_branch: {
            "default-branch": default_branch,
            "pages-branch": pages_branch,
            "repo": repo,
        },
    )

    exit_code = workflow_helpers.main(
        [
            "audit-repo-settings",
            "--repo",
            "owner/repo",
            "--default-branch",
            "main",
            "--pages-branch",
            "gh-pages",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "default-branch": "main",
        "pages-branch": "gh-pages",
        "repo": "owner/repo",
    }
