from __future__ import annotations

import os
from itertools import chain
from pathlib import Path


def reject_path_symlinks(path: Path, *, label: str = "Path") -> None:
    """Raise ``ValueError`` when *path* or any lexical parent is a symlink."""
    absolute_path = path.absolute()
    for candidate in (absolute_path, *absolute_path.parents):
        if candidate.is_symlink():
            raise ValueError(f"{label} must not be a symlinked path: {candidate}")


def reject_symlinked_tree(path: Path, *, label: str) -> None:
    """Raise ``ValueError`` when *path* has a symlinked parent or holds any symlink.

    A path that does not exist yet passes the tree walk, so it can name an
    output directory the caller is about to create.
    """
    reject_path_symlinks(path, label=label)
    if path.exists():
        reject_symlinks(path)


def reject_symlinks(root: Path) -> None:
    """Raise ``ValueError`` if any symlink exists under *root*.

    Walks the directory tree rooted at *root* without following symlinks.
    Both symlinked files and symlinked directories are rejected on first
    encounter.
    """
    for walk_root, dirnames, filenames in os.walk(root, followlinks=False):
        for name in chain(dirnames, filenames):
            path = Path(walk_root) / name
            if path.is_symlink():
                raise ValueError(f"Refusing to process tree containing symlink: {path}")
