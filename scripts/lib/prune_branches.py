#!/usr/bin/env python3
"""Prune local branches whose content already exists in the base branch.

``git for-each-ref --merged`` is a pure ancestry test, so it cannot find
branches that landed through a squash merge. A squash merge replays the branch
as one new commit on the base, so the original branch tip is not an ancestor of
the base and ``--merged`` never lists it.

This helper asks a different question: would merging the branch into the base
change the base at all? ``git merge-tree --write-tree``
answers it entirely in the object store, without touching the working tree or
the current checkout. An identical tree means the branch contributes nothing
and is safe to drop. A different tree, or a merge conflict, means the branch
may hold work that exists nowhere else, so it is reported and kept rather than
deleted.

Deletion uses ``git branch -D``. ``-d`` applies the same ancestry test and
would refuse every squash-merged branch, so the force flag is required. The tree
comparison is what makes forcing safe.

The Makefile forwards three inputs through the environment:

- ``PRUNE_MAIN_BRANCH``: the base branch name, never deleted.
- ``PRUNE_PAGES_BRANCH``: a second protected branch name, may be empty.
- ``PRUNE_CONFIRM``: ``1`` deletes; anything else reports and exits.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence

# A runner takes the git command vector and returns the completed process.
# Injectable so tests never touch a real repository.
GitRunner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]

MERGE_TREE_HINT = "branch-prune needs git 2.38 or newer for merge-tree --write-tree."


def run_git(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run one git command without a shell and capture its output."""
    return subprocess.run(["git", *command], capture_output=True, text=True, check=False)


def resolve_base(main_branch: str, *, runner: GitRunner = run_git) -> str:
    """Return the remote-tracking base when it exists, else the local branch."""
    remote = f"origin/{main_branch}"
    result = runner(["show-ref", "--verify", "--quiet", f"refs/remotes/{remote}"])
    return remote if result.returncode == 0 else main_branch


def local_branches(*, runner: GitRunner = run_git) -> list[str]:
    """Return every local branch name in ref order."""
    result = runner(["for-each-ref", "--format=%(refname:short)", "refs/heads/"])
    return [line for line in result.stdout.splitlines() if line]


def current_branch(*, runner: GitRunner = run_git) -> str:
    """Return the checked-out branch name, or an empty string when detached."""
    return runner(["branch", "--show-current"]).stdout.strip()


def base_tree(base: str, *, runner: GitRunner = run_git) -> str:
    """Return the tree object id for the base branch tip."""
    result = runner(["rev-parse", f"{base}^{{tree}}"])
    if result.returncode != 0:
        raise RuntimeError(f"cannot resolve base branch {base}")
    return result.stdout.strip()


def is_contained(base: str, branch: str, tree: str, *, runner: GitRunner = run_git) -> bool:
    """Return whether merging the branch into the base would change nothing."""
    result = merge_tree_result(base, branch, runner=runner)
    if result.returncode != 0:
        return False
    return result.stdout.strip() == tree


def classify(
    base: str,
    branches: Sequence[str],
    tree: str,
    *,
    runner: GitRunner = run_git,
) -> tuple[list[str], list[str]]:
    """Split candidate branches into fully contained and possibly unique."""
    contained: list[str] = []
    unique: list[str] = []
    for branch in branches:
        if is_contained(base, branch, tree, runner=runner):
            contained.append(branch)
        else:
            unique.append(branch)
    return contained, unique


def candidate_branches(
    environ: Mapping[str, str], *, runner: GitRunner = run_git
) -> tuple[str, list[str]]:
    """Return the base branch and every local branch eligible for a decision."""
    main_branch = environ.get("PRUNE_MAIN_BRANCH") or "main"
    protected = {
        main_branch,
        environ.get("PRUNE_PAGES_BRANCH") or "",
        current_branch(runner=runner),
    }
    base = resolve_base(main_branch, runner=runner)
    return base, [branch for branch in local_branches(runner=runner) if branch not in protected]


def merge_tree_result(
    base: str, branch: str, *, runner: GitRunner = run_git
) -> subprocess.CompletedProcess[str]:
    """Run merge-tree and preserve its output for callers that report errors."""
    return runner(["merge-tree", "--write-tree", base, branch])


def merge_tree_error_detail(result: subprocess.CompletedProcess[str]) -> str:
    """Return diagnostic output without mistaking a tree id for an error."""
    stderr = result.stderr.strip()
    if stderr:
        return stderr

    stdout = result.stdout.strip()
    error_prefixes = ("error:", "fatal:", "usage:")
    if any(line.lower().startswith(error_prefixes) for line in stdout.splitlines()):
        return stdout
    return ""


def main(
    arguments: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    runner: GitRunner = run_git,
) -> int:
    """Report contained and unique branches, deleting the contained ones on confirm."""
    del arguments
    env = os.environ if environ is None else environ
    base, branches = candidate_branches(env, runner=runner)

    # Resolve the base before probing for merge-tree support. Both fail the same
    # way on an old git and on a missing base, so checking capability first would
    # blame the git version for what is really an unresolvable ref.
    try:
        tree = base_tree(base, runner=runner)
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1

    merge_tree_check = merge_tree_result(base, base, runner=runner)
    if merge_tree_check.returncode != 0:
        detail = merge_tree_error_detail(merge_tree_check)
        if detail:
            print(f"ERROR: git merge-tree --write-tree failed: {detail}", file=sys.stderr)
        else:
            print(MERGE_TREE_HINT, file=sys.stderr)
        return 1

    contained, unique = classify(base, branches, tree, runner=runner)

    if unique:
        _print_branches(
            f"Branches holding content not in {base} (kept, review before deleting):", unique
        )

    if not contained:
        print(f"No local branches are fully contained in {base}.")
        return 0

    _print_branches(f"Branches fully contained in {base} (safe to prune):", contained)

    if env.get("PRUNE_CONFIRM") != "1":
        print("Dry run only. Re-run with confirm=1 to delete them.")
        return 0

    return _delete_branches(contained, runner=runner)


def _print_branches(header: str, branches: Sequence[str]) -> None:
    """Print a heading, then one indented branch name per line."""
    print(header)
    for branch in branches:
        print(f"  {branch}")


def _delete_branches(branches: Sequence[str], *, runner: GitRunner) -> int:
    """Delete each branch, stopping at the first refusal, and return the exit code.

    Deletion is the destructive step, so a refusal stops the run rather than
    continuing down the list. git explains itself on stderr, which the caller
    needs to see to know whether anything was actually removed.
    """
    for branch in branches:
        result = runner(["branch", "-D", branch])
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip() or "git reported no detail"
            print(f"ERROR: cannot delete {branch}: {detail}", file=sys.stderr)
            return 1
        print(result.stdout.strip() or f"Deleted branch {branch}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
