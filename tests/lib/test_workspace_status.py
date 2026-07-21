from __future__ import annotations

import io
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from scripts.lib import workspace_status

if TYPE_CHECKING:
    import pytest

Predicate = Callable[[list[str]], bool]


class FakeRun:
    """Dispatch injected subprocess calls to scripted responses."""

    def __init__(self, responses: list[tuple[Predicate, object]]) -> None:
        self.responses = responses
        self.calls: list[list[str]] = []

    def __call__(self, cmd: Sequence[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return the first matching scripted response, or raise it."""
        command = list(cmd)
        self.calls.append(command)
        for predicate, response in self.responses:
            if predicate(command):
                if isinstance(response, Exception):
                    raise response
                assert isinstance(response, subprocess.CompletedProcess)
                return response
        raise AssertionError(f"unexpected command: {command}")


def _proc(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    """Build a completed process for the fake runner."""
    return subprocess.CompletedProcess(
        args=["x"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def _first(name: str) -> Predicate:
    """Match commands whose executable is ``name``."""
    return lambda cmd: cmd[0] == name


def _contains(token: str) -> Predicate:
    """Match commands that contain ``token``."""
    return lambda cmd: token in cmd


def _make_venv(root: Path) -> None:
    """Create an executable stub interpreter under ``root/.venv``."""
    venv_python = root / ".venv/bin/python"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("#!/bin/sh\n", encoding="utf-8")
    venv_python.chmod(0o755)


def _render(root: Path, runner: FakeRun) -> str:
    """Render the status report to a string."""
    out = io.StringIO()
    workspace_status.write_status(
        out, root=root, venv_python=".venv/bin/python", uv="uv", npm="npm", run_fn=runner
    )
    return out.getvalue()


def test_full_report_with_venv(tmp_path: Path) -> None:
    """A provisioned workspace reports OK for every section."""
    _make_venv(tmp_path)
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "_site").mkdir()

    runner = FakeRun(
        [
            (_first("git"), _proc(0, "## main...origin/main\n", "")),
            (_first("uv"), _proc(0)),
            (_first("npm"), _proc(0)),
            (_contains(workspace_status.DRIFT_CHECKER), _proc(0)),
            (_contains("summary"), _proc(0, "PR #1 [OPEN] Title\n")),
        ]
    )

    report = _render(tmp_path, runner)

    assert "## main...origin/main" in report
    assert "OK: .venv/bin/python exists" in report
    assert "OK: node_modules exists" in report
    assert "OK: uv.lock is current" in report
    assert "OK: package-lock.json is current" in report
    assert "css/style.css, README markers up to date" in report
    assert "OK: _site/" in report
    assert "PR #1 [OPEN] Title" in report


def test_report_without_venv_uses_fallbacks(tmp_path: Path) -> None:
    """Without a venv the report skips checks and probes generated files directly."""
    (tmp_path / "js").mkdir()
    (tmp_path / "js/data.js").write_text("", encoding="utf-8")

    runner = FakeRun(
        [
            (_first("git"), FileNotFoundError("git")),
            (_first("uv"), FileNotFoundError("uv")),
            (_first("npm"), FileNotFoundError("npm")),
        ]
    )

    report = _render(tmp_path, runner)

    assert "MISSING: run make setup" in report
    assert "STALE: run make lock" in report
    assert "STALE: run make lock-node" in report
    assert "SKIPPED: venv missing, run make setup" in report
    assert "PRESENT: js/data.js" in report
    assert "MISSING: js/gallery-config.js" in report
    assert "NOT BUILT: run make site" in report


def test_drift_and_stale_locks_with_venv(tmp_path: Path) -> None:
    """Stale locks and drift render their guidance and filtered drift lines."""
    _make_venv(tmp_path)

    runner = FakeRun(
        [
            (_first("git"), _proc(0, "## main\n", "")),
            (_first("uv"), _proc(1)),
            (_first("npm"), _proc(1)),
            (
                _contains(workspace_status.DRIFT_CHECKER),
                _proc(1, "- js/data.js is stale\nnoise line\n"),
            ),
            (_contains("summary"), _proc(0, "No pull request found.\n")),
        ]
    )

    report = _render(tmp_path, runner)

    assert "STALE: run make lock" in report
    assert "STALE: run make lock-node" in report
    assert "STALE: run make index && make styles" in report
    assert "  - js/data.js is stale" in report
    assert "noise line" not in report


def test_venv_python_path_absolute_is_unchanged(tmp_path: Path) -> None:
    """An absolute interpreter path is used verbatim."""
    absolute = tmp_path / "python"
    assert workspace_status._venv_python_path(str(absolute), tmp_path) == absolute


def test_default_run_captures_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The default runner captures output and never raises on a non-zero exit."""
    recorded: dict[str, object] = {}

    def fake_run(cmd: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = list(cmd)
        recorded["cwd"] = kwargs.get("cwd")
        return subprocess.CompletedProcess(args=list(cmd), returncode=2, stdout="hi")

    monkeypatch.setattr(workspace_status.subprocess, "run", fake_run)

    result = workspace_status._default_run(["git", "status"], cwd=tmp_path)

    assert result.returncode == 2
    assert recorded["cmd"] == ["git", "status"]
    assert recorded["cwd"] == tmp_path


def test_main_forwards_cli_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    """Forward parsed interpreter and tool overrides to write_status."""
    recorded: dict[str, object] = {}

    def fake_write_status(_out: object, **kwargs: object) -> None:
        recorded.update(kwargs)

    monkeypatch.setattr(workspace_status, "write_status", fake_write_status)

    exit_code = workspace_status.main(
        ["--venv-python", "custom/python", "--uv", "myuv", "--npm", "mynpm"]
    )

    assert exit_code == 0
    assert recorded["venv_python"] == "custom/python"
    assert recorded["uv"] == "myuv"
    assert recorded["npm"] == "mynpm"
    assert recorded["root"] == workspace_status.REPO_ROOT
