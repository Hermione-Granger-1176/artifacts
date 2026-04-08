from __future__ import annotations

from scripts.lib.gh_api import run_gh_api_form, run_gh_api_json

ISSUE_TITLE_MATCH_LIMIT = 100


def issue_payloads_by_title(
    repo: str,
    title: str,
    *,
    run_gh_api_json_fn=run_gh_api_json,
) -> list[dict[str, object]]:
    """Return open issue payloads whose title exactly matches ``title``."""
    payload = run_gh_api_json_fn(
        f"repos/{repo}/issues?state=open&per_page={ISSUE_TITLE_MATCH_LIMIT}",
        description=f"listing open issues for {repo}",
    )
    if not isinstance(payload, list):
        raise RuntimeError("Issues response must be a JSON array")

    return [
        item
        for item in payload
        if isinstance(item, dict)
        and not isinstance(item.get("pull_request"), dict)
        and item.get("title") == title
    ]


def _issue_number(issue_payload: dict[str, object]) -> int:
    """Return the validated issue number from a GitHub issue payload."""
    issue_number = issue_payload.get("number")
    if not isinstance(issue_number, int):
        raise RuntimeError("Matched issue number must be an integer")
    return issue_number


def _issue_url(issue_payload: dict[str, object]) -> str:
    """Return the validated html_url from a GitHub issue payload."""
    html_url = issue_payload.get("html_url")
    if not isinstance(html_url, str) or not html_url:
        raise RuntimeError("Matched issue html_url must be a non-empty string")
    return html_url


def sync_alert_issue(
    *,
    repo: str,
    title: str,
    body: str,
    labels: list[str],
    should_exist: bool,
    issue_payloads_by_title_fn=issue_payloads_by_title,
    run_gh_api_form_fn=run_gh_api_form,
) -> str:
    """Create, update, close, or reuse one alert issue addressed by exact title."""
    matches = issue_payloads_by_title_fn(repo, title)
    primary = matches[0] if matches else None
    fields = [
        ("title", title),
        ("body", body),
        *(("labels[]", label) for label in labels),
    ]

    if primary is None:
        if not should_exist:
            return ""

        return run_gh_api_form_fn(
            f"repos/{repo}/issues",
            method="POST",
            fields=fields,
            description=f"creating alert issue {title} for {repo}",
            jq_expr=".html_url",
        )

    issue_number = _issue_number(primary)
    if not should_exist:
        run_gh_api_form_fn(
            f"repos/{repo}/issues/{issue_number}",
            method="PATCH",
            fields=[("state", "closed")],
            description=f"closing alert issue {title} for {repo}",
        )
        return ""

    html_url = _issue_url(primary)

    run_gh_api_form_fn(
        f"repos/{repo}/issues/{issue_number}",
        method="PATCH",
        fields=fields,
        description=f"updating alert issue {title} for {repo}",
    )
    return html_url
