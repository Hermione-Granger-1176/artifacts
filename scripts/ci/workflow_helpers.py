#!/usr/bin/env python3
"""Provide small command-line helpers for GitHub Actions workflows.

These helpers keep trust-boundary decisions and artifact validation in tested
Python instead of inline shell.

Most subcommands are GitHub Actions entry points; workflow steps and local runs
invoke this CLI through the Make targets below, so prefer those targets over
calling this module directly. The exceptions are the thumbnail plan and
validation subcommands (thumbnail-plan, invalidate-thumbnails,
validate-thumbnail-artifact), which update.yml invokes directly because their
arguments come straight from the GitHub event context.

Examples:
    PLAN_JSON='{"browser_scope": "none", ...}' make ci-plan-outputs
    make ci-coverage-summary report=js-coverage.txt
    make ci-finalize-pages-dir root=.pages-publish
    make ci-audit-repo-settings repo=owner/repo
    make ci-audit-previews repo=owner/repo
    make ci-alert-issue title="Alert title" \
        run_url=https://github.com/owner/repo/actions/runs/1 \
        state=open detail="Optional extra context"
    make refresh-action-shas
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from scripts.build import thumbnail_plan as _thumbnail_plan
from scripts.ci import app_shards as _app_shards
from scripts.ci import audit_previews as _audit_previews
from scripts.ci import issue_alerts as _issue_alerts
from scripts.ci import repo_audit as _repo_audit
from scripts.lib import app_discovery as _app_discovery
from scripts.lib import gh_api as _gh_api
from scripts.lib.path_validation import reject_symlinks

LOCK_ARTIFACT_FILES = {
    "pr-number": Path(".artifacts/pr-number.txt"),
    "head-sha": Path(".artifacts/head-sha.txt"),
    "head-ref": Path(".artifacts/head-ref.txt"),
}

LOCK_ARTIFACT_LOCK_FILES = {
    "uv": Path("uv.lock"),
}

LOCK_ARTIFACT_REQUIRED_FILES = {
    **LOCK_ARTIFACT_LOCK_FILES,
    **LOCK_ARTIFACT_FILES,
}
LOCK_REFRESH_PR_NUMBER_PATTERN = re.compile(r"[1-9][0-9]*\Z")
LOCK_REFRESH_HEAD_SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
LOCK_REFRESH_HEAD_REF_PATTERN = re.compile(r"dependabot/uv/[A-Za-z0-9][A-Za-z0-9._/-]*\Z")

BOOL_LOOKUP = {
    "true": True,
    "1": True,
    "yes": True,
    "false": False,
    "0": False,
    "no": False,
}


def _parse_bool(value: str) -> bool:
    """Parse a GitHub-style boolean string."""
    normalized = value.strip().lower()
    try:
        return BOOL_LOOKUP[normalized]
    except KeyError as exc:
        raise ValueError(f"Invalid boolean value: {value}") from exc


def app_token_allowed(*, event_name: str, head_repo_fork: bool, pr_author: str) -> bool:
    """Return whether a workflow run may mint the GitHub App token."""
    if event_name != "pull_request":
        return True
    if head_repo_fork:
        return False
    return pr_author != "dependabot[bot]"


def read_lock_refresh_metadata(root: Path) -> dict[str, str]:
    """Read required lock-refresh metadata values from a downloaded artifact tree."""
    return {
        key: (root / relative_path).read_text(encoding="utf-8").strip()
        for key, relative_path in LOCK_ARTIFACT_FILES.items()
    }


def _expected_lock_refresh_metadata(
    *, pr_number: str, head_sha: str, head_ref: str
) -> dict[str, str]:
    """Return authenticated lock-refresh metadata after strict validation."""
    expected = {
        "pr-number": pr_number,
        "head-sha": head_sha,
        "head-ref": head_ref,
    }
    patterns = {
        "pr-number": LOCK_REFRESH_PR_NUMBER_PATTERN,
        "head-sha": LOCK_REFRESH_HEAD_SHA_PATTERN,
        "head-ref": LOCK_REFRESH_HEAD_REF_PATTERN,
    }
    for key, pattern in patterns.items():
        if not pattern.fullmatch(expected[key]):
            raise ValueError(f"Invalid authenticated lock refresh {key}: {expected[key]!r}")
    return expected


def lock_refresh_workflow_run_context(event_path: Path, *, repository: str) -> dict[str, str]:
    """Return validated Dependabot lock-refresh details from a workflow-run event."""
    event = json.loads(event_path.read_text(encoding="utf-8"))
    if not isinstance(event, dict):
        raise ValueError("Workflow-run event payload must be an object")
    workflow_run = event.get("workflow_run")
    if not isinstance(workflow_run, dict):
        raise ValueError("Workflow-run event payload is missing workflow_run")

    if (
        workflow_run.get("conclusion") != "success"
        or workflow_run.get("name") != "Refresh Python Locks"
        or workflow_run.get("event") != "pull_request"
    ):
        raise ValueError("Unexpected lock refresh workflow run")

    actor = workflow_run.get("actor")
    if not isinstance(actor, dict) or actor.get("login") != "dependabot[bot]":
        raise ValueError("Lock refresh workflow run was not started by Dependabot")

    head_repository = workflow_run.get("head_repository")
    if not isinstance(head_repository, dict) or head_repository.get("full_name") != repository:
        raise ValueError("Lock refresh workflow run did not originate from this repository")

    pull_requests = workflow_run.get("pull_requests")
    if not isinstance(pull_requests, list) or len(pull_requests) != 1:
        raise ValueError("Lock refresh workflow run must reference exactly one pull request")
    pull_request = pull_requests[0]
    if not isinstance(pull_request, dict):
        raise ValueError("Lock refresh workflow run pull request has an invalid shape")
    pr_number = pull_request.get("number")
    run_id = workflow_run.get("id")
    if (
        not isinstance(pr_number, int)
        or isinstance(pr_number, bool)
        or pr_number < 1
        or not isinstance(run_id, int)
        or isinstance(run_id, bool)
        or run_id < 1
    ):
        raise ValueError("Lock refresh workflow run has an invalid numeric identifier")

    expected = _expected_lock_refresh_metadata(
        pr_number=str(pr_number),
        head_sha=str(workflow_run.get("head_sha") or ""),
        head_ref=str(workflow_run.get("head_branch") or ""),
    )
    return {
        "artifact-name": f"python-lock-refresh-{expected['pr-number']}",
        "head-ref": expected["head-ref"],
        "head-sha": expected["head-sha"],
        "pr-number": expected["pr-number"],
        "run-id": str(run_id),
    }


def validate_lock_refresh_artifact(
    root: Path,
    *,
    expected_pr_number: str,
    expected_head_sha: str,
    expected_head_ref: str,
) -> None:
    """Reject unsafe artifact paths or metadata not bound to the triggering run."""
    reject_symlinks(root)

    for relative_path in LOCK_ARTIFACT_REQUIRED_FILES.values():
        path = root / relative_path
        if not path.is_file():
            raise ValueError(f"Required artifact file missing or not a regular file: {path}")

    expected = _expected_lock_refresh_metadata(
        pr_number=expected_pr_number,
        head_sha=expected_head_sha,
        head_ref=expected_head_ref,
    )
    metadata = read_lock_refresh_metadata(root)
    for key, expected_value in expected.items():
        if metadata[key] != expected_value:
            raise ValueError(f"Lock refresh artifact {key} does not match triggering workflow run")


def _run_gh_api(
    endpoint: str,
    *,
    paginate: list[str],
    jq_expr: str,
    description: str,
    required_permission: str | None = None,
) -> str:
    """Run ``gh api`` with bounded retries, timeout, and contextual failures."""
    return _gh_api.run_gh_api(
        endpoint,
        paginate=paginate,
        jq_expr=jq_expr,
        description=description,
        max_attempts=_gh_api.GH_API_MAX_ATTEMPTS,
        sleep_fn=time.sleep,
        subprocess_module=subprocess,
        timeout_seconds=_gh_api.GH_API_TIMEOUT_SECONDS,
        required_permission=required_permission,
    )


def _run_gh_api_json(
    endpoint: str, *, description: str, required_permission: str | None = None
) -> object:
    """Fetch JSON from ``gh api`` and parse it into a Python object."""
    return _gh_api.run_gh_api_json(
        endpoint,
        description=description,
        run_gh_api_fn=_run_gh_api,
        required_permission=required_permission,
    )


def _run_gh_api_form(
    endpoint: str,
    *,
    method: str,
    fields: list[tuple[str, str]],
    description: str,
    jq_expr: str = "",
    required_permission: str | None = None,
) -> str:
    """Run ``gh api`` with form fields and the shared retry/timeout behavior."""
    return _gh_api.run_gh_api_form(
        endpoint,
        method=method,
        fields=fields,
        description=description,
        jq_expr=jq_expr,
        max_attempts=_gh_api.GH_API_MAX_ATTEMPTS,
        sleep_fn=time.sleep,
        timeout_seconds=_gh_api.GH_API_TIMEOUT_SECONDS,
        required_permission=required_permission,
    )


missing_thumbnail_slugs = _app_discovery.missing_thumbnail_slugs
runtime_change_plan = _app_discovery.runtime_change_plan
validate_thumbnail_artifact = _thumbnail_plan.validate_thumbnail_artifact


def associated_pr_kind_for_commit(repo: str, commit_sha: str) -> str:
    """Return the associated PR kind for a commit on ``main`` pushes."""
    return _thumbnail_plan.associated_pr_kind_for_commit(
        repo,
        commit_sha,
        run_gh_api_json_fn=_run_gh_api_json,
    )


def list_commit_files(*, repo: str, commit_sha: str) -> list[str]:
    """Return the changed file list for a single commit (not PR-level)."""
    return _thumbnail_plan.list_commit_files(
        repo=repo,
        commit_sha=commit_sha,
        run_gh_api_fn=_run_gh_api,
    )


def thumbnail_plan(
    *,
    event_name: str,
    repo: str,
    pr_number: str,
    commit_sha: str,
    head_repo_fork: bool = False,
    pr_author: str = "",
    actor: str = "",
    app_bot_login: str = "",
    apps_root: Path | None = None,
    base_sha: str = "",
    head_sha: str = "",
    force_full: bool = False,
) -> dict[str, object]:
    """Return the strict thumbnail automation plan for one workflow event."""
    plan = _thumbnail_plan.thumbnail_plan(
        event_name=event_name,
        repo=repo,
        pr_number=pr_number,
        commit_sha=commit_sha,
        base_sha=base_sha,
        head_sha=head_sha,
        head_repo_fork=head_repo_fork,
        pr_author=pr_author,
        actor=actor,
        app_bot_login=app_bot_login,
        force_full=force_full,
        apps_root=apps_root,
        list_changed_files_fn=list_changed_files,
        list_commit_files_fn=list_commit_files,
        missing_thumbnail_slugs_fn=missing_thumbnail_slugs,
        runtime_change_plan_fn=runtime_change_plan,
        associated_pr_kind_for_commit_fn=associated_pr_kind_for_commit,
    )
    return _app_shards.add_shards(plan, apps_root=apps_root)


def _load_ruleset_detail(repo: str, ruleset: object) -> object:
    """Fetch one ruleset detail payload when the summary response is incomplete."""
    return _repo_audit.load_ruleset_detail(
        repo,
        ruleset,
        run_gh_api_json_fn=_run_gh_api_json,
    )


def audit_repo_settings(
    *,
    repo: str,
    default_branch: str = "main",
    pages_branch: str = "gh-pages",
) -> dict[str, object]:
    """Audit critical repository settings that the release flow depends on."""
    return _repo_audit.audit_repo_settings(
        repo=repo,
        default_branch=default_branch,
        pages_branch=pages_branch,
        run_gh_api_json_fn=_run_gh_api_json,
    )


def audit_previews(*, repo: str, pages_branch: str = "gh-pages") -> list[str]:
    """Detect leaked PR preview directories on the pages branch."""
    return _audit_previews.audit_previews(
        repo=repo,
        pages_branch=pages_branch,
        run_gh_api_json_fn=_run_gh_api_json,
    )


def list_changed_files(*, base_sha: str, head_sha: str) -> list[str]:
    """Return changed files from the checked-out base and head revisions."""
    return _thumbnail_plan.list_changed_files(
        base_sha=base_sha,
        head_sha=head_sha,
        run_git_fn=subprocess.run,
    )


def invalidate_thumbnails(
    *,
    event_name: str,
    repo: str,
    pr_number: str,
    commit_sha: str,
    base_sha: str = "",
    head_sha: str = "",
) -> list[str]:
    """Delete thumbnails for apps whose runtime or shared site assets changed."""
    return _thumbnail_plan.invalidate_thumbnails(
        event_name=event_name,
        repo=repo,
        pr_number=pr_number,
        commit_sha=commit_sha,
        base_sha=base_sha,
        head_sha=head_sha,
        list_changed_files_fn=list_changed_files,
        runtime_change_plan_fn=runtime_change_plan,
    )


# The node test reporter prefixes these lines with an info symbol; matching on
# the ASCII part keeps this module free of ambiguous unicode characters.
JS_COVERAGE_START_MARKER = "start of coverage report"
JS_COVERAGE_END_MARKER = "end of coverage report"


def _plan_str(plan: dict[str, object], key: str) -> str:
    """Return a required string field from a thumbnail automation plan."""
    value = plan.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Plan field {key} must be a string")
    return value


def _plan_bool(plan: dict[str, object], key: str) -> bool:
    """Return a required boolean field from a thumbnail automation plan."""
    value = plan.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"Plan field {key} must be a boolean")
    return value


def plan_output_lines(plan: dict[str, object]) -> list[str]:
    """Flatten a thumbnail automation plan into workflow output key=value lines."""
    skip = "true" if _plan_bool(plan, "skip_verification") else "false"
    return [
        f"browser-scope={_plan_str(plan, 'browser_scope')}",
        f"thumbnail-scope={_plan_str(plan, 'thumbnail_scope')}",
        f"shard-matrix={_app_shards.compact_matrix(plan)}",
        f"shard-count={_app_shards.shard_count(plan)}",
        f"persist-mode={_plan_str(plan, 'persist_mode')}",
        f"reason={_plan_str(plan, 'reason')}",
        f"skip-verification={skip}",
    ]


def extract_coverage_snippet(report: str, *, source: str) -> str:
    """Return the marker-delimited coverage section from a JS coverage report."""
    start = report.find(JS_COVERAGE_START_MARKER)
    if start == -1:
        raise ValueError(f"Coverage report markers not found in {source}")
    # Search past the start marker so an end marker appearing earlier in the
    # report cannot produce an inverted or partial slice.
    end = report.find(JS_COVERAGE_END_MARKER, start + len(JS_COVERAGE_START_MARKER))
    if end == -1:
        raise ValueError(f"Coverage report markers not found in {source}")
    return report[start : end + len(JS_COVERAGE_END_MARKER)]


def finalize_pages_dir(root: Path) -> None:
    """Validate a materialized pages payload and add the .nojekyll marker."""
    reject_symlinks(root)
    (root / ".nojekyll").touch()


def _issue_payloads_by_title(repo: str, title: str) -> list[dict[str, object]]:
    """Return open issue payloads whose title exactly matches ``title``."""
    return _issue_alerts.issue_payloads_by_title(
        repo,
        title,
        run_gh_api_json_fn=_run_gh_api_json,
    )


def sync_alert_issue(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
    should_exist: bool,
) -> str:
    """Create, update, close, or reuse one alert issue addressed by exact title."""
    return _issue_alerts.sync_alert_issue(
        repo=repo,
        title=title,
        body=body,
        labels=labels,
        should_exist=should_exist,
        issue_payloads_by_title_fn=_issue_payloads_by_title,
        run_gh_api_form_fn=_run_gh_api_form,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workflow helper commands")
    subparsers = parser.add_subparsers(dest="command", required=True)

    policy_parser = subparsers.add_parser(
        "app-token-policy", help="Determine whether app-token actions are allowed"
    )
    policy_parser.add_argument("--event-name", required=True)
    policy_parser.add_argument("--head-repo-fork", required=True)
    policy_parser.add_argument("--pr-author", default="")

    metadata_parser = subparsers.add_parser(
        "read-lock-metadata", help="Read lock refresh metadata from an artifact tree"
    )
    metadata_parser.add_argument("--root", required=True)

    artifact_parser = subparsers.add_parser(
        "validate-lock-artifact", help="Validate a downloaded lock refresh artifact"
    )
    artifact_parser.add_argument("--root", required=True)
    artifact_parser.add_argument("--expected-pr-number", required=True)
    artifact_parser.add_argument("--expected-head-sha", required=True)
    artifact_parser.add_argument("--expected-head-ref", required=True)

    workflow_run_parser = subparsers.add_parser(
        "lock-refresh-workflow-run",
        help="Validate a triggering Dependabot lock-refresh workflow run",
    )
    workflow_run_parser.add_argument("--event-path", required=True)
    workflow_run_parser.add_argument("--repository", required=True)

    thumb_parser = subparsers.add_parser(
        "invalidate-thumbnails",
        help="Delete stale thumbnails for apps with runtime or shared shell changes",
    )
    thumb_parser.add_argument("--event-name", required=True)
    thumb_parser.add_argument("--repo", required=True)
    thumb_parser.add_argument("--pr-number", default="")
    thumb_parser.add_argument("--commit-sha", default="")
    thumb_parser.add_argument("--base-sha", default="")
    thumb_parser.add_argument("--head-sha", default="")

    thumbnail_plan_parser = subparsers.add_parser(
        "thumbnail-plan",
        help="Plan thumbnail generation and persistence for changed files",
    )
    thumbnail_plan_parser.add_argument("--event-name", required=True)
    thumbnail_plan_parser.add_argument("--repo", required=True)
    thumbnail_plan_parser.add_argument("--pr-number", default="")
    thumbnail_plan_parser.add_argument("--commit-sha", default="")
    thumbnail_plan_parser.add_argument("--base-sha", default="")
    thumbnail_plan_parser.add_argument("--head-sha", default="")
    thumbnail_plan_parser.add_argument("--head-repo-fork", default="false")
    thumbnail_plan_parser.add_argument("--pr-author", default="")
    thumbnail_plan_parser.add_argument("--actor", default="")
    thumbnail_plan_parser.add_argument("--app-bot-login", default="")
    thumbnail_plan_parser.add_argument("--force-full", default="false")

    thumbnail_artifact_parser = subparsers.add_parser(
        "validate-thumbnail-artifact",
        help="Validate a downloaded thumbnail persistence artifact",
    )
    thumbnail_artifact_parser.add_argument("--root", required=True)

    subparsers.add_parser(
        "plan-outputs",
        help="Flatten the PLAN_JSON environment variable into workflow output lines",
    )

    coverage_parser = subparsers.add_parser(
        "coverage-summary",
        help="Print the JavaScript coverage summary markdown for the step summary",
    )
    coverage_parser.add_argument("--report", required=True)

    pages_parser = subparsers.add_parser(
        "finalize-pages-dir",
        help="Reject symlinks in a materialized pages payload and add .nojekyll",
    )
    pages_parser.add_argument("--root", required=True)

    audit_parser = subparsers.add_parser(
        "audit-repo-settings",
        help="Audit critical GitHub repository settings used by deployment workflows",
    )
    audit_parser.add_argument("--repo", required=True)
    audit_parser.add_argument("--default-branch", default="main")
    audit_parser.add_argument("--pages-branch", default="gh-pages")

    previews_parser = subparsers.add_parser(
        "audit-previews",
        help="Detect leaked PR preview directories on the GitHub Pages branch",
    )
    previews_parser.add_argument("--repo", required=True)
    previews_parser.add_argument("--pages-branch", default="gh-pages")

    alert_parser = subparsers.add_parser(
        "sync-alert-issue",
        help="Ensure one GitHub issue exists or is closed for a monitored alert",
    )
    alert_parser.add_argument("--repo", required=True)
    alert_parser.add_argument("--title", required=True)
    alert_parser.add_argument("--run-url", required=True)
    alert_parser.add_argument(
        "--state", required=True, choices=sorted(_issue_alerts.ALERT_BODY_LEADS)
    )
    alert_parser.add_argument("--detail", default="")
    alert_parser.add_argument("--detail-file", default="")
    alert_parser.add_argument("--label", action="append", default=[])

    return parser


def _handle_app_token_policy(args: argparse.Namespace) -> int:
    """Print whether GitHub App token actions are allowed for the current event."""
    allowed = app_token_allowed(
        event_name=args.event_name,
        head_repo_fork=_parse_bool(args.head_repo_fork),
        pr_author=args.pr_author,
    )
    print(f"allowed={'true' if allowed else 'false'}")
    return 0


def _handle_read_lock_metadata(args: argparse.Namespace) -> int:
    """Print lock refresh metadata as JSON."""
    print(json.dumps(read_lock_refresh_metadata(Path(args.root)), sort_keys=True))
    return 0


def _handle_validate_lock_artifact(args: argparse.Namespace) -> int:
    """Validate a downloaded lock refresh artifact tree."""
    validate_lock_refresh_artifact(
        Path(args.root),
        expected_pr_number=args.expected_pr_number,
        expected_head_sha=args.expected_head_sha,
        expected_head_ref=args.expected_head_ref,
    )
    return 0


def _handle_lock_refresh_workflow_run(args: argparse.Namespace) -> int:
    """Print validated lock-refresh workflow-run values as step outputs."""
    context = lock_refresh_workflow_run_context(Path(args.event_path), repository=args.repository)
    for key, value in context.items():
        print(f"{key}={value}")
    return 0


def _handle_invalidate_thumbnails(args: argparse.Namespace) -> int:
    """Print invalidated thumbnail paths, or a no-op message."""
    invalidated = invalidate_thumbnails(
        event_name=args.event_name,
        repo=args.repo,
        pr_number=args.pr_number,
        commit_sha=args.commit_sha,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
    )
    if not invalidated:
        print("No thumbnails invalidated")
    return 0


def _handle_thumbnail_plan(args: argparse.Namespace) -> int:
    """Print the thumbnail automation plan as JSON."""
    plan = thumbnail_plan(
        event_name=args.event_name,
        repo=args.repo,
        pr_number=args.pr_number,
        commit_sha=args.commit_sha,
        base_sha=args.base_sha,
        head_sha=args.head_sha,
        head_repo_fork=_parse_bool(args.head_repo_fork),
        pr_author=args.pr_author,
        actor=args.actor,
        app_bot_login=args.app_bot_login,
        force_full=_parse_bool(args.force_full),
    )
    print(json.dumps(plan, sort_keys=True))
    return 0


def _handle_validate_thumbnail_artifact(args: argparse.Namespace) -> int:
    """Validate a downloaded thumbnail artifact and print its plan JSON."""
    plan = validate_thumbnail_artifact(Path(args.root))
    print(json.dumps(plan, sort_keys=True))
    return 0


def _handle_plan_outputs(args: argparse.Namespace) -> int:
    """Print flattened plan outputs read from the PLAN_JSON environment variable."""
    del args
    raw_plan = os.environ.get("PLAN_JSON", "")
    if not raw_plan:
        raise ValueError("PLAN_JSON environment variable is required")
    plan = json.loads(raw_plan)
    if not isinstance(plan, dict):
        raise ValueError("PLAN_JSON must be a JSON object")
    for line in plan_output_lines(plan):
        print(line)
    return 0


def _handle_coverage_summary(args: argparse.Namespace) -> int:
    """Print the JavaScript coverage summary markdown for GITHUB_STEP_SUMMARY."""
    report = Path(args.report).read_text(encoding="utf-8")
    snippet = extract_coverage_snippet(report, source=args.report)
    print(f"## JavaScript Coverage\n\n```text\n{snippet}\n```")
    return 0


def _handle_finalize_pages_dir(args: argparse.Namespace) -> int:
    """Validate a materialized pages payload and add the .nojekyll marker."""
    finalize_pages_dir(Path(args.root))
    return 0


def _handle_audit_repo_settings(args: argparse.Namespace) -> int:
    """Audit repository settings and print a JSON summary when they match expectations."""
    summary = audit_repo_settings(
        repo=args.repo,
        default_branch=args.default_branch,
        pages_branch=args.pages_branch,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


def _handle_audit_previews(args: argparse.Namespace) -> int:
    """Audit PR preview directories and print the live previews as JSON."""
    previews = audit_previews(repo=args.repo, pages_branch=args.pages_branch)
    # Sorted so the output does not depend on Git trees API response ordering.
    print(json.dumps({"open-previews": sorted(previews)}, sort_keys=True))
    return 0


def _alert_detail(args: argparse.Namespace) -> str:
    """Combine inline detail text and the optional detail file into one block."""
    parts = [args.detail] if args.detail else []
    if args.detail_file:
        content = Path(args.detail_file).read_text(encoding="utf-8").strip()
        parts.append(f"Current failure output:\n\n```text\n{content}\n```")
    return "\n\n".join(parts)


def _handle_sync_alert_issue(args: argparse.Namespace) -> int:
    """Synchronize one alert issue with the current monitored state."""
    body = _issue_alerts.build_alert_body(
        state=args.state,
        run_url=args.run_url,
        detail=_alert_detail(args),
    )
    issue_url = sync_alert_issue(
        repo=args.repo,
        title=args.title,
        body=body,
        labels=args.label or list(_issue_alerts.ALERT_LABELS),
        should_exist=_issue_alerts.alert_should_exist(args.state),
    )
    print(issue_url)
    return 0


COMMAND_HANDLERS = {
    "app-token-policy": _handle_app_token_policy,
    "read-lock-metadata": _handle_read_lock_metadata,
    "validate-lock-artifact": _handle_validate_lock_artifact,
    "lock-refresh-workflow-run": _handle_lock_refresh_workflow_run,
    "invalidate-thumbnails": _handle_invalidate_thumbnails,
    "thumbnail-plan": _handle_thumbnail_plan,
    "validate-thumbnail-artifact": _handle_validate_thumbnail_artifact,
    "plan-outputs": _handle_plan_outputs,
    "coverage-summary": _handle_coverage_summary,
    "finalize-pages-dir": _handle_finalize_pages_dir,
    "audit-repo-settings": _handle_audit_repo_settings,
    "audit-previews": _handle_audit_previews,
    "sync-alert-issue": _handle_sync_alert_issue,
}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = _build_parser().parse_args(argv)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:
        raise ValueError(f"Unsupported command: {args.command}")
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
