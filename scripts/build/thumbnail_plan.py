from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

from scripts.ci.repo_audit import require_response_type
from scripts.lib.app_discovery import (
    artifact_base_path,
    full_impact_plan,
    missing_thumbnail_slugs,
    runtime_change_plan,
)
from scripts.lib.artifact_contract import load_contract as _load_contract
from scripts.lib.gh_api import run_gh_api, run_gh_api_json
from scripts.lib.path_validation import reject_path_symlinks, reject_symlinks

if TYPE_CHECKING:
    from collections.abc import Callable


def _build_thumbnail_pattern() -> str:
    """Build the thumbnail path regex from the shared artifact contract."""
    contract = _load_contract()
    base = re.escape(contract["artifactBasePath"])
    thumb = re.escape(contract["thumbnailFile"])
    return rf"^{base}/[a-z0-9-]+/{thumb}$"


THUMBNAIL_FOLLOWUP_BRANCH_PREFIX = "ci/save-generated-thumbnails"
THUMBNAIL_FOLLOWUP_PR_TITLE = "Save generated app thumbnails"
THUMBNAIL_FOLLOWUP_PR_MARKER = "<!-- artifacts:generated-thumbnails -->"
THUMBNAIL_ARTIFACT_PLAN_FILE = Path("plan.json")
THUMBNAIL_PATTERN = _build_thumbnail_pattern()
_THUMBNAIL_FILE = _load_contract()["thumbnailFile"]


def pr_field(pr_payload: object, field_name: str) -> str:
    """Return a string field from a PR payload when present."""
    if not isinstance(pr_payload, dict):
        return ""
    value = pr_payload.get(field_name)
    return value if isinstance(value, str) else ""


def is_generated_thumbnail_pr(pr_payload: object) -> bool:
    """Return True when a PR payload matches the generated-thumbnail PR marker."""
    if not isinstance(pr_payload, dict):
        return False

    title = pr_field(pr_payload, "title")
    body = pr_field(pr_payload, "body")
    head = pr_payload.get("head")
    head_ref = pr_field(head, "ref") if isinstance(head, dict) else ""

    return (
        head_ref.startswith(THUMBNAIL_FOLLOWUP_BRANCH_PREFIX)
        or THUMBNAIL_FOLLOWUP_PR_MARKER in body
        or title == THUMBNAIL_FOLLOWUP_PR_TITLE
    )


def associated_pr_kind_for_commit(
    repo: str,
    commit_sha: str,
    *,
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> str:
    """Return the associated PR kind for a commit on ``main`` pushes."""
    if not commit_sha:
        return "none"

    payload = run_gh_api_json_fn(
        f"repos/{repo}/commits/{commit_sha}/pulls",
        description=f"listing associated pull requests for {repo}@{commit_sha}",
    )
    require_response_type(payload, list, "Associated PRs response must be a JSON array")

    for pr_payload in cast("list[object]", payload):
        if is_generated_thumbnail_pr(pr_payload):
            return "thumbnail-followup"
        if isinstance(pr_payload, dict) and pr_payload.get("merged_at"):
            return "normal"

    return "none"


def list_changed_files(
    *,
    base_sha: str,
    head_sha: str,
    run_git_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[str]:
    """Return files changed since the merge base of ``base_sha`` and ``head_sha``.

    GitHub's changed-files REST payload is bounded, so the checked-out history
    is the only source of truth. Callers turn failures into a conservative
    all-app plan instead of trusting an incomplete changed-file list.
    """
    if not base_sha or not head_sha:
        raise RuntimeError("Both base and head revisions are required for changed-file detection")

    result = run_git_fn(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for raw_line in result.stdout.splitlines() if (line := raw_line.strip())]


def list_commit_files(
    *,
    repo: str,
    commit_sha: str,
    run_gh_api_fn: Callable[..., str] = run_gh_api,
) -> list[str]:
    """Return the changed file list for a single commit (not PR-level)."""
    if not commit_sha:
        return []
    stdout = run_gh_api_fn(
        f"repos/{repo}/commits/{commit_sha}",
        paginate=[],
        jq_expr=".files[].filename",
        description=f"listing changed files for commit {repo}@{commit_sha}",
    )
    return [line for raw_line in stdout.splitlines() if (line := raw_line.strip())]


def _all_thumbnail_files(files: list[str]) -> bool:
    """Return True when every file matches the thumbnail pattern."""
    return bool(files) and all(re.match(THUMBNAIL_PATTERN, f) for f in files)


def is_automated_thumbnail_commit(
    *,
    actor: str,
    app_bot_login: str,
    repo: str,
    commit_sha: str,
    list_commit_files_fn: Callable[..., list[str]] = list_commit_files,
) -> bool:
    """Return True when the triggering commit is an app-authored thumbnail-only change.

    Both conditions must hold:
    1. The workflow actor matches the trusted app bot login.
    2. Every file in the commit matches the thumbnail pattern.

    Returns False on any detection failure (empty actor, empty bot login,
    missing commit SHA, no files, or non-thumbnail files). This ensures the
    skip is a narrow optimization exit, never a default.
    """
    if not actor or not app_bot_login or actor != app_bot_login:
        return False
    try:
        files = list_commit_files_fn(repo=repo, commit_sha=commit_sha)
    except Exception:
        return False
    return _all_thumbnail_files(files)


def thumbnail_persist_decision(
    *,
    event_name: str,
    head_repo_fork: bool,
    pr_author: str,
    runtime_changed: bool,
    missing_slugs: list[str],
    associated_pr_kind: str,
) -> tuple[str, str]:
    """Return the allowed thumbnail persistence mode and reason."""
    has_thumbnail_work = runtime_changed or bool(missing_slugs)

    def handle_pull_request() -> tuple[str, str]:
        if head_repo_fork:
            return ("none", "fork-pr")
        if pr_author == "dependabot[bot]":
            return ("none", "dependabot-pr")
        if has_thumbnail_work:
            return ("pr-branch", "runtime-pr")
        return ("none", "docs-or-metadata-only")

    def handle_push() -> tuple[str, str]:
        if associated_pr_kind == "thumbnail-followup":
            return ("none", "merged-thumbnail-pr")
        if has_thumbnail_work:
            return ("followup-pr", "runtime-main")
        return ("none", "docs-or-metadata-only")

    decision_by_event = {
        "pull_request": handle_pull_request,
        "push": handle_push,
    }
    decide = decision_by_event.get(event_name)
    if decide is None:
        return ("none", "unsupported-event")
    return decide()


def thumbnail_plan(
    *,
    event_name: str,
    repo: str,
    pr_number: str,
    commit_sha: str,
    base_sha: str = "",
    head_sha: str = "",
    head_repo_fork: bool = False,
    pr_author: str = "",
    actor: str = "",
    app_bot_login: str = "",
    force_full: bool = False,
    apps_root: Path | None = None,
    list_changed_files_fn: Callable[..., list[str]] = list_changed_files,
    list_commit_files_fn: Callable[..., list[str]] = list_commit_files,
    missing_thumbnail_slugs_fn: Callable[..., list[str]] = missing_thumbnail_slugs,
    runtime_change_plan_fn: Callable[..., dict[str, object]] = runtime_change_plan,
    associated_pr_kind_for_commit_fn: Callable[..., str] = associated_pr_kind_for_commit,
) -> dict[str, object]:
    """Return the strict thumbnail automation plan for one workflow event."""
    del pr_number
    apps_root = apps_root or Path(artifact_base_path())
    comparison_available = not force_full
    try:
        if force_full:
            raise RuntimeError("Full verification was requested")
        changed_files = list_changed_files_fn(base_sha=base_sha, head_sha=head_sha)
        runtime_plan = runtime_change_plan_fn(changed_files)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        comparison_available = False
        runtime_plan = full_impact_plan()
    changed_slugs = cast("list[str]", runtime_plan["changed_slugs"])
    runtime_changed = cast("bool", runtime_plan["runtime_changed"])
    shared_runtime_changed = cast("bool", runtime_plan["shared_runtime_changed"])
    missing_slugs = missing_thumbnail_slugs_fn(apps_root)
    affected_slugs = sorted(set(changed_slugs) | set(missing_slugs))
    associated_pr_kind = (
        associated_pr_kind_for_commit_fn(repo, commit_sha) if event_name == "push" else "none"
    )

    persist_mode, reason = thumbnail_persist_decision(
        event_name=event_name,
        head_repo_fork=head_repo_fork,
        pr_author=pr_author,
        runtime_changed=runtime_changed,
        missing_slugs=missing_slugs,
        associated_pr_kind=associated_pr_kind,
    )

    # Detect automated thumbnail-only commits that need no verification.
    # For PRs: the actor must be the trusted app bot and the commit must
    # contain only thumbnail files. For main pushes: the PR provenance
    # must be a thumbnail-followup and the merge commit must contain only
    # thumbnail files. Any detection failure defaults to False (full run).
    skip_verification = not force_full and is_automated_thumbnail_commit(
        actor=actor,
        app_bot_login=app_bot_login,
        repo=repo,
        commit_sha=commit_sha,
        list_commit_files_fn=list_commit_files_fn,
    )
    if not force_full and not skip_verification and associated_pr_kind == "thumbnail-followup":
        try:
            commit_files = list_commit_files_fn(repo=repo, commit_sha=commit_sha)
        except Exception:
            commit_files = []
        skip_verification = _all_thumbnail_files(commit_files)

    return {
        "app_scope": cast("str", runtime_plan["app_scope"]),
        "browser_scope": cast("str", runtime_plan["browser_scope"]),
        "static_checks_scope": cast("str", runtime_plan["static_checks_scope"]),
        "deploy_scope": cast("str", runtime_plan["deploy_scope"]),
        "changed_slugs": changed_slugs,
        "persist_mode": persist_mode,
        "reason": reason,
        "shared_runtime_changed": shared_runtime_changed,
        "shared_browser_test_changed": cast("bool", runtime_plan["shared_browser_test_changed"]),
        "comparison_available": comparison_available,
        "skip_verification": skip_verification,
        "thumbnail_scope": "all"
        if runtime_plan["thumbnail_scope"] == "all"
        else ("changed" if affected_slugs else "none"),
        "thumbnail_slugs": [] if runtime_plan["thumbnail_scope"] == "all" else affected_slugs,
    }


def read_thumbnail_plan(root: Path) -> dict[str, object]:
    """Read a persisted thumbnail plan from an artifact root."""
    reject_path_symlinks(root, label="Thumbnail artifact root")
    plan_path = root / THUMBNAIL_ARTIFACT_PLAN_FILE
    if plan_path.is_symlink():
        raise ValueError(f"Thumbnail plan manifest must not be a symlink: {plan_path}")
    if not plan_path.is_file():
        raise ValueError(f"Thumbnail plan manifest is missing: {plan_path}")
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    require_response_type(payload, dict, "Thumbnail plan must be a JSON object")
    return cast("dict[str, object]", payload)


def validate_thumbnail_artifact(root: Path) -> dict[str, object]:
    """Validate a thumbnail-persistence artifact tree and return its plan."""
    reject_path_symlinks(root, label="Thumbnail artifact root")
    if not root.exists():
        raise ValueError(f"Thumbnail artifact root does not exist: {root}")

    plan = read_thumbnail_plan(root)
    allowed_slugs = set(cast("list[str]", plan.get("thumbnail_slugs", [])))
    all_thumbnail_scope = plan.get("thumbnail_scope") == "all" or bool(
        plan.get("shared_runtime_changed", False)
    )
    saw_thumbnail = False

    reject_symlinks(root)

    for walk_root, _dirnames, filenames in os.walk(root, followlinks=False):
        for filename in filenames:
            path = Path(walk_root) / filename
            relative = path.relative_to(root).as_posix()
            if relative == THUMBNAIL_ARTIFACT_PLAN_FILE.as_posix():
                continue

            if not Path(relative).match(f"{artifact_base_path()}/*/{_THUMBNAIL_FILE}"):
                raise ValueError(f"Unexpected file in thumbnail artifact: {relative}")

            saw_thumbnail = True
            slug = Path(relative).parts[1]
            if not all_thumbnail_scope and slug not in allowed_slugs:
                raise ValueError(f"Thumbnail artifact contains slug outside plan scope: {slug}")

    if plan.get("persist_mode") != "none" and not saw_thumbnail:
        raise ValueError(f"Thumbnail artifact has no {_THUMBNAIL_FILE} files to persist")

    return plan


def thumbnail_targets(*, app_scope: str, changed_slugs: list[str]) -> list[Path]:
    """Return thumbnail paths that should be invalidated for the runtime scope."""
    apps_root = Path(artifact_base_path())

    if app_scope == "all":
        if not apps_root.exists():
            return []
        return sorted(
            path / _THUMBNAIL_FILE
            for path in apps_root.iterdir()
            if path.is_dir() and (path / _THUMBNAIL_FILE).exists()
        )

    if app_scope == "changed":
        return [
            apps_root / slug / _THUMBNAIL_FILE
            for slug in changed_slugs
            if (apps_root / slug / _THUMBNAIL_FILE).exists()
        ]

    return []


def invalidate_thumbnails(
    *,
    event_name: str,
    repo: str,
    pr_number: str,
    commit_sha: str,
    base_sha: str = "",
    head_sha: str = "",
    list_changed_files_fn: Callable[..., list[str]] = list_changed_files,
    runtime_change_plan_fn: Callable[..., dict[str, object]] = runtime_change_plan,
) -> list[str]:
    """Delete thumbnails for apps whose runtime or shared site assets changed."""
    del event_name, repo, pr_number, commit_sha
    try:
        changed_files = list_changed_files_fn(base_sha=base_sha, head_sha=head_sha)
        plan = runtime_change_plan_fn(changed_files)
    except (OSError, RuntimeError, subprocess.SubprocessError):
        plan = full_impact_plan()
    invalidated = []
    targets = thumbnail_targets(
        app_scope=cast("str", plan["thumbnail_scope"]),
        changed_slugs=cast("list[str]", plan["changed_slugs"]),
    )

    for thumb in targets:
        thumb.unlink()
        invalidated.append(str(thumb))
        print(f"Invalidating {thumb}")
    return invalidated
