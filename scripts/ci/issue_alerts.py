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

    if not should_exist:
        if primary is None:
            return ""

        issue_number = primary.get("number")
        if not isinstance(issue_number, int):
            raise RuntimeError("Matched issue number must be an integer")
        run_gh_api_form_fn(
            f"repos/{repo}/issues/{issue_number}",
            method="PATCH",
            fields=[("state", "closed")],
            description=f"closing alert issue {title} for {repo}",
        )
        return ""

    if primary is None:
        return run_gh_api_form_fn(
            f"repos/{repo}/issues",
            method="POST",
            fields=fields,
            description=f"creating alert issue {title} for {repo}",
            jq_expr=".html_url",
        )

    issue_number = primary.get("number")
    if not isinstance(issue_number, int):
        raise RuntimeError("Matched issue number must be an integer")
    html_url = primary.get("html_url")
    if not isinstance(html_url, str) or not html_url:
        raise RuntimeError("Matched issue html_url must be a non-empty string")

    run_gh_api_form_fn(
        f"repos/{repo}/issues/{issue_number}",
        method="PATCH",
        fields=fields,
        description=f"updating alert issue {title} for {repo}",
    )
    return html_url
