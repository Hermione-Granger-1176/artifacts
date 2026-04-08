from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import cast

from scripts.ci.repo_audit import require_response_type
from scripts.lib.app_discovery import (
    _artifact_base_path,
    _load_contract,
    missing_thumbnail_slugs,
    runtime_change_plan,
)
from scripts.lib.gh_api import run_gh_api, run_gh_api_json
from scripts.lib.path_validation import reject_symlinks


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
    head_ref = ""
    if isinstance(head, dict):
        head_ref = pr_field(head, "ref")

    return (
        head_ref.startswith(THUMBNAIL_FOLLOWUP_BRANCH_PREFIX)
        or THUMBNAIL_FOLLOWUP_PR_MARKER in body
        or title == THUMBNAIL_FOLLOWUP_PR_TITLE
    )


def associated_pr_kind_for_commit(
    repo: str,
    commit_sha: str,
    *,
    run_gh_api_json_fn=run_gh_api_json,
) -> str:
    """Return the associated PR kind for a commit on ``main`` pushes."""
    if not commit_sha:
        return "none"

    payload = run_gh_api_json_fn(
        f"repos/{repo}/commits/{commit_sha}/pulls",
        description=f"listing associated pull requests for {repo}@{commit_sha}",
    )
    require_response_type(payload, list, "Associated PRs response must be a JSON array")

    for pr_payload in cast(list[object], payload):
        if is_generated_thumbnail_pr(pr_payload):
            return "thumbnail-followup"
        if isinstance(pr_payload, dict) and pr_payload.get("merged_at"):
            return "normal"

    return "none"


def list_changed_files(
    *,
    event_name: str,
    repo: str,
    pr_number: str,
    commit_sha: str,
    run_gh_api_fn=run_gh_api,
) -> list[str]:
    """Return the changed file list for a pull request or push event."""
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

    stdout = run_gh_api_fn(
        request["endpoint"],
        paginate=request["paginate"],
        jq_expr=request["jq_expr"],
        description=f"listing changed files for {event_name} {repo}",
    )
    return [line for raw_line in stdout.splitlines() if (line := raw_line.strip())]


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

    if event_name == "pull_request":
        if head_repo_fork:
            return ("none", "fork-pr")
        if pr_author == "dependabot[bot]":
            return ("none", "dependabot-pr")
        if has_thumbnail_work:
            return ("pr-branch", "runtime-pr")
        return ("none", "docs-or-metadata-only")

    if event_name == "push":
        if associated_pr_kind == "thumbnail-followup":
            return ("none", "merged-thumbnail-pr")
        if has_thumbnail_work:
            return ("followup-pr", "runtime-main")
        return ("none", "docs-or-metadata-only")

    return ("none", "unsupported-event")


def thumbnail_plan(
    *,
    event_name: str,
    repo: str,
    pr_number: str,
    commit_sha: str,
    head_repo_fork: bool = False,
    pr_author: str = "",
    apps_root: Path | None = None,
    app_token_allowed_fn,
    list_changed_files_fn=list_changed_files,
    missing_thumbnail_slugs_fn=missing_thumbnail_slugs,
    runtime_change_plan_fn=runtime_change_plan,
    associated_pr_kind_for_commit_fn=associated_pr_kind_for_commit,
) -> dict[str, object]:
    """Return the strict thumbnail automation plan for one workflow event."""
    apps_root = apps_root or Path(_artifact_base_path())
    changed_files = list_changed_files_fn(
        event_name=event_name,
        repo=repo,
        pr_number=pr_number,
        commit_sha=commit_sha,
    )
    runtime_plan = runtime_change_plan_fn(changed_files)
    changed_slugs = cast(list[str], runtime_plan["changed_slugs"])
    runtime_changed = cast(bool, runtime_plan["runtime_changed"])
    shared_runtime_changed = cast(bool, runtime_plan["shared_runtime_changed"])
    missing_slugs = missing_thumbnail_slugs_fn(apps_root)
    affected_slugs = sorted(set(changed_slugs) | set(missing_slugs))
    trusted_pr = event_name == "pull_request" and app_token_allowed_fn(
        event_name=event_name,
        head_repo_fork=head_repo_fork,
        pr_author=pr_author,
    )
    associated_pr_kind = (
        associated_pr_kind_for_commit_fn(repo, commit_sha)
        if event_name == "push"
        else "none"
    )

    persist_mode, reason = thumbnail_persist_decision(
        event_name=event_name,
        head_repo_fork=head_repo_fork,
        pr_author=pr_author,
        runtime_changed=runtime_changed,
        missing_slugs=missing_slugs,
        associated_pr_kind=associated_pr_kind,
    )

    return {
        "app_scope": cast(str, runtime_plan["app_scope"]),
        "associated_pr_kind": associated_pr_kind,
        "browser_scope": cast(str, runtime_plan["app_scope"]),
        "changed_files": changed_files,
        "changed_slugs": changed_slugs,
        "head_repo_fork": head_repo_fork,
        "missing_thumbnail_slugs": missing_slugs,
        "persist_allowed": persist_mode != "none",
        "persist_mode": persist_mode,
        "pr_author": pr_author,
        "reason": reason,
        "runtime_changed": runtime_changed,
        "shared_runtime_changed": shared_runtime_changed,
        "thumbnail_scope": "all"
        if shared_runtime_changed
        else ("changed" if affected_slugs else "none"),
        "thumbnail_slugs": [] if shared_runtime_changed else affected_slugs,
        "trusted_pr": trusted_pr,
    }


def read_thumbnail_plan(root: Path) -> dict[str, object]:
    """Read a persisted thumbnail plan from an artifact root."""
    plan_path = root / THUMBNAIL_ARTIFACT_PLAN_FILE
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    require_response_type(payload, dict, "Thumbnail plan must be a JSON object")
    return cast(dict[str, object], payload)


def validate_thumbnail_artifact(root: Path) -> dict[str, object]:
    """Validate a thumbnail-persistence artifact tree and return its plan."""
    if not root.exists():
        raise ValueError(f"Thumbnail artifact root does not exist: {root}")
    if not (root / THUMBNAIL_ARTIFACT_PLAN_FILE).is_file():
        raise ValueError("Thumbnail artifact is missing plan.json")

    plan = read_thumbnail_plan(root)
    allowed_slugs = set(cast(list[str], plan.get("thumbnail_slugs", [])))
    shared_runtime_changed = bool(plan.get("shared_runtime_changed", False))
    saw_thumbnail = False

    reject_symlinks(root)

    for walk_root, _dirnames, filenames in os.walk(root, followlinks=False):
        for filename in filenames:
            path = Path(walk_root) / filename
            relative = path.relative_to(root).as_posix()
            if relative == THUMBNAIL_ARTIFACT_PLAN_FILE.as_posix():
                continue

            if not Path(relative).match(f"{_artifact_base_path()}/*/{_THUMBNAIL_FILE}"):
                raise ValueError(f"Unexpected file in thumbnail artifact: {relative}")

            saw_thumbnail = True
            slug = Path(relative).parts[1]
            if shared_runtime_changed or slug in allowed_slugs:
                continue
            raise ValueError(
                f"Thumbnail artifact contains slug outside plan scope: {slug}"
            )

    if plan.get("persist_mode") != "none" and not saw_thumbnail:
        raise ValueError(
            f"Thumbnail artifact has no {_THUMBNAIL_FILE} files to persist"
        )

    return plan


def thumbnail_targets(*, app_scope: str, changed_slugs: list[str]) -> list[Path]:
    """Return thumbnail paths that should be invalidated for the runtime scope."""
    apps_root = Path(_artifact_base_path())

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
    list_changed_files_fn=list_changed_files,
    runtime_change_plan_fn=runtime_change_plan,
) -> list[str]:
    """Delete thumbnails for apps whose runtime or shared app shell changed."""
    changed_files = list_changed_files_fn(
        event_name=event_name,
        repo=repo,
        pr_number=pr_number,
        commit_sha=commit_sha,
    )
    plan = runtime_change_plan_fn(changed_files)
    invalidated = []
    targets = thumbnail_targets(
        app_scope=cast(str, plan["app_scope"]),
        changed_slugs=cast(list[str], plan["changed_slugs"]),
    )

    for thumb in targets:
        thumb.unlink()
        invalidated.append(str(thumb))
        print(f"Invalidating {thumb}")
    return invalidated
