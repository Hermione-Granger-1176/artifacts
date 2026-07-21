#!/usr/bin/env python3
"""Report workspace health for ``make status``.

This backs the ``status`` Make target. It must run on the system interpreter
before ``make setup`` provisions a virtual environment, so it imports only the
standard library and shells out (git, uv, npm, and the venv helpers) exactly
like the previous inline shell recipe, guarding each on availability.

The sections mirror the old recipe: Git, Venv, Node plus lock currency,
Generated files (drift or a venv-less fallback) plus the ``_site`` payload, and
the Pull request overview.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TextIO

from scripts import REPO_ROOT

# A runner takes a command vector plus a working directory and optional env, and
# returns the completed process. Injectable so tests never touch real tooling.
Runner = Callable[..., "subprocess.CompletedProcess[str]"]

DRIFT_CHECKER = "scripts/lint/check_generated_drift.py"


def _default_run(
    cmd: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command with captured output, never raising on a non-zero exit."""
    return subprocess.run(
        list(cmd),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _succeeds(
    cmd: Sequence[str],
    *,
    cwd: Path,
    run_fn: Runner,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """Return the completed process, or ``None`` when the tool cannot launch.

    Mirrors the shell ``cmd >/dev/null 2>&1 && ... || ...`` idiom, where a
    command that cannot even launch (missing, not executable, wrong format)
    counts as a plain failure. ``OSError`` covers every such launch error. Every
    subprocess in this module routes through here so no launch failure can hard
    fail ``make status``.
    """
    try:
        return run_fn(cmd, cwd=cwd, env=env)
    except OSError:
        return None


def _ok(result: subprocess.CompletedProcess[str] | None) -> bool:
    """Return whether a lock-currency check ran and reported no drift."""
    return result is not None and result.returncode == 0


def _venv_python_path(venv_python: str, root: Path) -> Path:
    """Resolve the interpreter path used for the executable check."""
    candidate = Path(venv_python)
    return candidate if candidate.is_absolute() else root / candidate


def write_status(
    out: TextIO,
    *,
    root: Path,
    venv_python: str,
    uv: str,
    npm: str,
    run_fn: Runner | None = None,
) -> None:
    """Write the full workspace status report to ``out``."""
    run = run_fn or _default_run

    def emit(line: str = "") -> None:
        print(line, file=out)

    venv_ok = os.access(_venv_python_path(venv_python, root), os.X_OK)

    # --- Git ---
    emit("=== Git ===")
    git = _succeeds(["git", "status", "-sb"], cwd=root, run_fn=run)
    if git is not None:
        out.write(git.stdout)
        out.write(git.stderr)
    emit()

    # --- Venv ---
    emit("=== Venv ===")
    emit(f"OK: {venv_python} exists" if venv_ok else "MISSING: run make setup")
    emit()

    # --- Node and lock currency ---
    emit("=== Node ===")
    node_ok = (root / "node_modules").is_dir()
    emit("OK: node_modules exists" if node_ok else "MISSING: run make setup")
    uv_check = _succeeds([uv, "lock", "--check"], cwd=root, run_fn=run)
    emit("OK: uv.lock is current" if _ok(uv_check) else "STALE: run make lock")
    npm_check = _succeeds(
        [npm, "install", "--package-lock-only", "--ignore-scripts", "--dry-run"],
        cwd=root,
        run_fn=run,
    )
    emit("OK: package-lock.json is current" if _ok(npm_check) else "STALE: run make lock-node")
    emit()

    # --- Generated files ---
    emit("=== Generated files ===")
    _write_generated_files(emit, root=root, venv_python=venv_python, venv_ok=venv_ok, run=run)
    emit("OK: _site/" if (root / "_site").is_dir() else "NOT BUILT: run make site")
    emit()

    # --- Pull request ---
    emit("=== Pull request ===")
    if venv_ok:
        summary = _succeeds(
            [venv_python, "-m", "scripts.gh.cli", "summary"],
            cwd=root,
            run_fn=run,
            env={**os.environ, "PYTHONPATH": "."},
        )
        # Old shell ran ``$(GH) summary || true``: any failure, including a
        # launch failure, is swallowed and the target still succeeds. A launch
        # failure yields ``None`` here, so nothing extra is printed.
        if summary is not None:
            out.write(summary.stdout)
            out.write(summary.stderr)
    else:
        emit("SKIPPED: venv missing, run make setup")


def _write_generated_files(
    emit: Callable[[str], None],
    *,
    root: Path,
    venv_python: str,
    venv_ok: bool,
    run: Runner,
) -> None:
    """Write the drift check, or the venv-less presence fallback."""
    if not venv_ok:
        emit("SKIPPED: venv missing, run make setup")
        emit("PRESENT: js/data.js" if (root / "js/data.js").is_file() else "MISSING: js/data.js")
        emit(
            "PRESENT: js/gallery-config.js"
            if (root / "js/gallery-config.js").is_file()
            else "MISSING: js/gallery-config.js"
        )
        return

    drift = _succeeds([venv_python, DRIFT_CHECKER], cwd=root, run_fn=run)
    if drift is not None and drift.returncode == 0:
        emit("OK: js/data.js, js/gallery-config.js, css/style.css, README markers up to date")
        return
    # Old shell: any failure (a nonzero exit or a launch failure) falls through
    # to the STALE branch with whatever drift text was captured, which is empty
    # on a launch failure (``drift`` is ``None`` here).
    emit("STALE: run make index && make styles")
    if drift is not None:
        for line in drift.stdout.splitlines():
            if line.startswith("- "):
                emit(f"  {line}")


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and print the workspace status report."""
    parser = argparse.ArgumentParser(description="Report workspace health for make status.")
    parser.add_argument("--venv-python", default=".venv/bin/python")
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--npm", default="npm")
    args = parser.parse_args(argv)
    write_status(
        sys.stdout,
        root=REPO_ROOT,
        venv_python=args.venv_python,
        uv=args.uv,
        npm=args.npm,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
