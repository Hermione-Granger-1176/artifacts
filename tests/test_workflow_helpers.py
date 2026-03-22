from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.workflow_helpers as workflow_helpers


class FakeSubprocessResult:
    """Reusable fake for subprocess.run return values."""

    def __init__(self, stdout: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
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
    assert workflow_helpers.check_fallback(
        "https://github.com/owner/repo/pull/42"
    ) is True


def test_check_fallback_detects_commit_url() -> None:
    assert workflow_helpers.check_fallback(
        "https://github.com/owner/repo/commit/abc123"
    ) is False


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
        captured_cmd.extend(args[0] if args else [])
        return FakeSubprocessResult("apps/calculator/index.html\n")

    monkeypatch.setattr(workflow_helpers.subprocess, "run", fake_run)
    workflow_helpers.invalidate_thumbnails(
        event_name="push", repo="owner/repo", pr_number="", commit_sha="abc123"
    )
    assert "repos/owner/repo/commits/abc123" in captured_cmd
    assert "--paginate" not in captured_cmd
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
        workflow_helpers, "_build_parser",
        lambda: type("P", (), {"parse_args": lambda self, argv=None: fake_ns})()
    )
    with pytest.raises(ValueError, match="Unsupported command"):
        workflow_helpers.main([])
