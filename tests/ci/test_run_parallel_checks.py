from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

from scripts.ci.run_parallel_checks import (
    CheckResult,
    format_results,
    main,
    run_check,
    run_checks,
)


def _make_run_fn(*, returncode: int = 0, stdout: str = "", stderr: str = ""):
    """Return a subprocess.run stand-in with fixed output."""

    def fake_run(cmd, **kwargs):
        return SimpleNamespace(returncode=returncode, stdout=stdout, stderr=stderr)

    return fake_run


def test_run_check_captures_passing_target() -> None:
    result = run_check("lint", run_fn=_make_run_fn(stdout="all good\n"))

    assert result.name == "lint"
    assert result.passed is True
    assert result.output == "all good"
    assert result.elapsed >= 0


def test_run_check_captures_failing_target() -> None:
    result = run_check("test-py", run_fn=_make_run_fn(returncode=1, stderr="FAILED\n"))

    assert result.name == "test-py"
    assert result.passed is False
    assert "FAILED" in result.output


def test_run_check_combines_stdout_and_stderr() -> None:
    result = run_check(
        "security",
        run_fn=_make_run_fn(stdout="out\n", stderr="err\n"),
    )

    assert result.output == "out\nerr"


def test_run_check_preserves_internal_whitespace() -> None:
    result = run_check(
        "lint",
        run_fn=_make_run_fn(stdout="  indented\n\n  block\n"),
    )

    assert result.output == "  indented\n\n  block"


def test_run_check_handles_timeout() -> None:
    def timeout_run(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout", 600))

    result = run_check("slow", timeout=5, run_fn=timeout_run)

    assert result.passed is False
    assert "Timed out" in result.output


def test_run_check_handles_os_error() -> None:
    def broken_run(cmd, **kwargs):
        raise OSError("No such file or directory: 'make'")

    result = run_check("lint", run_fn=broken_run)

    assert result.passed is False
    assert "Failed to run" in result.output


def test_run_checks_returns_sorted_results() -> None:
    results = run_checks(
        ["zebra", "alpha", "middle"],
        run_fn=_make_run_fn(stdout="ok"),
    )

    assert tuple(r.name for r in results) == ("alpha", "middle", "zebra")
    assert all(r.passed for r in results)


def test_run_checks_propagates_failures() -> None:
    def deterministic_run(cmd, **kwargs):
        target = cmd[-1]
        fail = target == "b"
        return SimpleNamespace(
            returncode=1 if fail else 0, stdout="", stderr="boom" if fail else ""
        )

    results = run_checks(["a", "b", "c"], run_fn=deterministic_run)

    assert [r.passed for r in results] == [True, False, True]
    assert next(r for r in results if r.name == "b").output == "boom"


def test_format_results_folds_passing_expands_failing() -> None:
    results = (
        CheckResult(name="lint", passed=True, elapsed=1.0, output="clean"),
        CheckResult(name="test-py", passed=False, elapsed=2.5, output="FAILED: x"),
    )

    output = format_results(results)

    assert "✓ lint (1.0s)" in output
    assert "✗ test-py (2.5s)" in output
    assert "::group::lint" in output
    assert "::endgroup::" in output
    assert "--- test-py (failed) ---" in output
    assert "FAILED: x" in output
    assert "::error::Failed: test-py" in output


def test_format_results_no_error_line_when_all_pass() -> None:
    results = (CheckResult(name="lint", passed=True, elapsed=1.0, output="ok"),)

    output = format_results(results)

    assert "::error::" not in output


def test_main_returns_zero_on_all_passing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.ci.run_parallel_checks.subprocess",
        SimpleNamespace(run=_make_run_fn(stdout="ok")),
    )

    assert main(["lint", "test-py"]) == 0


def test_main_returns_one_on_any_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "scripts.ci.run_parallel_checks.subprocess",
        SimpleNamespace(run=_make_run_fn(returncode=1, stderr="fail")),
    )

    assert main(["lint"]) == 1


def test_main_passes_timeout_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_timeout = {}

    def recording_run(cmd, **kwargs):
        captured_timeout["value"] = kwargs.get("timeout")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(
        "scripts.ci.run_parallel_checks.subprocess",
        SimpleNamespace(run=recording_run),
    )

    assert main(["--timeout", "42", "lint"]) == 0
    assert captured_timeout["value"] == 42


def test_main_rejects_timeout_without_value() -> None:
    assert main(["--timeout"]) == 1


def test_main_rejects_non_numeric_timeout() -> None:
    assert main(["--timeout", "abc", "lint"]) == 1


def test_main_rejects_non_positive_timeout() -> None:
    assert main(["--timeout", "0", "lint"]) == 1
    assert main(["--timeout", "-5", "lint"]) == 1


def test_main_returns_one_with_no_targets() -> None:
    assert main([]) == 1
