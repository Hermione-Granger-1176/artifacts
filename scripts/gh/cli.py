"""Command-line dispatcher for the GitHub PR/CI helpers.

Internal entrypoint for the PR/CI helper commands. The Makefile is the sole
supported contributor interface and will wrap these commands in pr-*/ci-* targets
in a later PR, so this module is not meant to be invoked directly by contributors.
Each subcommand documents its own options via ``--help`` so the command surface
can be discovered without re-deriving any ``gh`` plumbing.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from . import ci_status, pr_review
from .gh_runner import GhError


def _add_body_options(parser: argparse.ArgumentParser) -> None:
    """Add shared reply body options to a subcommand parser."""
    body_group = parser.add_mutually_exclusive_group(required=True)
    body_group.add_argument("--body", help="Reply text")
    body_group.add_argument("--body-file", help="Path to a file containing reply text")


def _body_text(args: argparse.Namespace) -> str:
    """Return the body text from ``--body`` or ``--body-file``."""
    if args.body_file:
        try:
            return Path(args.body_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise GhError(
                f"could not read --body-file {args.body_file}: {exc}"
            ) from exc
    return str(args.body)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh-helper", description="GitHub pull-request and CI helper commands"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List pull-request review threads")
    list_parser.add_argument(
        "--pr", type=int, help="PR number (default: current branch)"
    )
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
    reply_parser.add_argument("--thread", required=True, help="Thread id (PRRT_...)")
    _add_body_options(reply_parser)

    resolve_parser = subparsers.add_parser(
        "resolve", help="Resolve a review thread by id"
    )
    resolve_parser.add_argument("--thread", required=True, help="Thread id (PRRT_...)")

    address_parser = subparsers.add_parser(
        "address", help="Reply to and resolve a review thread in one step"
    )
    address_parser.add_argument("--thread", required=True, help="Thread id (PRRT_...)")
    _add_body_options(address_parser)

    list_comments_parser = subparsers.add_parser(
        "list-comments", help="List individual review comments with node ids"
    )
    list_comments_parser.add_argument(
        "--pr", type=int, help="PR number (default: current branch)"
    )
    list_comments_parser.add_argument(
        "--json", action="store_true", dest="as_json", help="Emit machine-readable JSON"
    )

    delete_comment_parser = subparsers.add_parser(
        "delete-comment", help="Delete a review comment by its node id"
    )
    delete_comment_parser.add_argument(
        "--comment", required=True, help="Comment node id (PRRC_...)"
    )

    summary_parser = subparsers.add_parser("summary", help="One-screen PR overview")
    summary_parser.add_argument(
        "--pr", type=int, help="PR number (default: current branch)"
    )

    ci_parser = subparsers.add_parser(
        "ci-failures", help="Show failed-step logs for the latest run"
    )
    ci_parser.add_argument(
        "--run", type=int, help="Run id (default: latest for this branch)"
    )

    copilot_parser = subparsers.add_parser(
        "copilot-review", help="Request a Copilot code review on the PR"
    )
    copilot_parser.add_argument(
        "--pr", type=int, help="PR number (default: current branch)"
    )

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
    pr_review.reply_to_thread(args.thread, _body_text(args))
    print(f"Replied to {args.thread}")
    return 0


def _handle_resolve(args: argparse.Namespace) -> int:
    """Resolve a single review thread."""
    pr_review.resolve_thread(args.thread)
    print(f"Resolved {args.thread}")
    return 0


def _handle_address(args: argparse.Namespace) -> int:
    """Reply to and resolve a single review thread."""
    pr_review.address_thread(args.thread, _body_text(args))
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


def _handle_summary(args: argparse.Namespace) -> int:
    """Print the PR overview."""
    print(pr_review.pr_summary(args.pr))
    return 0


def _handle_ci_failures(args: argparse.Namespace) -> int:
    """Print failed-step logs for a run."""
    print(ci_status.failure_digest(args.run))
    return 0


def _handle_copilot_review(args: argparse.Namespace) -> int:
    """Request a Copilot code review on the PR."""
    pr_review.request_copilot_review(args.pr)
    print("Requested Copilot review")
    return 0


COMMAND_HANDLERS = {
    "list": _handle_list,
    "reply": _handle_reply,
    "resolve": _handle_resolve,
    "address": _handle_address,
    "list-comments": _handle_list_comments,
    "delete-comment": _handle_delete_comment,
    "summary": _handle_summary,
    "ci-failures": _handle_ci_failures,
    "copilot-review": _handle_copilot_review,
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
