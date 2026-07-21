#!/usr/bin/env python3
"""Stage files for ``make stage`` without letting a shell parse any path.

The old recipe ran ``git add -- $(files)`` with the value interpolated straight
into the shell, so a path was subject to word splitting, globbing, and shell
syntax; a value containing ``;`` could start another command instead of naming
a file. This helper reads paths from the environment and hands them to
``git add`` as separate argv entries with ``shell=False``, so shell
metacharacters in a filename stay inert.

The Makefile forwards two optional inputs:

- ``STAGE_FILE``: exactly one path, kept intact even when it contains spaces.
- ``STAGE_FILES``: a whitespace-separated list for the common multi-file case.

At least one must be non-empty; otherwise a usage message is printed and the
command exits non-zero.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence

# A runner takes the git command vector and returns the completed process.
# Injectable so tests never touch a real repository.
GitRunner = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]

USAGE = 'Usage: make stage files="a.txt b.txt" OR make stage file="one file with spaces.txt"'


def collect_paths(environ: Mapping[str, str]) -> list[str]:
    """Return the paths to stage from ``STAGE_FILES`` (split) and ``STAGE_FILE`` (exact).

    ``STAGE_FILES`` is split on whitespace for the multi-file case, so a single
    path containing spaces cannot be expressed there; ``STAGE_FILE`` carries such
    a path verbatim. A blank or whitespace-only ``STAGE_FILE`` counts as unset.
    """
    paths = environ.get("STAGE_FILES", "").split()
    single = environ.get("STAGE_FILE", "")
    if single.strip():
        paths.append(single)
    return paths


def _default_run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run ``git`` without a shell, never raising on a non-zero exit."""
    return subprocess.run(list(cmd), check=False, shell=False, text=True)


def stage_paths(paths: Sequence[str], *, run_fn: GitRunner | None = None) -> int:
    """Stage ``paths`` via ``git add -- <paths>`` and return git's exit code.

    The ``--`` stops option parsing so a leading-dash path is treated as a file,
    and passing each path as its own argv entry keeps spaces and shell
    metacharacters literal.
    """
    runner = run_fn or _default_run
    return runner(["git", "add", "--", *paths]).returncode


def main(*, environ: Mapping[str, str] | None = None, run_fn: GitRunner | None = None) -> int:
    """Collect paths from the environment and stage them, returning an exit code."""
    paths = collect_paths(os.environ if environ is None else environ)
    if not paths:
        print(USAGE, file=sys.stderr)
        return 1
    return stage_paths(paths, run_fn=run_fn)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
