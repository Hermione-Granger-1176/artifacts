from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"

CREATE_APP_TOKEN_SHA_PIN = re.compile(
    r"^actions/create-github-app-token@[0-9a-f]{40}$"
)


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
    for target in (
        "lint",
        "test-py",
        "coverage-js",
        "security",
        "validate",
        "test-browser-root",
    ):
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

    assert workflow["env"]["PAGES_DEPLOY_TIMEOUT_MS"] == "240000"
    assert workflow["env"]["VERIFY_DEPLOY_ATTEMPTS"] == "12"
    assert workflow["env"]["VERIFY_DEPLOY_DELAY_SECONDS"] == "5"
    assert publish["permissions"] == {
        "actions": "read",
        "contents": "write",
        "deployments": "write",
        "issues": "write",
        "pages": "write",
        "pull-requests": "write",
        "id-token": "write",
    }
    assert publish["concurrency"] == {
        "group": "pages-publish-${{ github.repository }}",
        "cancel-in-progress": False,
    }
    assert _step_uses(publish, "Download verified site artifact").startswith(
        "actions/download-artifact@"
    )
    assert (
        _step_run(publish, "Install dependencies for live browser verification").strip()
        == "make setup-ci"
    )
    assert _step_uses(publish, "Deploy main site") == "./.github/actions/deploy-site"
    assert _step(publish, "Deploy main site")["with"]["skip-build"] == "true"
    assert "commit=$commit" in _step_run(publish, "Resolve gh-pages publish commit")
    materialize_run = _step_run(publish, "Materialize GitHub Pages payload")
    assert "git archive" in materialize_run
    assert "reject_symlinks(root)" in materialize_run
    assert _step_uses(publish, "Upload GitHub Pages artifact").startswith(
        "actions/upload-pages-artifact@"
    )
    assert _step_with(publish, "Upload GitHub Pages artifact") == {
        "path": "${{ env.PAGES_PUBLISH_DIR }}",
        "include-hidden-files": True,
    }
    assert _step_uses(publish, "Deploy GitHub Pages artifact").startswith(
        "actions/deploy-pages@"
    )
    assert _step_with(publish, "Deploy GitHub Pages artifact")["timeout"] == (
        "${{ env.PAGES_DEPLOY_TIMEOUT_MS }}"
    )
    assert "verify_deploy.py" in _step_run(publish, "Verify main site deployment")
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


def test_update_publish_job_writes_classic_deployment_records() -> None:
    workflow = _load_workflow("update.yml")
    publish = _job(workflow, "publish")

    main_guard = (
        "github.event_name != 'pull_request' && "
        "steps.setup.outputs.token-available == 'true'"
    )
    log_url = (
        "${{ github.server_url }}/${{ github.repository }}"
        "/actions/runs/${{ github.run_id }}"
    )

    create = _step(publish, "Create main deployment record")
    assert create["id"] == "deployment-record"
    assert create["if"] == main_guard
    assert create["env"]["GH_TOKEN"] == "${{ github.token }}"
    create_run = _step_run(publish, "Create main deployment record")
    assert "repos/${{ github.repository }}/deployments" in create_run
    assert "--input -" in create_run
    assert '"required_contexts": []' in create_run
    assert '"ref": "${{ github.sha }}"' in create_run
    assert '"environment": "github-pages"' in create_run
    assert '"production_environment": true' in create_run
    assert 'echo "id=$deployment_id" >> "$GITHUB_OUTPUT"' in create_run

    success = _step(publish, "Mark main deployment successful")
    assert success["if"] == main_guard
    assert success["env"]["GH_TOKEN"] == "${{ github.token }}"
    success_run = _step_run(publish, "Mark main deployment successful")
    assert (
        "repos/${{ github.repository }}/deployments/"
        "${{ steps.deployment-record.outputs.id }}/statuses" in success_run
    )
    assert "-f state=success" in success_run
    assert (
        '-f environment_url="${{ steps.live-site-url.outputs.url }}"' in success_run
    )
    assert f'-f log_url="{log_url}"' in success_run

    failure = _step(publish, "Mark main deployment failed")
    assert failure["if"] == "failure() && steps.deployment-record.outputs.id != ''"
    assert failure["env"]["GH_TOKEN"] == "${{ github.token }}"
    failure_run = _step_run(publish, "Mark main deployment failed")
    assert (
        "repos/${{ github.repository }}/deployments/"
        "${{ steps.deployment-record.outputs.id }}/statuses" in failure_run
    )
    assert "-f state=failure" in failure_run
    assert f'-f log_url="{log_url}"' in failure_run


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
    assert cleanup["timeout-minutes"] == 8
    assert cleanup["permissions"] == {
        "actions": "read",
        "contents": "write",
        "issues": "write",
        "pages": "write",
        "pull-requests": "write",
        "id-token": "write",
    }
    assert cleanup["concurrency"] == {
        "group": "pages-publish-${{ github.repository }}",
        "cancel-in-progress": False,
    }
    assert _step(cleanup, "CI setup")["with"]["event-name"] == "pull_request"
    assert "commit=$CLEANUP_COMMIT" in _step_run(
        cleanup, "Resolve gh-pages cleanup commit"
    )
    assert "git archive" in _step_run(cleanup, "Materialize GitHub Pages payload")
    assert _step_uses(cleanup, "Upload GitHub Pages artifact").startswith(
        "actions/upload-pages-artifact@"
    )
    assert _step_with(cleanup, "Deploy GitHub Pages artifact")["timeout"] == (
        "${{ env.PAGES_DEPLOY_TIMEOUT_MS }}"
    )
    assert _step(cleanup, "Remove PR preview link comment")["with"]["delete"] is True


def test_refresh_python_locks_workflow_uses_dependabot_and_make_lock_contract() -> None:
    workflow = _load_workflow("refresh-python-locks.yml")
    on_block = _workflow_on(workflow)
    refresh = _job(workflow, "refresh-locks")

    assert on_block["pull_request"]["branches"] == ["main"]
    assert on_block["pull_request"]["paths"] == ["pyproject.toml", "uv.lock"]
    assert on_block["pull_request"]["types"] == ["opened", "reopened", "synchronize"]
    assert "dependabot[bot]" in refresh["if"]
    assert "github.actor == 'dependabot[bot]'" in refresh["if"]
    assert "dependabot/uv/" in refresh["if"]
    assert (
        _step_run(refresh, "Install uv").strip()
        == "python -m pip install --upgrade pip uv"
    )
    assert _step_run(refresh, "Refresh Python lock files").strip() == "make lock"
    upload_step = _step(refresh, "Upload refreshed Python lock files")
    assert _step_uses(refresh, "Upload refreshed Python lock files").startswith(
        "actions/upload-artifact@"
    )
    assert upload_step["with"]["path"].splitlines()[0] == "uv.lock"


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
    assert commit["env"]["LOCK_FILE_PATHSPEC"] == "uv.lock"
    assert "LOCK_FILE_ARGS" not in commit["env"]
    assert "read-lock-metadata" in _step_run(commit, "Read refresh metadata")
    assert "validate-lock-artifact" in _step_run(
        commit, "Validate downloaded artifact contents"
    )
    assert _step_run(commit, "Copy refreshed Python lock files into workspace").strip() == (
        'cp "$LOCK_REFRESH_ROOT/uv.lock" uv.lock'
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
        workflow = _load_workflow(workflow_name)
        refresh = _job(workflow, "refresh")

        assert workflow["concurrency"] == {
            "group": "${{ github.workflow }}",
            "cancel-in-progress": False,
        }

        token_inputs = _step_with(refresh, "Create escalation token")
        token_uses = _step_uses(refresh, "Create escalation token")
        assert CREATE_APP_TOKEN_SHA_PIN.fullmatch(token_uses), (
            f"Expected actions/create-github-app-token pinned to a 40-char SHA, "
            f"got {token_uses!r}"
        )
        assert token_inputs["app-id"] == "${{ vars.ESCALATION_APP_ID }}"
        assert token_inputs["private-key"] == "${{ secrets.ESCALATION_APP_PRIVATE_KEY }}"

        commit_inputs = _step_with(refresh, "Commit changes (verified)")
        assert commit_inputs["github-token"] == "${{ steps.escalation-token.outputs.token }}"
        assert commit_inputs["base-branch"] == "${{ github.event.repository.default_branch }}"
        assert commit_inputs["commit-mode"] == "force-pr"
        assert commit_inputs["fallback-branch-prefix"] == fallback_branch_prefix


def test_setup_python_steps_cache_uv_lock_and_uv_downloads() -> None:
    update = _load_workflow("update.yml")
    refresh = _load_workflow("refresh-python-locks.yml")
    ci_setup = yaml.safe_load(
        (REPO_ROOT / ".github" / "actions" / "ci-setup" / "action.yml").read_text(
            encoding="utf-8"
        )
    )

    verify_step = _step(_job(update, "verify"), "Set up Python")
    assert verify_step["with"]["cache"] == "pip"
    assert verify_step["with"]["cache-dependency-path"] == "uv.lock"
    verify_uv_cache = _step(_job(update, "verify"), "Cache uv downloads")
    assert _step_uses(_job(update, "verify"), "Cache uv downloads") == (
        "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9"
    )
    assert verify_uv_cache["with"]["path"] == "~/.cache/uv"
    assert verify_uv_cache["with"]["key"] == (
        "uv-${{ runner.os }}-${{ env.PYTHON_VERSION }}-${{ hashFiles('uv.lock') }}"
    )
    assert (
        "uv-${{ runner.os }}-${{ env.PYTHON_VERSION }}-"
        in verify_uv_cache["with"]["restore-keys"]
    )
    assert _step_run(_job(update, "verify"), "Install uv").strip() == (
        "python -m pip install --upgrade pip uv"
    )
    assert _step_with(_job(update, "verify"), "Cache Playwright browsers")["key"] == (
        "playwright-${{ hashFiles('uv.lock') }}"
    )
    assert _step_with(_job(update, "publish"), "Cache Playwright browsers")[
        "key"
    ] == "playwright-${{ hashFiles('uv.lock') }}"
    publish_uv_install = _step_run(
        _job(update, "publish"), "Install uv for live browser verification"
    )
    assert publish_uv_install.strip() == "python -m pip install --upgrade pip uv"

    refresh_step = _step(_job(refresh, "refresh-locks"), "Set up Python")
    assert refresh_step["with"]["cache"] == "pip"
    assert refresh_step["with"]["cache-dependency-path"] == "uv.lock"

    ci_setup_steps = ci_setup["runs"]["steps"]
    setup_python = next(s for s in ci_setup_steps if s.get("name") == "Set up Python")
    assert setup_python["with"]["cache"] == "pip"
    assert setup_python["with"]["cache-dependency-path"] == "uv.lock"
    ci_uv_cache = next(s for s in ci_setup_steps if s.get("name") == "Cache uv downloads")
    assert ci_uv_cache["uses"] == (
        "actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9"
    )
    assert ci_uv_cache["with"]["path"] == "~/.cache/uv"
    assert ci_uv_cache["with"]["key"] == (
        "uv-${{ runner.os }}-${{ inputs.python-version }}-${{ hashFiles('uv.lock') }}"
    )
    assert (
        "uv-${{ runner.os }}-${{ inputs.python-version }}-"
        in ci_uv_cache["with"]["restore-keys"]
    )
