"""REST reads that stand in for ``gh pr view --json`` when GraphQL is blocked.

``gh pr view`` uses GraphQL, so it fails in environments that refuse that
endpoint. Each helper here rebuilds the JSON shape ``gh pr view --json``
produces (upper-case check states, bot-free review logins, node-id review ids),
so the summary, watch, and checks logic parses one format whichever path
supplied it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from . import gh_runner
from .gh_runner import GhError, RunFunction, require_mapping

if TYPE_CHECKING:
    from collections.abc import Sequence

# gh accepts ``@copilot`` as a reviewer. The REST reviewer-request route has no
# such alias, so it takes the bot's login instead.
COPILOT_REVIEWER = "@copilot"
COPILOT_REST_REVIEWER = "copilot-pull-request-reviewer[bot]"


def pull_request(slug: str, pr: int, *, run_fn: RunFunction | None = None) -> dict[str, Any]:
    """Return the REST pull-request object for ``pr``."""
    return require_mapping(
        gh_runner.rest(f"repos/{slug}/pulls/{pr}", run_fn=run_fn),
        f"Unexpected pull request response shape for PR {pr}.",
    )


def pull_state(pull: dict[str, Any]) -> str:
    """Return the ``OPEN``, ``CLOSED``, or ``MERGED`` state ``gh`` reports for a pull request."""
    if pull.get("merged"):
        return "MERGED"
    return str(pull.get("state") or "").upper()


def head_sha(pull: dict[str, Any]) -> str:
    """Return the head commit SHA of a REST pull-request object."""
    head = pull.get("head")
    sha = head.get("sha") if isinstance(head, dict) else None
    if not isinstance(sha, str) or not sha:
        raise GhError("Pull request response has no head commit.")
    return sha


def _check_run(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a REST check run into a ``statusCheckRollup`` check-run entry."""
    return {
        "name": entry.get("name"),
        "status": str(entry.get("status") or "").upper(),
        "conclusion": str(entry.get("conclusion") or "").upper(),
        "detailsUrl": entry.get("details_url") or entry.get("html_url") or "",
        "startedAt": entry.get("started_at"),
        "completedAt": entry.get("completed_at"),
    }


def _run_id(entry: dict[str, Any]) -> int:
    """Return a check run's numeric id (``0`` when missing), which grows with each new run."""
    run_id = entry.get("id")
    return run_id if isinstance(run_id, int) else 0


def _suite_id(entry: dict[str, Any]) -> object:
    """Return the id of the check suite a check run belongs to, or ``None``."""
    suite = entry.get("check_suite")
    return suite.get("id") if isinstance(suite, dict) else None


def _latest_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the newest check run of each name within each check suite.

    A workflow re-run adds a run to the same suite, and an older failed run must
    not outweigh the re-run that replaced it. Separate suites (another workflow,
    event, or App) can reuse a name, so each keeps its own entry.
    """
    latest: dict[tuple[object, str], dict[str, Any]] = {}
    for run in runs:
        key = (_suite_id(run), str(run.get("name") or ""))
        kept = latest.get(key)
        if kept is None or _run_id(run) > _run_id(kept):
            latest[key] = run
    return list(latest.values())


def _status_context(status: Any) -> dict[str, Any]:
    """Convert a REST commit status into a ``statusCheckRollup`` status-context entry."""
    entry = require_mapping(status, "Unexpected commit status shape in status response.")
    return {
        "context": entry.get("context"),
        "state": str(entry.get("state") or "").upper(),
        "targetUrl": entry.get("target_url") or "",
    }


def status_check_rollup(
    slug: str, sha: str, *, run_fn: RunFunction | None = None
) -> list[dict[str, Any]]:
    """Return the check runs and commit statuses on ``sha`` as a ``statusCheckRollup`` list.

    Only the newest run of each check name in each check suite is kept. The
    combined status ``state`` is ignored on purpose: it reads ``pending`` for a commit with no
    statuses at all, which would hold every settled rollup open.
    """
    runs = gh_runner.rest_pages(
        f"repos/{slug}/commits/{sha}/check-runs", items_key="check_runs", run_fn=run_fn
    )
    statuses = gh_runner.rest_pages(
        f"repos/{slug}/commits/{sha}/status", items_key="statuses", run_fn=run_fn
    )
    return [_check_run(run) for run in _latest_runs(runs)] + [
        _status_context(status) for status in statuses
    ]


def _review(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a REST review into the entry ``gh pr view --json reviews`` produces."""
    user = entry.get("user")
    login = user.get("login") if isinstance(user, dict) else None
    return {
        "id": entry.get("node_id") or str(entry.get("id") or ""),
        "author": {"login": str(login).removesuffix("[bot]")} if login else None,
        "submittedAt": entry.get("submitted_at"),
        "body": entry.get("body") or "",
        "state": str(entry.get("state") or "").upper(),
    }


def reviews(slug: str, pr: int, *, run_fn: RunFunction | None = None) -> list[dict[str, Any]]:
    """Return the reviews on ``pr`` in the ``gh pr view --json reviews`` shape."""
    raw = gh_runner.rest_pages(f"repos/{slug}/pulls/{pr}/reviews", run_fn=run_fn)
    return [_review(review) for review in raw]


def pr_view(pr: int, fields: Sequence[str], *, run_fn: RunFunction | None = None) -> dict[str, Any]:
    """Return ``gh pr view --json``-shaped data for the requested ``fields``.

    Supports ``number``, ``title``, ``state``, ``url``, ``statusCheckRollup``,
    and ``reviews``. Check and review lookups run only when asked for.
    """
    slug = gh_runner.resolve_repo(run_fn=run_fn)
    pull = pull_request(slug, pr, run_fn=run_fn)
    view: dict[str, Any] = {}
    for field in fields:
        if field == "number":
            view[field] = pull.get("number")
        elif field == "title":
            view[field] = pull.get("title")
        elif field == "state":
            view[field] = pull_state(pull)
        elif field == "url":
            view[field] = pull.get("html_url")
        elif field == "statusCheckRollup":
            view[field] = status_check_rollup(slug, head_sha(pull), run_fn=run_fn)
        elif field == "reviews":
            view[field] = reviews(slug, pr, run_fn=run_fn)
        else:
            raise GhError(f"The REST fallback cannot supply the {field} field.")
    return view
