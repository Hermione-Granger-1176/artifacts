from __future__ import annotations

import os
from itertools import chain
from pathlib import Path


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
