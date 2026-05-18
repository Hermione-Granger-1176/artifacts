from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


def _load_workflow(name: str) -> dict[str, object]:
    data = yaml.safe_load((WORKFLOWS_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _workflow_on(workflow: dict[str, object]) -> dict[str, object]:
    on_block = workflow.get("on", workflow.get(True))
    assert isinstance(on_block, dict)
    return on_block


def _jobs(workflow: dict[str, object]) -> dict[str, dict[str, object]]:
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    return jobs


def _job(workflow: dict[str, object], name: str) -> dict[str, object]:
    job = _jobs(workflow)[name]
    assert isinstance(job, dict)
    return job


def _steps(job: dict[str, object]) -> list[dict[str, object]]:
    steps = job.get("steps")
    assert isinstance(steps, list)
    return [step for step in steps if isinstance(step, dict)]


def _step(job: dict[str, object], name: str) -> dict[str, object]:
    for step in _steps(job):
        if step.get("name") == name:
            return step
    raise AssertionError(f"Step not found: {name}")


def _step_run(job: dict[str, object], name: str) -> str:
    run = _step(job, name).get("run")
    assert isinstance(run, str)
    return run


def _step_uses(job: dict[str, object], name: str) -> str:
    uses = _step(job, name).get("uses")
    assert isinstance(uses, str)
    return uses


def _step_with(job: dict[str, object], name: str) -> dict[str, object]:
    inputs = _step(job, name).get("with")
    assert isinstance(inputs, dict)
    return inputs


def test_update_workflow_keeps_expected_triggers_and_jobs() -> None:
    workflow = _load_workflow("update.yml")
    on_block = _workflow_on(workflow)

    assert set(on_block) == {"workflow_dispatch", "push", "pull_request"}
    assert on_block["push"]["branches"] == ["main"]
    assert on_block["pull_request"]["branches"] == ["main"]
    assert on_block["pull_request"]["types"] == [
        "opened",
        "reopened",
        "synchronize",
        "closed",
    ]
    assert set(_jobs(workflow)) == {
        "plan",
        "verify",
        "secret-scan",
        "dependency-review",
        "publish",
        "persist-thumbnails",
        "cleanup-preview",
    }
    assert _job(workflow, "verify")["needs"] == "plan"
    assert set(_job(workflow, "publish")["needs"]) == {
        "plan",
        "verify",
        "secret-scan",
        "dependency-review",
    }
    assert set(_job(workflow, "persist-thumbnails")["needs"]) == {
        "plan",
        "verify",
        "publish",
    }


def test_update_verify_job_runs_expected_make_targets() -> None:
    workflow = _load_workflow("update.yml")
    verify = _job(workflow, "verify")

    assert "make setup-ci" in _step_run(verify, "Install workspace dependencies")

    parallel_step = _step(verify, "Run parallel checks")
    parallel_run = _step_run(verify, "Run parallel checks")
    assert "run_parallel_checks.py" in parallel_run
    for target in ("lint", "test-py", "coverage-js", "security", "validate", "test-browser-root"):
        assert target in parallel_run
    assert parallel_step["env"]["COVERAGE_OUTPUT"] == "js-coverage.txt"

    selective_browser = _step(verify, "Run selective app browser verification")
    assert selective_browser["if"] == "needs.plan.outputs.browser-scope != 'none'"
    assert selective_browser["env"]["ARTIFACTS_BROWSER_APP_SLUGS"] == (
        "${{ needs.plan.outputs.browser-scope == 'changed' && needs.plan.outputs.changed-slugs || '' }}"
    )
    assert "make test-browser-apps" in _step_run(
        verify, "Run selective app browser verification"
    )

    build_step = _step(verify, "Build verified site")
    assert build_step["env"]["ARTIFACTS_THUMBNAIL_SLUGS"] == (
        "${{ needs.plan.outputs.thumbnail-scope == 'changed' && needs.plan.outputs.thumbnail-slugs || '' }}"
    )
    assert (
        build_step["env"]["ARTIFACTS_THUMBNAIL_MANIFEST"]
        == ".artifacts/thumbnail-persist/manifest.json"
    )
    build_run = _step_run(verify, "Build verified site")
    assert "make thumbnails" in build_run
    assert "make check-generated" in build_run
    assert "make index" in build_run
    assert "make site" in build_run

    package_run = _step_run(verify, "Package thumbnail persistence artifact")
    assert 'printf \'%s\' "$PLAN_JSON" > "$root/plan.json"' in package_run
    assert "thumbnail-persist-${{ github.run_id }}" in package_run

    upload_site = _step(verify, "Upload verified site artifact")
    assert upload_site["with"]["name"] == "site-${{ github.run_id }}"
    assert upload_site["with"]["path"] == "_site"

    upload_thumbnail = _step(verify, "Upload thumbnail persistence artifact")
    assert upload_thumbnail["with"]["path"] == ".artifacts/thumbnail-persist"


def test_update_publish_job_reuses_verified_site_artifact() -> None:
    workflow = _load_workflow("update.yml")
    publish = _job(workflow, "publish")

    assert _step_uses(publish, "Download verified site artifact").startswith(
        "actions/download-artifact@"
    )
    assert (
        _step_run(publish, "Install dependencies for live browser verification").strip()
        == "make setup-ci"
    )
    assert _step_uses(publish, "Deploy main site") == "./.github/actions/deploy-site"
    assert _step(publish, "Deploy main site")["with"]["skip-build"] == "true"
    assert _step_run(publish, "Run PR preview browser verification").strip() == (
        "make test-browser-live"
    )
    assert _step_run(publish, "Run live main site browser verification").strip() == (
        "make test-browser-live"
    )

    publish_runs = "\n".join(
        step.get("run", "")
        for step in _steps(publish)
        if isinstance(step.get("run"), str)
    )
    assert "make thumbnails" not in publish_runs
    assert "make index" not in publish_runs
    assert "make site" not in publish_runs


def test_update_thumbnail_persistence_and_cleanup_stay_bounded() -> None:
    workflow = _load_workflow("update.yml")
    persist = _job(workflow, "persist-thumbnails")
    cleanup = _job(workflow, "cleanup-preview")

    validate_run = _step_run(persist, "Validate thumbnail artifact")
    assert (
        "validate-thumbnail-artifact --root .artifacts/thumbnail-persist"
        in validate_run
    )
    assert 'echo "json=$plan" >> "$GITHUB_OUTPUT"' in validate_run
    assert (
        _step_uses(persist, "Persist thumbnails into the same PR branch")
        == "./.github/actions/verified-commit"
    )
    assert (
        _step_uses(persist, "Create or update thumbnail follow-up PR")
        == "./.github/actions/verified-commit"
    )
    assert cleanup["if"] == (
        "github.event_name == 'pull_request' && github.event.action == 'closed'"
    )
    assert _step(cleanup, "CI setup")["with"]["event-name"] == "pull_request"
    assert _step(cleanup, "Remove PR preview link comment")["with"]["delete"] is True


def test_refresh_python_locks_workflow_uses_dependabot_and_make_lock_contract() -> None:
    workflow = _load_workflow("refresh-python-locks.yml")
    on_block = _workflow_on(workflow)
    refresh = _job(workflow, "refresh-locks")

    assert on_block["pull_request"]["branches"] == ["main"]
    assert on_block["pull_request"]["paths"] == ["pyproject.toml"]
    assert on_block["pull_request"]["types"] == ["opened", "reopened", "synchronize"]
    assert "dependabot[bot]" in refresh["if"]
    assert "dependabot/pip/" in refresh["if"]
    assert _step_run(refresh, "Refresh Python lock files").strip() == "make lock"
    assert _step_uses(refresh, "Upload refreshed Python lock files").startswith(
        "actions/upload-artifact@"
    )


def test_commit_python_locks_workflow_keeps_validation_and_verified_commit_steps() -> (
    None
):
    workflow = _load_workflow("commit-python-locks.yml")
    on_block = _workflow_on(workflow)
    commit = _job(workflow, "commit-locks")

    assert on_block["workflow_run"]["workflows"] == ["Refresh Python Locks"]
    assert on_block["workflow_run"]["types"] == ["completed"]
    assert "Refresh Python Locks" in commit["if"]
    assert "workflow_run.event == 'pull_request'" in commit["if"]
    assert "read-lock-metadata" in _step_run(commit, "Read refresh metadata")
    assert "validate-lock-artifact" in _step_run(
        commit, "Validate downloaded artifact contents"
    )
    assert _step_uses(commit, "Commit refreshed Python lock files (verified)") == (
        "./.github/actions/verified-commit"
    )


def test_audit_and_refresh_action_workflows_keep_expected_entrypoints() -> None:
    audit = _load_workflow("audit-repo-settings.yml")
    live_smoke = _load_workflow("live-site-smoke.yml")
    refresh = _load_workflow("refresh-action-shas.yml")

    assert set(_workflow_on(audit)) == {"workflow_dispatch", "schedule"}
    assert _workflow_on(audit)["schedule"] == [{"cron": "23 8 * * 1"}]
    assert "audit-repo-settings" in _step_run(
        _job(audit, "audit"), "Audit repository settings"
    )
    audit_job = _job(audit, "audit")
    audit_run = _step_run(audit_job, "Audit repository settings")
    assert audit_job["permissions"] == {"contents": "read", "issues": "write"}
    assert "> audit-repo-settings.json 2>&1" in audit_run
    assert 'echo "status=$status" >> "$GITHUB_OUTPUT"' in audit_run
    assert "sync-alert-issue" in _step_run(
        audit_job, "Open or update repository settings drift issue"
    )
    assert "sync-alert-issue" in _step_run(
        audit_job, "Close repository settings drift issue when clean"
    )

    assert set(_workflow_on(live_smoke)) == {"workflow_dispatch", "schedule"}
    assert _workflow_on(live_smoke)["schedule"] == [{"cron": "17 6 * * *"}]
    smoke_job = _job(live_smoke, "smoke")
    assert smoke_job["permissions"] == {"contents": "read", "issues": "write"}
    assert _step_uses(smoke_job, "CI setup") == "./.github/actions/ci-setup"
    assert (
        _step_run(smoke_job, "Run published-site browser verification")
        .strip()
        .startswith("set +e")
    )
    assert "make test-browser-live" in _step_run(
        smoke_job, "Run published-site browser verification"
    )
    assert "sync-alert-issue" in _step_run(
        smoke_job, "Open or update live-site smoke issue"
    )
    assert "sync-alert-issue" in _step_run(
        smoke_job, "Close live-site smoke issue when clean"
    )

    assert set(_workflow_on(refresh)) == {"schedule", "workflow_dispatch"}
    assert _workflow_on(refresh)["schedule"] == [{"cron": "0 3 1 * *"}]
    assert (
        _step_uses(_job(refresh, "refresh"), "Commit changes (verified)")
        == "./.github/actions/verified-commit"
    )


def test_scheduled_maintenance_workflows_always_create_pull_requests() -> None:
    workflows = {
        "refresh-action-shas.yml": "ci/refresh-action-shas",
        "refresh-locks.yml": "ci/refresh-locks",
    }

    for workflow_name, fallback_branch_prefix in workflows.items():
        refresh = _job(_load_workflow(workflow_name), "refresh")

        token_inputs = _step_with(refresh, "Create escalation token")
        assert (
            _step_uses(refresh, "Create escalation token")
            == "actions/create-github-app-token@1b10c78c7865c340bc4f6099eb2f838309f1e8c3"
        )
        assert token_inputs["app-id"] == "${{ vars.ESCALATION_APP_ID }}"
        assert token_inputs["private-key"] == "${{ secrets.ESCALATION_APP_PRIVATE_KEY }}"

        commit_inputs = _step_with(refresh, "Commit changes (verified)")
        assert commit_inputs["github-token"] == "${{ steps.escalation-token.outputs.token }}"
        assert commit_inputs["base-branch"] == "${{ github.event.repository.default_branch }}"
        assert commit_inputs["commit-mode"] == "force-pr"
        assert commit_inputs["fallback-branch-prefix"] == fallback_branch_prefix


def test_setup_python_steps_cache_pip() -> None:
    update = _load_workflow("update.yml")
    refresh = _load_workflow("refresh-python-locks.yml")
    ci_setup = yaml.safe_load(
        (REPO_ROOT / ".github" / "actions" / "ci-setup" / "action.yml").read_text(
            encoding="utf-8"
        )
    )

    verify_step = _step(_job(update, "verify"), "Set up Python")
    assert verify_step["with"]["cache"] == "pip"
    assert verify_step["with"]["cache-dependency-path"] == "locks/requirements-dev.lock"

    refresh_step = _step(_job(refresh, "refresh-locks"), "Set up Python")
    assert refresh_step["with"]["cache"] == "pip"
    assert refresh_step["with"]["cache-dependency-path"] == "locks/requirements-dev.lock"

    ci_setup_steps = ci_setup["runs"]["steps"]
    setup_python = next(s for s in ci_setup_steps if s.get("name") == "Set up Python")
    assert setup_python["with"]["cache"] == "pip"
    assert setup_python["with"]["cache-dependency-path"] == "locks/requirements-dev.lock"
