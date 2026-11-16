#!/usr/bin/env python3
"""Show the changes Prettier would make to files, without changing them.

``make format-prettier-diff`` feeds this the paths from stdin through
``scripts.lib.stdin_paths``. Each path is formatted with the repository's
Prettier configuration and compared with the file on disk as a unified diff.

The exit code is 0 whether or not a file differs. A Markdown path is refused,
since ``make align-tables-check`` owns Markdown formatting. A Prettier failure,
such as a syntax error or an unreadable file, stops the run and returns
Prettier's exit code.

Both sides are decoded without newline translation, so CRLF-only differences
appear in the diff.
"""

from __future__ import annotations

import argparse
import difflib
import shlex
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

PRETTIER_ARGS = (
    "prettier",
    "--config",
    "config/prettierrc.json",
    "--ignore-path",
    "config/prettierignore",
)
MARKDOWN_SUFFIXES = (".md", ".markdown")

# A formatter takes the command vector and returns the completed process.
# Injectable so tests can replace the Prettier call.
Formatter = Callable[[Sequence[str]], "subprocess.CompletedProcess[str]"]


def _default_format(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    """Run Prettier without a shell, capturing its output with line endings intact."""
    result = subprocess.run(list(command), check=False, shell=False, capture_output=True)
    return subprocess.CompletedProcess(
        result.args,
        result.returncode,
        result.stdout.decode("utf-8"),
        result.stderr.decode("utf-8", errors="replace"),
    )


def diff_for(path: str, formatted: str) -> str:
    """Return a unified diff from the file on disk to ``formatted``, or an empty string."""
    original = Path(path).read_bytes().decode("utf-8")
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            formatted.splitlines(keepends=True),
            fromfile=path,
            tofile=f"{path} (formatted)",
        )
    )


def main(argv: Sequence[str] | None = None, *, format_fn: Formatter | None = None) -> int:
    """Print the Prettier diff of every path and return 0, or a failure code."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--runner",
        default="npm exec --no --",
        help="Command that runs a local package binary (default: npm exec --no --)",
    )
    parser.add_argument("paths", nargs="+", help="Files to compare with their formatted form")
    args = parser.parse_args(argv)
    markdown = [path for path in args.paths if path.lower().endswith(MARKDOWN_SUFFIXES)]
    if markdown:
        print(
            "Markdown formatting is owned by make align-tables-check: " + ", ".join(markdown),
            file=sys.stderr,
        )
        return 2
    formatter = format_fn or _default_format
    for path in args.paths:
        result = formatter([*shlex.split(args.runner), *PRETTIER_ARGS, "--", path])
        if result.returncode != 0:
            sys.stderr.write(result.stderr)
            return result.returncode
        sys.stdout.write(diff_for(path, result.stdout))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
