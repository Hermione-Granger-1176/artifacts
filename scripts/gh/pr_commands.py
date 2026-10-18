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
        if branch == "HEAD":
            raise GhError("HEAD is detached. Check out a branch before creating a pull request.")
        target = base or gh_runner.default_branch(slug, run_fn=run_fn)
        source = gh_runner.checkout_repo(slug, run_fn=run_fn)
        _require_pushed(source, branch, run_fn=run_fn)
        head = branch if gh_runner.same_repo(source, slug) else f"{source.split('/')[0]}:{branch}"
        pr_title, pr_body = (
            (title, body)
            if title is not None
            else _filled_text(slug, target, head, branch, run_fn=run_fn)
        )
        pull = gh_runner.rest(
            f"repos/{slug}/pulls",
            method="POST",
            fields={"title": pr_title, "head": head, "base": target, "body": pr_body},
            run_fn=run_fn,
        )
        print(pull.get("html_url") if isinstance(pull, dict) else "Created pull request")
        return 0

    return gh_runner.gh_or_rest(
        args, create_with_rest, run_fn=run_fn, stdin_text=body if title is not None else None
    )


def _require_pushed(slug: str, branch: str, *, run_fn: RunFunction | None) -> None:
    """Fail unless GitHub's copy of ``branch`` points at the local ``HEAD``.

    ``gh pr create`` offers to push the branch first. The REST fallback does
    not push, so it refuses rather than open a PR that is missing commits.
    """
    local = gh_runner.run_git(["rev-parse", "HEAD"], run_fn=run_fn)
    try:
        remote = as_object(
            gh_runner.rest(f"repos/{slug}/branches/{quote(branch, safe='')}", run_fn=run_fn)
        )
    except GhError as exc:
        # Only a 404 means the branch is missing. Rate limits and permission
        # errors keep their own message.
        if "HTTP 404" not in str(exc):
            raise
        raise GhError(f"Branch {branch} is not on GitHub. Run make push first.") from exc
    if as_object(remote.get("commit")).get("sha") != local:
        raise GhError(f"GitHub's {branch} does not match your local HEAD. Run make push first.")


def _filled_text(
    slug: str, base: str, head: str, branch: str, *, run_fn: RunFunction | None = None
) -> tuple[str, str]:
    """Return a PR title and body drawn from the commits ``head`` adds to ``base``.

    Mirrors ``gh pr create --fill``: one commit supplies its own subject and
    body, several commits give the branch name as the title and their subjects
    as a list. GitHub's compare API reads the commits, so the result never
    depends on a local tracking ref that is missing, stale, or from a fork.
    """
    entries = gh_runner.rest_pages(
        f"repos/{slug}/compare/{quote(base, safe='')}...{quote(head, safe=':')}",
        items_key="commits",
        run_fn=run_fn,
    )
    commits = [
        str(as_object(entry.get("commit")).get("message") or "").partition("\n")
        for entry in entries
    ]
    if not commits:
        raise GhError(f"No commits on {branch} ahead of {base} to fill a pull request from.")
    if len(commits) == 1:
        subject, _sep, body = commits[0]
        return subject.strip(), body.strip()
    title = branch.replace("-", " ").replace("_", " ").strip().capitalize()
    return title, "\n".join(f"- {subject.strip()}" for subject, _sep, _body in commits)


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
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
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
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
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
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
        diff = gh_runner.rest_text(
            f"repos/{slug}/pulls/{number}", headers=[_DIFF_ACCEPT], run_fn=run_fn
        )
        sys.stdout.write(diff)
        return 0

    return gh_runner.gh_or_rest(_pr_command(["pr", "diff"], pr), diff_with_rest, run_fn=run_fn)


def _fetch_pr_into_branch(pr: int, branch: str, *, run_fn: RunFunction | None) -> None:
    """Fetch a PR's head into ``branch`` and check it out, fast-forwarding an existing one."""
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


def _pr_upstream(
    pull: dict[str, Any],
    pr: int,
    head_ref: str,
    head_info: dict[str, Any],
    *,
    is_fork: bool,
) -> tuple[str, str]:
    """Return the remote and merge ref a checked-out PR branch should track.

    A fork branch tracks the fork itself when maintainers may push to it, and
    the read-only pull ref otherwise.
    """
    if not is_fork:
        return "origin", f"refs/heads/{head_ref}"
    clone_url = head_info.get("clone_url")
    if pull.get("maintainer_can_modify") and isinstance(clone_url, str) and clone_url:
        return clone_url, f"refs/heads/{head_ref}"
    return "origin", f"refs/pull/{pr}/head"


def checkout_pr(pr: int, *, run_fn: RunFunction | None = None) -> int:
    """Check out a PR's branch locally (``gh pr checkout``)."""

    def checkout_with_rest() -> int:
        slug = gh_runner.resolve_repo(run_fn=run_fn)
        gh_runner.require_checkout_repo(slug, f"check out PR #{pr}", run_fn=run_fn)
        pull = pr_rest.pull_request(slug, pr, run_fn=run_fn)
        head = as_object(pull.get("head"))
        branch = head.get("ref")
        if not isinstance(branch, str) or not branch:
            raise GhError(f"PR #{pr} has no head branch to check out.")
        head_ref = branch
        head_info = as_object(head.get("repo"))
        head_repo = str(head_info.get("full_name") or "")
        is_fork = not gh_runner.same_repo(head_repo, slug)
        if is_fork:
            # A fork's branch can share a local name such as main, so it gets
            # the fork owner as a prefix instead of updating that branch.
            branch = f"{head_repo.split('/')[0] or 'fork'}/{branch}"
        _fetch_pr_into_branch(pr, branch, run_fn=run_fn)
        gh_runner.run_git(
            ["config", f"branch.{branch}.{gh_runner.PR_NUMBER_CONFIG}", str(pr)], run_fn=run_fn
        )
        gh_runner.run_git(
            ["config", f"branch.{branch}.{gh_runner.PR_REPO_CONFIG}", slug], run_fn=run_fn
        )
        # Track the PR's branch like gh pr checkout, so git pull works afterwards.
        remote, merge = _pr_upstream(pull, pr, head_ref, head_info, is_fork=is_fork)
        gh_runner.run_git(["config", f"branch.{branch}.remote", remote], run_fn=run_fn)
        gh_runner.run_git(["config", f"branch.{branch}.merge", merge], run_fn=run_fn)
        print(f"Checked out {branch} for PR #{pr}")
        return 0

    return gh_runner.gh_or_rest(["pr", "checkout", str(pr)], checkout_with_rest, run_fn=run_fn)


def view_comments(pr: int | None = None, *, run_fn: RunFunction | None = None) -> int:
    """Show a PR with its comments and review summaries (``gh pr view --comments``)."""

    def view_with_rest() -> int:
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
        pull = pr_rest.pull_request(slug, number, run_fn=run_fn)
        print(f"{pull.get('title')} #{number}")
        print(f"state: {pr_rest.pull_state(pull)}")
        print(pull.get("html_url"))
        if pull.get("body"):
            print(f"\n{pull['body']}")
        gh_runner.print_rest_comments(
            gh_runner.rest_pages(f"repos/{slug}/issues/{number}/comments", run_fn=run_fn)
        )
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
        or not gh_runner.same_repo(str(as_object(head.get("repo")).get("full_name") or ""), slug)
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
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
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
            # GitHub rejects the merge if the head moved after the state check.
            fields={"merge_method": "squash", "sha": pr_rest.head_sha(pull)},
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
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
        # gh names a team as org/slug. REST takes the team slug separately.
        names = [
            pr_rest.COPILOT_REST_REVIEWER if name == pr_rest.COPILOT_REVIEWER else name
            for name in split_list(users)
        ]
        gh_runner.rest(
            f"repos/{slug}/pulls/{number}/requested_reviewers",
            method="POST",
            fields={
                "reviewers": [name for name in names if "/" not in name],
                "team_reviewers": [name.split("/", 1)[1] for name in names if "/" in name],
            },
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
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
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
        slug, number = gh_runner.resolve_repo_and_pr(pr, run_fn=run_fn)
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
