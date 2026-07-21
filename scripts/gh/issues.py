"""Read-only issue overview built on the ``gh`` JSON API.

Backs ``make issue-summary``: one screen with an issue's state, author, labels,
assignees, milestone, and its most recent comments, so triaging an issue does
not need several ``gh issue view`` passes. Every parse helper is defensive so a
malformed field surfaces as a clear ``GhError`` instead of an opaque
``TypeError``.
"""

from __future__ import annotations

from typing import Any

from . import gh_runner
from .gh_runner import GhError, RunFunction

# Fields requested from ``gh issue view --json``. Kept in one constant so the
# request and the parse helpers below stay in sync.
_ISSUE_FIELDS = "number,title,state,url,author,labels,assignees,milestone,comments"

# How many of the most recent comments to echo in the summary.
_RECENT_COMMENTS = 3


def _require_mapping(value: Any, message: str) -> dict[str, Any]:
    """Return ``value`` as a mapping, raising ``GhError`` with ``message`` otherwise."""
    if not isinstance(value, dict):
        raise GhError(message)
    return value


def _required_number(value: Any) -> int:
    """Return a required issue number, rejecting missing or non-integer values."""
    if not isinstance(value, int) or isinstance(value, bool):
        raise GhError("Unexpected number shape in issue view response.")
    return value


def _required_text(value: Any, field: str) -> str:
    """Return a required non-empty text field from an issue response."""
    if not isinstance(value, str) or not value:
        raise GhError(f"Unexpected {field} shape in issue view response.")
    return value


def _login(value: Any) -> str:
    """Return an actor's login (``unknown`` for a null author or missing login).

    A non-null, non-mapping author is a malformed shape and raises ``GhError``.
    """
    if value is None:
        return "unknown"
    mapping = _require_mapping(value, "Unexpected author shape in issue view response.")
    return str(mapping.get("login") or "unknown")


def _names(value: Any, key: str, message: str) -> list[str]:
    """Return each object's ``key`` field from a list (labels' name, assignees' login)."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise GhError(message)
    names: list[str] = []
    for item in value:
        text = _require_mapping(item, message).get(key)
        if text:
            names.append(str(text))
    return names


def _milestone_title(value: Any) -> str:
    """Return the milestone title, or ``none`` when the issue has no milestone."""
    if value is None:
        return "none"
    mapping = _require_mapping(value, "Unexpected milestone shape in issue view response.")
    return str(mapping.get("title") or "none")


def _comment_list(value: Any) -> list[Any]:
    """Return the comments array (``None`` means no comments), or raise on a bad shape."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise GhError("Unexpected comments shape in issue view response.")
    return value


def _recent_comments(comments: list[Any]) -> list[str]:
    """Render the last few comments as ``@author: first-line`` strings."""
    rendered: list[str] = []
    for comment in comments[-_RECENT_COMMENTS:]:
        mapping = _require_mapping(comment, "Unexpected comment shape in issue view response.")
        body = str(mapping.get("body") or "")
        first_line = body.splitlines()[0] if body else ""
        rendered.append(f"  @{_login(mapping.get('author'))}: {first_line}")
    return rendered


def issue_summary(issue: int, *, run_fn: RunFunction | None = None) -> str:
    """Return a one-screen overview of ``issue``: meta, labels, assignees, comments."""
    meta = _require_mapping(
        gh_runner.gh_json(["issue", "view", str(issue), "--json", _ISSUE_FIELDS], run_fn=run_fn),
        f"Unexpected issue view response shape for issue {issue}.",
    )
    number = _required_number(meta.get("number"))
    state = _required_text(meta.get("state"), "state")
    title = _required_text(meta.get("title"), "title")
    url = _required_text(meta.get("url"), "url")
    labels = _names(meta.get("labels"), "name", "Unexpected labels shape in issue view response.")
    assignees = _names(
        meta.get("assignees"), "login", "Unexpected assignees shape in issue view response."
    )
    comments = _comment_list(meta.get("comments"))
    lines = [
        f"Issue #{number} [{state}] {title}",
        f"  {url}",
        f"  author: @{_login(meta.get('author'))}",
        f"  labels: {', '.join(labels) or 'none'}",
        f"  assignees: {', '.join(f'@{login}' for login in assignees) or 'none'}",
        f"  milestone: {_milestone_title(meta.get('milestone'))}",
        f"  comments: {len(comments)}",
    ]
    recent = _recent_comments(comments)
    if recent:
        lines.append("")
        lines.append("recent comments:")
        lines.extend(recent)
    return "\n".join(lines)
