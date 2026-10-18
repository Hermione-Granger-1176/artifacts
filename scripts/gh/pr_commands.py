"""Pull-request management commands behind the ``make pr-*`` targets.

Each command runs the same ``gh pr ...`` invocation the Makefile used to call
inline, with standard output left on the terminal so ``gh`` formats it exactly
as before. When the environment blocks GitHub GraphQL (which every ``gh pr``
subcommand needs), the command is rebuilt on the REST API instead. The
functions return the process exit code so a failing check still fails the
target.
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from . import gh_runner, pr_rest
from .gh_runner import GhError, RunFunction, as_object, split_list

if TYPE_CHECKING:
    from collections.abc import Callable

# ``gh pr list`` shows 30 pull requests unless told otherwise.
_LIST_LIMIT = 30
# ``gh pr checks`` polls every 10 seconds. The REST watch also stops after an
# hour so a check that never finishes cannot hold a terminal forever.
CHECKS_INTERVAL_SECONDS = 10.0
CHECKS_MAX_POLLS = 360
# REST ``mergeable_state`` values that mean branch protection allows a merge.
# ``unstable`` has failing checks that are not required.
_MERGEABLE_STATES = frozenset({"clean", "unstable", "has_hooks"})
# ``gh pr checks`` exits 8 while any check is still running.
_PENDING_EXIT_CODE = 8
_DIFF_ACCEPT = "Accept: application/vnd.github.diff"


@dataclass(frozen=True)
class CheckRow:
    """One check shown in the ``gh pr checks`` style table."""

    name: str
    bucket: str
    elapsed: str
    url: str


def _pr_command(base: list[str], pr: int | None) -> list[str]:
    """Return ``base`` followed by the PR number when one was given."""
    return [*base, str(pr)] if pr is not None else base


def _target(pr: int | None, *, run_fn: RunFunction | None) -> tuple[str, int]:
    """Return the ``(owner/name, pr)`` pair a REST fallback acts on."""
    slug = gh_runner.resolve_repo(run_fn=run_fn)
    return slug, pr if pr is not None else gh_runner.current_pr_number(run_fn=run_fn)


def _bucket(entry: dict[str, Any]) -> str:
    """Classify a ``statusCheckRollup`` entry as pass, fail, pending, skipping, or cancel."""
    if "status" in entry:
        if entry["status"] != "COMPLETED":
            return "pending"
        conclusion = entry.get("conclusion")
        if conclusion in {"SUCCESS", "NEUTRAL"}:
            return "pass"
        if conclusion == "SKIPPED":
            return "skipping"
        return "cancel" if conclusion == "CANCELLED" else "fail"
    state = entry.get("state")
    if state == "SUCCESS":
        return "pass"
    return "pending" if state in {"PENDING", "EXPECTED"} else "fail"


def _elapsed(started: object, completed: object) -> str:
    """Return how long a check ran as ``1m5s``, or an empty string when unknown."""
    try:
        begin = datetime.fromisoformat(str(started))
        end = datetime.fromisoformat(str(completed))
    except ValueError:
        return ""
    minutes, seconds = divmod(max(0, int((end - begin).total_seconds())), 60)
    return f"{minutes}m{seconds}s" if minutes else f"{seconds}s"


def check_rows(rollup: list[dict[str, Any]]) -> list[CheckRow]:
    """Convert a ``statusCheckRollup`` list into table rows."""
    return [
        CheckRow(
            name=str(entry.get("name") or entry.get("context") or ""),
            bucket=_bucket(entry),
            elapsed=_elapsed(entry.get("startedAt"), entry.get("completedAt")),
            url=str(entry.get("detailsUrl") or entry.get("targetUrl") or ""),
        )
        for entry in rollup
    ]


def _print_rows(rows: list[CheckRow]) -> None:
    """Print check rows tab-separated, the layout ``gh pr checks`` uses when piped."""
    for row in rows:
        print(f"{row.name}\t{row.bucket}\t{row.elapsed}\t{row.url}")


def _exit_code(rows: list[CheckRow]) -> int:
    """Return the ``gh pr checks`` exit code: 1 when a check failed, 8 while pending, else 0."""
    buckets = {row.bucket for row in rows}
    if buckets & {"fail", "cancel"}:
        return 1
    return _PENDING_EXIT_CODE if "pending" in buckets else 0


def _current_rows(slug: str, pr: int, *, run_fn: RunFunction | None) -> list[CheckRow]:
    """Return the checks on the PR's current head commit."""
    pull = pr_rest.pull_request(slug, pr, run_fn=run_fn)
    rollup = pr_rest.status_check_rollup(slug, pr_rest.head_sha(pull), run_fn=run_fn)
    return check_rows(rollup)


def create_pr(
    *,
    title: str | None = None,
    base: str | None = None,
    body: str = "",
    run_fn: RunFunction | None = None,
) -> int:
    """Open a pull request, filling the text from commits unless a ``title`` is given.

    Without ``title`` this is ``gh pr create --fill``. With one, ``body`` is
    piped to ``--body-file -``.
    """
    args = ["pr", "create"]
    if title is None:
        args.append("--fill")
    if base:
        args += ["--base", base]
    if title is not None:
        args += ["--title", title, "--body-file", "-"]

    def create_with_rest() -> int:
        slug = gh_runner.resolve_repo(run_fn=run_fn)
        branch = gh_runner.current_branch(run_fn=run_fn)
        target = base or gh_runner.default_branch(slug, run_fn=run_fn)
        pr_title, pr_body = (
            (title, body) if title is not None else _filled_text(target, branch, run_fn=run_fn)
        )
        pull = gh_runner.rest(
            f"repos/{slug}/pulls",
            method="POST",
            fields={"title": pr_title, "head": branch, "base": target, "body": pr_body},
            run_fn=run_fn,
        )
        print(pull.get("html_url") if isinstance(pull, dict) else "Created pull request")
        return 0

    return gh_runner.gh_or_rest(
        args, create_with_rest, run_fn=run_fn, stdin_text=body if title is not None else None
    )


def _filled_text(base: str, branch: str, *, run_fn: RunFunction | None = None) -> tuple[str, str]:
    """Return a PR title and body drawn from the commits on ``branch`` ahead of ``base``.

    Mirrors ``gh pr create --fill``: one commit supplies its own subject and
    body, several commits give the branch name as the title and their subjects
    as a list.
    """
    log = gh_runner.run_git(
        ["log", "--reverse", "--format=%s%x1f%b%x1e", f"origin/{base}..HEAD"], run_fn=run_fn
    )
    # run_git strips the output, which drops the separators after a final
    # subject-only commit, so a record without one has an empty body.
    commits = [
        record.strip("\n").partition("\x1f") for record in log.split("\x1e") if record.strip()
    ]
    if not commits:
        raise GhError(f"No commits on {branch} ahead of {base} to fill a pull request from.")
    if len(commits) == 1:
        subject, _sep, body = commits[0]
        return subject, body.strip()
    title = branch.replace("-", " ").replace("_", " ").strip().capitalize()
    return title, "\n".join(f"- {subject}" for subject, _sep, _body in commits)


def list_prs(*, run_fn: RunFunction | None = None) -> int:
    """List open pull requests (``gh pr list``)."""

    def list_with_rest() -> int:
        slug = gh_runner.resolve_repo(run_fn=run_fn)
        pulls = gh_runner.rest_pages(
            f"repos/{slug}/pulls", fields={"state": "open"}, limit=_LIST_LIMIT, run_fn=run_fn
        )
        if not pulls:
            print(f"No open pull requests in {slug}", file=sys.stderr)
        for pull in pulls:
            state = "DRAFT" if pull.get("draft") else "OPEN"
            branch = as_object(pull.get("head")).get("ref", "")
            print(f"{pull.get('number')}\t{pull.get('title')}\t{branch}\t{state}")
        return 0

    return gh_runner.gh_or_rest(["pr", "list"], list_with_rest, run_fn=run_fn)


def pr_checks_status(pr: int | None = None, *, run_fn: RunFunction | None = None) -> int:
    """Show a PR's CI checks once (``gh pr checks``)."""

    def status_with_rest() -> int:
        slug, number = _target(pr, run_fn=run_fn)
        rows = _current_rows(slug, number, run_fn=run_fn)
        if not rows:
            print(f"no checks reported on PR #{number}", file=sys.stderr)
            return 1
        _print_rows(rows)
        return _exit_code(rows)

    return gh_runner.gh_or_rest(_pr_command(["pr", "checks"], pr), status_with_rest, run_fn=run_fn)


def watch_pr_checks(
    pr: int | None = None,
    *,
    interval: float = CHECKS_INTERVAL_SECONDS,
    max_polls: int = CHECKS_MAX_POLLS,
    run_fn: RunFunction | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> int:
    """Watch CI checks until they finish or one fails (``gh pr checks --watch --fail-fast``).

    The REST fallback polls every ``interval`` seconds and returns as soon as a
    check fails or every check has finished. It raises ``GhError`` after
    ``max_polls`` polls so a stuck check cannot wait forever.
    """

    def watch_with_rest() -> int:
        sleeper = sleep_fn or time.sleep
        slug, number = _target(pr, run_fn=run_fn)
        for poll in range(1, max_polls + 1):
            rows = _current_rows(slug, number, run_fn=run_fn)
            code = _exit_code(rows)
            if rows and code != _PENDING_EXIT_CODE:
                _print_rows(rows)
                return code
            if poll < max_polls:
                pending = sum(row.bucket == "pending" for row in rows)
                print(f"Waiting on {pending} pending check(s) on PR #{number}", file=sys.stderr)
                sleeper(interval)
        raise GhError(f"PR #{number} checks did not finish after {max_polls} polls.")

    return gh_runner.gh_or_rest(
        [*_pr_command(["pr", "checks"], pr), "--watch", "--fail-fast"],
        watch_with_rest,
        run_fn=run_fn,
    )


def show_diff(pr: int | None = None, *, run_fn: RunFunction | None = None) -> int:
    """Print a PR's diff (``gh pr diff``)."""

    def diff_with_rest() -> int:
        slug, number = _target(pr, run_fn=run_fn)
        diff = gh_runner.rest_text(
            f"repos/{slug}/pulls/{number}", headers=[_DIFF_ACCEPT], run_fn=run_fn
        )
        sys.stdout.write(diff)
        return 0

    return gh_runner.gh_or_rest(_pr_command(["pr", "diff"], pr), diff_with_rest, run_fn=run_fn)


def checkout_pr(pr: int, *, run_fn: RunFunction | None = None) -> int:
    """Check out a PR's branch locally (``gh pr checkout``)."""

    def checkout_with_rest() -> int:
        slug = gh_runner.resolve_repo(run_fn=run_fn)
        pull = pr_rest.pull_request(slug, pr, run_fn=run_fn)
        branch = as_object(pull.get("head")).get("ref")
        if not isinstance(branch, str) or not branch:
            raise GhError(f"PR #{pr} has no head branch to check out.")
        try:
            gh_runner.run_git(
                ["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], run_fn=run_fn
            )
        except GhError:
            gh_runner.run_git(["fetch", "origin", f"pull/{pr}/head:{branch}"], run_fn=run_fn)
            gh_runner.run_git(["checkout", branch], run_fn=run_fn)
        else:
            gh_runner.run_git(["fetch", "origin", f"pull/{pr}/head"], run_fn=run_fn)
            gh_runner.run_git(["checkout", branch], run_fn=run_fn)
            gh_runner.run_git(["merge", "--ff-only", "FETCH_HEAD"], run_fn=run_fn)
        print(f"Checked out {branch} for PR #{pr}")
        return 0

    return gh_runner.gh_or_rest(["pr", "checkout", str(pr)], checkout_with_rest, run_fn=run_fn)


def view_comments(pr: int | None = None, *, run_fn: RunFunction | None = None) -> int:
    """Show a PR with its comments and review summaries (``gh pr view --comments``)."""

    def view_with_rest() -> int:
        slug, number = _target(pr, run_fn=run_fn)
        pull = pr_rest.pull_request(slug, number, run_fn=run_fn)
        print(f"{pull.get('title')} #{number}")
        print(f"state: {pr_rest.pull_state(pull)}")
        print(pull.get("html_url"))
        if pull.get("body"):
            print(f"\n{pull['body']}")
        for comment in gh_runner.rest_pages(
            f"repos/{slug}/issues/{number}/comments", run_fn=run_fn
        ):
            author = as_object(comment.get("user")).get("login", "unknown")
            print(f"\n--\ncomment by @{author}\n{comment.get('body') or ''}")
        for review in pr_rest.reviews(slug, number, run_fn=run_fn):
            if review["body"]:
                author = (review["author"] or {}).get("login", "unknown")
                print(f"\n--\nreview by @{author} [{review['state']}]\n{review['body']}")
        return 0

    return gh_runner.gh_or_rest(
        [*_pr_command(["pr", "view"], pr), "--comments"], view_with_rest, run_fn=run_fn
    )


def _delete_head_branch(slug: str, pull: dict[str, Any], *, run_fn: RunFunction | None) -> None:
    """Delete a same-repository PR branch after a merge or close, unless it is the default.

    A failed delete only warns: the merge or close it follows has already happened.
    """
    head = as_object(pull.get("head"))
    branch = head.get("ref")
    default_branch = as_object(as_object(pull.get("base")).get("repo")).get("default_branch")
    if (
        not branch
        or as_object(head.get("repo")).get("full_name") != slug
        or branch == default_branch
    ):
        return
    try:
        gh_runner.rest(
            f"repos/{slug}/git/refs/heads/{quote(branch, safe='/')}", method="DELETE", run_fn=run_fn
        )
    except GhError as exc:
        print(f"Could not delete branch {branch}: {exc}", file=sys.stderr)


def merge_pr(
    pr: int | None = None, *, admin: bool = False, run_fn: RunFunction | None = None
) -> int:
    """Squash-merge a PR and delete its branch (``gh pr merge --squash --delete-branch``).

    The REST merge endpoint has no admin switch: a token allowed to bypass
    branch protection always bypasses it. So without ``admin`` the fallback
    first requires GitHub to report the PR as mergeable under its rules, and
    refuses when that state is blocked or not yet computed.
    """

    def merge_with_rest() -> int:
        slug, number = _target(pr, run_fn=run_fn)
        pull = pr_rest.pull_request(slug, number, run_fn=run_fn)
        state = pull.get("mergeable_state")
        if not admin and state not in _MERGEABLE_STATES:
            raise GhError(
                f"PR #{number} is not ready to merge (mergeable_state: {state}). "
                "Wait for its required checks and reviews, or use make pr-merge-admin."
            )
        gh_runner.rest(
            f"repos/{slug}/pulls/{number}/merge",
            method="PUT",
            fields={"merge_method": "squash"},
            run_fn=run_fn,
        )
        print(f"Squashed and merged pull request #{number}")
        _delete_head_branch(slug, pull, run_fn=run_fn)
        return 0

    args = [*_pr_command(["pr", "merge"], pr), "--squash", "--delete-branch"]
    return gh_runner.gh_or_rest(
        [*args, "--admin"] if admin else args, merge_with_rest, run_fn=run_fn
    )


def add_reviewers(users: str, pr: int | None = None, *, run_fn: RunFunction | None = None) -> int:
    """Request reviews from a comma-separated list of ``users`` (``gh pr edit --add-reviewer``)."""

    def reviewers_with_rest() -> int:
        slug, number = _target(pr, run_fn=run_fn)
        gh_runner.rest(
            f"repos/{slug}/pulls/{number}/requested_reviewers",
            method="POST",
            fields={"reviewers": split_list(users)},
            run_fn=run_fn,
        )
        print(f"Requested review on PR #{number} from {users}")
        return 0

    return gh_runner.gh_or_rest(
        [*_pr_command(["pr", "edit"], pr), "--add-reviewer", users],
        reviewers_with_rest,
        run_fn=run_fn,
    )


def add_labels(labels: str, pr: int | None = None, *, run_fn: RunFunction | None = None) -> int:
    """Add a comma-separated list of ``labels`` to a PR (``gh pr edit --add-label``)."""

    def labels_with_rest() -> int:
        slug, number = _target(pr, run_fn=run_fn)
        gh_runner.rest(
            f"repos/{slug}/issues/{number}/labels",
            method="POST",
            fields={"labels": split_list(labels)},
            run_fn=run_fn,
        )
        print(f"Added labels to PR #{number}: {labels}")
        return 0

    return gh_runner.gh_or_rest(
        [*_pr_command(["pr", "edit"], pr), "--add-label", labels], labels_with_rest, run_fn=run_fn
    )


def close_pr(pr: int | None = None, *, run_fn: RunFunction | None = None) -> int:
    """Close a PR and delete its branch (``gh pr close --delete-branch``)."""

    def close_with_rest() -> int:
        slug, number = _target(pr, run_fn=run_fn)
        pull = pr_rest.pull_request(slug, number, run_fn=run_fn)
        gh_runner.rest(
            f"repos/{slug}/pulls/{number}",
            method="PATCH",
            fields={"state": "closed"},
            run_fn=run_fn,
        )
        print(f"Closed pull request #{number}")
        _delete_head_branch(slug, pull, run_fn=run_fn)
        return 0

    return gh_runner.gh_or_rest(
        [*_pr_command(["pr", "close"], pr), "--delete-branch"], close_with_rest, run_fn=run_fn
    )
