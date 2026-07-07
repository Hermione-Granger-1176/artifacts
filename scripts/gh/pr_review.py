"""Pull-request review-thread operations built on the GraphQL API.

The listing prints each thread's node id (``PRRT_...``), and replies/resolves key
off that id via ``addPullRequestReviewThreadReply`` and ``resolveReviewThread``.
This avoids the extra lookup the old REST flow needed to turn a thread into a
numeric comment ``databaseId``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from . import gh_runner
from .gh_runner import GhError, RunFunction

_THREADS_QUERY = """
query($owner: String!, $name: String!, $pr: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          path
          line
          comments(first: 1) {
            nodes { body url author { login } }
          }
        }
      }
    }
  }
}
"""

_REPLY_MUTATION = """
mutation($thread: ID!, $body: String!) {
  addPullRequestReviewThreadReply(
    input: { pullRequestReviewThreadId: $thread, body: $body }
  ) {
    comment { url }
  }
}
"""

_RESOLVE_MUTATION = """
mutation($thread: ID!) {
  resolveReviewThread(input: { threadId: $thread }) {
    thread { id isResolved }
  }
}
"""

_COMMENTS_QUERY = """
query($owner: String!, $name: String!, $pr: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $pr) {
      reviewThreads(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          comments(first: 100) {
            pageInfo { hasNextPage endCursor }
            nodes { id body url author { login } }
          }
        }
      }
    }
  }
}
"""

_THREAD_COMMENTS_QUERY = """
query($thread: ID!, $after: String) {
  node(id: $thread) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $after) {
        pageInfo { hasNextPage endCursor }
        nodes { id body url author { login } }
      }
    }
  }
}
"""

_DELETE_COMMENT_MUTATION = """
mutation($comment: ID!) {
  deletePullRequestReviewComment(input: { id: $comment }) {
    pullRequestReviewComment { id }
  }
}
"""


@dataclass(frozen=True)
class ReviewThread:
    """One review thread on a pull request."""

    thread_id: str
    state: str
    path: str
    line: int | None
    author: str
    body: str
    url: str


def _review_threads(data: Any) -> dict[str, Any]:
    """Return the ``reviewThreads`` connection (``pageInfo`` + ``nodes``).

    Raises:
        GhError: If the payload has no repository or pull request. An invalid or
            inaccessible PR returns ``pullRequest: null`` (with no ``errors``
            array), which would otherwise surface as an opaque ``TypeError``.
    """
    repository = data.get("repository") if isinstance(data, dict) else None
    pull_request = (
        repository.get("pullRequest") if isinstance(repository, dict) else None
    )
    if not isinstance(pull_request, dict):
        raise GhError(
            "No pull request in GraphQL response (invalid or inaccessible PR?)."
        )
    connection = pull_request.get("reviewThreads")
    if not isinstance(connection, dict):
        raise GhError("No review threads in GraphQL response (unexpected shape?).")
    return connection


def _parse_nodes(nodes: list[Any]) -> list[ReviewThread]:
    """Convert ``reviewThreads.nodes`` entries into ``ReviewThread`` objects."""
    if not isinstance(nodes, list):
        raise GhError("Unexpected reviewThreads.nodes shape in GraphQL response.")
    threads: list[ReviewThread] = []
    for node in nodes:
        if not isinstance(node, dict):
            raise GhError("Unexpected review thread node shape in GraphQL response.")
        thread_id = node.get("id")
        if not thread_id:
            raise GhError("Review thread node missing id in GraphQL response.")
        raw_comments = node.get("comments")
        if raw_comments is not None and not isinstance(raw_comments, dict):
            raise GhError(
                "Unexpected review thread comments shape in GraphQL response."
            )
        comments = (raw_comments or {}).get("nodes", [])
        if not isinstance(comments, list):
            raise GhError(
                "Unexpected review thread comments nodes shape in GraphQL response."
            )
        first = comments[0] if comments else {}
        if not isinstance(first, dict):
            raise GhError(
                "Unexpected review thread comment node shape in GraphQL response."
            )
        author = first.get("author")
        if author is not None and not isinstance(author, dict):
            raise GhError("Unexpected review comment author shape in GraphQL response.")
        author = author or {}
        threads.append(
            ReviewThread(
                thread_id=str(thread_id),
                state="resolved" if node.get("isResolved") else "open",
                path=str(node.get("path") or ""),
                line=node.get("line"),
                author=str(author.get("login") or "unknown"),
                body=str(first.get("body") or ""),
                url=str(first.get("url") or ""),
            )
        )
    return threads


def parse_threads(data: Any) -> list[ReviewThread]:
    """Convert a single GraphQL ``reviewThreads`` page into ``ReviewThread`` objects."""
    return _parse_nodes(_review_threads(data).get("nodes"))


def list_threads(
    pr: int | None = None,
    *,
    include_resolved: bool = False,
    run_fn: RunFunction | None = None,
) -> list[ReviewThread]:
    """Return the review threads for ``pr`` (auto-detected when omitted).

    Pages through ``reviewThreads`` so a PR with more than 100 threads is
    reported in full instead of being silently truncated at the first page.
    """
    owner, name = _owner_name(run_fn=run_fn)
    pr = pr if pr is not None else gh_runner.current_pr_number(run_fn=run_fn)

    threads: list[ReviewThread] = []
    after: str | None = None
    while True:
        variables: dict[str, object] = {"owner": owner, "name": name, "pr": pr}
        if after is not None:
            variables["after"] = after
        connection = _review_threads(
            gh_runner.graphql(_THREADS_QUERY, variables=variables, run_fn=run_fn)
        )
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise GhError("Unexpected reviewThreads.nodes shape in GraphQL response.")
        threads.extend(_parse_nodes(nodes))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict):
            raise GhError(
                "Unexpected reviewThreads pageInfo shape in GraphQL response."
            )
        after = page_info.get("endCursor")
        if not page_info.get("hasNextPage") or not after:
            break

    if include_resolved:
        return threads
    return [thread for thread in threads if thread.state == "open"]


def reply_to_thread(
    thread_id: str, body: str, *, run_fn: RunFunction | None = None
) -> None:
    """Reply to a review thread by its node id.

    Posting a reply is not idempotent, so it does not auto-retry: a lost
    response after a successful write would otherwise double-post the comment.
    """
    gh_runner.graphql(
        _REPLY_MUTATION,
        variables={"thread": thread_id, "body": body},
        run_fn=run_fn,
        retries=0,
    )


def resolve_thread(thread_id: str, *, run_fn: RunFunction | None = None) -> None:
    """Resolve a review thread by its node id (idempotent, so retries apply)."""
    gh_runner.graphql(
        _RESOLVE_MUTATION,
        variables={"thread": thread_id},
        run_fn=run_fn,
    )


def address_thread(
    thread_id: str, body: str, *, run_fn: RunFunction | None = None
) -> None:
    """Reply to a review thread and then resolve it, in that order."""
    reply_to_thread(thread_id, body, run_fn=run_fn)
    resolve_thread(thread_id, run_fn=run_fn)


@dataclass(frozen=True)
class ReviewComment:
    """One individual comment within a pull-request review thread."""

    comment_id: str
    author: str
    body: str
    url: str


def _parse_comment_nodes(nodes: list[Any]) -> list[ReviewComment]:
    """Convert raw comment nodes into ``ReviewComment`` objects."""
    if not isinstance(nodes, list):
        raise GhError("Unexpected review comment nodes shape in GraphQL response.")
    comments: list[ReviewComment] = []
    for comment in nodes:
        if not isinstance(comment, dict):
            raise GhError("Unexpected review comment node shape in GraphQL response.")
        comment_id = comment.get("id")
        if not comment_id:
            raise GhError("Review comment node missing id in GraphQL response.")
        author = comment.get("author")
        if author is not None and not isinstance(author, dict):
            raise GhError("Unexpected review comment author shape in GraphQL response.")
        author = author or {}
        comments.append(
            ReviewComment(
                comment_id=str(comment_id),
                author=str(author.get("login") or "unknown"),
                body=str(comment.get("body") or ""),
                url=str(comment.get("url") or ""),
            )
        )
    return comments


def _remaining_thread_comments(
    thread_id: str, page_info: dict[str, Any], *, run_fn: RunFunction | None = None
) -> list[ReviewComment]:
    """Page a single thread's comments beyond the first 100 already collected."""
    comments: list[ReviewComment] = []
    after = page_info.get("endCursor")
    while page_info.get("hasNextPage") and after:
        result = gh_runner.graphql(
            _THREAD_COMMENTS_QUERY,
            variables={"thread": thread_id, "after": after},
            run_fn=run_fn,
        )
        node = result.get("node")
        if not isinstance(node, dict) or "comments" not in node:
            raise GhError(f"review thread {thread_id} not found or inaccessible")
        connection = node["comments"]
        if not isinstance(connection, dict):
            raise GhError(f"review thread {thread_id} comments shape is unexpected")
        comments.extend(_parse_comment_nodes(connection.get("nodes") or []))
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict):
            raise GhError(f"review thread {thread_id} pageInfo shape is unexpected")
        after = page_info.get("endCursor")
    return comments


def list_comments(
    pr: int | None = None, *, run_fn: RunFunction | None = None
) -> list[ReviewComment]:
    """Return every individual review comment on ``pr`` (auto-detected when omitted).

    Unlike ``list_threads`` (which keeps only each thread's first comment for a
    summary view), this flattens all comments so a specific reply can be
    targeted by its node id, e.g. to delete a stray one. Both the thread list
    and each thread's comments are fully paginated, so "every" is literal even
    past the 100-per-page GraphQL caps.
    """
    owner, name = _owner_name(run_fn=run_fn)
    pr = pr if pr is not None else gh_runner.current_pr_number(run_fn=run_fn)

    comments: list[ReviewComment] = []
    after: str | None = None
    while True:
        variables: dict[str, object] = {"owner": owner, "name": name, "pr": pr}
        if after is not None:
            variables["after"] = after
        connection = _review_threads(
            gh_runner.graphql(_COMMENTS_QUERY, variables=variables, run_fn=run_fn)
        )
        nodes = connection.get("nodes")
        if not isinstance(nodes, list):
            raise GhError("Unexpected reviewThreads.nodes shape in GraphQL response.")
        for node in nodes:
            if not isinstance(node, dict):
                raise GhError(
                    "Unexpected review thread node shape in GraphQL response."
                )
            node_id = node.get("id")
            if not node_id:
                raise GhError("Review thread node missing id in GraphQL response.")
            thread_comments = node.get("comments")
            if not isinstance(thread_comments, dict):
                raise GhError("Unexpected thread comments shape in GraphQL response.")
            comments.extend(_parse_comment_nodes(thread_comments.get("nodes") or []))
            comments.extend(
                _remaining_thread_comments(
                    str(node_id), thread_comments.get("pageInfo") or {}, run_fn=run_fn
                )
            )
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, dict):
            raise GhError(
                "Unexpected reviewThreads pageInfo shape in GraphQL response."
            )
        after = page_info.get("endCursor")
        if not page_info.get("hasNextPage") or not after:
            break
    return comments


def delete_review_comment(
    comment_id: str, *, run_fn: RunFunction | None = None
) -> None:
    """Delete a single review comment by its node id.

    Deletion is destructive and not idempotent (a retry would error on the
    already-removed comment), so it does not auto-retry.
    """
    gh_runner.graphql(
        _DELETE_COMMENT_MUTATION,
        variables={"comment": comment_id},
        run_fn=run_fn,
        retries=0,
    )


def format_comments(comments: list[ReviewComment]) -> str:
    """Render review comments as greppable one-line-per-comment text."""
    if not comments:
        return "No review comments."
    blocks: list[str] = []
    for comment in comments:
        first_line = comment.body.splitlines()[0] if comment.body else ""
        blocks.append(f"comment={comment.comment_id}  @{comment.author}: {first_line}")
    return "\n".join(blocks)


def format_threads(threads: list[ReviewThread]) -> str:
    """Render threads as stable, greppable, one-block-per-thread text."""
    if not threads:
        return "No matching review threads."
    blocks: list[str] = []
    for thread in threads:
        location = thread.path or "(no path)"
        if thread.line is not None:
            location = f"{location}:{thread.line}"
        first_line = thread.body.splitlines()[0] if thread.body else ""
        blocks.append(
            f"thread={thread.thread_id}  state={thread.state}  path={location}\n"
            f"  @{thread.author}: {first_line}"
        )
    return "\n".join(blocks)


def pr_summary(pr: int | None = None, *, run_fn: RunFunction | None = None) -> str:
    """Return a one-screen overview: PR meta, CI rollup, and open threads."""
    pr = pr if pr is not None else gh_runner.current_pr_number(run_fn=run_fn)
    meta = gh_runner.gh_json(
        ["pr", "view", str(pr), "--json", "number,title,state,url,statusCheckRollup"],
        run_fn=run_fn,
    )
    if not isinstance(meta, dict):
        raise GhError(f"Unexpected PR view response shape for PR {pr}.")
    open_threads = list_threads(pr, include_resolved=False, run_fn=run_fn)
    lines = [
        f"PR #{meta.get('number')} [{meta.get('state')}] {meta.get('title')}",
        f"  {meta.get('url')}",
        f"  checks: {_rollup_summary(meta.get('statusCheckRollup') or [])}",
        f"  open review threads: {len(open_threads)}",
    ]
    if open_threads:
        lines.append("")
        lines.append(format_threads(open_threads))
    return "\n".join(lines)


def _rollup_summary(rollup: list[dict[str, Any]]) -> str:
    """Summarize a ``statusCheckRollup`` list as a conclusion tally."""
    if not rollup:
        return "none"
    counts: Counter[str] = Counter()
    for check in rollup:
        outcome = check.get("conclusion") or check.get("state") or "PENDING"
        counts[str(outcome).lower()] += 1
    return ", ".join(f"{count} {label}" for label, count in sorted(counts.items()))


def _owner_name(*, run_fn: RunFunction | None = None) -> tuple[str, str]:
    """Return the ``(owner, name)`` pair for the current repository."""
    slug = gh_runner.resolve_repo(run_fn=run_fn)
    owner, name = slug.split("/", 1)
    if not owner or not name:
        raise GhError(f"Invalid repository slug: {slug}")
    return owner, name
