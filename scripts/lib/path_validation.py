from __future__ import annotations

import os
from itertools import chain
from pathlib import Path


def reject_symlinks(root: Path) -> None:
    """Raise ``ValueError`` if any symlink exists under *root*.

    Walks the directory tree rooted at *root* without following symlinks.
    Both symlinked files and symlinked directories are rejected on first
    encounter.  Symlinked directories are pruned from further traversal so
    the walk never follows them.

    Args:
        root: Directory tree to scan.

    Raises:
        ValueError: If a symlink is found anywhere in the tree.
    """
    for walk_root, dirnames, filenames in os.walk(root, followlinks=False):
        for name in chain(dirnames, filenames):
            path = Path(walk_root) / name
            if path.is_symlink():
                raise ValueError(
                    f"Refusing to process tree containing symlink: {path}"
                )

        dirnames[:] = [
            name for name in dirnames if not (Path(walk_root) / name).is_symlink()
        ]
