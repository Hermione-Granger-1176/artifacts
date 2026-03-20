from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.workflow_helpers as workflow_helpers


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


def test_main_raises_for_unsupported_command() -> None:
    class Args:
        command = "unsupported"
        root = "."

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            workflow_helpers,
            "_build_parser",
            lambda: type(
                "Parser", (), {"parse_args": lambda self, argv=None: Args()}
            )(),
        )
        with pytest.raises(ValueError, match="Unsupported command"):
            workflow_helpers.main([])
