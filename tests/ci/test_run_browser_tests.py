from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from scripts.ci import run_browser_tests


class FakeRunner:
    """Record pytest invocations and return a scripted sequence of exit codes."""

    def __init__(self, exit_codes: Sequence[int]) -> None:
        self._exit_codes = list(exit_codes)
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(self, flags: Sequence[str], env: Mapping[str, str]) -> int:
        """Return the next scripted exit code and record the call."""
        self.calls.append((list(flags), dict(env)))
        return self._exit_codes.pop(0)


def test_first_pass_runs_once_and_sets_require_env() -> None:
    """A passing first run does not retry and exports the require-browser flag."""
    runner = FakeRunner([0])

    status = run_browser_tests.run_browser_tests(
        ["tests/browser/test_smoke.py"],
        base_env={},
        run_fn=runner,
        warn=lambda _message: None,
    )

    assert status == 0
    assert len(runner.calls) == 1
    flags, env = runner.calls[0]
    assert flags == ["--no-cov", "tests/browser/test_smoke.py"]
    assert env[run_browser_tests.REQUIRE_BROWSER_TESTS_ENV_VAR] == "1"


def test_extra_env_is_merged() -> None:
    """Extra environment pairs are merged on top of the base environment."""
    runner = FakeRunner([0])

    run_browser_tests.run_browser_tests(
        ["tests/browser/test_smoke.py"],
        extra_env={"ARTIFACTS_BROWSER_ENGINE": "webkit"},
        base_env={"EXISTING": "1"},
        run_fn=runner,
        warn=lambda _message: None,
    )

    _flags, env = runner.calls[0]
    assert env["EXISTING"] == "1"
    assert env["ARTIFACTS_BROWSER_ENGINE"] == "webkit"


def test_flaky_retry_pass_warns_and_writes_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A failed first run then a passing retry reports flaky and writes the summary."""
    summary_path = tmp_path / "summary.md"
    runner = FakeRunner([1, 0])

    status = run_browser_tests.run_browser_tests(
        ["tests/browser/test_smoke.py"],
        base_env={run_browser_tests.STEP_SUMMARY_ENV_VAR: str(summary_path)},
        run_fn=runner,
    )

    assert status == 0
    assert len(runner.calls) == 2
    retry_flags, _env = runner.calls[1]
    assert retry_flags == [
        "--no-cov",
        "--last-failed",
        "--last-failed-no-failures",
        "none",
        "tests/browser/test_smoke.py",
    ]
    out = capsys.readouterr().out
    assert "::warning::Browser tests failed." in out
    assert "::warning::FLAKY BROWSER TESTS" in out
    assert summary_path.read_text(encoding="utf-8") == run_browser_tests.FLAKY_SUMMARY


def test_flaky_retry_pass_without_summary_env_skips_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """When GITHUB_STEP_SUMMARY is unset the flaky note is only printed."""
    runner = FakeRunner([1, 0])

    status = run_browser_tests.run_browser_tests(
        ["tests/browser/test_smoke.py"],
        base_env={},
        run_fn=runner,
    )

    assert status == 0
    assert "FLAKY BROWSER TESTS" in capsys.readouterr().out


def test_retry_failure_returns_retry_status() -> None:
    """When the retry also fails, its exit code is returned."""
    runner = FakeRunner([1, 3])

    status = run_browser_tests.run_browser_tests(
        ["tests/browser/test_smoke.py"],
        base_env={},
        run_fn=runner,
        warn=lambda _message: None,
    )

    assert status == 3


def test_default_run_invokes_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    """The default runner shells out to pytest under the current interpreter."""
    recorded: dict[str, object] = {}

    def fake_run(cmd: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = list(cmd)
        recorded["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(args=list(cmd), returncode=5)

    monkeypatch.setattr(run_browser_tests.subprocess, "run", fake_run)

    status = run_browser_tests._default_run(["--no-cov", "file.py"], env={"A": "B"})

    assert status == 5
    assert recorded["cmd"][1:] == ["-m", "pytest", "--no-cov", "file.py"]
    assert recorded["env"] == {"A": "B"}


def test_emit_warning_prints_annotation(capsys: pytest.CaptureFixture[str]) -> None:
    """The warning helper prints a GitHub Actions annotation."""
    run_browser_tests._emit_warning("boom")

    assert capsys.readouterr().out.strip() == "::warning::boom"


def test_append_flaky_summary_noop_when_unset(tmp_path: Path) -> None:
    """No summary file is written when the env var is blank."""
    run_browser_tests._append_flaky_summary({run_browser_tests.STEP_SUMMARY_ENV_VAR: "   "})
    assert list(tmp_path.iterdir()) == []


def test_main_threads_env_and_pytest_args(monkeypatch: pytest.MonkeyPatch) -> None:
    """Parse --env pairs and forward remaining tokens as pytest args."""
    recorded: dict[str, object] = {}

    def fake_run_browser_tests(
        pytest_args: Sequence[str], *, extra_env: Mapping[str, str] | None = None
    ) -> int:
        recorded["pytest_args"] = list(pytest_args)
        recorded["extra_env"] = dict(extra_env or {})
        return 0

    monkeypatch.setattr(run_browser_tests, "run_browser_tests", fake_run_browser_tests)

    exit_code = run_browser_tests.main(
        ["--env", "ARTIFACTS_BROWSER_ENGINE=webkit", "tests/browser/test_smoke.py", "-k", "hero"]
    )

    assert exit_code == 0
    assert recorded["pytest_args"] == ["tests/browser/test_smoke.py", "-k", "hero"]
    assert recorded["extra_env"] == {"ARTIFACTS_BROWSER_ENGINE": "webkit"}


def test_main_rejects_malformed_env_pair() -> None:
    """A malformed --env pair exits with a usage error."""
    with pytest.raises(SystemExit):
        run_browser_tests.main(["--env", "NOEQUALS", "tests/browser/test_smoke.py"])
