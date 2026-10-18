"""Command-line dispatcher for the GitHub PR/CI helpers.

Run as ``python -m scripts.gh.cli <command>``. The Makefile wraps each command
in a thin target, and ``<command> --help`` documents its options, so an agent
can discover the full surface without re-deriving any ``gh`` plumbing.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import (
    ci_status,
    commit_message,
    gh_runner,
    issue_commands,
    issues,
    pr_commands,
    pr_review,
    pr_watch,
)
from .gh_runner import GhError


def _add_body_options(parser: argparse.ArgumentParser, *, required: bool = True) -> None:
    """Add the shared body options (reply, comment, or PR body) to a subcommand parser."""
    body_group = parser.add_mutually_exclusive_group(required=required)
    body_group.add_argument("--body", help="Body text")
    body_group.add_argument(
        "--body-file", help="Path to a file containing the body text (- reads stdin)"
    )


def _add_pr_option(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    """Add the shared ``--pr`` option (the current branch's PR when omitted)."""
    parser.add_argument(
        "--pr",
        type=int,
        required=required,
        help="PR number" if required else "PR number (default: current branch)",
    )


def _add_thread_options(parser: argparse.ArgumentParser) -> None:
    """Add the thread id and PR options shared by the reply, resolve, and address commands."""
    parser.add_argument(
        "--thread",
        required=True,
        help="Thread id (PRRT_..., or the numeric id printed when GraphQL is unavailable)",
    )
    _add_pr_option(parser)


def _add_issue_option(parser: argparse.ArgumentParser) -> None:
    """Add the required ``--issue`` number option."""
    parser.add_argument("--issue", type=int, required=True, help="Issue number")


def _body_text(args: argparse.Namespace) -> str:
    """Return the body text from ``--body`` or ``--body-file`` (``-`` reads stdin)."""
    if args.body_file is not None:
        if args.body_file == "-":
            return sys.stdin.read()
        try:
            return Path(args.body_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise GhError(f"Could not read --body-file {args.body_file}: {exc}") from exc
    return str(args.body)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh-helper", description="GitHub pull-request and CI helper commands"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List pull-request review threads")
    list_parser.add_argument("--pr", type=int, help="PR number (default: current branch)")
    list_parser.add_argument(
        "--all",
        action="store_true",
        dest="include_resolved",
        help="Include resolved threads",
    )
    list_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Emit machine-readable JSON"
    )

    reply_parser = subparsers.add_parser("reply", help="Reply to a review thread by id")
    _add_thread_options(reply_parser)
    _add_body_options(reply_parser)

    resolve_parser = subparsers.add_parser("resolve", help="Resolve a review thread by id")
    _add_thread_options(resolve_parser)

    address_parser = subparsers.add_parser(
        "address", help="Reply to and resolve a review thread in one step"
    )
    _add_thread_options(address_parser)
    _add_body_options(address_parser)

    list_comments_parser = subparsers.add_parser(
        "list-comments", help="List individual review comments with node ids"
    )
    list_comments_parser.add_argument("--pr", type=int, help="PR number (default: current branch)")
    list_comments_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Emit machine-readable JSON"
    )

    delete_comment_parser = subparsers.add_parser(
        "delete-comment", help="Delete a review comment by its node id"
    )
    delete_comment_parser.add_argument(
        "--comment", required=True, help="Comment node id (PRRC_...) or numeric id"
    )

    comment_parser = subparsers.add_parser("comment", help="Add a PR-level comment")
    comment_parser.add_argument("--pr", type=int, help="PR number (default: current branch)")
    _add_body_options(comment_parser)

    edit_pr_parser = subparsers.add_parser("edit-pr", help="Edit a PR title and/or body")
    edit_pr_parser.add_argument("--pr", type=int, help="PR number (default: current branch)")
    edit_pr_parser.add_argument("--title", help="New PR title")
    _add_body_options(edit_pr_parser, required=False)

    summary_parser = subparsers.add_parser("summary", help="One-screen PR overview")
    summary_parser.add_argument("--pr", type=int, help="PR number (default: current branch)")

    issue_summary_parser = subparsers.add_parser("issue-summary", help="One-screen issue overview")
    issue_summary_parser.add_argument("--issue", type=int, required=True, help="Issue number")

    watch_parser = subparsers.add_parser(
        "watch",
        help="Observe the latest Copilot review and successful checks",
    )
    watch_parser.add_argument("--pr", type=int, help="PR number (default: current branch)")
    watch_parser.add_argument(
        "--interval",
        type=float,
        default=45.0,
        help="Poll interval in seconds",
    )
    watch_parser.add_argument(
        "--max-polls",
        type=int,
        default=40,
        help="Maximum poll count",
    )
    watch_parser.add_argument(
        "--expected-checks",
        type=int,
        default=pr_watch.DEFAULT_EXPECTED_CHECKS,
        help="Minimum expected check count",
    )
    watch_parser.add_argument(
        "--checks-only",
        action="store_true",
        help="Wait for checks without waiting for a Copilot review",
    )
    watch_parser.add_argument(
        "--request-copilot",
        action="store_true",
        help="Request Copilot after capturing the review baseline",
    )

    ci_parser = subparsers.add_parser(
        "ci-failures", help="Show failed-step logs for the latest run"
    )
    ci_parser.add_argument("--run", type=int, help="Run id (default: latest for this branch)")

    subparsers.add_parser(
        "latest-run-id", help="Print the latest workflow run id for the current branch"
    )

    copilot_parser = subparsers.add_parser(
        "copilot-review", help="Request a Copilot code review on the PR"
    )
    copilot_parser.add_argument("--pr", type=int, help="PR number (default: current branch)")

    check_commit_parser = subparsers.add_parser(
        "check-commit-message",
        help="Reject a commit message that leaked shell text (heredoc fragments)",
    )
    check_commit_parser.add_argument(
        "--message-file",
        required=True,
        help="Path to the commit message (- reads stdin)",
    )

    subparsers.add_parser("current-pr", help="Print the current branch's PR number")

    pr_create_parser = subparsers.add_parser("pr-create", help="Open a pull request")
    pr_create_parser.add_argument("--base", help="Base branch (default: the repository default)")
    pr_create_parser.add_argument(
        "--title",
        help="PR title; the body is then read from --body-file (default: fill from commits)",
    )
    _add_body_options(pr_create_parser, required=False)

    subparsers.add_parser("pr-list", help="List open pull requests")

    pr_status_parser = subparsers.add_parser("pr-status", help="Show a PR's CI checks")
    _add_pr_option(pr_status_parser)

    pr_checks_parser = subparsers.add_parser(
        "pr-checks", help="Watch a PR's CI checks until they finish or one fails"
    )
    _add_pr_option(pr_checks_parser)
    pr_checks_parser.add_argument(
        "--interval",
        type=float,
        default=pr_commands.CHECKS_INTERVAL_SECONDS,
        help="Poll interval in seconds (REST fallback)",
    )
    pr_checks_parser.add_argument(
        "--max-polls",
        type=int,
        default=pr_commands.CHECKS_MAX_POLLS,
        help="Maximum poll count (REST fallback)",
    )

    pr_diff_parser = subparsers.add_parser("pr-diff", help="Show a PR's diff")
    _add_pr_option(pr_diff_parser)

    pr_checkout_parser = subparsers.add_parser("pr-checkout", help="Check out a PR's branch")
    _add_pr_option(pr_checkout_parser, required=True)

    pr_comments_parser = subparsers.add_parser(
        "pr-comments", help="Show a PR with its comments and review summaries"
    )
    _add_pr_option(pr_comments_parser)

    pr_merge_parser = subparsers.add_parser(
        "pr-merge", help="Squash-merge a PR and delete its branch"
    )
    _add_pr_option(pr_merge_parser)
    pr_merge_parser.add_argument(
        "--admin", action="store_true", help="Merge past branch protection with admin rights"
    )

    pr_reviewers_parser = subparsers.add_parser("pr-reviewers", help="Request PR reviewers")
    _add_pr_option(pr_reviewers_parser)
    pr_reviewers_parser.add_argument("--users", required=True, help="Comma-separated reviewers")

    pr_label_parser = subparsers.add_parser("pr-label", help="Add labels to a PR")
    _add_pr_option(pr_label_parser)
    pr_label_parser.add_argument("--labels", required=True, help="Comma-separated labels")

    pr_close_parser = subparsers.add_parser("pr-close", help="Close a PR and delete its branch")
    _add_pr_option(pr_close_parser)

    issue_list_parser = subparsers.add_parser("issue-list", help="List issues")
    issue_list_parser.add_argument("--state", help="open, closed, or all")
    issue_list_parser.add_argument("--label", help="Comma-separated labels")
    issue_list_parser.add_argument(
        "--assignee", action="append", help="Assignee login or @me (repeatable)"
    )
    issue_list_parser.add_argument("--author", help="Author login")
    issue_list_parser.add_argument("--limit", type=int, help="Maximum issues to list")
    issue_list_parser.add_argument("--search", help="Free-text search query")

    issue_view_parser = subparsers.add_parser("issue-view", help="Show an issue with its comments")
    _add_issue_option(issue_view_parser)

    issue_create_parser = subparsers.add_parser("issue-create", help="Open an issue")
    issue_create_parser.add_argument("--title", required=True, help="Issue title")
    issue_create_parser.add_argument("--labels", help="Comma-separated labels")
    issue_create_parser.add_argument("--assignee", help="Assignee login or @me")
    _add_body_options(issue_create_parser)

    issue_comment_parser = subparsers.add_parser("issue-comment", help="Comment on an issue")
    _add_issue_option(issue_comment_parser)
    _add_body_options(issue_comment_parser)

    issue_edit_parser = subparsers.add_parser("issue-edit", help="Edit an issue title and/or body")
    _add_issue_option(issue_edit_parser)
    issue_edit_parser.add_argument("--title", help="New issue title")
    _add_body_options(issue_edit_parser, required=False)

    for command, summary in (
        ("issue-label", "Add labels to an issue"),
        ("issue-unlabel", "Remove labels from an issue"),
    ):
        label_parser = subparsers.add_parser(command, help=summary)
        _add_issue_option(label_parser)
        label_parser.add_argument("--labels", required=True, help="Comma-separated labels")

    for command, summary in (
        ("issue-assign", "Assign users to an issue"),
        ("issue-unassign", "Remove assignees from an issue"),
    ):
        assign_parser = subparsers.add_parser(command, help=summary)
        _add_issue_option(assign_parser)
        assign_parser.add_argument("--users", help="Comma-separated logins")
        assign_parser.add_argument("--mine", action="store_true", help="Use the authenticated user")

    issue_close_parser = subparsers.add_parser("issue-close", help="Close an issue")
    _add_issue_option(issue_close_parser)
    issue_close_parser.add_argument("--reason", help="completed or 'not planned'")
    issue_close_parser.add_argument("--comment", help="Comment to post when closing")

    issue_reopen_parser = subparsers.add_parser("issue-reopen", help="Reopen an issue")
    _add_issue_option(issue_reopen_parser)
    issue_reopen_parser.add_argument("--comment", help="Comment to post when reopening")

    issue_develop_parser = subparsers.add_parser(
        "issue-develop", help="Create and check out a branch for an issue"
    )
    _add_issue_option(issue_develop_parser)
    issue_develop_parser.add_argument(
        "--base", help="Base branch (default: the repository default)"
    )
    issue_develop_parser.add_argument("--name", help="Branch name (default: from the issue)")

    return parser


def _handle_list(args: argparse.Namespace) -> int:
    """List review threads as text or JSON."""
    threads = pr_review.list_threads(args.pr, include_resolved=args.include_resolved)
    if args.as_json:
        print(json.dumps([asdict(thread) for thread in threads]))
    else:
        print(pr_review.format_threads(threads))
    return 0


def _handle_reply(args: argparse.Namespace) -> int:
    """Reply to a single review thread."""
    pr_review.reply_to_thread(args.thread, _body_text(args), pr=args.pr)
    print(f"Replied to {args.thread}")
    return 0


def _handle_resolve(args: argparse.Namespace) -> int:
    """Resolve a single review thread."""
    pr_review.resolve_thread(args.thread, pr=args.pr)
    print(f"Resolved {args.thread}")
    return 0


def _handle_address(args: argparse.Namespace) -> int:
    """Reply to and resolve a single review thread."""
    pr_review.address_thread(args.thread, _body_text(args), pr=args.pr)
    print(f"Replied to and resolved {args.thread}")
    return 0


def _handle_list_comments(args: argparse.Namespace) -> int:
    """List individual review comments as text or JSON."""
    comments = pr_review.list_comments(args.pr)
    if args.as_json:
        print(json.dumps([asdict(comment) for comment in comments]))
    else:
        print(pr_review.format_comments(comments))
    return 0


def _handle_delete_comment(args: argparse.Namespace) -> int:
    """Delete a single review comment by node id."""
    pr_review.delete_review_comment(args.comment)
    print(f"Deleted {args.comment}")
    return 0


def _handle_comment(args: argparse.Namespace) -> int:
    """Post a PR-level comment."""
    pr_review.comment_on_pr(args.pr, _body_text(args))
    print("Commented on the PR")
    return 0


def _handle_edit_pr(args: argparse.Namespace) -> int:
    """Edit a pull request's title and/or body.

    The body file is forwarded to ``gh pr edit --body-file`` rather than read
    here, so gh handles large files (and ``-`` stdin) without an oversized
    command-line argument.
    """
    pr_review.edit_pr(args.pr, title=args.title, body=args.body, body_file=args.body_file)
    print("Edited PR")
    return 0


def _handle_summary(args: argparse.Namespace) -> int:
    """Print the PR overview."""
    print(pr_review.pr_summary(args.pr))
    return 0


def _handle_issue_summary(args: argparse.Namespace) -> int:
    """Print the issue overview."""
    print(issues.issue_summary(args.issue))
    return 0


def _handle_watch(args: argparse.Namespace) -> int:
    """Wait for a pull request to settle, then print its report."""
    print(
        pr_watch.watch_pr(
            args.pr,
            interval=args.interval,
            max_polls=args.max_polls,
            expected_checks=args.expected_checks,
            checks_only=args.checks_only,
            request_copilot=args.request_copilot,
        )
    )
    return 0


def _handle_ci_failures(args: argparse.Namespace) -> int:
    """Print failed-step logs for a run."""
    print(ci_status.failure_digest(args.run))
    return 0


def _handle_latest_run_id(_args: argparse.Namespace) -> int:
    """Print the latest workflow run id for the current branch."""
    print(ci_status.latest_run().run_id)
    return 0


def _handle_copilot_review(args: argparse.Namespace) -> int:
    """Request a Copilot code review on the PR."""
    pr_review.request_copilot_review(args.pr)
    print("Requested Copilot review")
    return 0


def _handle_check_commit_message(args: argparse.Namespace) -> int:
    """Validate a commit message and reject leaked shell fragments."""
    if args.message_file == "-":
        message = sys.stdin.read()
    else:
        try:
            message = Path(args.message_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise GhError(f"Could not read --message-file {args.message_file}: {exc}") from exc
    try:
        commit_message.validate_commit_message(message)
    except ValueError as exc:
        raise GhError(str(exc)) from exc
    return 0


def _handle_current_pr(_args: argparse.Namespace) -> int:
    """Print the current branch's PR number."""
    print(gh_runner.current_pr_number())
    return 0


def _handle_pr_create(args: argparse.Namespace) -> int:
    """Open a pull request, with commit-filled text unless a title is given."""
    if args.title is None:
        if args.body is not None or args.body_file is not None:
            raise GhError("A PR body needs a --title; without one the text is filled from commits.")
        return pr_commands.create_pr(base=args.base)
    body = _body_text(args) if args.body is not None or args.body_file is not None else ""
    return pr_commands.create_pr(title=args.title, base=args.base, body=body)


def _handle_pr_list(_args: argparse.Namespace) -> int:
    """List open pull requests."""
    return pr_commands.list_prs()


def _handle_pr_status(args: argparse.Namespace) -> int:
    """Show a PR's CI checks."""
    return pr_commands.pr_checks_status(args.pr)


def _handle_pr_checks(args: argparse.Namespace) -> int:
    """Watch a PR's CI checks."""
    return pr_commands.watch_pr_checks(args.pr, interval=args.interval, max_polls=args.max_polls)


def _handle_pr_diff(args: argparse.Namespace) -> int:
    """Show a PR's diff."""
    return pr_commands.show_diff(args.pr)


def _handle_pr_checkout(args: argparse.Namespace) -> int:
    """Check out a PR's branch."""
    return pr_commands.checkout_pr(args.pr)


def _handle_pr_comments(args: argparse.Namespace) -> int:
    """Show a PR with its comments."""
    return pr_commands.view_comments(args.pr)


def _handle_pr_merge(args: argparse.Namespace) -> int:
    """Squash-merge a PR."""
    return pr_commands.merge_pr(args.pr, admin=args.admin)


def _handle_pr_reviewers(args: argparse.Namespace) -> int:
    """Request PR reviewers."""
    return pr_commands.add_reviewers(args.users, args.pr)


def _handle_pr_label(args: argparse.Namespace) -> int:
    """Add labels to a PR."""
    return pr_commands.add_labels(args.labels, args.pr)


def _handle_pr_close(args: argparse.Namespace) -> int:
    """Close a PR."""
    return pr_commands.close_pr(args.pr)


def _handle_issue_list(args: argparse.Namespace) -> int:
    """List issues."""
    return issue_commands.list_issues(
        state=args.state,
        labels=args.label,
        assignees=args.assignee,
        author=args.author,
        limit=args.limit,
        search=args.search,
    )


def _handle_issue_view(args: argparse.Namespace) -> int:
    """Show an issue with its comments."""
    return issue_commands.view_issue(args.issue)


def _handle_issue_create(args: argparse.Namespace) -> int:
    """Open an issue."""
    return issue_commands.create_issue(
        args.title, _body_text(args), labels=args.labels, assignee=args.assignee
    )


def _handle_issue_comment(args: argparse.Namespace) -> int:
    """Comment on an issue."""
    return issue_commands.comment_issue(args.issue, _body_text(args))


def _handle_issue_edit(args: argparse.Namespace) -> int:
    """Edit an issue's title and/or body."""
    has_body = args.body is not None or args.body_file is not None
    return issue_commands.edit_issue(
        args.issue, title=args.title, body=_body_text(args) if has_body else None
    )


def _handle_issue_label(args: argparse.Namespace) -> int:
    """Add labels to an issue."""
    return issue_commands.label_issue(args.issue, args.labels)


def _handle_issue_unlabel(args: argparse.Namespace) -> int:
    """Remove labels from an issue."""
    return issue_commands.label_issue(args.issue, args.labels, remove=True)


def _handle_issue_assign(args: argparse.Namespace) -> int:
    """Assign users to an issue."""
    return issue_commands.assign_issue(args.issue, users=args.users, mine=args.mine)


def _handle_issue_unassign(args: argparse.Namespace) -> int:
    """Remove assignees from an issue."""
    return issue_commands.assign_issue(args.issue, users=args.users, mine=args.mine, remove=True)


def _handle_issue_close(args: argparse.Namespace) -> int:
    """Close an issue."""
    return issue_commands.close_issue(args.issue, reason=args.reason, comment=args.comment)


def _handle_issue_reopen(args: argparse.Namespace) -> int:
    """Reopen an issue."""
    return issue_commands.reopen_issue(args.issue, comment=args.comment)


def _handle_issue_develop(args: argparse.Namespace) -> int:
    """Create and check out a branch for an issue."""
    return issue_commands.develop_issue(args.issue, base=args.base, name=args.name)


COMMAND_HANDLERS = {
    "list": _handle_list,
    "reply": _handle_reply,
    "resolve": _handle_resolve,
    "address": _handle_address,
    "list-comments": _handle_list_comments,
    "delete-comment": _handle_delete_comment,
    "comment": _handle_comment,
    "edit-pr": _handle_edit_pr,
    "summary": _handle_summary,
    "issue-summary": _handle_issue_summary,
    "watch": _handle_watch,
    "ci-failures": _handle_ci_failures,
    "latest-run-id": _handle_latest_run_id,
    "copilot-review": _handle_copilot_review,
    "check-commit-message": _handle_check_commit_message,
    "current-pr": _handle_current_pr,
    "pr-create": _handle_pr_create,
    "pr-list": _handle_pr_list,
    "pr-status": _handle_pr_status,
    "pr-checks": _handle_pr_checks,
    "pr-diff": _handle_pr_diff,
    "pr-checkout": _handle_pr_checkout,
    "pr-comments": _handle_pr_comments,
    "pr-merge": _handle_pr_merge,
    "pr-reviewers": _handle_pr_reviewers,
    "pr-label": _handle_pr_label,
    "pr-close": _handle_pr_close,
    "issue-list": _handle_issue_list,
    "issue-view": _handle_issue_view,
    "issue-create": _handle_issue_create,
    "issue-comment": _handle_issue_comment,
    "issue-edit": _handle_issue_edit,
    "issue-label": _handle_issue_label,
    "issue-unlabel": _handle_issue_unlabel,
    "issue-assign": _handle_issue_assign,
    "issue-unassign": _handle_issue_unassign,
    "issue-close": _handle_issue_close,
    "issue-reopen": _handle_issue_reopen,
    "issue-develop": _handle_issue_develop,
}


def main(argv: list[str] | None = None) -> int:
    """Run a GitHub helper command."""
    args = _build_parser().parse_args(argv)
    handler = COMMAND_HANDLERS[args.command]
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except (GhError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
