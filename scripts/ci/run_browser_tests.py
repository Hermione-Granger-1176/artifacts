#!/usr/bin/env python3
"""Run browser pytest files with a single retry and flaky reporting.

This backs the ``test-browser-*`` Make targets. It replaces the previous inline
Makefile macro so the retry-once policy and the flaky ``GITHUB_STEP_SUMMARY``
note live in tested Python instead of shell.

Behavior mirrors the old macro exactly:

1. Always export ``ARTIFACTS_REQUIRE_BROWSER_TESTS=1`` (plus any ``--env`` pairs).
2. Run ``pytest --no-cov <args>``.
3. On failure, retry once with ``--no-cov --last-failed
   --last-failed-no-failures none <args>``.
4. If the retry passes, emit a flaky ``::warning::`` line and append a note to
   ``GITHUB_STEP_SUMMARY`` when that variable is set, then exit 0.
5. Otherwise the exit code is the retry's exit code.

Invoke as ``python -m scripts.ci.run_browser_tests [--env KEY=VAL ...]
<pytest file args...>``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

# A runner takes the pytest flag vector (everything after ``-m pytest``) and the
# environment mapping, and returns the process exit code.
PytestRunner = Callable[[Sequence[str], Mapping[str, str]], int]
Warner = Callable[[str], None]

REQUIRE_BROWSER_TESTS_ENV_VAR = "ARTIFACTS_REQUIRE_BROWSER_TESTS"
STEP_SUMMARY_ENV_VAR = "GITHUB_STEP_SUMMARY"
FLAKY_SUMMARY = "## Flaky browser tests\n\nA retry passed after an initial failure.\n"


def _default_run(pytest_flags: Sequence[str], env: Mapping[str, str]) -> int:
    """Run pytest under the current interpreter and return its exit code."""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *pytest_flags],
        env=dict(env),
        check=False,
    )
    return completed.returncode


def _emit_warning(message: str) -> None:
    """Print a GitHub Actions warning annotation to stdout."""
    print(f"::warning::{message}")


def _append_flaky_summary(env: Mapping[str, str]) -> None:
    """Append the flaky-test note to ``GITHUB_STEP_SUMMARY`` when it is set."""
    summary_path = env.get(STEP_SUMMARY_ENV_VAR, "").strip()
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as summary_file:
        summary_file.write(FLAKY_SUMMARY)


def run_browser_tests(
    pytest_args: Sequence[str],
    *,
    extra_env: Mapping[str, str] | None = None,
    base_env: Mapping[str, str] | None = None,
    run_fn: PytestRunner | None = None,
    warn: Warner | None = None,
) -> int:
    """Run browser pytest files with one retry, returning the final exit code."""
    env = dict(os.environ if base_env is None else base_env)
    env[REQUIRE_BROWSER_TESTS_ENV_VAR] = "1"
    env.update(extra_env or {})

    runner = run_fn or _default_run
    emit = warn or _emit_warning

    first_status = runner(["--no-cov", *pytest_args], env)
    if first_status == 0:
        return 0

    emit("Browser tests failed. Retrying only failed tests once.")
    retry_status = runner(
        ["--no-cov", "--last-failed", "--last-failed-no-failures", "none", *pytest_args],
        env,
    )
    if retry_status == 0:
        emit("FLAKY BROWSER TESTS: retry passed after an initial failure.")
        _append_flaky_summary(env)
        return 0
    return retry_status


def _parse_env_pairs(pairs: Sequence[str], parser: argparse.ArgumentParser) -> dict[str, str]:
    """Parse ``KEY=VAL`` strings into a mapping, erroring on malformed input."""
    parsed: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator or not key:
            parser.error(f"--env expects KEY=VAL, got {pair!r}")
        parsed[key] = value
    return parsed


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and run the browser tests, returning an exit code."""
    parser = argparse.ArgumentParser(
        prog="run-browser-tests",
        description="Run browser pytest files with a single retry and flaky reporting.",
    )
    parser.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VAL",
        help="Extra environment variable to export for the pytest run (repeatable)",
    )
    args, pytest_args = parser.parse_known_args(argv)
    extra_env = _parse_env_pairs(args.env, parser)
    return run_browser_tests(pytest_args, extra_env=extra_env)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
