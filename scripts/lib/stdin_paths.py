#!/usr/bin/env python3
"""Run commands with paths read from stdin, one per line.

Every Make target that takes files reads them this way, so a path can hold
spaces, quotes, or shell metacharacters without any quoting rules::

    make stage <<'EOF'
    My Notes.md
    scripts/lib/stdin_paths.py
    EOF

Usage: ``python -m scripts.lib.stdin_paths [--require] [--name NAME] [DEFAULT ...]
-- COMMAND ... [--then COMMAND ...]``

Each non-blank stdin line is one path, kept exactly, apart from a trailing
carriage return. A terminal or a closed stdin counts as no paths, so an optional list
never waits for typing. With no paths, each command runs with the ``DEFAULT``
arguments instead, or, with ``--require``, the usage message is printed and the
exit code is 2. A relative path that starts with ``-`` gets a ``./`` prefix so
a command cannot read it as an option.

``--then`` separates commands that each receive the same paths, such as a lint
fix followed by a format. They run in order, without a shell, and the first
nonzero exit code stops the chain and is returned.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TextIO

# A runner takes the command vector and returns its exit code.
# Injectable so tests never start a real process.
CommandRunner = Callable[[Sequence[str]], int]

THEN = "--then"
USAGE = (
    "Usage: python -m scripts.lib.stdin_paths [--require] [--name NAME] [DEFAULT ...] "
    "-- COMMAND ... [--then COMMAND ...]"
)


@dataclass(frozen=True)
class Invocation:
    """A parsed command line: what to run, and what to do without paths."""

    commands: list[list[str]]
    defaults: list[str]
    require: bool
    name: str


def split_commands(argv: Sequence[str]) -> list[list[str]]:
    """Split the arguments after ``--`` into commands at each ``--then``.

    Raises:
        ValueError: If any command is empty.
    """
    commands: list[list[str]] = [[]]
    for argument in argv:
        if argument == THEN:
            commands.append([])
        else:
            commands[-1].append(argument)
    if any(not command for command in commands):
        raise ValueError("missing command after -- or --then")
    return commands


def parse_invocation(argv: Sequence[str]) -> Invocation:
    """Split options and defaults from the commands after ``--``.

    Raises:
        ValueError: If ``--`` or a command is missing, or ``--name`` has no value.
    """
    if "--" not in argv:
        raise ValueError("missing -- before the command")
    split = list(argv).index("--")
    before = list(argv[:split])
    commands = split_commands(argv[split + 1 :])
    require = False
    name = "this target"
    defaults: list[str] = []
    index = 0
    while index < len(before):
        argument = before[index]
        if argument == "--require":
            require = True
        elif argument == "--name":
            if index + 1 >= len(before):
                raise ValueError("--name needs a value")
            index += 1
            name = before[index]
        else:
            defaults.append(argument)
        index += 1
    return Invocation(commands=commands, defaults=defaults, require=require, name=name)


def read_paths(stream: TextIO | None) -> list[str]:
    """Return one path per non-blank line, or none when stdin is a terminal or closed."""
    if stream is None or stream.isatty():
        return []
    paths = []
    for line in stream.read().split("\n"):
        path = line.removesuffix("\r")
        if path.strip():
            paths.append(path)
    return paths


def as_argument(path: str) -> str:
    """Keep a relative path that starts with ``-`` from reading as an option."""
    return f"./{path}" if path.startswith("-") else path


def _default_run(command: Sequence[str]) -> int:
    """Run ``command`` without a shell and return its exit code."""
    return subprocess.run(list(command), check=False, shell=False).returncode


def main(
    argv: Sequence[str] | None = None,
    *,
    stdin: TextIO | None = None,
    run_fn: CommandRunner | None = None,
) -> int:
    """Run each command on the stdin paths, or on its defaults, and return the exit code."""
    try:
        invocation = parse_invocation(sys.argv[1:] if argv is None else argv)
    except ValueError as error:
        print(f"stdin_paths: {error}\n{USAGE}", file=sys.stderr)
        return 2
    paths = read_paths(sys.stdin if stdin is None else stdin)
    if not paths and invocation.require:
        print(
            f"{invocation.name} needs paths on stdin, one per line:\n\n"
            f"    {invocation.name} <<'EOF'\n    path/one.txt\n    path with spaces.md\n    EOF",
            file=sys.stderr,
        )
        return 2
    arguments = [as_argument(path) for path in paths] if paths else invocation.defaults
    runner = run_fn or _default_run
    for command in invocation.commands:
        code = runner([*command, *arguments])
        if code != 0:
            return code
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
