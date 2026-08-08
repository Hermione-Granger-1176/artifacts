from __future__ import annotations

import subprocess
from collections.abc import Sequence

import pytest

from scripts import REPO_ROOT
from scripts.lib import prune_branches


def make_runner(
    responses: dict[tuple[str, ...], tuple[int, str]],
    *,
    calls: list[tuple[str, ...]] | None = None,
) -> prune_branches.GitRunner:
    """Return a runner answering from a table and recording every invocation."""

    def runner(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        key = tuple(command)
        if calls is not None:
            calls.append(key)
        returncode, stdout = responses.get(key, (0, ""))
        return subprocess.CompletedProcess(list(command), returncode, stdout, "")

    return runner


def test_makefile_branch_prune_target_uses_the_helper() -> None:
    """The Make target forwards its inputs and holds no inline shell control flow."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "branch-prune: export PRUNE_MAIN_BRANCH := $(MAIN_BRANCH)" in makefile
    assert "branch-prune: export PRUNE_PAGES_BRANCH := $(PAGES_BRANCH)" in makefile
    assert "branch-prune: export PRUNE_CONFIRM := $(confirm)" in makefile
    assert "$(PYTHON) -m scripts.lib.prune_branches" in makefile
    assert "--merged" not in makefile


def test_branch_prune_is_not_in_the_control_flow_allowlist() -> None:
    """The ratchet stays closed once the recipe no longer holds shell logic."""
    from scripts.lint.make_targets import CONTROL_FLOW_ALLOWLIST

    assert "branch-prune" not in CONTROL_FLOW_ALLOWLIST


def test_resolve_base_prefers_the_remote_tracking_branch() -> None:
    """A present origin ref wins over the local branch name."""
    runner = make_runner({("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): (0, "")})
    assert prune_branches.resolve_base("main", runner=runner) == "origin/main"


def test_resolve_base_falls_back_to_the_local_branch() -> None:
    """A missing origin ref leaves the local branch as the base."""
    runner = make_runner({("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): (1, "")})
    assert prune_branches.resolve_base("main", runner=runner) == "main"


def test_local_branches_drops_blank_lines() -> None:
    """Ref listing tolerates a trailing newline."""
    runner = make_runner(
        {("for-each-ref", "--format=%(refname:short)", "refs/heads/"): (0, "main\nfeature\n\n")}
    )
    assert prune_branches.local_branches(runner=runner) == ["main", "feature"]


def test_current_branch_is_empty_when_detached() -> None:
    """A detached HEAD reports no current branch."""
    runner = make_runner({("branch", "--show-current"): (0, "\n")})
    assert prune_branches.current_branch(runner=runner) == ""


def test_base_tree_returns_the_tree_id() -> None:
    """The base tree id is read from rev-parse."""
    runner = make_runner({("rev-parse", "main^{tree}"): (0, "abc123\n")})
    assert prune_branches.base_tree("main", runner=runner) == "abc123"


def test_base_tree_raises_when_the_base_is_unresolvable() -> None:
    """A missing base branch fails loudly rather than pruning against nothing."""
    runner = make_runner({("rev-parse", "nope^{tree}"): (1, "")})
    with pytest.raises(RuntimeError, match="cannot resolve base branch nope"):
        prune_branches.base_tree("nope", runner=runner)


def test_is_contained_true_when_the_merge_changes_nothing() -> None:
    """A merge producing the base tree means the branch adds nothing."""
    runner = make_runner({("merge-tree", "--write-tree", "main", "done"): (0, "tree1\n")})
    assert prune_branches.is_contained("main", "done", "tree1", runner=runner) is True


def test_is_contained_false_when_the_merge_adds_content() -> None:
    """A differing merged tree means the branch still holds work."""
    runner = make_runner({("merge-tree", "--write-tree", "main", "wip"): (0, "tree2\n")})
    assert prune_branches.is_contained("main", "wip", "tree1", runner=runner) is False


def test_is_contained_false_when_the_merge_conflicts() -> None:
    """A conflicting merge is treated as unique content, never as prunable."""
    runner = make_runner({("merge-tree", "--write-tree", "main", "clash"): (1, "tree1\n")})
    assert prune_branches.is_contained("main", "clash", "tree1", runner=runner) is False


def test_classify_splits_contained_from_unique() -> None:
    """Branches are partitioned by whether the merge would change the base."""
    runner = make_runner(
        {
            ("merge-tree", "--write-tree", "main", "done"): (0, "tree1"),
            ("merge-tree", "--write-tree", "main", "wip"): (0, "tree2"),
        }
    )
    assert prune_branches.classify("main", ["done", "wip"], "tree1", runner=runner) == (
        ["done"],
        ["wip"],
    )


def test_candidate_branches_excludes_protected_and_current() -> None:
    """Main, the pages branch, and the checkout are never candidates."""
    runner = make_runner(
        {
            ("branch", "--show-current"): (0, "feature\n"),
            ("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): (0, ""),
            ("for-each-ref", "--format=%(refname:short)", "refs/heads/"): (
                0,
                "main\ngh-pages\nfeature\nold\n",
            ),
        }
    )
    base, branches = prune_branches.candidate_branches(
        {"PRUNE_MAIN_BRANCH": "main", "PRUNE_PAGES_BRANCH": "gh-pages"}, runner=runner
    )
    assert base == "origin/main"
    assert branches == ["old"]


def test_candidate_branches_defaults_when_environment_is_empty() -> None:
    """An unset main branch falls back to main and an unset pages branch is ignored."""
    runner = make_runner(
        {
            ("branch", "--show-current"): (0, "main\n"),
            ("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): (1, ""),
            ("for-each-ref", "--format=%(refname:short)", "refs/heads/"): (0, "main\nold\n"),
        }
    )
    base, branches = prune_branches.candidate_branches({}, runner=runner)
    assert base == "main"
    assert branches == ["old"]


def test_supports_merge_tree_reports_old_git() -> None:
    """A git without merge-tree --write-tree is detected up front."""
    runner = make_runner({("merge-tree", "--write-tree", "main", "main"): (129, "")})
    assert prune_branches.supports_merge_tree("main", runner=runner) is False


def base_environment() -> dict[str, str]:
    """Return the Makefile-supplied inputs for a dry run."""
    return {"PRUNE_MAIN_BRANCH": "main", "PRUNE_PAGES_BRANCH": "gh-pages"}


def main_runner(
    *, merge_tree_ok: bool = True, calls: list[tuple[str, ...]] | None = None
) -> prune_branches.GitRunner:
    """Return a runner describing one contained branch and one unique branch."""
    return make_runner(
        {
            ("branch", "--show-current"): (0, "main\n"),
            ("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): (0, ""),
            ("for-each-ref", "--format=%(refname:short)", "refs/heads/"): (
                0,
                "main\ngh-pages\ndone\nwip\n",
            ),
            ("merge-tree", "--write-tree", "origin/main", "origin/main"): (
                0 if merge_tree_ok else 129,
                "tree1",
            ),
            ("rev-parse", "origin/main^{tree}"): (0, "tree1"),
            ("merge-tree", "--write-tree", "origin/main", "done"): (0, "tree1"),
            ("merge-tree", "--write-tree", "origin/main", "wip"): (0, "tree2"),
            ("branch", "-D", "done"): (0, "Deleted branch done (was abc1234).\n"),
        },
        calls=calls,
    )


def test_main_dry_run_reports_both_groups_and_deletes_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without confirm the helper only reports, and unique branches are surfaced."""
    calls: list[tuple[str, ...]] = []
    assert prune_branches.main(environ=base_environment(), runner=main_runner(calls=calls)) == 0

    out = capsys.readouterr().out
    assert "Branches holding content not in origin/main" in out
    assert "  wip" in out
    assert "Branches fully contained in origin/main" in out
    assert "  done" in out
    assert "Dry run only. Re-run with confirm=1 to delete them." in out
    assert ("branch", "-D", "done") not in calls


def test_main_deletes_only_contained_branches_on_confirm(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With confirm the contained branch is force-deleted and the unique one is kept."""
    calls: list[tuple[str, ...]] = []
    environ = base_environment() | {"PRUNE_CONFIRM": "1"}
    assert prune_branches.main(environ=environ, runner=main_runner(calls=calls)) == 0

    out = capsys.readouterr().out
    assert "Deleted branch done (was abc1234)." in out
    assert ("branch", "-D", "done") in calls
    assert ("branch", "-D", "wip") not in calls


def test_main_prints_a_fallback_line_when_git_is_quiet(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A silent delete still reports which branch went."""
    responses = {
        ("branch", "--show-current"): (0, "main\n"),
        ("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): (0, ""),
        ("for-each-ref", "--format=%(refname:short)", "refs/heads/"): (0, "main\ndone\n"),
        ("merge-tree", "--write-tree", "origin/main", "origin/main"): (0, "tree1"),
        ("rev-parse", "origin/main^{tree}"): (0, "tree1"),
        ("merge-tree", "--write-tree", "origin/main", "done"): (0, "tree1"),
    }
    environ = base_environment() | {"PRUNE_CONFIRM": "1"}
    assert prune_branches.main(environ=environ, runner=make_runner(responses)) == 0
    assert "Deleted branch done" in capsys.readouterr().out


def test_main_reports_when_nothing_is_contained(capsys: pytest.CaptureFixture[str]) -> None:
    """A repository with only unique branches says so and exits cleanly."""
    responses = {
        ("branch", "--show-current"): (0, "main\n"),
        ("show-ref", "--verify", "--quiet", "refs/remotes/origin/main"): (0, ""),
        ("for-each-ref", "--format=%(refname:short)", "refs/heads/"): (0, "main\n"),
        ("merge-tree", "--write-tree", "origin/main", "origin/main"): (0, "tree1"),
        ("rev-parse", "origin/main^{tree}"): (0, "tree1"),
    }
    assert prune_branches.main(environ=base_environment(), runner=make_runner(responses)) == 0
    assert "No local branches are fully contained in origin/main." in capsys.readouterr().out


def test_main_fails_on_git_without_merge_tree(capsys: pytest.CaptureFixture[str]) -> None:
    """An unsupported git aborts with a clear hint instead of pruning blindly."""
    runner = main_runner(merge_tree_ok=False)
    assert prune_branches.main(environ=base_environment(), runner=runner) == 1
    assert prune_branches.MERGE_TREE_HINT in capsys.readouterr().err


def test_main_reads_the_process_environment_by_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Omitting environ falls back to os.environ so the Make target needs no arguments."""
    monkeypatch.setenv("PRUNE_MAIN_BRANCH", "main")
    monkeypatch.setenv("PRUNE_PAGES_BRANCH", "gh-pages")
    monkeypatch.delenv("PRUNE_CONFIRM", raising=False)
    assert prune_branches.main(runner=main_runner()) == 0
    assert "Dry run only." in capsys.readouterr().out


def test_run_git_executes_a_real_command() -> None:
    """The default runner shells out to git without a shell."""
    result = prune_branches.run_git(["--version"])
    assert result.returncode == 0
    assert result.stdout.startswith("git version")
