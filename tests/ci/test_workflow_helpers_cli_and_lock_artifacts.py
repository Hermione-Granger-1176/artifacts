from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.ci.workflow_helpers as workflow_helpers
from tests.ci.workflow_helpers_test_support import write_text


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
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/uv/demo\n")

    assert workflow_helpers.read_lock_refresh_metadata(tmp_path) == {
        "head-ref": "dependabot/uv/demo",
        "head-sha": "abc123",
        "pr-number": "8",
    }


def test_validate_lock_refresh_artifact_accepts_expected_files(tmp_path: Path) -> None:
    """Test validate lock refresh artifact accepts expected files."""
    write_text(tmp_path / "uv.lock", "version = 1\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/uv/demo\n")

    workflow_helpers.validate_lock_refresh_artifact(tmp_path)


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_validate_lock_refresh_artifact_rejects_symlinks(tmp_path: Path) -> None:
    """Test validate lock refresh artifact rejects symlinks."""
    write_text(tmp_path / "uv.lock", "version = 1\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/uv/demo\n")
    linked = tmp_path / "linked.txt"
    write_text(linked, "secret\n")
    (tmp_path / ".artifacts" / "escape.txt").symlink_to(linked)

    with pytest.raises(ValueError, match="Refusing to process tree containing symlink"):
        workflow_helpers.validate_lock_refresh_artifact(tmp_path)


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_validate_lock_refresh_artifact_rejects_symlinked_directories(
    tmp_path: Path,
) -> None:
    """Test validate lock refresh artifact rejects symlinked directories."""
    write_text(tmp_path / "uv.lock", "version = 1\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/uv/demo\n")
    linked_dir = tmp_path / "linked-dir"
    linked_dir.mkdir()
    (tmp_path / ".artifacts" / "nested-link").symlink_to(linked_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="Refusing to process tree containing symlink"):
        workflow_helpers.validate_lock_refresh_artifact(tmp_path)


def test_validate_lock_refresh_artifact_rejects_missing_files(tmp_path: Path) -> None:
    """Test validate lock refresh artifact rejects missing files."""
    write_text(tmp_path / "uv.lock", "version = 1\n")

    with pytest.raises(ValueError, match="Required artifact file missing or not a regular file"):
        workflow_helpers.validate_lock_refresh_artifact(tmp_path)


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
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/uv/demo\n")

    exit_code = workflow_helpers.main(["read-lock-metadata", "--root", str(tmp_path)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "head-ref": "dependabot/uv/demo",
        "head-sha": "abc123",
        "pr-number": "8",
    }


def test_main_validate_lock_artifact_returns_zero(tmp_path: Path) -> None:
    """Test main validate lock artifact returns zero."""
    write_text(tmp_path / "uv.lock", "version = 1\n")
    write_text(tmp_path / ".artifacts" / "pr-number.txt", "8\n")
    write_text(tmp_path / ".artifacts" / "head-sha.txt", "abc123\n")
    write_text(tmp_path / ".artifacts" / "head-ref.txt", "dependabot/uv/demo\n")

    assert workflow_helpers.main(["validate-lock-artifact", "--root", str(tmp_path)]) == 0


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


def test_main_sync_alert_issue_prints_issue_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main sync alert issue prints issue url."""
    monkeypatch.setattr(
        workflow_helpers,
        "sync_alert_issue",
        lambda **_kwargs: "https://github.com/owner/repo/issues/3",
    )

    exit_code = workflow_helpers.main(
        [
            "sync-alert-issue",
            "--repo",
            "owner/repo",
            "--title",
            "Artifact alert",
            "--body",
            "Body",
            "--label",
            "ci",
            "--should-exist",
            "true",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "https://github.com/owner/repo/issues/3"
