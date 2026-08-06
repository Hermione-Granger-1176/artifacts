"""Shared constants and traversal helpers for lint scripts."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

# Directories the lint walkers never descend into. Every ignored directory in
# .gitignore that can be named by a single path component belongs here: an
# ignored tree holds generated or vendored content that is not ours to lint, and
# walking one is slow and produces false failures (the extracted Debian packages
# under .playwright/ are hundreds of megabytes).
#
# Entries are matched one path component at a time (`part in SKIP_DIRECTORIES`),
# so a nested pattern such as .gitignore's `.claude/plans/` cannot be represented
# here. Listing the bare component `plans` would skip any directory of that name
# anywhere in the tree, and listing `.claude` would skip more than .gitignore
# excludes, since only two of its subdirectories are ignored. Those stay walked.
# tests/lint/test_skip_directories.py fails if .gitignore grows a single-component
# directory that is missing here, so this list cannot silently fall behind.
SKIP_DIRECTORIES = frozenset(
    {
        ".artifacts",
        ".git",
        ".idea",
        ".mypy_cache",
        ".playwright",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vscode",
        "__pycache__",
        "_site",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "test-results",
        "vendor",
    }
)


def contains_symlink(path: Path, root: Path) -> bool:
    """Return whether any repository-relative path component is a symbolic link."""
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def iter_lint_paths(root: Path) -> Iterator[Path]:
    """Yield sorted real files without descending into ignored or symlinked trees."""
    for current_root, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_path = Path(current_root)
        directory_names[:] = sorted(
            name
            for name in directory_names
            if name not in SKIP_DIRECTORIES and not (current_path / name).is_symlink()
        )
        for file_name in sorted(file_names):
            path = current_path / file_name
            if path.is_file() and not path.is_symlink():
                yield path
