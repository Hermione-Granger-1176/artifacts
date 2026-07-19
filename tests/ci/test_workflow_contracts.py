from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
ACTIONS_DIR = REPO_ROOT / ".github" / "actions"

CREATE_APP_TOKEN_SHA_PIN = re.compile(r"^actions/create-github-app-token@[0-9a-f]{40}$")
CODEQL_ACTION_SHA_PIN = re.compile(r"^github/codeql-action/(init|autobuild|analyze)@[0-9a-f]{40}$")

USES_LINE_PATTERN = re.compile(r"^\s*(?:-\s*)?uses:\s*(\S+)\s*(#.*)?$")
SHA_PINNED_PATTERN = re.compile(r"^[^@\s]+@[0-9a-f]{40}$")


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
    """Update workflow keeps expected triggers and jobs."""
    workflow = _load_workflow("update.yml")
    on_block = _workflow_on(workflow)

    assert set(on_block) == {"workflow_dispatch", "schedule", "push", "pull_request"}
    assert on_block["schedule"] == [{"cron": "23 4 * * 0"}]
    assert on_block["workflow_dispatch"]["inputs"]["full-sweep"] == {
        "description": "Force a conservative full verification sweep.",
        "required": False,
        "default": True,
        "type": "boolean",
    }
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
        "quick-gates",
        "heavy-checks",
        "root-browser",
        "app-shard",
        "assemble-site",
        "verify",
        "save-app-ledger",
        "secret-scan",
        "dependency-review",
        "publish",
        "persist-thumbnails",
        "cleanup-preview",
    }
    assert _job(workflow, "quick-gates")["needs"] == "plan"
    assert set(_job(workflow, "heavy-checks")["needs"]) == {"plan", "quick-gates"}
    assert set(_job(workflow, "root-browser")["needs"]) == {"plan", "quick-gates"}
    assert set(_job(workflow, "app-shard")["needs"]) == {"plan", "quick-gates"}
    assert set(_job(workflow, "assemble-site")["needs"]) == {
        "plan",
        "quick-gates",
        "heavy-checks",
        "root-browser",
        "app-shard",
    }
    assert set(_job(workflow, "verify")["needs"]) == {
        "plan",
        "quick-gates",
        "heavy-checks",
        "root-browser",
        "app-shard",
        "assemble-site",
        "secret-scan",
        "dependency-review",
    }
    assert set(_job(workflow, "publish")["needs"]) == {"plan", "verify"}
    assert set(_job(workflow, "save-app-ledger")["needs"]) == {"plan", "verify"}
    assert set(_job(workflow, "persist-thumbnails")["needs"]) == {
        "plan",
        "assemble-site",
        "publish",
    }

    plan = _job(workflow, "plan")
    assert _step(plan, "Checkout repository")["with"]["fetch-depth"] == 0
    plan_run = _step_run(plan, "Compute app impact plan")
    assert "make ci-thumbnail-plan" in plan_run
    assert (
        "force_full=\"${{ github.event_name == 'schedule'"
        " || inputs.full-sweep == true || inputs.full-sweep == 'true' }}\"" in plan_run
    )
    assert "make ci-apply-app-ledger" in plan_run
    assert 'PLAN_JSON="$plan" make ci-plan-outputs >> "$GITHUB_OUTPUT"' in plan_run
    restore_ledger = _step(plan, "Restore main verification ledger")
    assert restore_ledger["with"]["key"] == "app-ledger-${{ github.sha }}"
    assert restore_ledger["with"]["restore-keys"] == "app-ledger-\n"
    upload = _step(plan, "Upload app impact plan")
    assert upload["with"]["name"] == "ci-plan-${{ github.run_id }}"
    assert upload["with"]["path"] == ".artifacts/ci-plan/plan.json"


def test_update_parallel_shards_and_assembly_use_manifest_bound_make_targets() -> None:
    """Update workflow keeps the bounded shard and single assembly contracts."""
    workflow = _load_workflow("update.yml")
    quick = _job(workflow, "quick-gates")
    heavy = _job(workflow, "heavy-checks")
    assert "make ci-quick-gates" in _step_run(quick, "Run quick gates")
    assert "make ci-heavy-checks" in _step_run(heavy, "Run heavy checks")
    assert "make ci-coverage-summary report=js-coverage.txt" in _step_run(
        heavy, "Report JavaScript coverage"
    )
    assert _step_with(quick, "CI setup")["install-browsers"] == "false"
    assert _step_with(heavy, "CI setup")["install-browsers"] == "false"
    assert "make test-browser-root" in _step_run(
        _job(workflow, "root-browser"), "Run root browser verification"
    )

    shard = _job(workflow, "app-shard")
    assert shard["strategy"] == {
        "fail-fast": False,
        "max-parallel": 12,
        "matrix": "${{ fromJSON(needs.plan.outputs.shard-matrix) }}",
    }
    assert _step(shard, "Download app impact plan")["with"]["name"] == (
        "ci-plan-${{ github.run_id }}"
    )
    assert "make ci-write-shard-manifest" in _step_run(shard, "Write shard manifest")
    assert (
        "make test-browser-apps-shard shard_manifest=.artifacts/shard-manifest.json"
        in _step_run(shard, "Run app browser shard")
    )
    assert "make thumbnails-shard shard_manifest=.artifacts/shard-manifest.json" in _step_run(
        shard, "Capture shard thumbnails"
    )
    assert "make ci-package-shard-result" in _step_run(shard, "Package shard thumbnail result")
    assert _step(shard, "Upload shard thumbnail result")["with"]["name"] == (
        "app-shard-${{ github.run_id }}-${{ matrix.shard }}"
    )

    assemble = _job(workflow, "assemble-site")
    assert _step_with(assemble, "CI setup")["install-browsers"] == "false"
    download_results = _step(assemble, "Download shard thumbnail results")
    assert download_results["with"]["pattern"] == "app-shard-${{ github.run_id }}-*"
    assert "make ci-merge-shard-results root=.artifacts/shard-results" in _step_run(
        assemble, "Merge shard thumbnails"
    )
    build_run = _step_run(assemble, "Build assembled site once")
    assert (
        build_run.index("make check-generated")
        < build_run.index("make index")
        < build_run.index("make site")
    )
    package_run = _step_run(assemble, "Package thumbnail persistence artifact")
    assert 'cp .artifacts/ci-plan/plan.json "$root/plan.json"' in package_run
    assert "thumbnail-persist-${{ github.run_id }}" in package_run

    upload_site = _step(assemble, "Upload assembled site artifact")
    assert upload_site["with"]["name"] == "site-${{ github.run_id }}"
    assert upload_site["with"]["path"] == "_site"

    upload_thumbnail = _step(assemble, "Upload thumbnail persistence artifact")
    assert upload_thumbnail["with"]["path"] == ".artifacts/thumbnail-persist"

    verify = _job(workflow, "verify")
    assert [step["name"] for step in _steps(verify)] == ["Check required job results"]
    verify_run = _step_run(verify, "Check required job results")
    for result in (
        "QUICK_GATES_RESULT",
        "HEAVY_CHECKS_RESULT",
        "ROOT_BROWSER_RESULT",
        "APP_SHARD_RESULT",
        "ASSEMBLE_RESULT",
    ):
        assert result in verify_run

    ledger = _job(workflow, "save-app-ledger")
    ledger_condition = ledger["if"].strip()
    # The implicit success() would treat the transitively skipped
    # dependency-review job as a failure and skip this job on every push.
    assert ledger_condition.startswith("!cancelled() &&")
    assert "github.event_name == 'push'" in ledger_condition
    assert "github.ref == 'refs/heads/main'" in ledger_condition
    assert "needs.verify.result == 'success'" in ledger_condition
    assert "make ci-update-app-ledger" in _step_run(ledger, "Update main verification ledger")
    assert _step(ledger, "Save verification ledger")["if"] == (
        "steps.app-ledger.outputs.cache-hit != 'true'"
    )


def test_update_publish_job_reuses_verified_site_artifact() -> None:
    """Update publish job reuses verified site artifact."""
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
    assert 'make ci-finalize-pages-dir root="$PAGES_PUBLISH_DIR"' in materialize_run
    assert _step_uses(publish, "Upload GitHub Pages artifact").startswith(
        "actions/upload-pages-artifact@"
    )
    assert _step_with(publish, "Upload GitHub Pages artifact") == {
        "path": "${{ env.PAGES_PUBLISH_DIR }}",
        "include-hidden-files": True,
    }
    assert _step_uses(publish, "Deploy GitHub Pages artifact").startswith("actions/deploy-pages@")
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
        step.get("run", "") for step in _steps(publish) if isinstance(step.get("run"), str)
    )
    assert "make thumbnails" not in publish_runs
    assert "make index" not in publish_runs
    assert "make site" not in publish_runs


def test_browser_make_targets_retry_only_failed_tests_once() -> None:
    """Browser Make targets retry their failed tests and surface flaky passes."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "--last-failed --last-failed-no-failures none" in makefile
    assert "FLAKY BROWSER TESTS" in makefile
    assert "A retry passed after an initial failure." in makefile


def test_update_publish_job_writes_classic_deployment_records() -> None:
    """Update publish job writes classic deployment records."""
    workflow = _load_workflow("update.yml")
    publish = _job(workflow, "publish")

    main_guard = (
        "github.event_name != 'pull_request' && steps.setup.outputs.token-available == 'true'"
    )
    log_url = "${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"

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
    assert '-f environment_url="${{ steps.live-site-url.outputs.url }}"' in success_run
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
    """Update thumbnail persistence and cleanup stay bounded."""
    workflow = _load_workflow("update.yml")
    persist = _job(workflow, "persist-thumbnails")
    cleanup = _job(workflow, "cleanup-preview")

    persist_condition = persist["if"].strip()
    assert persist_condition.startswith("!cancelled() &&")
    assert "needs.publish.result == 'success'" in persist_condition
    validate_run = _step_run(persist, "Validate thumbnail artifact")
    assert "validate-thumbnail-artifact --root .artifacts/thumbnail-persist" in validate_run
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
    assert "commit=$CLEANUP_COMMIT" in _step_run(cleanup, "Resolve gh-pages cleanup commit")
    cleanup_materialize_run = _step_run(cleanup, "Materialize GitHub Pages payload")
    assert "git archive" in cleanup_materialize_run
    assert 'make ci-finalize-pages-dir root="$PAGES_PUBLISH_DIR"' in cleanup_materialize_run
    assert _step_uses(cleanup, "Upload GitHub Pages artifact").startswith(
        "actions/upload-pages-artifact@"
    )
    assert _step_with(cleanup, "Deploy GitHub Pages artifact")["timeout"] == (
        "${{ env.PAGES_DEPLOY_TIMEOUT_MS }}"
    )
    assert _step(cleanup, "Remove PR preview link comment")["with"]["delete"] is True


def test_refresh_python_locks_workflow_uses_dependabot_and_make_lock_contract() -> None:
    """Refresh python locks workflow uses dependabot and make lock contract."""
    workflow = _load_workflow("refresh-python-locks.yml")
    on_block = _workflow_on(workflow)
    refresh = _job(workflow, "refresh-locks")

    assert on_block["pull_request"]["branches"] == ["main"]
    assert on_block["pull_request"]["paths"] == ["pyproject.toml", "uv.lock"]
    assert on_block["pull_request"]["types"] == ["opened", "reopened", "synchronize"]
    assert "dependabot[bot]" in refresh["if"]
    assert "github.actor == 'dependabot[bot]'" in refresh["if"]
    assert "dependabot/uv/" in refresh["if"]
    assert _step_run(refresh, "Install uv").strip() == "python -m pip install --upgrade pip uv"
    assert _step_run(refresh, "Refresh Python lock files").strip() == "make lock"
    upload_step = _step(refresh, "Upload refreshed Python lock files")
    assert _step_uses(refresh, "Upload refreshed Python lock files").startswith(
        "actions/upload-artifact@"
    )
    assert upload_step["with"]["path"].splitlines()[0] == "uv.lock"


def test_commit_python_locks_workflow_keeps_validation_and_verified_commit_steps() -> None:
    """Commit python locks workflow keeps validation and verified commit steps."""
    workflow = _load_workflow("commit-python-locks.yml")
    on_block = _workflow_on(workflow)
    commit = _job(workflow, "commit-locks")

    assert on_block["workflow_run"]["workflows"] == ["Refresh Python Locks"]
    assert on_block["workflow_run"]["types"] == ["completed"]
    assert "Refresh Python Locks" in commit["if"]
    assert "workflow_run.event == 'pull_request'" in commit["if"]
    assert commit["env"]["LOCK_FILE_PATHSPEC"] == "uv.lock"
    assert "LOCK_REFRESH_PR_NUMBER" not in commit["env"]
    assert "LOCK_FILE_ARGS" not in commit["env"]

    triggering_run = _step_run(commit, "Validate triggering Dependabot workflow run")
    assert "lock-refresh-workflow-run" in triggering_run
    assert '--event-path "$GITHUB_EVENT_PATH"' in triggering_run
    assert '--repository "$GITHUB_REPOSITORY"' in triggering_run

    artifact_detection = _step(commit, "Detect lock refresh artifact")
    assert (
        artifact_detection["env"]["LOCK_REFRESH_ARTIFACT_NAME"]
        == "${{ steps.triggering-run.outputs.artifact-name }}"
    )
    assert (
        artifact_detection["env"]["LOCK_REFRESH_RUN_ID"]
        == "${{ steps.triggering-run.outputs.run-id }}"
    )
    assert "${{ github.event.workflow_run.id }}" not in artifact_detection["run"]

    download_step = _step_with(commit, "Download refreshed Python lock files")
    assert download_step["name"] == "${{ steps.triggering-run.outputs.artifact-name }}"
    assert download_step["run-id"] == "${{ steps.triggering-run.outputs.run-id }}"

    artifact_validation = _step_run(commit, "Validate downloaded artifact contents")
    assert "validate-lock-artifact" in artifact_validation
    assert '--expected-pr-number "$LOCK_REFRESH_PR_NUMBER"' in artifact_validation
    assert '--expected-head-sha "$LOCK_REFRESH_HEAD_SHA"' in artifact_validation
    assert '--expected-head-ref "$LOCK_REFRESH_HEAD_REF"' in artifact_validation
    validation_step = _step(commit, "Validate downloaded artifact contents")
    assert (
        validation_step["env"]["LOCK_REFRESH_PR_NUMBER"]
        == "${{ steps.triggering-run.outputs.pr-number }}"
    )
    assert (
        validation_step["env"]["LOCK_REFRESH_HEAD_REF"]
        == "${{ steps.triggering-run.outputs.head-ref }}"
    )
    assert (
        validation_step["env"]["LOCK_REFRESH_HEAD_SHA"]
        == "${{ steps.triggering-run.outputs.head-sha }}"
    )
    assert "Read refresh metadata" not in [step.get("name") for step in _steps(commit)]
    branch_state = _step_run(commit, "Validate Dependabot branch state")
    assert "${{ steps.metadata.outputs" not in branch_state
    assert 'gh pr view "$LOCK_REFRESH_PR_NUMBER"' in branch_state
    assert '"$LOCK_REFRESH_HEAD_SHA"' in branch_state
    assert '"$LOCK_REFRESH_HEAD_REF"' in branch_state
    assert _step_run(commit, "Copy refreshed Python lock files into workspace").strip() == (
        'cp "$LOCK_REFRESH_ROOT/uv.lock" uv.lock'
    )
    verified_commit = _step(commit, "Commit refreshed Python lock files (verified)")
    assert _step_uses(commit, "Commit refreshed Python lock files (verified)") == (
        "./.github/actions/verified-commit"
    )
    assert verified_commit["with"]["base-branch"] == "${{ steps.triggering-run.outputs.head-ref }}"
    assert (
        verified_commit["with"]["expected-head-sha"]
        == "${{ steps.triggering-run.outputs.head-sha }}"
    )


def test_audit_and_refresh_action_workflows_keep_expected_entrypoints() -> None:
    """Audit and refresh action workflows keep expected entrypoints."""
    audit = _load_workflow("audit-repo-settings.yml")
    live_smoke = _load_workflow("live-site-smoke.yml")
    refresh = _load_workflow("refresh-action-shas.yml")

    assert set(_workflow_on(audit)) == {"workflow_dispatch", "schedule"}
    assert _workflow_on(audit)["schedule"] == [{"cron": "23 8 * * 1"}]
    assert "audit-repo-settings" in _step_run(_job(audit, "audit"), "Audit repository settings")
    audit_job = _job(audit, "audit")
    audit_run = _step_run(audit_job, "Audit repository settings")
    assert audit_job["permissions"] == {"contents": "read", "issues": "write"}
    assert "> audit-repo-settings.json 2>&1" in audit_run
    assert 'echo "status=$status" >> "$GITHUB_OUTPUT"' in audit_run
    drift_open_run = _step_run(audit_job, "Open or update repository settings drift issue")
    assert "make ci-alert-issue" in drift_open_run
    assert "state=open" in drift_open_run
    assert "detail_file=audit-repo-settings.json" in drift_open_run
    drift_close_run = _step_run(audit_job, "Close repository settings drift issue when clean")
    assert "make ci-alert-issue" in drift_close_run
    assert "state=close" in drift_close_run

    # The stale-preview audit is folded into the settings audit step so the run
    # stays green in the actionlint linter and shares one drift-alert channel.
    assert "make ci-audit-repo-settings" in audit_run
    assert "make ci-audit-previews" in audit_run
    audit_fallback = _step(audit_job, "Alert when repository settings audit setup fails")
    assert audit_fallback["if"] == "failure() && steps.audit.outputs.status == ''"
    assert audit_fallback["env"]["GH_TOKEN"] == "${{ github.token }}"
    audit_fallback_run = _step_run(audit_job, "Alert when repository settings audit setup fails")
    assert "make ci-alert-issue" in audit_fallback_run
    assert "state=setup-failure" in audit_fallback_run

    assert set(_workflow_on(live_smoke)) == {"workflow_dispatch", "schedule"}
    assert _workflow_on(live_smoke)["schedule"] == [{"cron": "17 6 * * *"}]
    smoke_job = _job(live_smoke, "smoke")
    assert smoke_job["permissions"] == {"contents": "read", "issues": "write"}
    assert _step_uses(smoke_job, "CI setup") == "./.github/actions/ci-setup"
    assert (
        _step_run(smoke_job, "Run published-site browser verification").strip().startswith("set +e")
    )
    assert "make test-browser-live" in _step_run(
        smoke_job, "Run published-site browser verification"
    )
    smoke_open_run = _step_run(smoke_job, "Open or update live-site smoke issue")
    assert "make ci-alert-issue" in smoke_open_run
    assert "state=open" in smoke_open_run
    smoke_close_run = _step_run(smoke_job, "Close live-site smoke issue when clean")
    assert "make ci-alert-issue" in smoke_close_run
    assert "state=close" in smoke_close_run
    open_token = _step(smoke_job, "Open or update live-site smoke issue")["env"]["GH_TOKEN"]
    assert open_token == "${{ github.token }}"
    close_token = _step(smoke_job, "Close live-site smoke issue when clean")["env"]["GH_TOKEN"]
    assert close_token == "${{ github.token }}"
    smoke_fallback = _step(smoke_job, "Alert when live-site smoke setup fails")
    assert smoke_fallback["if"] == "failure() && steps.smoke.outputs.status == ''"
    assert smoke_fallback["env"]["GH_TOKEN"] == "${{ github.token }}"
    smoke_fallback_run = _step_run(smoke_job, "Alert when live-site smoke setup fails")
    assert "make ci-alert-issue" in smoke_fallback_run
    assert "state=setup-failure" in smoke_fallback_run

    assert set(_workflow_on(refresh)) == {"schedule", "workflow_dispatch"}
    assert _workflow_on(refresh)["schedule"] == [{"cron": "0 3 1 * *"}]
    refresh_job = _job(refresh, "refresh")
    commit_uses = _step_uses(refresh_job, "Commit changes (verified)")
    assert commit_uses == "./.github/actions/verified-commit"
    assert _step_uses(refresh_job, "Set up Python").startswith("actions/setup-python@")
    assert _step_run(refresh_job, "Update action SHAs").strip() == "make refresh-action-shas"
    update_token = _step(refresh_job, "Update action SHAs")["env"]["GH_TOKEN"]
    assert update_token == "${{ steps.escalation-token.outputs.token }}"


def test_codeql_workflow_scans_supported_languages_with_shared_config() -> None:
    """CodeQL workflow scans JavaScript, Python, and Actions with the shared config."""
    workflow = _load_workflow("codeql.yml")
    on_block = _workflow_on(workflow)

    assert set(on_block) == {"workflow_dispatch", "push", "pull_request", "schedule"}
    assert on_block["push"]["branches"] == ["main"]
    assert on_block["pull_request"]["branches"] == ["main"]
    assert on_block["schedule"] == [{"cron": "30 6 * * 1"}]

    assert workflow["permissions"] == {
        "actions": "read",
        "contents": "read",
        "security-events": "write",
    }

    assert set(_jobs(workflow)) == {"analyze-javascript", "analyze-python", "analyze-actions"}

    languages = {
        "analyze-javascript": "javascript-typescript",
        "analyze-python": "python",
        "analyze-actions": "actions",
    }
    for job_name, language in languages.items():
        job = _job(workflow, job_name)
        init_inputs = _step_with(job, "Initialize CodeQL")
        assert init_inputs["languages"] == language
        assert init_inputs["config-file"] == "./.github/codeql/codeql-config.yml"
        assert _step_with(job, "Perform CodeQL Analysis")["category"] == f"/language:{language}"
        for step_name in ("Initialize CodeQL", "Autobuild", "Perform CodeQL Analysis"):
            uses = _step_uses(job, step_name)
            assert CODEQL_ACTION_SHA_PIN.fullmatch(uses), (
                f"Expected github/codeql-action pinned to a 40-char SHA, got {uses!r}"
            )


def test_codeql_config_ignores_generated_and_vendored_paths() -> None:
    """CodeQL config ignores generated and vendored paths."""
    config = yaml.safe_load(
        (REPO_ROOT / ".github" / "codeql" / "codeql-config.yml").read_text(encoding="utf-8")
    )
    assert isinstance(config, dict)
    assert config["paths-ignore"] == [
        "tests/**",
        "apps/*/js/vendor/**",
        "js/data.js",
        "js/gallery-config.js",
    ]


def _workflow_and_action_files() -> list[Path]:
    """Return every workflow file and composite action definition."""
    files = sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.yaml"))
    files += sorted(ACTIONS_DIR.glob("*/action.yml")) + sorted(ACTIONS_DIR.glob("*/action.yaml"))
    return files


def _iter_uses_references() -> list[tuple[Path, int, str, str | None]]:
    """Return every ``uses:`` reference across workflows and composite actions."""
    references: list[tuple[Path, int, str, str | None]] = []
    for path in _workflow_and_action_files():
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            match = USES_LINE_PATTERN.match(line)
            if match is not None:
                references.append((path, lineno, match.group(1), match.group(2)))
    return references


def test_all_action_references_are_pinned_or_local() -> None:
    """Every uses: reference is a local path or a SHA pin with a version comment."""
    references = _iter_uses_references()
    assert references, "expected at least one uses: reference to validate"

    for path, lineno, ref, comment in references:
        # Repo-relative so a failure names the exact file among the action.yml copies.
        location = f"{path.relative_to(REPO_ROOT)}:{lineno}"
        if ref.startswith("./"):
            continue
        assert SHA_PINNED_PATTERN.fullmatch(ref), (
            f"{location} action reference is not pinned to a 40-char commit SHA: {ref}"
        )
        assert comment is not None and comment.startswith("#"), (
            f"{location} SHA-pinned action reference must keep a version comment: {ref}"
        )


def test_no_python_heredocs_remain_in_workflows_or_actions() -> None:
    """No workflow or composite action embeds an inline Python heredoc."""
    # Also match versioned interpreters such as python3.12 so no heredoc slips by.
    heredoc_pattern = re.compile(r"python3?(?:\.\d+)?\s+-\s*<<")
    files = _workflow_and_action_files()
    assert files, "expected at least one workflow or action file to validate"

    for path in files:
        assert not heredoc_pattern.search(path.read_text(encoding="utf-8")), (
            f"{path.relative_to(REPO_ROOT)} embeds an inline Python heredoc; "
            "move the logic into scripts/ and call it as a command instead"
        )


def test_dependency_audit_workflow_runs_audits_and_syncs_alert_issue() -> None:
    """Dependency audit workflow runs audits and syncs the alert issue."""
    workflow = _load_workflow("dependency-audit.yml")
    on_block = _workflow_on(workflow)

    assert set(on_block) == {"workflow_dispatch", "schedule"}
    assert on_block["schedule"] == [{"cron": "0 6 * * 1"}]

    assert set(_jobs(workflow)) == {"audit"}
    audit = _job(workflow, "audit")
    assert audit["permissions"] == {"contents": "read", "issues": "write"}
    assert _step_uses(audit, "CI setup") == "./.github/actions/ci-setup"

    audit_run = _step_run(audit, "Run dependency audits")
    assert audit_run.startswith("set +e")
    for target in ("make audit-python", "make audit-node", "make check-overrides"):
        assert target in audit_run
    assert 'echo "status=$status" >> "$GITHUB_OUTPUT"' in audit_run
    assert audit_run.rstrip().endswith("exit 0")

    open_step = _step(audit, "Open or update dependency audit issue")
    assert open_step["if"] == "steps.audit.outputs.status != '0'"
    open_run = _step_run(audit, "Open or update dependency audit issue")
    assert "make ci-alert-issue" in open_run
    assert "state=open" in open_run

    close_step = _step(audit, "Close dependency audit issue when clean")
    assert close_step["if"] == "steps.audit.outputs.status == '0'"
    close_run = _step_run(audit, "Close dependency audit issue when clean")
    assert "make ci-alert-issue" in close_run
    assert "state=close" in close_run

    fail_step = _step(audit, "Fail workflow when audit detects issues")
    assert fail_step["if"] == "steps.audit.outputs.status != '0'"
    assert _step_run(audit, "Fail workflow when audit detects issues").strip() == "exit 1"

    fallback_step = _step(audit, "Alert when dependency audit setup fails")
    assert fallback_step["if"] == "failure() && steps.audit.outputs.status == ''"
    assert fallback_step["env"]["GH_TOKEN"] == "${{ github.token }}"
    fallback_run = _step_run(audit, "Alert when dependency audit setup fails")
    assert "make ci-alert-issue" in fallback_run
    assert "state=setup-failure" in fallback_run


def test_scheduled_maintenance_workflows_always_create_pull_requests() -> None:
    """Scheduled maintenance workflows always create pull requests."""
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
            f"Expected actions/create-github-app-token pinned to a 40-char SHA, got {token_uses!r}"
        )
        assert token_inputs["app-id"] == "${{ vars.ESCALATION_APP_ID }}"
        assert token_inputs["private-key"] == "${{ secrets.ESCALATION_APP_PRIVATE_KEY }}"

        commit_inputs = _step_with(refresh, "Commit changes (verified)")
        assert commit_inputs["github-token"] == "${{ steps.escalation-token.outputs.token }}"
        assert commit_inputs["base-branch"] == "${{ github.event.repository.default_branch }}"
        assert commit_inputs["commit-mode"] == "force-pr"
        assert commit_inputs["fallback-branch-prefix"] == fallback_branch_prefix


def test_setup_python_steps_cache_uv_lock_and_uv_downloads() -> None:
    """Setup python steps cache uv lock and uv downloads."""
    update = _load_workflow("update.yml")
    refresh = _load_workflow("refresh-python-locks.yml")
    ci_setup = yaml.safe_load(
        (REPO_ROOT / ".github" / "actions" / "ci-setup" / "action.yml").read_text(encoding="utf-8")
    )

    for job_name in ("quick-gates", "heavy-checks", "root-browser", "app-shard", "assemble-site"):
        assert _step_uses(_job(update, job_name), "CI setup") == "./.github/actions/ci-setup"
        assert _step_with(_job(update, job_name), "CI setup")["install-deps"] == "true"
    for job_name in ("quick-gates", "heavy-checks", "assemble-site"):
        assert _step_with(_job(update, job_name), "CI setup")["install-browsers"] == "false"
    assert _step_with(_job(update, "publish"), "Cache Playwright browsers")["key"] == (
        "playwright-${{ hashFiles('uv.lock') }}"
    )
    ci_setup_cache = next(
        step
        for step in ci_setup["runs"]["steps"]
        if step.get("name") == "Cache Playwright browsers"
    )
    assert (
        ci_setup_cache["if"] == "inputs.install-deps == 'true' && inputs.install-browsers == 'true'"
    )
    assert ci_setup_cache["id"] == "playwright-cache"
    assert ci_setup_cache["with"]["key"] == "playwright-${{ hashFiles('uv.lock') }}"
    assert ci_setup["inputs"]["install-browsers"]["default"] == "true"
    venv_cache = next(
        step
        for step in ci_setup["runs"]["steps"]
        if step.get("name") == "Cache virtual environment"
    )
    assert venv_cache["with"]["path"] == ".venv"
    assert venv_cache["with"]["key"] == (
        "venv-${{ runner.os }}-${{ runner.arch }}"
        "-${{ steps.setup-python.outputs.python-version }}-${{ hashFiles('uv.lock') }}"
    )
    setup_python = next(
        step for step in ci_setup["runs"]["steps"] if step.get("name") == "Set up Python"
    )
    assert setup_python["id"] == "setup-python"
    assert "restore-keys" not in venv_cache["with"]
    node_modules_cache = next(
        step for step in ci_setup["runs"]["steps"] if step.get("name") == "Cache node modules"
    )
    assert node_modules_cache["with"]["path"] == "node_modules"
    assert node_modules_cache["with"]["key"] == (
        "node-modules-${{ runner.os }}-${{ inputs.node-version }}"
        "-${{ hashFiles('package-lock.json') }}"
    )
    assert "restore-keys" not in node_modules_cache["with"]
    uv_install = next(
        step for step in ci_setup["runs"]["steps"] if step.get("name") == "Install uv"
    )
    # uv itself must always be installed: audit-python invokes uv directly,
    # so a cached .venv is not a substitute for the uv binary.
    assert uv_install["if"] == "inputs.install-deps == 'true'"
    workspace_install = next(
        step
        for step in ci_setup["runs"]["steps"]
        if step.get("name") == "Install workspace dependencies"
    )
    for skip_guard in (
        'if [ "$VENV_CACHE_HIT" != "true" ]',
        'if [ "$NODE_MODULES_CACHE_HIT" != "true" ]',
        'if [ "$PLAYWRIGHT_CACHE_HIT" = "true" ]',
        "make setup-playwright-ci",
    ):
        assert skip_guard in workspace_install["run"]
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
    assert ci_uv_cache["uses"] == ("actions/cache@55cc8345863c7cc4c66a329aec7e433d2d1c52a9")
    assert ci_uv_cache["with"]["path"] == "~/.cache/uv"
    assert ci_uv_cache["with"]["key"] == (
        "uv-${{ runner.os }}-${{ inputs.python-version }}-${{ hashFiles('uv.lock') }}"
    )
    assert (
        "uv-${{ runner.os }}-${{ inputs.python-version }}-" in ci_uv_cache["with"]["restore-keys"]
    )
