"""Issue management commands behind the ``make issue-*`` targets.

Each command runs the same ``gh issue ...`` invocation the Makefile used to call
inline, with standard output left on the terminal so ``gh`` formats it exactly
as before. When the environment blocks GitHub GraphQL, the command is rebuilt on
the REST API instead. The functions return the process exit code.
"""

from __future__ import annotations

import re
import sys
from typing import Any
from urllib.parse import quote

from . import gh_runner
from .gh_runner import GhError, RunFunction, as_object, split_list

# ``gh issue list`` shows 30 issues unless told otherwise.
_LIST_LIMIT = 30


def _login(name: str, *, run_fn: RunFunction | None) -> str:
    """Return ``name``, resolving the ``@me`` shorthand to the authenticated login."""
    if name != "@me":
        return name
    login = as_object(gh_runner.rest("user", run_fn=run_fn)).get("login")
    if not isinstance(login, str) or not login:
        raise GhError("Could not resolve @me to a GitHub login.")
    return login


def _issue_url(issue: Any) -> str:
    """Return the web URL of a REST issue or comment response."""
    return str(as_object(issue).get("html_url") or "")


def _rest_issue_path(issue: int, *, run_fn: RunFunction | None) -> str:
    """Return the REST path of ``issue`` in the current repository."""
    return f"repos/{gh_runner.resolve_repo(run_fn=run_fn)}/issues/{issue}"


def _labels_of(issue: dict[str, Any]) -> list[str]:
    """Return the label names on a REST issue."""
    labels = issue.get("labels")
    return [str(as_object(label).get("name") or "") for label in labels] if labels else []


def _flag(name: str, value: str | None) -> list[str]:
    """Return ``[name, value]`` for a set option, or nothing when it is empty."""
    return [name, value] if value else []


def _print_issue_rows(slug: str, issues: list[dict[str, Any]]) -> None:
    """Print issues as tab-separated rows the way ``gh issue list`` does."""
    if not issues:
        print(f"No issues match your search in {slug}", file=sys.stderr)
    for issue in issues:
        labels_text = ", ".join(_labels_of(issue))
        state_text = str(issue.get("state") or "").upper()
        print(f"{issue.get('number')}\t{state_text}\t{issue.get('title')}\t{labels_text}")


def _list_filters(
    state: str | None,
    labels: str | None,
    assignee: str | None,
    author: str | None,
    *,
    run_fn: RunFunction | None,
) -> dict[str, object]:
    """Return the REST query fields for the ``list_issues`` filters."""
    fields: dict[str, object] = {"state": state or "open"}
    if labels:
        fields["labels"] = ",".join(split_list(labels))
    if assignee:
        fields["assignee"] = _login(assignee, run_fn=run_fn)
    if author:
        fields["creator"] = _login(author, run_fn=run_fn)
    return fields


def list_issues(
    *,
    state: str | None = None,
    labels: str | None = None,
    assignees: list[str] | None = None,
    author: str | None = None,
    limit: int | None = None,
    search: str | None = None,
    run_fn: RunFunction | None = None,
) -> int:
    """List issues (``gh issue list``) with the same filters the target accepts.

    Without ``search`` the REST fallback lists the repository's issues
    directly. With it, the fallback sends the filters and the search text
    through the REST search endpoint, which some sandboxes do not expose.
    """
    args = [
        "issue",
        "list",
        *_flag("--state", state),
        *_flag("--label", labels),
        *(part for assignee in assignees or [] for part in ("--assignee", assignee)),
        *_flag("--author", author),
        *_flag("--limit", None if limit is None else str(limit)),
        *_flag("--search", search),
    ]

    # gh's --assignee is a single-value flag, so a repeated one keeps the last value.
    last_assignee = assignees[-1] if assignees else None

    def list_with_rest() -> int:
        slug = gh_runner.resolve_repo(run_fn=run_fn)
        count = limit if limit is not None else _LIST_LIMIT
        if search:
            issues = gh_runner.rest_pages(
                "search/issues",
                items_key="items",
                fields={
                    "q": _search_query(slug, state, labels, last_assignee, author, search),
                    "sort": "created",
                    "order": "desc",
                },
                limit=count,
                run_fn=run_fn,
            )
        else:
            issues = gh_runner.rest_pages(
                f"repos/{slug}/issues",
                fields=_list_filters(state, labels, last_assignee, author, run_fn=run_fn),
                limit=count,
                accept=lambda item: "pull_request" not in item,
                run_fn=run_fn,
            )
        _print_issue_rows(slug, issues)
        return 0

    return gh_runner.gh_or_rest(args, list_with_rest, run_fn=run_fn)


def _search_query(
    slug: str,
    state: str | None,
    labels: str | None,
    assignee: str | None,
    author: str | None,
    search: str,
) -> str:
    """Build a search query that applies the list filters to ``search``."""
    terms = [f"repo:{slug}", "is:issue"]
    if (state or "open") != "all":
        terms.append(f"is:{state or 'open'}")
    terms += [f'label:"{label}"' for label in split_list(labels or "")]
    if assignee:
        terms.append(f"assignee:{assignee}")
    if author:
        terms.append(f"author:{author}")
    terms.append(search)
    return " ".join(terms)


def view_issue(issue: int, *, run_fn: RunFunction | None = None) -> int:
    """Show an issue with its comments (``gh issue view --comments``)."""

    def view_with_rest() -> int:
        path = _rest_issue_path(issue, run_fn=run_fn)
        raw = as_object(gh_runner.rest(path, run_fn=run_fn))
        assignees = [str(as_object(user).get("login")) for user in raw.get("assignees") or []]
        print(f"{raw.get('title')} #{raw.get('number')}")
        print(f"state: {str(raw.get('state') or '').upper()}")
        print(f"author: @{as_object(raw.get('user')).get('login', 'unknown')}")
        print(f"labels: {', '.join(_labels_of(raw)) or 'none'}")
        print(f"assignees: {', '.join(assignees) or 'none'}")
        print(f"milestone: {as_object(raw.get('milestone')).get('title') or 'none'}")
        print(raw.get("html_url"))
        if raw.get("body"):
            print(f"\n{raw['body']}")
        gh_runner.print_rest_comments(gh_runner.rest_pages(f"{path}/comments", run_fn=run_fn))
        return 0

    return gh_runner.gh_or_rest(
        ["issue", "view", str(issue), "--comments"], view_with_rest, run_fn=run_fn
    )


def create_issue(
    title: str,
    body: str,
    *,
    labels: str | None = None,
    assignee: str | None = None,
    run_fn: RunFunction | None = None,
) -> int:
    """Open an issue with ``body`` on standard input (``gh issue create``)."""
    args = ["issue", "create", "--title", title]
    if labels:
        args += ["--label", labels]
    if assignee:
        args += ["--assignee", assignee]
    args += ["--body-file", "-"]

    def create_with_rest() -> int:
        slug = gh_runner.resolve_repo(run_fn=run_fn)
        fields: dict[str, object] = {"title": title, "body": body}
        if labels:
            fields["labels"] = split_list(labels)
        if assignee:
            fields["assignees"] = [_login(name, run_fn=run_fn) for name in split_list(assignee)]
        created = gh_runner.rest(
            f"repos/{slug}/issues", method="POST", fields=fields, run_fn=run_fn
        )
        print(_issue_url(created))
        return 0

    return gh_runner.gh_or_rest(args, create_with_rest, run_fn=run_fn, stdin_text=body)


def comment_issue(issue: int, body: str, *, run_fn: RunFunction | None = None) -> int:
    """Comment on an issue with ``body`` on standard input (``gh issue comment``)."""

    def comment_with_rest() -> int:
        path = _rest_issue_path(issue, run_fn=run_fn)
        created = gh_runner.rest(
            f"{path}/comments", method="POST", fields={"body": body}, run_fn=run_fn
        )
        print(_issue_url(created))
        return 0

    return gh_runner.gh_or_rest(
        ["issue", "comment", str(issue), "--body-file", "-"],
        comment_with_rest,
        run_fn=run_fn,
        stdin_text=body,
    )


def edit_issue(
    issue: int,
    *,
    title: str | None = None,
    body: str | None = None,
    run_fn: RunFunction | None = None,
) -> int:
    """Change an issue's title and/or body (``gh issue edit``).

    ``body`` is piped to ``--body-file -`` so a large body never hits the
    command-line length limit.
    """
    if title is None and body is None:
        raise GhError("Provide a title or body to edit.")
    args = ["issue", "edit", str(issue)]
    if title is not None:
        args += ["--title", title]
    if body is not None:
        args += ["--body-file", "-"]

    def edit_with_rest() -> int:
        fields: dict[str, object] = {}
        if title is not None:
            fields["title"] = title
        if body is not None:
            fields["body"] = body
        edited = gh_runner.rest(
            _rest_issue_path(issue, run_fn=run_fn), method="PATCH", fields=fields, run_fn=run_fn
        )
        print(_issue_url(edited))
        return 0

    return gh_runner.gh_or_rest(args, edit_with_rest, run_fn=run_fn, stdin_text=body)


def label_issue(
    issue: int, labels: str, *, remove: bool = False, run_fn: RunFunction | None = None
) -> int:
    """Add (or with ``remove``, remove) comma-separated ``labels`` on an issue."""
    flag = "--remove-label" if remove else "--add-label"

    def label_with_rest() -> int:
        path = _rest_issue_path(issue, run_fn=run_fn)
        names = split_list(labels)
        if not remove:
            gh_runner.rest(f"{path}/labels", method="POST", fields={"labels": names}, run_fn=run_fn)
            print(f"Added labels to issue #{issue}: {labels}")
            return 0
        # Deleting a label the issue does not carry is a 404, while gh treats it
        # as a no-op, so only the labels actually present are removed, under the
        # spelling the issue uses.
        current = _labels_of(as_object(gh_runner.rest(path, run_fn=run_fn)))
        present = {label.lower(): label for label in current}
        for name in names:
            actual = present.get(name.lower())
            if actual is not None:
                gh_runner.rest(
                    f"{path}/labels/{quote(actual, safe='')}", method="DELETE", run_fn=run_fn
                )
        print(f"Removed labels from issue #{issue}: {labels}")
        return 0

    return gh_runner.gh_or_rest(
        ["issue", "edit", str(issue), flag, labels], label_with_rest, run_fn=run_fn
    )


def assign_issue(
    issue: int,
    *,
    users: str | None = None,
    mine: bool = False,
    remove: bool = False,
    run_fn: RunFunction | None = None,
) -> int:
    """Add (or with ``remove``, remove) assignees: ``mine`` is the authenticated user."""
    flag = "--remove-assignee" if remove else "--add-assignee"
    args = ["issue", "edit", str(issue)]
    if mine:
        args += [flag, "@me"]
    if users:
        args += [flag, users]

    def assign_with_rest() -> int:
        requested = (["@me"] if mine else []) + split_list(users or "")
        names = [_login(name, run_fn=run_fn) for name in requested]
        gh_runner.rest(
            f"{_rest_issue_path(issue, run_fn=run_fn)}/assignees",
            method="DELETE" if remove else "POST",
            fields={"assignees": names},
            run_fn=run_fn,
        )
        verb = "Removed" if remove else "Added"
        print(f"{verb} assignees on issue #{issue}: {', '.join(names)}")
        return 0

    return gh_runner.gh_or_rest(args, assign_with_rest, run_fn=run_fn)


def _set_issue_state(
    issue: int,
    state: str,
    *,
    reason: str | None,
    comment: str | None,
    run_fn: RunFunction | None,
) -> None:
    """Post an optional ``comment``, then set the issue ``state`` through REST."""
    path = _rest_issue_path(issue, run_fn=run_fn)
    if comment:
        gh_runner.rest(f"{path}/comments", method="POST", fields={"body": comment}, run_fn=run_fn)
    fields: dict[str, object] = {"state": state}
    if reason:
        fields["state_reason"] = reason.strip().lower().replace(" ", "_")
    gh_runner.rest(path, method="PATCH", fields=fields, run_fn=run_fn)


def close_issue(
    issue: int,
    *,
    reason: str | None = None,
    comment: str | None = None,
    run_fn: RunFunction | None = None,
) -> int:
    """Close an issue with an optional ``reason`` and ``comment`` (``gh issue close``)."""
    args = ["issue", "close", str(issue)]
    if reason:
        args += ["--reason", reason]
    if comment:
        args += ["--comment", comment]

    def close_with_rest() -> int:
        _set_issue_state(issue, "closed", reason=reason, comment=comment, run_fn=run_fn)
        print(f"Closed issue #{issue}")
        return 0

    return gh_runner.gh_or_rest(args, close_with_rest, run_fn=run_fn)


def reopen_issue(
    issue: int, *, comment: str | None = None, run_fn: RunFunction | None = None
) -> int:
    """Reopen a closed issue with an optional ``comment`` (``gh issue reopen``)."""
    args = ["issue", "reopen", str(issue)]
    if comment:
        args += ["--comment", comment]

    def reopen_with_rest() -> int:
        _set_issue_state(issue, "open", reason=None, comment=comment, run_fn=run_fn)
        print(f"Reopened issue #{issue}")
        return 0

    return gh_runner.gh_or_rest(args, reopen_with_rest, run_fn=run_fn)


def develop_issue(
    issue: int,
    *,
    base: str | None = None,
    name: str | None = None,
    run_fn: RunFunction | None = None,
) -> int:
    """Create and check out a branch linked to an issue (``gh issue develop --checkout``).

    Linking a branch to an issue is a GraphQL-only feature. The fallback creates
    and checks out the branch locally and says that it is not linked.
    """
    args = ["issue", "develop", str(issue), "--checkout"]
    if base:
        args += ["--base", base]
    if name:
        args += ["--name", name]

    def develop_with_rest() -> int:
        slug = gh_runner.resolve_repo(run_fn=run_fn)
        gh_runner.require_checkout_repo(slug, f"develop issue #{issue}", run_fn=run_fn)
        target = base or gh_runner.default_branch(slug, run_fn=run_fn)
        branch = name or _branch_name(issue, slug, run_fn=run_fn)
        gh_runner.run_git(["fetch", "origin", target], run_fn=run_fn)
        # FETCH_HEAD exists even in a clone whose refspec has no origin/<target>.
        gh_runner.run_git(["checkout", "-b", branch, "--no-track", "FETCH_HEAD"], run_fn=run_fn)
        print(
            f"Created and checked out {branch} from {target}. GitHub GraphQL is unavailable, "
            f"so the branch is not linked to issue #{issue}.",
            file=sys.stderr,
        )
        return 0

    return gh_runner.gh_or_rest(args, develop_with_rest, run_fn=run_fn)


def _branch_name(issue: int, slug: str, *, run_fn: RunFunction | None) -> str:
    """Return ``<number>-<title-slug>``, the branch name ``gh issue develop`` would pick."""
    raw = as_object(gh_runner.rest(f"repos/{slug}/issues/{issue}", run_fn=run_fn))
    title = re.sub(r"[^a-z0-9]+", "-", str(raw.get("title") or "").lower()).strip("-")
    return f"{issue}-{title}" if title else str(issue)
