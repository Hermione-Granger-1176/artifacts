from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import quote

from scripts.lib.gh_api import run_gh_api_form, run_gh_api_json

if TYPE_CHECKING:
    from collections.abc import Callable

ISSUE_TITLE_MATCH_LIMIT = 100

ALERT_LABELS = ("ops", "ci")

ALERT_BODY_LEADS = {
    "open": "Scheduled checks behind this alert are failing.",
    "close": "Scheduled checks behind this alert are passing again.",
    "setup-failure": (
        "The scheduled workflow failed before its checks could report a status, "
        "so this is likely a setup or infrastructure failure rather than a check "
        "regression. Inspect the failed run logs to find the failing setup step."
    ),
}


def _require_state(state: str) -> str:
    """Return ``state`` when it names a supported alert state."""
    if state not in ALERT_BODY_LEADS:
        supported = ", ".join(sorted(ALERT_BODY_LEADS))
        raise ValueError(f"Unsupported alert state: {state!r}. Expected one of: {supported}.")
    return state


def _require_argument(value: str, name: str) -> str:
    """Return a non-empty alert argument that cannot be mistaken for a flag."""
    if not value or not value.strip():
        raise ValueError(f"Alert {name} must not be empty.")
    if value.startswith("-"):
        raise ValueError(f"Alert {name} must not start with '-': {value!r}.")
    return value


def _require_run_url(run_url: str) -> str:
    """Return a run URL that points at a GitHub Actions run."""
    _require_argument(run_url, "run URL")
    if not run_url.startswith("https://"):
        raise ValueError(f"Alert run URL must be an https URL: {run_url!r}.")
    if "/actions/runs/" not in run_url:
        raise ValueError(f"Alert run URL must reference an Actions run: {run_url!r}.")
    return run_url


def _validate_labels(labels: list[str]) -> tuple[str, ...]:
    """Return normalized labels suitable for an issue query and mutation."""
    normalized: list[str] = []
    for label in labels:
        _require_argument(label, "label")
        if label not in normalized:
            normalized.append(label)
    return tuple(normalized)


def alert_should_exist(state: str) -> bool:
    """Return whether the alert issue should exist after syncing ``state``."""
    return _require_state(state) != "close"


def build_alert_body(*, state: str, run_url: str, detail: str = "") -> str:
    """Build the canned alert issue body for one monitored workflow state."""
    lead = ALERT_BODY_LEADS[_require_state(state)]
    body = f"{lead}\n\nWorkflow run: {_require_run_url(run_url)}"
    if detail.strip():
        body = f"{body}\n\n{detail.strip()}"
    return body


def issue_payloads_by_title(
    repo: str,
    title: str,
    *,
    labels: list[str] | None = None,
    run_gh_api_json_fn: Callable[..., object] = run_gh_api_json,
) -> list[dict[str, object]]:
    """Return bounded open issue payloads whose title and labels match."""
    _require_argument(repo, "repository")
    _require_argument(title, "title")
    label_values = _validate_labels(labels or [])
    endpoint = f"repos/{repo}/issues?state=open&per_page={ISSUE_TITLE_MATCH_LIMIT}"
    if label_values:
        endpoint += f"&labels={quote(','.join(label_values), safe=',')}"
    payload = run_gh_api_json_fn(
        endpoint,
        description=f"listing open issues for {repo}",
        required_permission="issues: read",
    )
    if not isinstance(payload, list):
        raise RuntimeError("Issues response must be a JSON array")
    if len(payload) >= ISSUE_TITLE_MATCH_LIMIT:
        raise RuntimeError(
            f"Refusing to sync alert {title!r}: the issue result reached the "
            f"{ISSUE_TITLE_MATCH_LIMIT}-item limit and may be truncated."
        )

    matches: list[dict[str, object]] = []
    for item in payload:
        if not isinstance(item, dict):
            raise RuntimeError("Issue response entries must be JSON objects")
        if isinstance(item.get("pull_request"), dict):
            continue
        if item.get("title") == title:
            matches.append(item)
    return sorted(matches, key=_issue_number)


def _issue_number(issue_payload: dict[str, object]) -> int:
    """Return the validated issue number from a GitHub issue payload."""
    issue_number = issue_payload.get("number")
    if not isinstance(issue_number, int) or isinstance(issue_number, bool) or issue_number < 1:
        raise RuntimeError("Matched issue number must be a positive integer")
    return issue_number


def _issue_url(issue_payload: dict[str, object]) -> str:
    """Return the validated html_url from a GitHub issue payload."""
    html_url = issue_payload.get("html_url")
    if not isinstance(html_url, str) or not html_url.strip():
        raise RuntimeError("Matched issue html_url must be a non-empty string")
    return html_url.strip()


def sync_alert_issue(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
    should_exist: bool,
    issue_payloads_by_title_fn: Callable[..., list[dict[str, object]]] = issue_payloads_by_title,
    run_gh_api_form_fn: Callable[..., str] = run_gh_api_form,
) -> str:
    """Create, comment on, close, or reuse one alert issue addressed by title and labels."""
    _require_argument(repo, "repository")
    _require_argument(title, "title")
    _validate_labels(labels)
    matches = issue_payloads_by_title_fn(repo, title, labels=labels)
    primary = matches[0] if matches else None
    fields = [
        ("title", title),
        ("body", body),
        *(("labels[]", label) for label in labels),
    ]

    if primary is None:
        if not should_exist:
            return ""

        created_url = run_gh_api_form_fn(
            f"repos/{repo}/issues",
            method="POST",
            fields=fields,
            description=f"creating alert issue {title} for {repo}",
            jq_expr=".html_url",
            required_permission="issues: write",
        )
        if not created_url.strip():
            raise RuntimeError(f"Creating alert issue {title!r} returned no URL")
        return created_url.strip()

    issue_number = _issue_number(primary)
    if not should_exist:
        run_gh_api_form_fn(
            f"repos/{repo}/issues/{issue_number}",
            method="PATCH",
            fields=[("state", "closed")],
            description=f"closing alert issue {title} for {repo}",
            required_permission="issues: write",
        )
        return ""

    html_url = _issue_url(primary)
    run_gh_api_form_fn(
        f"repos/{repo}/issues/{issue_number}/comments",
        method="POST",
        fields=[("body", body)],
        description=f"commenting on alert issue {title} for {repo}",
        required_permission="issues: write",
    )
    return html_url
