"""Run Make targets in parallel with CI-friendly reporting."""

from __future__ import annotations

import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    """Outcome of one parallel check."""

    name: str
    passed: bool
    elapsed: float
    output: str


DEFAULT_TIMEOUT = 600


def run_check(
    name: str, *, timeout: int = DEFAULT_TIMEOUT, run_fn=None
) -> CheckResult:
    """Run a single make target and return the captured result."""
    start = time.monotonic()
    try:
        result = (run_fn or subprocess.run)(
            ["make", name], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return CheckResult(
            name=name,
            passed=False,
            elapsed=time.monotonic() - start,
            output=f"Timed out after {timeout}s",
        )
    except OSError as exc:
        return CheckResult(
            name=name,
            passed=False,
            elapsed=time.monotonic() - start,
            output=f"Failed to run: {exc}",
        )
    elapsed = time.monotonic() - start
    return CheckResult(
        name=name,
        passed=result.returncode == 0,
        elapsed=elapsed,
        output=(result.stdout + result.stderr).strip(),
    )


def run_checks(
    targets: list[str], *, timeout: int = DEFAULT_TIMEOUT, run_fn=None
) -> tuple[CheckResult, ...]:
    """Run all targets in parallel and return results sorted by name."""
    with ThreadPoolExecutor() as pool:
        futures = {
            pool.submit(run_check, t, timeout=timeout, run_fn=run_fn): t
            for t in targets
        }
        results = [future.result() for future in as_completed(futures)]
    return tuple(sorted(results, key=lambda r: r.name))


def format_results(results: tuple[CheckResult, ...]) -> str:
    """Build CI log output: summary, folded pass logs, expanded fail logs."""
    summary = [
        f"{'✓' if r.passed else '✗'} {r.name} ({r.elapsed:.1f}s)" for r in results
    ]
    logs = []
    for r in results:
        header = f"::group::{r.name}" if r.passed else f"--- {r.name} (failed) ---"
        body = r.output or "(no output)"
        footer = "::endgroup::" if r.passed else ""
        logs.extend([header, body, *(line for line in [footer] if line)])

    failed = [r.name for r in results if not r.passed]
    error = [f"\n::error::Failed: {', '.join(failed)}"] if failed else []
    return "\n".join([*summary, "", *logs, *error])


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: run provided Make targets in parallel."""
    args = argv if argv is not None else sys.argv[1:]
    timeout = DEFAULT_TIMEOUT
    usage = "Usage: run_parallel_checks.py [--timeout N] target1 target2 ..."
    if "--timeout" in args:
        idx = args.index("--timeout")
        if idx + 1 >= len(args):
            print("Error: --timeout requires an integer value.")
            print(usage)
            return 1
        try:
            timeout = int(args[idx + 1])
        except ValueError:
            print(f"Error: invalid timeout value: {args[idx + 1]!r}.")
            print(usage)
            return 1
        args = args[:idx] + args[idx + 2:]

    if not args:
        print(usage)
        return 1

    results = run_checks(args, timeout=timeout)
    print(format_results(results))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
