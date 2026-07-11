#!/usr/bin/env python3
"""Detect leaked PR preview directories on the GitHub Pages branch.

PR previews are published under ``pr-preview/pr-<number>/`` on the ``gh-pages``
branch and are removed by the PR-close cleanup job. When that single cleanup
run fails, the preview directory leaks and is never reclaimed. This module
lists the top-level ``pr-preview/`` directories through the git trees API,
compares them against the open pull requests, and reports any preview whose
pull request is no longer open so the cleanup can be re-run.

For normal use, prefer ``make ci-audit-previews`` over calling this module
directly.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

from scripts.lib.gh_api import run_gh_api_json

if TYPE_CHECKING:
    from collections.abc import Callable

PREVIEW_ROOT = "pr-preview"
PREVIEW_DIR_PATTERN = re.compile(r"^pr-(\d+)$")
_PULLS_PER_PAGE = 100


def _tree_entries(payload: object, description: str) -> list[dict[str, object]]:
    """Return the ``tree`` entry list from a git trees API payload."""
    if not isinstance(payload, dict):
        raise RuntimeError(f"{description} must be a JSON object")
    entries = payload.get("tree")
    if not isinstance(entries, list):
        raise RuntimeError(f"{description} must include a tree array")
    return [entry for entry in entries if isinstance(entry, dict)]


def list_preview_dir_names(
    repo: str,
    pages_branch: str,
    *,
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> list[str]:
    """Return the names of directories directly under ``pr-preview/``."""
    root_payload = run_gh_api_json_fn(
        f"repos/{repo}/git/trees/{pages_branch}",
        description=f"reading {pages_branch} tree for {repo}",
        required_permission="contents: read",
    )
    root_entries = _tree_entries(root_payload, f"{pages_branch} tree for {repo}")

    preview_entry = next(
        (
            entry
            for entry in root_entries
            if entry.get("path") == PREVIEW_ROOT and entry.get("type") == "tree"
        ),
        None,
    )
    if preview_entry is None:
        return []

    preview_sha = preview_entry.get("sha")
    if not isinstance(preview_sha, str):
        raise RuntimeError(f"{PREVIEW_ROOT} tree entry for {repo} is missing a sha")

    preview_payload = run_gh_api_json_fn(
        f"repos/{repo}/git/trees/{preview_sha}",
        description=f"reading {PREVIEW_ROOT} tree for {repo}",
        required_permission="contents: read",
    )
    preview_entries = _tree_entries(preview_payload, f"{PREVIEW_ROOT} tree for {repo}")
    return [
        cast("str", entry["path"])
        for entry in preview_entries
        if entry.get("type") == "tree" and isinstance(entry.get("path"), str)
    ]


def list_open_pr_numbers(
    repo: str,
    *,
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> set[int]:
    """Return the set of open pull request numbers for ``repo``.

    The listing endpoint caps each page at ``_PULLS_PER_PAGE`` results, so pages
    are fetched sequentially until a short (or empty) page signals the end.
    Without this, repos with more open pull requests than one page would leave
    later PRs unseen and their live previews wrongly flagged as stale.
    """
    numbers: set[int] = set()
    page = 1
    while True:
        payload = run_gh_api_json_fn(
            f"repos/{repo}/pulls?state=open&per_page={_PULLS_PER_PAGE}&page={page}",
            description=f"listing open pull requests for {repo} (page {page})",
            required_permission="pull_requests: read",
        )
        if not isinstance(payload, list):
            raise RuntimeError(f"Open pull requests response for {repo} must be a JSON array")
        numbers.update(
            item["number"]
            for item in payload
            if isinstance(item, dict) and isinstance(item.get("number"), int)
        )
        if len(payload) < _PULLS_PER_PAGE:
            break
        page += 1
    return numbers


def find_stale_previews(preview_dirs: list[str], open_pr_numbers: set[int]) -> list[str]:
    """Return preview directory names that have no matching open pull request."""
    stale: list[str] = []
    for name in preview_dirs:
        match = PREVIEW_DIR_PATTERN.match(name)
        if match is None:
            continue
        if int(match.group(1)) not in open_pr_numbers:
            stale.append(name)
    return sorted(stale)


def audit_previews(
    *,
    repo: str,
    pages_branch: str = "gh-pages",
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> list[str]:
    """Return live preview directories, raising when stale previews leak.

    A stale preview is a ``pr-preview/pr-<number>/`` directory whose pull
    request is no longer open. When any are found, a ``ValueError`` is raised
    naming the directories and the cleanup action to take.
    """
    preview_dirs = list_preview_dir_names(repo, pages_branch, run_gh_api_json_fn=run_gh_api_json_fn)
    open_pr_numbers = list_open_pr_numbers(repo, run_gh_api_json_fn=run_gh_api_json_fn)
    stale = find_stale_previews(preview_dirs, open_pr_numbers)
    if stale:
        stale_list = ", ".join(stale)
        raise ValueError(
            "Stale PR preview directories found on "
            f"{pages_branch}: {stale_list}. "
            "These previews have no matching open pull request. Re-run the "
            "PR-close cleanup job in update.yml for the affected PRs, or delete "
            f"the leaked pr-preview/<dir>/ paths from the {pages_branch} branch."
        )
    return preview_dirs
