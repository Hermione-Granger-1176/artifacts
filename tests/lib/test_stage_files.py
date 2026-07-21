from __future__ import annotations

import subprocess
from collections.abc import Sequence
from typing import TYPE_CHECKING

from scripts import REPO_ROOT
from scripts.lib import stage_files

if TYPE_CHECKING:
    import pytest


def test_makefile_stage_target_uses_the_safe_helper() -> None:
    """The Make target exports both inputs and never interpolates paths into shell code."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "stage: export STAGE_FILES := $(files)" in makefile
    assert "stage: export STAGE_FILE := $(file)" in makefile
    assert "$(PYTHON) -m scripts.lib.stage_files" in makefile
    assert "git add -- $(files)" not in makefile


def test_collect_paths_splits_multi_file_input() -> None:
    """The legacy files input remains a whitespace-separated path list."""
    assert stage_files.collect_paths({"STAGE_FILES": "a.txt  b.txt\tc.txt"}) == [
        "a.txt",
        "b.txt",
        "c.txt",
    ]


def test_collect_paths_preserves_exact_single_path() -> None:
    """The file input preserves spaces and shell metacharacters verbatim."""
    path = "one file; $(not-a-command).txt"
    assert stage_files.collect_paths({"STAGE_FILE": path}) == [path]


def test_collect_paths_combines_multi_and_single_inputs() -> None:
    """Supplying both inputs stages the multi-file list followed by the exact path."""
    assert stage_files.collect_paths(
        {"STAGE_FILES": "a.txt b.txt", "STAGE_FILE": "one file.txt"}
    ) == ["a.txt", "b.txt", "one file.txt"]


def test_collect_paths_ignores_blank_inputs() -> None:
    """Missing and whitespace-only inputs do not create empty path arguments."""
    assert stage_files.collect_paths({}) == []
    assert stage_files.collect_paths({"STAGE_FILES": "  ", "STAGE_FILE": "  "}) == []


def test_stage_paths_passes_literal_argv_and_returns_status() -> None:
    """Paths remain distinct argv entries after --, including a leading dash."""
    calls: list[list[str]] = []

    def fake_run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=list(cmd), returncode=3)

    status = stage_files.stage_paths(
        ["one file.txt", "; touch /tmp/nope", "-leading-dash"], run_fn=fake_run
    )

    assert status == 3
    assert calls == [["git", "add", "--", "one file.txt", "; touch /tmp/nope", "-leading-dash"]]


def test_default_run_invokes_subprocess_without_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default runner forwards argv directly and never enables a shell."""
    recorded: dict[str, object] = {}

    def fake_subprocess_run(
        cmd: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = list(cmd)
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=list(cmd), returncode=0)

    monkeypatch.setattr(stage_files.subprocess, "run", fake_subprocess_run)

    result = stage_files._default_run(["git", "add", "--", "a;b.txt"])

    assert result.returncode == 0
    assert recorded == {
        "cmd": ["git", "add", "--", "a;b.txt"],
        "kwargs": {"check": False, "shell": False, "text": True},
    }


def test_main_prints_usage_when_no_paths(capsys: pytest.CaptureFixture[str]) -> None:
    """No input exits non-zero without invoking git."""
    called = False

    def fake_run(_cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        nonlocal called
        called = True
        return subprocess.CompletedProcess(args=[], returncode=0)

    assert stage_files.main(environ={}, run_fn=fake_run) == 1
    assert not called
    assert stage_files.USAGE in capsys.readouterr().err


def test_main_stages_collected_paths() -> None:
    """The entry point collects environment inputs and returns git's status."""
    calls: list[list[str]] = []

    def fake_run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=list(cmd), returncode=0)

    assert stage_files.main(environ={"STAGE_FILE": "one file.txt"}, run_fn=fake_run) == 0
    assert calls == [["git", "add", "--", "one file.txt"]]
