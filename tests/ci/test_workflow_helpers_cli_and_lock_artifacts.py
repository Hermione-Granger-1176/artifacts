from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ci.workflow_helpers as workflow_helpers
from tests.ci.workflow_helpers_test_support import write_text

LOCK_PR_NUMBER = "8"
LOCK_HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"
LOCK_HEAD_REF = "dependabot/uv/demo"


def _write_lock_refresh_artifact(
    root: Path,
    *,
    pr_number: str = LOCK_PR_NUMBER,
    head_sha: str = LOCK_HEAD_SHA,
    head_ref: str = LOCK_HEAD_REF,
) -> None:
    """Write a complete lock-refresh artifact fixture."""
    write_text(root / "uv.lock", "version = 1\n")
    write_text(root / ".artifacts" / "pr-number.txt", f"{pr_number}\n")
    write_text(root / ".artifacts" / "head-sha.txt", f"{head_sha}\n")
    write_text(root / ".artifacts" / "head-ref.txt", f"{head_ref}\n")


def _workflow_run_event(
    *,
    actor: str = "dependabot[bot]",
    head_repository: str = "owner/artifacts",
    pr_number: int = 8,
    head_sha: str = LOCK_HEAD_SHA,
    head_ref: str = LOCK_HEAD_REF,
) -> dict[str, object]:
    """Build the trusted workflow-run event shape used by the lock writer."""
    return {
        "workflow_run": {
            "actor": {"login": actor},
            "conclusion": "success",
            "event": "pull_request",
            "head_branch": head_ref,
            "head_repository": {"full_name": head_repository},
            "head_sha": head_sha,
            "id": 42,
            "name": "Refresh Python Locks",
            "pull_requests": [{"number": pr_number}],
        }
    }


def test_parse_bool_accepts_common_values() -> None:
    """Test parse bool accepts common values."""
    assert workflow_helpers._parse_bool("true") is True
    assert workflow_helpers._parse_bool("1") is True
    assert workflow_helpers._parse_bool("false") is False
    assert workflow_helpers._parse_bool("0") is False


def test_parse_bool_rejects_invalid_values() -> None:
    """Test parse bool rejects invalid values."""
    with pytest.raises(ValueError, match="Invalid boolean value"):
        workflow_helpers._parse_bool("maybe")


def test_app_token_allowed_for_non_pull_request_events() -> None:
    """Test app token allowed for non pull request events."""
    assert workflow_helpers.app_token_allowed(
        event_name="push", head_repo_fork=False, pr_author="dependabot[bot]"
    )


def test_app_token_allowed_rejects_forks_and_dependabot_prs() -> None:
    """Test app token allowed rejects forks and dependabot prs."""
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
    """Test read lock refresh metadata reads required values."""
    _write_lock_refresh_artifact(tmp_path)

    assert workflow_helpers.read_lock_refresh_metadata(tmp_path) == {
        "head-ref": LOCK_HEAD_REF,
        "head-sha": LOCK_HEAD_SHA,
        "pr-number": LOCK_PR_NUMBER,
    }


def test_validate_lock_refresh_artifact_accepts_expected_files(tmp_path: Path) -> None:
    """Test validate lock refresh artifact accepts expected files."""
    _write_lock_refresh_artifact(tmp_path)

    workflow_helpers.validate_lock_refresh_artifact(
        tmp_path,
        expected_pr_number=LOCK_PR_NUMBER,
        expected_head_sha=LOCK_HEAD_SHA,
        expected_head_ref=LOCK_HEAD_REF,
    )


def test_lock_refresh_workflow_run_context_accepts_dependabot_event(tmp_path: Path) -> None:
    """Accept the authenticated source values for one Dependabot lock refresh."""
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_workflow_run_event()), encoding="utf-8")

    assert workflow_helpers.lock_refresh_workflow_run_context(
        event_path, repository="owner/artifacts"
    ) == {
        "artifact-name": "python-lock-refresh-8",
        "head-ref": LOCK_HEAD_REF,
        "head-sha": LOCK_HEAD_SHA,
        "pr-number": LOCK_PR_NUMBER,
        "run-id": "42",
    }


@pytest.mark.parametrize(
    ("actor", "head_repository", "message"),
    [
        ("alice", "owner/artifacts", "not started by Dependabot"),
        ("dependabot[bot]", "attacker/artifacts", "did not originate from this repository"),
    ],
)
def test_lock_refresh_workflow_run_context_rejects_untrusted_source(
    tmp_path: Path, actor: str, head_repository: str, message: str
) -> None:
    """Reject a non-Dependabot or non-same-repository triggering run."""
    event_path = tmp_path / "event.json"
    event_path.write_text(
        json.dumps(_workflow_run_event(actor=actor, head_repository=head_repository)),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        workflow_helpers.lock_refresh_workflow_run_context(event_path, repository="owner/artifacts")


@pytest.mark.parametrize(
    ("pr_number", "head_sha", "head_ref"),
    [
        ("$(printf injected)", LOCK_HEAD_SHA, LOCK_HEAD_REF),
        ("9", LOCK_HEAD_SHA, LOCK_HEAD_REF),
    ],
)
def test_validate_lock_refresh_artifact_rejects_metadata_not_bound_to_event(
    tmp_path: Path, pr_number: str, head_sha: str, head_ref: str
) -> None:
    """Reject raw shell syntax and valid-looking metadata for another target."""
    _write_lock_refresh_artifact(
        tmp_path,
        pr_number=pr_number,
        head_sha=head_sha,
        head_ref=head_ref,
    )

    with pytest.raises(ValueError, match="does not match triggering workflow run"):
        workflow_helpers.validate_lock_refresh_artifact(
            tmp_path,
            expected_pr_number=LOCK_PR_NUMBER,
            expected_head_sha=LOCK_HEAD_SHA,
            expected_head_ref=LOCK_HEAD_REF,
        )


def test_validate_lock_refresh_artifact_rejects_malformed_authenticated_context(
    tmp_path: Path,
) -> None:
    """Reject malformed event data before accepting matching artifact metadata."""
    _write_lock_refresh_artifact(tmp_path)

    with pytest.raises(ValueError, match="Invalid authenticated lock refresh head-sha"):
        workflow_helpers.validate_lock_refresh_artifact(
            tmp_path,
            expected_pr_number=LOCK_PR_NUMBER,
            expected_head_sha="not-a-sha",
            expected_head_ref=LOCK_HEAD_REF,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ([], "must be an object"),
        ({}, "missing workflow_run"),
    ],
)
def test_lock_refresh_workflow_run_context_rejects_missing_payload_shape(
    tmp_path: Path, payload: object, message: str
) -> None:
    """Reject event documents that lack a usable workflow-run object."""
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        workflow_helpers.lock_refresh_workflow_run_context(event_path, repository="owner/artifacts")


def test_lock_refresh_workflow_run_context_rejects_unexpected_run(tmp_path: Path) -> None:
    """Reject a run that did not successfully complete the expected workflow."""
    payload = _workflow_run_event()
    workflow_run = payload["workflow_run"]
    assert isinstance(workflow_run, dict)
    workflow_run["conclusion"] = "failure"
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Unexpected lock refresh workflow run"):
        workflow_helpers.lock_refresh_workflow_run_context(event_path, repository="owner/artifacts")


@pytest.mark.parametrize(
    ("pull_requests", "message"),
    [
        ([], "exactly one pull request"),
        ([None], "invalid shape"),
        ([{"number": 0}], "invalid numeric identifier"),
    ],
)
def test_lock_refresh_workflow_run_context_rejects_invalid_pull_request(
    tmp_path: Path, pull_requests: list[object], message: str
) -> None:
    """Reject malformed or unusable triggering pull-request data."""
    payload = _workflow_run_event()
    workflow_run = payload["workflow_run"]
    assert isinstance(workflow_run, dict)
    workflow_run["pull_requests"] = pull_requests
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        workflow_helpers.lock_refresh_workflow_run_context(event_path, repository="owner/artifacts")


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_validate_lock_refresh_artifact_rejects_symlinks(tmp_path: Path) -> None:
    """Test validate lock refresh artifact rejects symlinks."""
    _write_lock_refresh_artifact(tmp_path)
    linked = tmp_path / "linked.txt"
    write_text(linked, "secret\n")
    (tmp_path / ".artifacts" / "escape.txt").symlink_to(linked)

    with pytest.raises(ValueError, match="Refusing to process tree containing symlink"):
        workflow_helpers.validate_lock_refresh_artifact(
            tmp_path,
            expected_pr_number=LOCK_PR_NUMBER,
            expected_head_sha=LOCK_HEAD_SHA,
            expected_head_ref=LOCK_HEAD_REF,
        )


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_validate_lock_refresh_artifact_rejects_symlinked_directories(
    tmp_path: Path,
) -> None:
    """Test validate lock refresh artifact rejects symlinked directories."""
    _write_lock_refresh_artifact(tmp_path)
    linked_dir = tmp_path / "linked-dir"
    linked_dir.mkdir()
    (tmp_path / ".artifacts" / "nested-link").symlink_to(linked_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="Refusing to process tree containing symlink"):
        workflow_helpers.validate_lock_refresh_artifact(
            tmp_path,
            expected_pr_number=LOCK_PR_NUMBER,
            expected_head_sha=LOCK_HEAD_SHA,
            expected_head_ref=LOCK_HEAD_REF,
        )


def test_validate_lock_refresh_artifact_rejects_missing_files(tmp_path: Path) -> None:
    """Test validate lock refresh artifact rejects missing files."""
    write_text(tmp_path / "uv.lock", "version = 1\n")

    with pytest.raises(ValueError, match="Required artifact file missing or not a regular file"):
        workflow_helpers.validate_lock_refresh_artifact(
            tmp_path,
            expected_pr_number=LOCK_PR_NUMBER,
            expected_head_sha=LOCK_HEAD_SHA,
            expected_head_ref=LOCK_HEAD_REF,
        )


def test_main_app_token_policy_prints_allowed(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test main app token policy prints allowed."""
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
    """Test main read lock metadata prints json."""
    _write_lock_refresh_artifact(tmp_path)

    exit_code = workflow_helpers.main(["read-lock-metadata", "--root", str(tmp_path)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "head-ref": LOCK_HEAD_REF,
        "head-sha": LOCK_HEAD_SHA,
        "pr-number": LOCK_PR_NUMBER,
    }


def test_main_validate_lock_artifact_returns_zero(tmp_path: Path) -> None:
    """Test main validate lock artifact returns zero."""
    _write_lock_refresh_artifact(tmp_path)

    assert (
        workflow_helpers.main(
            [
                "validate-lock-artifact",
                "--root",
                str(tmp_path),
                "--expected-pr-number",
                LOCK_PR_NUMBER,
                "--expected-head-sha",
                LOCK_HEAD_SHA,
                "--expected-head-ref",
                LOCK_HEAD_REF,
            ]
        )
        == 0
    )


def test_main_lock_refresh_workflow_run_prints_validated_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the event command emits only validated lock-refresh context."""
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_workflow_run_event()), encoding="utf-8")

    assert (
        workflow_helpers.main(
            [
                "lock-refresh-workflow-run",
                "--event-path",
                str(event_path),
                "--repository",
                "owner/artifacts",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out.splitlines() == [
        "artifact-name=python-lock-refresh-8",
        f"head-ref={LOCK_HEAD_REF}",
        f"head-sha={LOCK_HEAD_SHA}",
        "pr-number=8",
        "run-id=42",
    ]


def test_main_rejects_unknown_command(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main rejects unknown command."""
    import argparse

    fake_ns = argparse.Namespace(command="nonexistent")
    monkeypatch.setattr(
        workflow_helpers,
        "_build_parser",
        lambda: type("P", (), {"parse_args": lambda _self, _argv=None: fake_ns})(),
    )
    with pytest.raises(ValueError, match="Unsupported command"):
        workflow_helpers.main([])


def test_main_plan_outputs_flattens_plan_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the plan-outputs command flattens the plan JSON."""
    plan = {
        "browser_scope": "changed",
        "changed_slugs": ["demo", "other"],
        "thumbnail_scope": "changed",
        "thumbnail_slugs": ["demo"],
        "persist_mode": "pr-branch",
        "reason": "runtime files changed",
        "skip_verification": False,
    }
    monkeypatch.setenv("PLAN_JSON", json.dumps(plan))

    assert workflow_helpers.main(["plan-outputs"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "browser-scope=changed",
        "changed-slugs=demo,other",
        "thumbnail-scope=changed",
        "thumbnail-slugs=demo",
        "persist-mode=pr-branch",
        "reason=runtime files changed",
        "skip-verification=false",
    ]


def test_main_plan_outputs_reports_true_skip_verification(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main plan outputs reports true skip verification."""
    plan = {
        "browser_scope": "none",
        "changed_slugs": [],
        "thumbnail_scope": "none",
        "thumbnail_slugs": [],
        "persist_mode": "none",
        "reason": "no runtime changes",
        "skip_verification": True,
    }
    monkeypatch.setenv("PLAN_JSON", json.dumps(plan))

    assert workflow_helpers.main(["plan-outputs"]) == 0
    assert "skip-verification=true" in capsys.readouterr().out.splitlines()


def test_main_plan_outputs_requires_plan_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main plan outputs requires plan json."""
    monkeypatch.delenv("PLAN_JSON", raising=False)
    with pytest.raises(ValueError, match="PLAN_JSON environment variable is required"):
        workflow_helpers.main(["plan-outputs"])


def test_main_plan_outputs_rejects_non_object_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test main plan outputs rejects non object payload."""
    monkeypatch.setenv("PLAN_JSON", "[]")
    with pytest.raises(ValueError, match="PLAN_JSON must be a JSON object"):
        workflow_helpers.main(["plan-outputs"])


def test_plan_output_lines_rejects_malformed_fields() -> None:
    """Test plan output lines rejects malformed fields."""
    valid = {
        "browser_scope": "none",
        "changed_slugs": [],
        "thumbnail_scope": "none",
        "thumbnail_slugs": [],
        "persist_mode": "none",
        "reason": "no runtime changes",
        "skip_verification": False,
    }
    with pytest.raises(ValueError, match="Plan field browser_scope must be a string"):
        workflow_helpers.plan_output_lines({**valid, "browser_scope": 1})
    with pytest.raises(ValueError, match="Plan field changed_slugs must be a list of strings"):
        workflow_helpers.plan_output_lines({**valid, "changed_slugs": "demo"})
    with pytest.raises(ValueError, match="Plan field changed_slugs must be a list of strings"):
        workflow_helpers.plan_output_lines({**valid, "changed_slugs": ["demo", 2]})
    with pytest.raises(ValueError, match="Plan field skip_verification must be a boolean"):
        workflow_helpers.plan_output_lines({**valid, "skip_verification": "false"})


def test_main_coverage_summary_prints_marked_section(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """Test main coverage summary prints marked section."""
    report = tmp_path / "js-coverage.txt"
    report.write_text(
        "noise before\n"
        "start of coverage report\n"
        "all files | 100 |\n"
        "end of coverage report\n"
        "noise after\n",
        encoding="utf-8",
    )

    assert workflow_helpers.main(["coverage-summary", "--report", str(report)]) == 0
    out = capsys.readouterr().out
    assert out.startswith("## JavaScript Coverage\n\n```text\n")
    assert "all files | 100 |" in out
    assert "noise before" not in out
    assert "noise after" not in out
    assert out.rstrip().endswith("```")


def test_main_coverage_summary_rejects_missing_markers(tmp_path: Path) -> None:
    """Test main coverage summary rejects missing markers."""
    no_markers = tmp_path / "empty.txt"
    no_markers.write_text("no markers here\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Coverage report markers not found"):
        workflow_helpers.main(["coverage-summary", "--report", str(no_markers)])

    start_only = tmp_path / "start-only.txt"
    start_only.write_text("start of coverage report\nrows\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Coverage report markers not found"):
        workflow_helpers.main(["coverage-summary", "--report", str(start_only)])

    inverted = tmp_path / "inverted.txt"
    inverted.write_text(
        "end of coverage report\nrows\nstart of coverage report\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Coverage report markers not found"):
        workflow_helpers.main(["coverage-summary", "--report", str(inverted)])


def test_main_finalize_pages_dir_adds_nojekyll(tmp_path: Path) -> None:
    """Test main finalize pages dir adds nojekyll."""
    (tmp_path / "index.html").write_text("<p>hi</p>", encoding="utf-8")

    assert workflow_helpers.main(["finalize-pages-dir", "--root", str(tmp_path)]) == 0
    assert (tmp_path / ".nojekyll").is_file()


def test_main_finalize_pages_dir_rejects_symlinked_payloads(tmp_path: Path) -> None:
    """Test main finalize pages dir rejects symlinked payloads."""
    (tmp_path / "escape").symlink_to("/etc")

    with pytest.raises(ValueError):
        workflow_helpers.main(["finalize-pages-dir", "--root", str(tmp_path)])
    assert not (tmp_path / ".nojekyll").exists()


def test_main_sync_alert_issue_builds_open_body_and_prints_issue_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main sync alert issue builds open body and prints issue url."""
    captured: dict[str, object] = {}

    def fake_sync_alert_issue(**kwargs: object) -> str:
        captured.update(kwargs)
        return "https://github.com/owner/repo/issues/3"

    monkeypatch.setattr(workflow_helpers, "sync_alert_issue", fake_sync_alert_issue)

    exit_code = workflow_helpers.main(
        [
            "sync-alert-issue",
            "--repo",
            "owner/repo",
            "--title",
            "Artifact alert",
            "--run-url",
            "https://github.com/owner/repo/actions/runs/9",
            "--state",
            "open",
            "--label",
            "custom",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "https://github.com/owner/repo/issues/3"
    assert captured["repo"] == "owner/repo"
    assert captured["title"] == "Artifact alert"
    assert captured["labels"] == ["custom"]
    assert captured["should_exist"] is True
    body = captured["body"]
    assert isinstance(body, str)
    assert "Workflow run: https://github.com/owner/repo/actions/runs/9" in body


def test_main_sync_alert_issue_close_uses_default_labels(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main sync alert issue close uses default labels."""
    captured: dict[str, object] = {}

    def fake_sync_alert_issue(**kwargs: object) -> str:
        captured.update(kwargs)
        return ""

    monkeypatch.setattr(workflow_helpers, "sync_alert_issue", fake_sync_alert_issue)

    exit_code = workflow_helpers.main(
        [
            "sync-alert-issue",
            "--repo",
            "owner/repo",
            "--title",
            "Artifact alert",
            "--run-url",
            "https://github.com/owner/repo/actions/runs/9",
            "--state",
            "close",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""
    assert captured["labels"] == ["ops", "ci"]
    assert captured["should_exist"] is False


def test_main_sync_alert_issue_combines_detail_and_detail_file(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Test main sync alert issue combines detail and detail file."""
    captured: dict[str, object] = {}

    def fake_sync_alert_issue(**kwargs: object) -> str:
        captured.update(kwargs)
        return "https://github.com/owner/repo/issues/4"

    monkeypatch.setattr(workflow_helpers, "sync_alert_issue", fake_sync_alert_issue)
    detail_file = tmp_path / "audit.json"
    detail_file.write_text('{"drift": true}\n', encoding="utf-8")

    exit_code = workflow_helpers.main(
        [
            "sync-alert-issue",
            "--repo",
            "owner/repo",
            "--title",
            "Artifact alert",
            "--run-url",
            "https://github.com/owner/repo/actions/runs/9",
            "--state",
            "setup-failure",
            "--detail",
            "Published URL: https://example.test/",
            "--detail-file",
            str(detail_file),
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "https://github.com/owner/repo/issues/4"
    assert captured["should_exist"] is True
    body = captured["body"]
    assert isinstance(body, str)
    assert "Published URL: https://example.test/" in body
    assert 'Current failure output:\n\n```text\n{"drift": true}\n```' in body
