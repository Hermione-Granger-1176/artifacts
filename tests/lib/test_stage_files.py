from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path
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


def test_collect_paths_preserves_spaced_legacy_value_when_it_is_one_path() -> None:
    """The files input stays intact when its full value resolves to one path."""
    raw = "one file with spaces.txt"

    assert stage_files.collect_paths(
        {"STAGE_FILES": raw}, is_exact_path=lambda path: path == raw
    ) == [raw]


def test_collect_paths_trims_outer_whitespace_before_exact_probe() -> None:
    """Outer list whitespace is ignored before deciding whether files names one path."""
    expected = "one file.txt"
    probed: list[str] = []

    def is_exact_path(path: str) -> bool:
        probed.append(path)
        return path == expected

    assert stage_files.collect_paths(
        {"STAGE_FILES": f"  {expected}  "}, is_exact_path=is_exact_path
    ) == [expected]
    assert probed == [expected]


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


def test_existing_path_does_not_need_a_git_lookup(tmp_path: Path) -> None:
    """An existing spaced path is recognized without invoking git."""
    path = tmp_path / "one file.txt"
    path.write_text("content", encoding="utf-8")

    def unexpected_run(_cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        raise AssertionError("git should not run for an existing path")

    assert stage_files._is_existing_or_tracked(str(path), probe_fn=unexpected_run)


def test_tracked_path_lookup_is_literal_and_returns_git_status() -> None:
    """Missing paths are checked as literal tracked paths without pathspec magic."""
    calls: list[list[str]] = []
    statuses = iter([0, 1])

    def fake_run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=list(cmd), returncode=next(statuses))

    assert stage_files._is_existing_or_tracked("tracked file.txt", probe_fn=fake_run)
    assert not stage_files._is_existing_or_tracked("missing file.txt", probe_fn=fake_run)
    assert calls == [
        [
            "git",
            "--literal-pathspecs",
            "ls-files",
            "--error-unmatch",
            "--",
            "tracked file.txt",
        ],
        [
            "git",
            "--literal-pathspecs",
            "ls-files",
            "--error-unmatch",
            "--",
            "missing file.txt",
        ],
    ]


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


def test_default_probe_suppresses_expected_lookup_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The tracked-path probe hides stdout and stderr without enabling a shell."""
    recorded: dict[str, object] = {}

    def fake_subprocess_run(
        cmd: Sequence[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = list(cmd)
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(args=list(cmd), returncode=1)

    monkeypatch.setattr(stage_files.subprocess, "run", fake_subprocess_run)

    result = stage_files._default_probe(["git", "ls-files", "missing file.txt"])

    assert result.returncode == 1
    assert recorded == {
        "cmd": ["git", "ls-files", "missing file.txt"],
        "kwargs": {
            "check": False,
            "shell": False,
            "stderr": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "text": True,
        },
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


def test_main_preserves_tracked_spaced_files_value() -> None:
    """The legacy files input stages one spaced path when git reports it tracked."""
    calls: list[list[str]] = []

    def fake_run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=list(cmd), returncode=0)

    raw = "one tracked file.txt"
    assert stage_files.main(environ={"STAGE_FILES": raw}, run_fn=fake_run, probe_fn=fake_run) == 0
    assert calls == [
        ["git", "--literal-pathspecs", "ls-files", "--error-unmatch", "--", raw],
        ["git", "add", "--", raw],
    ]


def test_main_splits_unmatched_multi_file_value() -> None:
    """The legacy files input still splits when its complete value is not one path."""
    calls: list[list[str]] = []

    def fake_run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        returncode = 1 if "ls-files" in cmd else 0
        return subprocess.CompletedProcess(args=list(cmd), returncode=returncode)

    assert (
        stage_files.main(environ={"STAGE_FILES": "a.txt b.txt"}, run_fn=fake_run, probe_fn=fake_run)
        == 0
    )
    assert calls == [
        [
            "git",
            "--literal-pathspecs",
            "ls-files",
            "--error-unmatch",
            "--",
            "a.txt b.txt",
        ],
        ["git", "add", "--", "a.txt", "b.txt"],
    ]


def test_main_stages_collected_paths() -> None:
    """The entry point collects environment inputs and returns git's status."""
    calls: list[list[str]] = []

    def fake_run(cmd: Sequence[str]) -> subprocess.CompletedProcess[str]:
        calls.append(list(cmd))
        return subprocess.CompletedProcess(args=list(cmd), returncode=0)

    assert stage_files.main(environ={"STAGE_FILE": "one file.txt"}, run_fn=fake_run) == 0
    assert calls == [["git", "add", "--", "one file.txt"]]
