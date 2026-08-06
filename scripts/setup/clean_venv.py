"""Safely remove the repository-local Python virtual environment."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


class CleanVenvError(RuntimeError):
    """A virtual-environment path is unsafe or cannot be removed."""


def require_real_directory(path: Path, mode: int) -> None:
    """Reject anything except a non-symlinked directory."""
    if stat.S_ISLNK(mode):
        raise CleanVenvError(f"VENV must not be a symlink: {path}")
    if not stat.S_ISDIR(mode):
        raise CleanVenvError(f"VENV must be a directory: {path}")


def validated_venv_path(repo_root: Path, value: str) -> Path:
    """Return a safe direct child of the resolved repository root."""
    try:
        resolved_root = repo_root.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise CleanVenvError(f"cannot resolve repository root {repo_root}: {error}") from error

    if not resolved_root.is_dir():
        raise CleanVenvError(f"repository root is not a directory: {resolved_root}")

    raw_path = Path(value)
    if not value or raw_path.is_absolute() or len(raw_path.parts) != 1 or value in {".", ".."}:
        raise CleanVenvError(
            f"VENV must name one directory directly below the repository root: {value!r}"
        )

    candidate = resolved_root / raw_path
    try:
        mode = candidate.lstat().st_mode
    except FileNotFoundError:
        return candidate
    except OSError as error:
        raise CleanVenvError(f"cannot inspect virtual environment {candidate}: {error}") from error

    require_real_directory(candidate, mode)
    return candidate


def remove_venv(repo_root: Path, value: str) -> bool:
    """Remove the validated virtual environment and report whether it existed."""
    path = validated_venv_path(repo_root, value)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return False
    except OSError as error:
        raise CleanVenvError(f"cannot inspect virtual environment {path}: {error}") from error

    require_real_directory(path, mode)
    try:
        shutil.rmtree(path)
    except OSError as error:
        raise CleanVenvError(f"cannot remove virtual environment {path}: {error}") from error
    return True


def parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the Make-facing command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root_value = os.environ.get("CLEAN_REPO_ROOT")
    repo_root = Path(repo_root_value) if repo_root_value else None
    venv = os.environ.get("CLEAN_VENV") or None
    parser.add_argument("--repo-root", default=repo_root, required=repo_root is None, type=Path)
    parser.add_argument("--venv", default=venv, required=venv is None)
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """Validate and remove the requested repository-local environment."""
    options = parse_args(arguments)
    try:
        remove_venv(options.repo_root, options.venv)
    except CleanVenvError as error:
        print(f"ERROR: refusing to clean: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
