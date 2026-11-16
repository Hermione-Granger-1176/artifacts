"""Tests for the Prettier diff behind make format-prettier-diff."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import TYPE_CHECKING

from scripts.lint import format_prettier_diff

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

RUNNER = ["npm", "exec", "--no", "--"]


def formatter(
    outputs: dict[str, tuple[int, str, str]],
) -> tuple[list[list[str]], format_prettier_diff.Formatter]:
    """Return the commands Prettier receives, and a fake Prettier keyed by path."""
    commands: list[list[str]] = []

    def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        commands.append(list(command))
        code, stdout, stderr = outputs[command[-1]]
        return subprocess.CompletedProcess(list(command), code, stdout, stderr)

    return commands, run


def test_prints_a_unified_diff_and_exits_zero_when_files_differ(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Exit 0 with a unified diff on stdout when Prettier would change the file."""
    path = tmp_path / "eslint.config.js"
    path.write_text("const a=1\n", encoding="utf-8")
    commands, run = formatter({str(path): (0, "const a = 1;\n", "")})

    code = format_prettier_diff.main([str(path)], format_fn=run)

    assert code == 0
    output = capsys.readouterr().out
    assert f"--- {path}\n+++ {path} (formatted)\n" in output
    assert "-const a=1\n+const a = 1;\n" in output
    assert commands == [[*RUNNER, *format_prettier_diff.PRETTIER_ARGS, "--", str(path)]]


def test_prints_nothing_for_a_formatted_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A file Prettier would leave alone produces no output."""
    path = tmp_path / "tags.json"
    path.write_text("[]\n", encoding="utf-8")
    _, run = formatter({str(path): (0, "[]\n", "")})

    assert format_prettier_diff.main([str(path)], format_fn=run) == 0
    assert capsys.readouterr().out == ""


def test_shows_a_diff_for_line_endings_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A CRLF file differs from Prettier's LF output even when the text matches."""
    path = tmp_path / "crlf.js"
    path.write_bytes(b"const a = 1;\r\n")
    _, run = formatter({str(path): (0, "const a = 1;\n", "")})

    assert format_prettier_diff.main([str(path)], format_fn=run) == 0
    assert "-const a = 1;\r\n+const a = 1;\n" in capsys.readouterr().out


def test_refuses_markdown_before_running_prettier(capsys: pytest.CaptureFixture[str]) -> None:
    """Markdown paths are rejected with exit 2 before Prettier runs."""
    commands, run = formatter({})

    code = format_prettier_diff.main(["a.yml", "README.md", "notes.MARKDOWN"], format_fn=run)

    assert code == 2
    assert commands == []
    assert "README.md, notes.MARKDOWN" in capsys.readouterr().err


def test_a_prettier_failure_stops_the_run_with_its_exit_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failing Prettier run returns its exit code and skips the remaining files."""
    broken = tmp_path / "broken.js"
    broken.write_text("const =\n", encoding="utf-8")
    later = tmp_path / "later.js"
    later.write_text("x\n", encoding="utf-8")
    commands, run = formatter(
        {str(broken): (2, "", "SyntaxError: Unexpected token\n"), str(later): (0, "x\n", "")}
    )

    code = format_prettier_diff.main([str(broken), str(later)], format_fn=run)

    assert code == 2
    assert "SyntaxError" in capsys.readouterr().err
    assert len(commands) == 1


def test_runs_the_configured_runner(tmp_path: Path) -> None:
    """The runner may carry its own arguments."""
    path = tmp_path / "a.yml"
    path.write_text("a: 1\n", encoding="utf-8")
    commands, run = formatter({str(path): (0, "a: 1\n", "")})

    format_prettier_diff.main(["--runner", "npx --yes", str(path)], format_fn=run)

    assert commands[0][:3] == ["npx", "--yes", "prettier"]


def test_default_formatter_captures_output_without_a_shell(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default formatter runs without a shell and decodes raw output with replacement."""
    seen: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 2, b"out\r\n", b"bad \xff\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = format_prettier_diff._default_format(["prettier", "a.js"])

    assert (result.returncode, result.stdout) == (2, "out\r\n")
    assert result.stderr == "bad �\n"
    assert seen["shell"] is False
    assert seen["capture_output"] is True
    assert "text" not in seen
