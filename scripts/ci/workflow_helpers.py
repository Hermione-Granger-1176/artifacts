#!/usr/bin/env python3
"""Provide small command-line helpers for GitHub Actions workflows.

These helpers keep trust-boundary decisions and artifact validation in tested
Python instead of inline shell.

Workflow entry points used by GitHub Actions. For normal local use, prefer
`make ci` wrappers instead of calling this module directly.

Examples:
    python scripts/ci/workflow_helpers.py app-token-policy --event-name pull_request \
        --head-repo-fork false --pr-author login
    python scripts/ci/workflow_helpers.py read-lock-metadata --root .artifacts/lock-refresh
    python scripts/ci/workflow_helpers.py validate-lock-artifact --root .artifacts/lock-refresh
    python scripts/ci/workflow_helpers.py invalidate-thumbnails --event-name pull_request \
        --repo owner/repo --pr-number 42
    python scripts/ci/workflow_helpers.py thumbnail-plan --event-name push \
        --repo owner/repo --commit-sha abc123 \
        --actor bot-login[bot] --app-bot-login bot-login[bot]
    python scripts/ci/workflow_helpers.py validate-thumbnail-artifact \
        --root .artifacts/thumbnail-persist
    python scripts/ci/workflow_helpers.py audit-repo-settings --repo owner/repo
    python scripts/ci/workflow_helpers.py sync-alert-issue --repo owner/repo \
        --title "Alert title" --body "Alert body" --label ci --should-exist true
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from scripts.build import thumbnail_plan as _thumbnail_plan
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

LOCK_ARTIFACT_REQUIRED_FILES = {
    "requirements": Path("locks/requirements.lock"),
    "requirements-dev": Path("locks/requirements-dev.lock"),
    **LOCK_ARTIFACT_FILES,
}

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


def validate_lock_refresh_artifact(root: Path) -> None:
    """Fail if a downloaded lock-refresh artifact tree contains unsafe paths."""
    reject_symlinks(root)

    for relative_path in LOCK_ARTIFACT_REQUIRED_FILES.values():
        path = root / relative_path
        if not path.is_file():
            raise ValueError(
                f"Required artifact file missing or not a regular file: {path}"
            )


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
        retry_delay_seconds=_gh_api.GH_API_RETRY_DELAY_SECONDS,
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
) -> str:
    """Run ``gh api`` with form fields and the shared retry/timeout behavior."""
    return _gh_api.run_gh_api_form(
        endpoint,
        method=method,
        fields=fields,
        description=description,
        jq_expr=jq_expr,
        max_attempts=_gh_api.GH_API_MAX_ATTEMPTS,
        retry_delay_seconds=_gh_api.GH_API_RETRY_DELAY_SECONDS,
        sleep_fn=time.sleep,
        timeout_seconds=_gh_api.GH_API_TIMEOUT_SECONDS,
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
) -> dict[str, object]:
    """Return the strict thumbnail automation plan for one workflow event."""
    return _thumbnail_plan.thumbnail_plan(
        event_name=event_name,
        repo=repo,
        pr_number=pr_number,
        commit_sha=commit_sha,
        head_repo_fork=head_repo_fork,
        pr_author=pr_author,
        actor=actor,
        app_bot_login=app_bot_login,
        apps_root=apps_root,
        list_changed_files_fn=list_changed_files,
        list_commit_files_fn=list_commit_files,
        missing_thumbnail_slugs_fn=missing_thumbnail_slugs,
        runtime_change_plan_fn=runtime_change_plan,
        associated_pr_kind_for_commit_fn=associated_pr_kind_for_commit,
    )


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


def list_changed_files(
    *, event_name: str, repo: str, pr_number: str, commit_sha: str
) -> list[str]:
    """Return the changed file list for a pull request or push event."""
    return _thumbnail_plan.list_changed_files(
        event_name=event_name,
        repo=repo,
        pr_number=pr_number,
        commit_sha=commit_sha,
        run_gh_api_fn=_run_gh_api,
    )


def invalidate_thumbnails(
    *, event_name: str, repo: str, pr_number: str, commit_sha: str
) -> list[str]:
    """Delete thumbnails for apps whose runtime or shared app shell changed."""
    return _thumbnail_plan.invalidate_thumbnails(
        event_name=event_name,
        repo=repo,
        pr_number=pr_number,
        commit_sha=commit_sha,
        list_changed_files_fn=list_changed_files,
        runtime_change_plan_fn=runtime_change_plan,
    )


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
    issue_url: str = "",
    should_exist: bool,
) -> str:
    """Create, update, close, or reuse one alert issue addressed by exact title."""
    del issue_url
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

    thumb_parser = subparsers.add_parser(
        "invalidate-thumbnails",
        help="Delete stale thumbnails for apps with runtime or shared shell changes",
    )
    thumb_parser.add_argument("--event-name", required=True)
    thumb_parser.add_argument("--repo", required=True)
    thumb_parser.add_argument("--pr-number", default="")
    thumb_parser.add_argument("--commit-sha", default="")

    thumbnail_plan_parser = subparsers.add_parser(
        "thumbnail-plan",
        help="Plan thumbnail generation and persistence for changed files",
    )
    thumbnail_plan_parser.add_argument("--event-name", required=True)
    thumbnail_plan_parser.add_argument("--repo", required=True)
    thumbnail_plan_parser.add_argument("--pr-number", default="")
    thumbnail_plan_parser.add_argument("--commit-sha", default="")
    thumbnail_plan_parser.add_argument("--head-repo-fork", default="false")
    thumbnail_plan_parser.add_argument("--pr-author", default="")
    thumbnail_plan_parser.add_argument("--actor", default="")
    thumbnail_plan_parser.add_argument("--app-bot-login", default="")

    thumbnail_artifact_parser = subparsers.add_parser(
        "validate-thumbnail-artifact",
        help="Validate a downloaded thumbnail persistence artifact",
    )
    thumbnail_artifact_parser.add_argument("--root", required=True)

    audit_parser = subparsers.add_parser(
        "audit-repo-settings",
        help="Audit critical GitHub repository settings used by deployment workflows",
    )
    audit_parser.add_argument("--repo", required=True)
    audit_parser.add_argument("--default-branch", default="main")
    audit_parser.add_argument("--pages-branch", default="gh-pages")

    alert_parser = subparsers.add_parser(
        "sync-alert-issue",
        help="Ensure one GitHub issue exists or is closed for a monitored alert",
    )
    alert_parser.add_argument("--repo", required=True)
    alert_parser.add_argument("--title", required=True)
    alert_parser.add_argument("--body", required=True)
    alert_parser.add_argument("--label", action="append", default=[])
    alert_parser.add_argument("--issue-url", default="")
    alert_parser.add_argument("--should-exist", required=True)

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
    validate_lock_refresh_artifact(Path(args.root))
    return 0


def _handle_invalidate_thumbnails(args: argparse.Namespace) -> int:
    """Print invalidated thumbnail paths, or a no-op message."""
    invalidated = invalidate_thumbnails(
        event_name=args.event_name,
        repo=args.repo,
        pr_number=args.pr_number,
        commit_sha=args.commit_sha,
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
        head_repo_fork=_parse_bool(args.head_repo_fork),
        pr_author=args.pr_author,
        actor=args.actor,
        app_bot_login=args.app_bot_login,
    )
    print(json.dumps(plan, sort_keys=True))
    return 0


def _handle_validate_thumbnail_artifact(args: argparse.Namespace) -> int:
    """Validate a downloaded thumbnail artifact and print its plan JSON."""
    plan = validate_thumbnail_artifact(Path(args.root))
    print(json.dumps(plan, sort_keys=True))
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


def _handle_sync_alert_issue(args: argparse.Namespace) -> int:
    """Synchronize one alert issue with the current monitored state."""
    issue_url = sync_alert_issue(
        repo=args.repo,
        title=args.title,
        body=args.body,
        labels=args.label,
        issue_url=args.issue_url,
        should_exist=_parse_bool(args.should_exist),
    )
    print(issue_url)
    return 0


COMMAND_HANDLERS = {
    "app-token-policy": _handle_app_token_policy,
    "read-lock-metadata": _handle_read_lock_metadata,
    "validate-lock-artifact": _handle_validate_lock_artifact,
    "invalidate-thumbnails": _handle_invalidate_thumbnails,
    "thumbnail-plan": _handle_thumbnail_plan,
    "validate-thumbnail-artifact": _handle_validate_thumbnail_artifact,
    "audit-repo-settings": _handle_audit_repo_settings,
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
