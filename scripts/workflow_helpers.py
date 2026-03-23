#!/usr/bin/env python3
"""Provide small command-line helpers for GitHub Actions workflows.

These helpers keep trust-boundary decisions and artifact validation in tested
Python instead of inline shell.

Usage:
    python scripts/workflow_helpers.py app-token-policy --event-name pull_request \
        --head-repo-fork false --pr-author login
    python scripts/workflow_helpers.py read-lock-metadata --root .artifacts/lock-refresh
    python scripts/workflow_helpers.py validate-lock-artifact --root .artifacts/lock-refresh
    python scripts/workflow_helpers.py invalidate-thumbnails --event-name pull_request \
        --repo owner/repo --pr-number 42
    python scripts/workflow_helpers.py check-fallback --result-url https://github.com/...
    python scripts/workflow_helpers.py audit-repo-settings --repo owner/repo
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from itertools import chain
from pathlib import Path
from typing import cast

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

GH_API_TIMEOUT_SECONDS = 15
GH_API_MAX_ATTEMPTS = 3
GH_API_RETRY_DELAY_SECONDS = 0.5
GH_API_RETRYABLE_ERROR_PATTERN = re.compile(
    r"429|502|503|504|timed out|timeout|ECONNRESET|connection reset|network",
    re.IGNORECASE,
)
EXPECTED_MAIN_REQUIRED_CHECKS = {"verify", "secret-scan", "dependency-review"}
EXPECTED_REPOSITORY_VARIABLES = {"APP_ID", "ESCALATION_APP_ID"}
EXPECTED_REPOSITORY_SECRETS = {"APP_PRIVATE_KEY", "ESCALATION_APP_PRIVATE_KEY"}


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
    for walk_root, dirnames, filenames in os.walk(root, followlinks=False):
        for name in chain(dirnames, filenames):
            path = Path(walk_root) / name
            if path.is_symlink():
                raise ValueError(f"Refusing artifact containing symlink: {path}")
        dirnames[:] = [
            name for name in dirnames if not (Path(walk_root) / name).is_symlink()
        ]

    for relative_path in LOCK_ARTIFACT_REQUIRED_FILES.values():
        path = root / relative_path
        if not path.is_file():
            raise ValueError(
                f"Required artifact file missing or not a regular file: {path}"
            )


def _is_retryable_gh_api_failure(message: str) -> bool:
    """Return True when ``gh api`` failed with a likely transient error."""
    return bool(GH_API_RETRYABLE_ERROR_PATTERN.search(message))


def _run_gh_api(
    endpoint: str, *, paginate: list[str], jq_expr: str, description: str
) -> str:
    """Run ``gh api`` with bounded retries, timeout, and contextual failures."""
    command = ["gh", "api", endpoint, *paginate, "--jq", jq_expr]
    last_error: str | None = None

    for attempt in range(1, GH_API_MAX_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=GH_API_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            last_error = (
                f"timed out after {GH_API_TIMEOUT_SECONDS} seconds while {description}"
            )
            if attempt < GH_API_MAX_ATTEMPTS:
                print(
                    f"Retrying gh api for {description} after attempt "
                    f"{attempt}/{GH_API_MAX_ATTEMPTS} timed out.",
                    file=sys.stderr,
                )
                time.sleep(GH_API_RETRY_DELAY_SECONDS * attempt)
                continue
            raise RuntimeError(f"gh api {description} failed: {last_error}") from exc

        if result.returncode == 0:
            return result.stdout

        stderr = (
            result.stderr.strip() or result.stdout.strip() or "unknown gh api error"
        )
        last_error = stderr
        if attempt < GH_API_MAX_ATTEMPTS and _is_retryable_gh_api_failure(stderr):
            print(
                f"Retrying gh api for {description} after attempt "
                f"{attempt}/{GH_API_MAX_ATTEMPTS} failed: {stderr}",
                file=sys.stderr,
            )
            time.sleep(GH_API_RETRY_DELAY_SECONDS * attempt)
            continue

        raise RuntimeError(f"gh api {description} failed: {stderr}")

    raise RuntimeError(f"gh api {description} failed: {last_error or 'unknown error'}")


def _run_gh_api_json(endpoint: str, *, description: str) -> object:
    """Fetch JSON from ``gh api`` and parse it into a Python object."""
    raw = _run_gh_api(endpoint, paginate=[], jq_expr=".", description=description)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh api {description} returned invalid JSON") from exc


def _require_response_type(value: object, expected_type: type, message: str) -> None:
    """Raise when a GitHub API response does not match the expected JSON shape."""
    if not isinstance(value, expected_type):
        raise RuntimeError(message)


def _collect_named_items(payload: dict[str, object], key: str) -> set[str]:
    """Collect string ``name`` fields from a GitHub API list payload."""
    names: set[str] = set()
    items = payload.get(key)
    if not isinstance(items, list):
        return names

    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            names.add(name)
    return names


def _append_missing_items(
    issues: list[str], *, actual: set[str], expected: set[str], label: str
) -> None:
    """Append a formatted issue when expected items are missing."""
    missing_items = expected - actual
    if missing_items:
        issues.append(f"missing {label}: " + ", ".join(sorted(missing_items)))


def _extract_required_checks(protection: object) -> set[str]:
    """Return the normalized set of required status checks from branch protection."""
    if not isinstance(protection, dict):
        return set()

    required_status_checks = protection.get("required_status_checks")
    if not isinstance(required_status_checks, dict):
        return set()

    contexts = required_status_checks.get("contexts")
    checks = required_status_checks.get("checks")
    names = {
        str(context)
        for context in (contexts or [])
        if isinstance(context, str) and context
    }
    names.update(
        str(item.get("context"))
        for item in (checks or [])
        if isinstance(item, dict) and isinstance(item.get("context"), str)
    )
    return names


def _ruleset_targets_branch(ruleset: object, branch_name: str) -> bool:
    """Return whether a ruleset explicitly targets the given branch name."""
    if not isinstance(ruleset, dict) or ruleset.get("target") != "branch":
        return False

    conditions = ruleset.get("conditions")
    if not isinstance(conditions, dict):
        return False

    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, dict):
        return False

    include = ref_name.get("include")
    if not isinstance(include, list):
        return False

    expected_refs = {branch_name, f"refs/heads/{branch_name}"}
    return any(isinstance(value, str) and value in expected_refs for value in include)


def audit_repo_settings(
    *,
    repo: str,
    default_branch: str = "main",
    pages_branch: str = "gh-pages",
) -> dict[str, object]:
    """Audit critical repository settings that the release flow depends on."""
    repository = _run_gh_api_json(
        f"repos/{repo}", description=f"reading repository metadata for {repo}"
    )
    pages = _run_gh_api_json(
        f"repos/{repo}/pages", description=f"reading Pages settings for {repo}"
    )
    protection = _run_gh_api_json(
        f"repos/{repo}/branches/{default_branch}/protection",
        description=f"reading branch protection for {repo}:{default_branch}",
    )
    variables = _run_gh_api_json(
        f"repos/{repo}/actions/variables",
        description=f"listing Actions variables for {repo}",
    )
    secrets = _run_gh_api_json(
        f"repos/{repo}/actions/secrets",
        description=f"listing Actions secrets for {repo}",
    )
    rulesets = _run_gh_api_json(
        f"repos/{repo}/rulesets", description=f"listing rulesets for {repo}"
    )

    _require_response_type(
        repository, dict, "Repository metadata must be a JSON object"
    )
    _require_response_type(pages, dict, "Pages settings must be a JSON object")
    _require_response_type(
        protection, dict, "Branch protection settings must be a JSON object"
    )
    _require_response_type(
        variables, dict, "Actions variables response must be a JSON object"
    )
    _require_response_type(
        secrets, dict, "Actions secrets response must be a JSON object"
    )
    _require_response_type(rulesets, list, "Rulesets response must be a JSON array")
    repository = cast(dict[str, object], repository)
    pages = cast(dict[str, object], pages)
    protection = cast(dict[str, object], protection)
    variables = cast(dict[str, object], variables)
    secrets = cast(dict[str, object], secrets)
    rulesets = cast(list[object], rulesets)

    issues = []
    actual_default_branch = repository.get("default_branch")
    if actual_default_branch != default_branch:
        issues.append(
            f"default branch is {actual_default_branch!r} instead of {default_branch!r}"
        )

    raw_pages_source = pages.get("source")
    pages_source = raw_pages_source if isinstance(raw_pages_source, dict) else {}
    pages_source_branch = pages_source.get("branch")
    pages_source_path = pages_source.get("path") or "/"
    if pages_source_branch != pages_branch:
        issues.append(
            f"Pages source branch is {pages_source_branch!r} instead of {pages_branch!r}"
        )
    if pages_source_path != "/":
        issues.append(f"Pages source path is {pages_source_path!r} instead of '/'")

    required_checks = _extract_required_checks(protection)
    missing_checks = EXPECTED_MAIN_REQUIRED_CHECKS - required_checks
    if missing_checks:
        issues.append(
            "main branch protection is missing required checks: "
            + ", ".join(sorted(missing_checks))
        )

    review_settings = protection.get("required_pull_request_reviews")
    if (
        not isinstance(review_settings, dict)
        or int(review_settings.get("required_approving_review_count", 0)) < 1
    ):
        issues.append(
            "main branch protection does not require at least 1 approving review"
        )

    for key, message in (
        (
            "required_signatures",
            "main branch protection does not require signed commits",
        ),
        (
            "required_linear_history",
            "main branch protection does not require linear history",
        ),
        (
            "required_conversation_resolution",
            "main branch protection does not require conversation resolution",
        ),
    ):
        setting = protection.get(key)
        if not isinstance(setting, dict) or setting.get("enabled") is not True:
            issues.append(message)

    variable_names = _collect_named_items(variables, "variables")
    _append_missing_items(
        issues,
        actual=variable_names,
        expected=EXPECTED_REPOSITORY_VARIABLES,
        label="repository variables",
    )

    secret_names = _collect_named_items(secrets, "secrets")
    _append_missing_items(
        issues,
        actual=secret_names,
        expected=EXPECTED_REPOSITORY_SECRETS,
        label="repository secrets",
    )

    if not any(_ruleset_targets_branch(ruleset, pages_branch) for ruleset in rulesets):
        issues.append(f"no branch ruleset explicitly targets {pages_branch!r}")

    if issues:
        issue_list = "\n- ".join(issues)
        raise ValueError(f"Repository settings audit failed:\n- {issue_list}")

    return {
        "default-branch": actual_default_branch,
        "pages-branch": pages_source_branch,
        "pages-path": pages_source_path,
        "required-checks": sorted(required_checks),
        "variables": sorted(variable_names),
        "secrets": sorted(secret_names),
        "gh-pages-ruleset": True,
    }


def invalidate_thumbnails(
    *, event_name: str, repo: str, pr_number: str, commit_sha: str
) -> list[str]:
    """Delete thumbnail.webp for apps whose index.html changed in a PR or push."""
    request = {
        "pull_request": {
            "endpoint": f"repos/{repo}/pulls/{pr_number}/files",
            "paginate": ["--paginate"],
            "jq_expr": ".[].filename",
        }
    }.get(
        event_name,
        {
            "endpoint": f"repos/{repo}/commits/{commit_sha}",
            "paginate": [],
            "jq_expr": ".files[].filename",
        },
    )

    stdout = _run_gh_api(
        request["endpoint"],
        paginate=request["paginate"],
        jq_expr=request["jq_expr"],
        description=f"listing changed files for {event_name} {repo}",
    )
    invalidated = []
    for line in stdout.splitlines():
        filename = line.strip()
        if not filename:
            continue
        parts = Path(filename).parts
        if not (len(parts) == 3 and parts[0] == "apps" and parts[2] == "index.html"):
            continue
        thumb = Path(parts[0]) / parts[1] / "thumbnail.webp"
        if not thumb.exists():
            continue
        thumb.unlink()
        invalidated.append(str(thumb))
        print(f"Invalidating {thumb} ({filename} changed)")
    return invalidated


def check_fallback(result_url: str) -> bool:
    """Return True when the verified-commit result URL points to a pull request."""
    return "/pull/" in result_url


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
        help="Delete stale thumbnails for apps with changed index.html",
    )
    thumb_parser.add_argument("--event-name", required=True)
    thumb_parser.add_argument("--repo", required=True)
    thumb_parser.add_argument("--pr-number", default="")
    thumb_parser.add_argument("--commit-sha", default="")

    fallback_parser = subparsers.add_parser(
        "check-fallback",
        help="Check if a verified-commit result URL is a fallback PR",
    )
    fallback_parser.add_argument("--result-url", required=True)

    audit_parser = subparsers.add_parser(
        "audit-repo-settings",
        help="Audit critical GitHub repository settings used by deployment workflows",
    )
    audit_parser.add_argument("--repo", required=True)
    audit_parser.add_argument("--default-branch", default="main")
    audit_parser.add_argument("--pages-branch", default="gh-pages")

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
    root = Path(args.root)
    print(json.dumps(read_lock_refresh_metadata(root), sort_keys=True))
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


def _handle_check_fallback(args: argparse.Namespace) -> int:
    """Print whether the verified-commit result is a fallback PR."""
    is_fallback = check_fallback(args.result_url)
    print(f"fallback={'true' if is_fallback else 'false'}")
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


COMMAND_HANDLERS = {
    "app-token-policy": _handle_app_token_policy,
    "read-lock-metadata": _handle_read_lock_metadata,
    "validate-lock-artifact": _handle_validate_lock_artifact,
    "invalidate-thumbnails": _handle_invalidate_thumbnails,
    "check-fallback": _handle_check_fallback,
    "audit-repo-settings": _handle_audit_repo_settings,
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
