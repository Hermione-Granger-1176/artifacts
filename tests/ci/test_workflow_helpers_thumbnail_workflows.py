from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.build.thumbnail_plan as thumbnail_plan
import scripts.ci.workflow_helpers as workflow_helpers
import scripts.lib.app_discovery as app_discovery
from tests.ci.workflow_helpers_test_support import FakeSubprocessResult, write_text


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


def test_invalidate_thumbnails_deletes_when_runtime_js_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    app_dir = tmp_path / "apps" / "my-app"
    app_dir.mkdir(parents=True)
    thumb = app_dir / "thumbnail.webp"
    thumb.write_bytes(b"old")

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/my-app/js/app.js\n",
    )

    result = workflow_helpers.invalidate_thumbnails(
        event_name="pull_request", repo="owner/repo", pr_number="1", commit_sha=""
    )

    assert result == ["apps/my-app/thumbnail.webp"]
    assert not thumb.exists()


def test_invalidate_thumbnails_deletes_all_for_shared_app_infra_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for slug in ("alpha", "beta"):
        app_dir = tmp_path / "apps" / slug
        app_dir.mkdir(parents=True)
        (app_dir / "thumbnail.webp").write_bytes(b"old")

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "css/app-shell.css\n",
    )

    result = workflow_helpers.invalidate_thumbnails(
        event_name="push", repo="owner/repo", pr_number="", commit_sha="abc123"
    )

    assert result == ["apps/alpha/thumbnail.webp", "apps/beta/thumbnail.webp"]


def test_invalidate_thumbnails_skips_missing_apps_root_for_shared_infra_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "css/app-shell.css\n",
    )

    result = workflow_helpers.invalidate_thumbnails(
        event_name="push", repo="owner/repo", pr_number="", commit_sha="abc123"
    )

    assert result == []


def test_invalidate_thumbnails_skips_browser_test_only_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for slug in ("alpha", "beta"):
        app_dir = tmp_path / "apps" / slug
        app_dir.mkdir(parents=True)
        (app_dir / "thumbnail.webp").write_bytes(b"old")

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "tests/browser/test_frontend_apps_smoke.py\n",
    )

    result = workflow_helpers.invalidate_thumbnails(
        event_name="push", repo="owner/repo", pr_number="", commit_sha="abc123"
    )

    assert result == []
    assert (tmp_path / "apps" / "alpha" / "thumbnail.webp").exists()
    assert (tmp_path / "apps" / "beta" / "thumbnail.webp").exists()


def test_thumbnail_plan_uses_pr_branch_mode_for_trusted_runtime_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/js/app.js\n",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="pull_request",
        repo="owner/repo",
        pr_number="1",
        commit_sha="",
        head_repo_fork=False,
        pr_author="alice",
    )

    assert plan["persist_mode"] == "pr-branch"
    assert plan["reason"] == "runtime-pr"
    assert plan["thumbnail_slugs"] == ["loan-amortization"]


def test_thumbnail_plan_uses_followup_pr_mode_for_main_runtime_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/index.html\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "none",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
    )

    assert plan["persist_mode"] == "followup-pr"
    assert plan["reason"] == "runtime-main"


def test_thumbnail_plan_skips_followup_pr_merge_loops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/index.html\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "thumbnail-followup",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
    )

    assert plan["persist_mode"] == "none"
    assert plan["reason"] == "merged-thumbnail-pr"


def test_thumbnail_plan_blocks_dependabot_and_forks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/index.html\n",
    )

    dependabot_plan = workflow_helpers.thumbnail_plan(
        event_name="pull_request",
        repo="owner/repo",
        pr_number="1",
        commit_sha="",
        head_repo_fork=False,
        pr_author="dependabot[bot]",
    )
    fork_plan = workflow_helpers.thumbnail_plan(
        event_name="pull_request",
        repo="owner/repo",
        pr_number="1",
        commit_sha="",
        head_repo_fork=True,
        pr_author="alice",
    )

    assert dependabot_plan["persist_mode"] == "none"
    assert dependabot_plan["reason"] == "dependabot-pr"
    assert fork_plan["persist_mode"] == "none"
    assert fork_plan["reason"] == "fork-pr"


def test_thumbnail_plan_triggers_for_missing_thumbnail_even_without_runtime_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "tokenizer-explorer" / "index.html", "<html></html>\n"
    )
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "README.md\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "none",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
    )

    assert plan["persist_mode"] == "followup-pr"
    assert plan["thumbnail_slugs"] == ["tokenizer-explorer"]


def test_thumbnail_plan_treats_browser_test_only_changes_as_non_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    (tmp_path / "apps" / "loan-amortization" / "thumbnail.webp").write_bytes(b"thumb")
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "tests/browser/test_frontend_apps_smoke.py\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "none",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
    )

    assert plan["app_scope"] == "none"
    assert plan["browser_scope"] == "none"
    assert plan["thumbnail_scope"] == "none"
    assert plan["persist_mode"] == "none"
    assert plan["shared_runtime_changed"] is False


def test_thumbnail_plan_passes_none_apps_root_to_shared_planner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = {}

    def fake_thumbnail_plan(**kwargs):
        captured.update(kwargs)
        return {"persist_mode": "none", "reason": "stub"}

    monkeypatch.setattr(
        workflow_helpers._thumbnail_plan, "thumbnail_plan", fake_thumbnail_plan
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
    )

    assert plan == {"persist_mode": "none", "reason": "stub"}
    assert captured["apps_root"] is None


def test_validate_thumbnail_artifact_accepts_expected_files(tmp_path: Path) -> None:
    artifact_root = tmp_path / "thumb-artifact"
    write_text(
        artifact_root / "plan.json",
        json.dumps(
            {
                "persist_mode": "followup-pr",
                "shared_runtime_changed": False,
                "thumbnail_slugs": ["loan-amortization"],
            }
        ),
    )
    (artifact_root / "apps" / "loan-amortization").mkdir(parents=True)
    (artifact_root / "apps" / "loan-amortization" / "thumbnail.webp").write_bytes(
        b"thumb"
    )

    plan = workflow_helpers.validate_thumbnail_artifact(artifact_root)

    assert plan["persist_mode"] == "followup-pr"


def test_validate_thumbnail_artifact_rejects_unexpected_files(tmp_path: Path) -> None:
    artifact_root = tmp_path / "thumb-artifact"
    write_text(
        artifact_root / "plan.json",
        json.dumps(
            {
                "persist_mode": "followup-pr",
                "shared_runtime_changed": False,
                "thumbnail_slugs": ["loan-amortization"],
            }
        ),
    )
    write_text(artifact_root / "apps" / "loan-amortization" / "oops.txt", "bad\n")

    with pytest.raises(ValueError, match="Unexpected file"):
        workflow_helpers.validate_thumbnail_artifact(artifact_root)


def test_discover_app_slugs_returns_empty_when_apps_dir_missing(tmp_path: Path) -> None:
    assert app_discovery.discover_app_slugs(tmp_path / "missing") == []


def test_runtime_change_plan_skips_app_docs_and_metadata_only_changes() -> None:
    plan = app_discovery.runtime_change_plan(
        [
            "apps/loan-amortization/docs/verification.md",
            "apps/loan-amortization/name.txt",
            "apps/loan-amortization/tags.txt",
        ]
    )

    assert plan == {
        "app_scope": "none",
        "changed_slugs": [],
        "runtime_changed": False,
        "shared_runtime_changed": False,
    }


def test_runtime_change_plan_rejects_non_kebab_slugs() -> None:
    plan = app_discovery.runtime_change_plan(
        [
            "apps/$(curl evil.com)/index.html",
            "apps/UPPER_CASE/js/app.js",
            "apps/has spaces/index.html",
        ]
    )

    assert plan == {
        "app_scope": "none",
        "changed_slugs": [],
        "runtime_changed": False,
        "shared_runtime_changed": False,
    }


def test_runtime_change_plan_treats_app_theme_bootstrap_as_shared_runtime() -> None:
    plan = app_discovery.runtime_change_plan(["js/app-theme.js"])

    assert plan == {
        "app_scope": "all",
        "changed_slugs": [],
        "runtime_changed": True,
        "shared_runtime_changed": True,
    }


def test_pr_field_and_generated_thumbnail_pr_helpers() -> None:
    assert thumbnail_plan.pr_field("not-a-dict", "title") == ""
    assert thumbnail_plan.pr_field({"title": 5}, "title") == ""
    assert thumbnail_plan.is_generated_thumbnail_pr("bad") is False
    assert thumbnail_plan.is_generated_thumbnail_pr(
        {
            "title": "Something else",
            "body": thumbnail_plan.THUMBNAIL_FOLLOWUP_PR_MARKER,
            "head": {"ref": "feature/demo"},
        }
    )


def test_associated_pr_kind_for_commit_handles_empty_and_normal_pr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert workflow_helpers.associated_pr_kind_for_commit("owner/repo", "") == "none"

    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda *args, **kwargs: [
            {"merged_at": "2026-03-26T00:00:00Z", "title": "Normal PR"}
        ],
    )

    assert (
        workflow_helpers.associated_pr_kind_for_commit("owner/repo", "abc123")
        == "normal"
    )


def test_associated_pr_kind_for_commit_detects_thumbnail_followup_and_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api_json",
        lambda *args, **kwargs: [
            {
                "title": thumbnail_plan.THUMBNAIL_FOLLOWUP_PR_TITLE,
                "body": thumbnail_plan.THUMBNAIL_FOLLOWUP_PR_MARKER,
                "head": {"ref": "ci/save-generated-thumbnails-20260326"},
            }
        ],
    )

    assert (
        workflow_helpers.associated_pr_kind_for_commit("owner/repo", "abc123")
        == "thumbnail-followup"
    )

    monkeypatch.setattr(
        workflow_helpers, "_run_gh_api_json", lambda *args, **kwargs: []
    )

    assert (
        workflow_helpers.associated_pr_kind_for_commit("owner/repo", "abc123") == "none"
    )


def test_thumbnail_plan_skips_docs_only_pr_and_unsupported_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "README.md\n",
    )

    docs_only_plan = workflow_helpers.thumbnail_plan(
        event_name="pull_request",
        repo="owner/repo",
        pr_number="1",
        commit_sha="",
        head_repo_fork=False,
        pr_author="alice",
    )
    manual_plan = workflow_helpers.thumbnail_plan(
        event_name="workflow_dispatch",
        repo="owner/repo",
        pr_number="",
        commit_sha="",
    )

    assert docs_only_plan["persist_mode"] == "none"
    assert docs_only_plan["reason"] == "docs-or-metadata-only"
    assert manual_plan["persist_mode"] == "none"
    assert manual_plan["reason"] == "unsupported-event"


def test_thumbnail_plan_skips_docs_only_push_without_missing_thumbnails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    (tmp_path / "apps" / "loan-amortization" / "thumbnail.webp").write_bytes(b"thumb")
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "README.md\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "none",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
    )

    assert plan["persist_mode"] == "none"
    assert plan["reason"] == "docs-or-metadata-only"


def test_validate_thumbnail_artifact_rejects_missing_root_and_plan(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        workflow_helpers.validate_thumbnail_artifact(tmp_path / "missing")

    artifact_root = tmp_path / "thumb-artifact"
    artifact_root.mkdir()
    with pytest.raises(ValueError, match="missing plan.json"):
        workflow_helpers.validate_thumbnail_artifact(artifact_root)
    with pytest.raises(FileNotFoundError):
        thumbnail_plan.read_thumbnail_plan(artifact_root)


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_validate_thumbnail_artifact_rejects_symlinks_and_out_of_scope_slugs(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "thumb-artifact"
    write_text(
        artifact_root / "plan.json",
        json.dumps(
            {
                "persist_mode": "followup-pr",
                "shared_runtime_changed": False,
                "thumbnail_slugs": ["loan-amortization"],
            }
        ),
    )
    outside = tmp_path / "outside.webp"
    outside.write_bytes(b"thumb")
    (artifact_root / "apps").mkdir(parents=True)
    (artifact_root / "apps" / "bad-link.webp").symlink_to(outside)

    with pytest.raises(ValueError, match="symlink"):
        workflow_helpers.validate_thumbnail_artifact(artifact_root)

    artifact_root = tmp_path / "thumb-artifact-2"
    write_text(
        artifact_root / "plan.json",
        json.dumps(
            {
                "persist_mode": "followup-pr",
                "shared_runtime_changed": False,
                "thumbnail_slugs": ["loan-amortization"],
            }
        ),
    )
    other_thumb = artifact_root / "apps" / "tokenizer-explorer" / "thumbnail.webp"
    other_thumb.parent.mkdir(parents=True)
    other_thumb.write_bytes(b"thumb")

    with pytest.raises(ValueError, match="outside plan scope"):
        workflow_helpers.validate_thumbnail_artifact(artifact_root)


def test_validate_thumbnail_artifact_rejects_missing_thumbnails_for_persisting_plan(
    tmp_path: Path,
) -> None:
    artifact_root = tmp_path / "thumb-artifact"
    write_text(
        artifact_root / "plan.json",
        json.dumps(
            {
                "persist_mode": "followup-pr",
                "shared_runtime_changed": False,
                "thumbnail_slugs": ["loan-amortization"],
            }
        ),
    )

    with pytest.raises(ValueError, match="has no thumbnail.webp files"):
        workflow_helpers.validate_thumbnail_artifact(artifact_root)


def test_main_validate_thumbnail_artifact_prints_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        workflow_helpers,
        "validate_thumbnail_artifact",
        lambda root: {"persist_mode": "none"},
    )

    exit_code = workflow_helpers.main(
        [
            "validate-thumbnail-artifact",
            "--root",
            "artifact-root",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {"persist_mode": "none"}


def test_main_thumbnail_plan_prints_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        workflow_helpers,
        "thumbnail_plan",
        lambda **kwargs: {
            "persist_mode": "followup-pr",
            "reason": "runtime-main",
        },
    )

    exit_code = workflow_helpers.main(
        [
            "thumbnail-plan",
            "--event-name",
            "push",
            "--repo",
            "owner/repo",
            "--commit-sha",
            "abc123",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "persist_mode": "followup-pr",
        "reason": "runtime-main",
    }


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


def test_is_automated_thumbnail_commit_true_for_bot_thumbnails() -> None:
    result = thumbnail_plan.is_automated_thumbnail_commit(
        actor="hermione1176[bot]",
        app_bot_login="hermione1176[bot]",
        repo="owner/repo",
        commit_sha="abc123",
        list_commit_files_fn=lambda **kw: [
            "apps/loan-amortization/thumbnail.webp",
            "apps/tokenizer-explorer/thumbnail.webp",
        ],
    )
    assert result is True


def test_is_automated_thumbnail_commit_false_when_non_thumbnail_file_present() -> None:
    result = thumbnail_plan.is_automated_thumbnail_commit(
        actor="hermione1176[bot]",
        app_bot_login="hermione1176[bot]",
        repo="owner/repo",
        commit_sha="abc123",
        list_commit_files_fn=lambda **kw: [
            "apps/loan-amortization/thumbnail.webp",
            "apps/loan-amortization/index.html",
        ],
    )
    assert result is False


def test_is_automated_thumbnail_commit_false_when_actor_is_human() -> None:
    result = thumbnail_plan.is_automated_thumbnail_commit(
        actor="alice",
        app_bot_login="hermione1176[bot]",
        repo="owner/repo",
        commit_sha="abc123",
        list_commit_files_fn=lambda **kw: [
            "apps/loan-amortization/thumbnail.webp",
        ],
    )
    assert result is False


def test_is_automated_thumbnail_commit_false_when_no_files() -> None:
    result = thumbnail_plan.is_automated_thumbnail_commit(
        actor="hermione1176[bot]",
        app_bot_login="hermione1176[bot]",
        repo="owner/repo",
        commit_sha="abc123",
        list_commit_files_fn=lambda **kw: [],
    )
    assert result is False


def test_is_automated_thumbnail_commit_false_when_empty_actor_or_bot_login() -> None:
    for actor, bot_login in [
        ("", "hermione1176[bot]"),
        ("hermione1176[bot]", ""),
        ("", ""),
    ]:
        result = thumbnail_plan.is_automated_thumbnail_commit(
            actor=actor,
            app_bot_login=bot_login,
            repo="owner/repo",
            commit_sha="abc123",
            list_commit_files_fn=lambda **kw: [
                "apps/loan-amortization/thumbnail.webp",
            ],
        )
        assert result is False


def test_is_automated_thumbnail_commit_false_on_api_error() -> None:
    def raise_api_error(**kw: object) -> list[str]:
        raise RuntimeError("gh api failed")

    result = thumbnail_plan.is_automated_thumbnail_commit(
        actor="hermione1176[bot]",
        app_bot_login="hermione1176[bot]",
        repo="owner/repo",
        commit_sha="abc123",
        list_commit_files_fn=raise_api_error,
    )
    assert result is False


def test_list_commit_files_returns_empty_for_empty_sha() -> None:
    result = thumbnail_plan.list_commit_files(
        repo="owner/repo",
        commit_sha="",
    )
    assert result == []


def test_thumbnail_plan_skip_verification_true_for_bot_thumbnail_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    (tmp_path / "apps" / "loan-amortization" / "thumbnail.webp").write_bytes(b"thumb")

    # PR-level files include both code and thumbnails (whole PR)
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: (
            "apps/loan-amortization/js/app.js\n"
            "apps/loan-amortization/thumbnail.webp\n"
        ),
    )
    # Commit-level files are only thumbnails (Hermione's commit)
    monkeypatch.setattr(
        workflow_helpers,
        "list_commit_files",
        lambda **kw: ["apps/loan-amortization/thumbnail.webp"],
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="pull_request",
        repo="owner/repo",
        pr_number="1",
        commit_sha="abc123",
        head_repo_fork=False,
        pr_author="alice",
        actor="hermione1176[bot]",
        app_bot_login="hermione1176[bot]",
    )

    assert plan["skip_verification"] is True


def test_thumbnail_plan_skip_verification_false_for_human_code_push(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/js/app.js\n",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="pull_request",
        repo="owner/repo",
        pr_number="1",
        commit_sha="abc123",
        head_repo_fork=False,
        pr_author="alice",
        actor="alice",
        app_bot_login="hermione1176[bot]",
    )

    assert plan["skip_verification"] is False


def test_thumbnail_plan_skip_verification_true_for_merged_thumbnail_followup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    (tmp_path / "apps" / "loan-amortization" / "thumbnail.webp").write_bytes(b"thumb")
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/thumbnail.webp\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "thumbnail-followup",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "list_commit_files",
        lambda **kw: ["apps/loan-amortization/thumbnail.webp"],
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
        actor="alice",
        app_bot_login="hermione1176[bot]",
    )

    assert plan["skip_verification"] is True
    assert plan["persist_mode"] == "none"
    assert plan["reason"] == "merged-thumbnail-pr"


def test_thumbnail_plan_skip_verification_false_for_followup_with_extra_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    (tmp_path / "apps" / "loan-amortization" / "thumbnail.webp").write_bytes(b"thumb")
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: (
            "apps/loan-amortization/thumbnail.webp\n"
            "apps/loan-amortization/index.html\n"
        ),
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "thumbnail-followup",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "list_commit_files",
        lambda **kw: [
            "apps/loan-amortization/thumbnail.webp",
            "apps/loan-amortization/index.html",
        ],
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
        actor="alice",
        app_bot_login="hermione1176[bot]",
    )

    assert plan["skip_verification"] is False


def test_thumbnail_plan_skip_verification_false_on_followup_api_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    (tmp_path / "apps" / "loan-amortization" / "thumbnail.webp").write_bytes(b"thumb")
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/thumbnail.webp\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "thumbnail-followup",
    )

    def raise_api_error(**kw: object) -> list[str]:
        raise RuntimeError("gh api failed")

    monkeypatch.setattr(
        workflow_helpers,
        "list_commit_files",
        raise_api_error,
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
        actor="alice",
        app_bot_login="hermione1176[bot]",
    )

    assert plan["skip_verification"] is False
    assert plan["persist_mode"] == "none"
    assert plan["reason"] == "merged-thumbnail-pr"


def test_thumbnail_plan_skip_verification_defaults_to_false_without_actor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    write_text(
        tmp_path / "apps" / "loan-amortization" / "index.html", "<html></html>\n"
    )
    monkeypatch.setattr(
        workflow_helpers,
        "_run_gh_api",
        lambda *args, **kwargs: "apps/loan-amortization/js/app.js\n",
    )
    monkeypatch.setattr(
        workflow_helpers,
        "associated_pr_kind_for_commit",
        lambda repo, commit_sha: "none",
    )

    plan = workflow_helpers.thumbnail_plan(
        event_name="push",
        repo="owner/repo",
        pr_number="",
        commit_sha="abc123",
    )

    assert plan["skip_verification"] is False


def test_main_thumbnail_plan_passes_actor_and_bot_login(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    captured: dict[str, object] = {}

    def fake_plan(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {"persist_mode": "none", "reason": "stub", "skip_verification": False}

    monkeypatch.setattr(workflow_helpers, "thumbnail_plan", fake_plan)

    exit_code = workflow_helpers.main(
        [
            "thumbnail-plan",
            "--event-name",
            "pull_request",
            "--repo",
            "owner/repo",
            "--pr-number",
            "1",
            "--actor",
            "hermione1176[bot]",
            "--app-bot-login",
            "hermione1176[bot]",
        ]
    )

    assert exit_code == 0
    assert captured["actor"] == "hermione1176[bot]"
    assert captured["app_bot_login"] == "hermione1176[bot]"
