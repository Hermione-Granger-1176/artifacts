"""Tests for the stdin path runner behind every path-taking Make target."""

from __future__ import annotations

import io
import subprocess
from collections.abc import Sequence
from typing import TYPE_CHECKING

import pytest

from scripts.lib import stdin_paths

if TYPE_CHECKING:
    from pathlib import Path


class TerminalInput(io.StringIO):
    """A stdin that reports itself as an interactive terminal."""

    def isatty(self) -> bool:
        """Report a terminal."""
        return True


def recorder(codes: Sequence[int] = ()) -> tuple[list[list[str]], stdin_paths.CommandRunner]:
    """Return the commands a runner receives, and the runner.

    The runner returns ``codes`` in order, then 0.
    """
    commands: list[list[str]] = []
    pending = list(codes)

    def run(command: Sequence[str]) -> int:
        commands.append(list(command))
        return pending.pop(0) if pending else 0

    return commands, run


def test_runs_the_command_with_one_argument_per_stdin_line() -> None:
    """Spaces and quotes inside a line stay part of one path."""
    commands, run = recorder()

    code = stdin_paths.main(
        ["--", "git", "add", "--"],
        stdin=io.StringIO('My Notes.md\napps/app.js\ndocs/a "quoted" name.md\n'),
        run_fn=run,
    )

    assert code == 0
    assert commands == [
        ["git", "add", "--", "My Notes.md", "apps/app.js", 'docs/a "quoted" name.md']
    ]


def test_skips_blank_lines_and_strips_only_line_endings() -> None:
    """Blank lines are ignored, and a path keeps its own leading or trailing spaces."""
    commands, run = recorder()

    stdin_paths.main(
        ["--", "lint"], stdin=io.StringIO("\n  spaced.md \r\n\n   \nlast.md"), run_fn=run
    )

    assert commands == [["lint", "  spaced.md ", "last.md"]]


def test_falls_back_to_the_defaults_without_paths() -> None:
    """An empty stdin runs the command on its default scope."""
    commands, run = recorder()

    stdin_paths.main([".", "--", "yamllint"], stdin=io.StringIO(""), run_fn=run)

    assert commands == [["yamllint", "."]]


def test_treats_a_terminal_as_no_paths_without_reading_it() -> None:
    """An optional list never waits for typing."""
    commands, run = recorder()

    stdin_paths.main(["scripts/", "--", "mypy"], stdin=TerminalInput("ignored.py\n"), run_fn=run)

    assert commands == [["mypy", "scripts/"]]


def test_treats_a_closed_stdin_as_no_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    """Python sets sys.stdin to None when fd 0 is closed (`make lint-py <&-`)."""
    commands, run = recorder()
    monkeypatch.setattr("sys.argv", ["stdin_paths", ".", "--", "ruff"])
    monkeypatch.setattr("sys.stdin", None)

    stdin_paths.main(run_fn=run)

    assert commands == [["ruff", "."]]


def test_prefixes_a_leading_dash_so_it_cannot_read_as_an_option() -> None:
    """A file named like an option stays a file."""
    commands, run = recorder()

    stdin_paths.main(["--", "git", "add", "--"], stdin=io.StringIO("-rf\n"), run_fn=run)

    assert commands == [["git", "add", "--", "./-rf"]]


def test_runs_each_then_command_on_the_same_paths() -> None:
    """A lint fix and a format both see every path."""
    commands, run = recorder()

    code = stdin_paths.main(
        [".", "--", "ruff", "check", "--fix", "--then", "ruff", "format"],
        stdin=io.StringIO("a.py\nb c.py\n"),
        run_fn=run,
    )

    assert code == 0
    assert commands == [
        ["ruff", "check", "--fix", "a.py", "b c.py"],
        ["ruff", "format", "a.py", "b c.py"],
    ]


def test_a_failing_command_stops_the_chain_and_sets_the_exit_code() -> None:
    """Nothing is staged when taking a side of a conflict fails."""
    commands, run = recorder(codes=[3])

    code = stdin_paths.main(
        ["--", "git", "checkout", "--ours", "--", "--then", "git", "add", "--"],
        stdin=io.StringIO("a.md\n"),
        run_fn=run,
    )

    assert code == 3
    assert commands == [["git", "checkout", "--ours", "--", "a.md"]]


def test_a_required_list_without_paths_prints_usage_and_runs_nothing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Running `make stage` with nothing to stage is a usage error."""
    commands, run = recorder()

    code = stdin_paths.main(
        ["--require", "--name", "make stage", "--", "git", "add", "--"],
        stdin=TerminalInput(""),
        run_fn=run,
    )

    assert code == 2
    assert commands == []
    assert "make stage needs paths on stdin, one per line" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["lint"], "missing -- before the command"),
        (["--"], "missing command after -- or --then"),
        (["--", "lint", "--then"], "missing command after -- or --then"),
        (["--", "--then", "lint"], "missing command after -- or --then"),
        (["--name"], "missing -- before the command"),
        (["--name", "--", "lint"], "--name needs a value"),
    ],
)
def test_rejects_a_malformed_invocation(
    argv: list[str], message: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A recipe mistake fails loudly instead of running the wrong command."""
    code = stdin_paths.main(argv, stdin=io.StringIO(""), run_fn=lambda _: 0)

    assert code == 2
    assert message in capsys.readouterr().err


def test_reads_the_process_stdin_and_arguments_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without injected streams, the real stdin and argv are used."""
    commands, run = recorder()
    monkeypatch.setattr("sys.argv", ["stdin_paths", "--", "lint"])
    monkeypatch.setattr("sys.stdin", io.StringIO("a.md\n"))

    stdin_paths.main(run_fn=run)

    assert commands == [["lint", "a.md"]]


def test_default_runner_executes_without_a_shell(tmp_path: Path) -> None:
    """The real runner passes each path as one argument and returns the exit code."""
    target = tmp_path / "name with $(spaces).txt"

    assert stdin_paths._default_run(["touch", str(target)]) == 0
    assert target.exists()
    assert stdin_paths._default_run(["false"]) == 1


def test_default_runner_uses_subprocess_without_a_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner never asks for a shell."""
    seen: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert stdin_paths._default_run(["lint"]) == 0
    assert seen["shell"] is False
