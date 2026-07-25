"""The shared lint skip list must keep pace with .gitignore."""

from __future__ import annotations

from pathlib import Path

from scripts.lint import SKIP_DIRECTORIES

REPO_ROOT = Path(__file__).resolve().parents[2]


def ignored_directory_names() -> set[str]:
    """Return the .gitignore directory names a component matcher can express.

    Only trailing-slash entries name a directory outright. A leading slash just
    anchors the pattern to the repository root, so ``/build/`` still names the
    single component ``build`` and must be kept; dropping those on sight is how
    root-anchored entries used to escape this contract.

    Globs and genuinely nested patterns are left to git. The walkers compare one
    path component at a time, so ``.claude/plans/`` has no faithful spelling
    here: the bare component ``plans`` would match that name anywhere, and
    ``.claude`` would skip siblings .gitignore does not exclude.
    """
    names: set[str] = set()
    for raw in (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
        entry = raw.strip()
        if not entry or entry.startswith(("#", "!")) or not entry.endswith("/"):
            continue
        name = entry.strip("/")
        if "*" in name or "/" in name:
            continue
        names.add(name)
    return names


def test_every_ignored_directory_is_skipped() -> None:
    """A new .gitignore directory must be added to SKIP_DIRECTORIES too."""
    missing = sorted(ignored_directory_names() - SKIP_DIRECTORIES)

    assert not missing, f"add these .gitignore directories to SKIP_DIRECTORIES: {missing}"


def test_the_gitignore_scan_finds_real_entries() -> None:
    """Guard the parser itself, so the check above cannot pass vacuously."""
    names = ignored_directory_names()

    assert "node_modules" in names
    assert ".playwright" in names
