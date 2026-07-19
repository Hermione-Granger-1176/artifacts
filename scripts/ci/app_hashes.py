#!/usr/bin/env python3
"""Hash app verification inputs and maintain the main-verified result ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, cast

from scripts.lib.app_discovery import (
    SHARED_APP_BROWSER_TEST_PATHS,
    artifact_base_path,
    discover_app_slugs,
    shared_app_runtime_paths,
)
from scripts.lib.path_validation import reject_path_symlinks, reject_symlinks

if TYPE_CHECKING:
    from collections.abc import Callable


LEDGER_VERSION = 1
LOCKFILE_PATHS = (Path("uv.lock"), Path("package-lock.json"))


def _reject_symlinked_file(path: Path, *, label: str) -> None:
    """Reject a symlink before reading or writing a single file."""
    reject_path_symlinks(path, label=label)


def _read_json_object(path: Path, *, label: str) -> dict[str, object]:
    """Read a required JSON object after validating its path."""
    _reject_symlinked_file(path, label=label)
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return cast("dict[str, object]", payload)


def read_plan(path: Path) -> dict[str, object]:
    """Read one required impact-plan JSON object."""
    return _read_json_object(path, label="Impact plan")


def read_ledger(path: Path) -> dict[str, str]:
    """Read and validate one persisted main-verification ledger."""
    payload = _read_json_object(path, label="Verification ledger")
    if payload.get("version") != LEDGER_VERSION:
        raise ValueError(f"Verification ledger has unsupported version: {path}")
    hashes = payload.get("hashes")
    if not isinstance(hashes, dict) or not all(
        isinstance(slug, str) and isinstance(value, str) for slug, value in hashes.items()
    ):
        raise ValueError(f"Verification ledger hashes must map strings to strings: {path}")
    return cast("dict[str, str]", hashes)


def _write_ledger(path: Path, hashes: dict[str, str]) -> None:
    """Write a deterministic ledger without following a symlinked output path."""
    _reject_symlinked_file(path, label="Verification ledger output")
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"hashes": dict(sorted(hashes.items())), "version": LEDGER_VERSION}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_ls_files(stdout: str) -> list[tuple[str, str]]:
    """Parse ``git ls-files -s`` records into blob hash and path pairs."""
    records: list[tuple[str, str]] = []
    for line in stdout.splitlines():
        metadata, separator, filename = line.partition("\t")
        fields = metadata.split()
        if not separator or len(fields) != 3:
            raise ValueError("git ls-files returned an invalid staged-file record")
        mode, blob_hash, stage = fields
        if mode == "120000":
            raise ValueError(f"Refusing to hash symlinked tracked input: {filename}")
        if stage != "0":
            raise ValueError(f"git ls-files returned a non-stage-zero input: {filename}")
        records.append((filename, blob_hash))
    return records


def git_blob_hashes(
    paths: list[str],
    *,
    repo_root: Path,
    run_git_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> list[tuple[str, str]]:
    """Return sorted tracked blob hashes for ``paths`` from the checked-out index."""
    reject_path_symlinks(repo_root, label="Repository root")
    result = run_git_fn(
        ["git", "ls-files", "-s", "--", *paths],
        check=True,
        capture_output=True,
        cwd=repo_root,
        text=True,
    )
    return sorted(_parse_ls_files(result.stdout))


def _shared_input_paths(repo_root: Path) -> list[str]:
    """Return common runtime, test-harness, and lockfile inputs for every app hash."""
    runtime_paths = [
        path.relative_to(repo_root).as_posix() for path in shared_app_runtime_paths(repo_root)
    ]
    return sorted(
        {
            *runtime_paths,
            *(sorted(SHARED_APP_BROWSER_TEST_PATHS)),
            *(path.as_posix() for path in LOCKFILE_PATHS),
        }
    )


def app_input_hashes(
    slugs: list[str],
    *,
    repo_root: Path = Path(),
    run_git_fn: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, str]:
    """Hash each app's own tracked files plus common verification inputs."""
    reject_path_symlinks(repo_root, label="Repository root")
    root = repo_root.resolve()
    apps_root = root / artifact_base_path()
    reject_path_symlinks(apps_root, label="App root")
    if apps_root.exists():
        reject_symlinks(apps_root)
    selected_slugs = sorted(set(slugs))
    if not selected_slugs:
        return {}
    common_records = git_blob_hashes(
        _shared_input_paths(root), repo_root=root, run_git_fn=run_git_fn
    )
    hashes: dict[str, str] = {}
    for slug in selected_slugs:
        app_dir = apps_root / slug
        if app_dir.is_symlink():
            raise ValueError(f"App input directory must not be a symlink: {app_dir}")
        records = git_blob_hashes(
            [f"{artifact_base_path()}/{slug}"], repo_root=root, run_git_fn=run_git_fn
        )
        digest = hashlib.sha256()
        for filename, blob_hash in [*common_records, *records]:
            digest.update(f"{filename}\0{blob_hash}\n".encode())
        hashes[slug] = digest.hexdigest()
    return hashes


def _string_list(plan: dict[str, object], key: str) -> list[str]:
    """Read one required list of strings from an impact plan."""
    value = plan.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Impact plan field {key} must be a list of strings")
    return sorted(set(cast("list[str]", value)))


def _browser_slugs(plan: dict[str, object], apps_root: Path) -> list[str]:
    """Resolve the pre-memoization browser app set for one impact plan."""
    scope = plan.get("browser_scope")
    if scope not in {"all", "changed", "none"}:
        raise ValueError("Impact plan browser_scope must be all, changed, or none")
    all_browser_slugs = [
        slug
        for slug in discover_app_slugs(apps_root)
        if (apps_root / slug / "js" / "app.js").is_file()
    ]
    if scope == "all":
        return all_browser_slugs
    if scope == "changed":
        return sorted(set(_string_list(plan, "changed_slugs")) & set(all_browser_slugs))
    return []


def apply_memoization(
    plan: dict[str, object],
    *,
    ledger_path: Path,
    repo_root: Path = Path(),
    hash_inputs_fn: Callable[..., dict[str, str]] = app_input_hashes,
) -> dict[str, object]:
    """Remove apps with matching main-green hashes, failing open on any ledger error."""
    reject_path_symlinks(repo_root, label="Repository root")
    root = repo_root.resolve()
    candidates = _browser_slugs(plan, root / artifact_base_path())
    updated = {
        **plan,
        "verified_browser_slugs": candidates,
        "memoized_browser_slugs": [],
        "memoization_available": False,
    }
    try:
        ledger = read_ledger(ledger_path)
        current_hashes = hash_inputs_fn(candidates, repo_root=root)
    except (OSError, ValueError, subprocess.SubprocessError):
        return updated

    memoized = sorted(slug for slug in candidates if ledger.get(slug) == current_hashes.get(slug))
    return {
        **updated,
        "browser_slugs": [slug for slug in candidates if slug not in set(memoized)],
        "memoized_browser_slugs": memoized,
        "memoization_available": True,
    }


def update_ledger(
    plan: dict[str, object],
    *,
    ledger_path: Path,
    repo_root: Path = Path(),
    hash_inputs_fn: Callable[..., dict[str, str]] = app_input_hashes,
) -> dict[str, str]:
    """Merge hashes for the plan's main-verified browser apps into the ledger."""
    reject_path_symlinks(repo_root, label="Repository root")
    _reject_symlinked_file(ledger_path, label="Verification ledger")
    ledger = read_ledger(ledger_path) if ledger_path.is_file() else {}
    verified_slugs = _string_list(plan, "verified_browser_slugs")
    current_hashes = hash_inputs_fn(verified_slugs, repo_root=repo_root.resolve())
    ledger.update(current_hashes)
    _write_ledger(ledger_path, ledger)
    return dict(sorted(ledger.items()))


def _parser() -> argparse.ArgumentParser:
    """Build the Makefile-facing command parser."""
    parser = argparse.ArgumentParser(description="Manage app verification input hashes")
    commands = parser.add_subparsers(dest="command", required=True)
    memoize = commands.add_parser(
        "apply-ledger", help="Apply a cached green-result ledger to a plan"
    )
    memoize.add_argument("--plan", required=True)
    memoize.add_argument("--ledger", required=True)
    memoize.add_argument("--output", required=True)
    update = commands.add_parser("update-ledger", help="Write main-verified app hashes to a ledger")
    update.add_argument("--plan", required=True)
    update.add_argument("--ledger", required=True)
    return parser


def _write_plan(path: Path, plan: dict[str, object]) -> None:
    """Write a plan output after rejecting a symlinked output path."""
    _reject_symlinked_file(path, label="Impact plan output")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, sort_keys=True), encoding="utf-8")


def _handle_apply_ledger(args: argparse.Namespace) -> int:
    """Apply a cached green-result ledger to a plan and write the result."""
    _write_plan(
        Path(args.output),
        apply_memoization(read_plan(Path(args.plan)), ledger_path=Path(args.ledger)),
    )
    return 0


def _handle_update_ledger(args: argparse.Namespace) -> int:
    """Write main-verified app hashes to the ledger."""
    update_ledger(read_plan(Path(args.plan)), ledger_path=Path(args.ledger))
    return 0


COMMAND_HANDLERS = {
    "apply-ledger": _handle_apply_ledger,
    "update-ledger": _handle_update_ledger,
}


def main(argv: list[str] | None = None) -> int:
    """Run one hash or ledger command requested through the Makefile."""
    args = _parser().parse_args(argv)
    handler = COMMAND_HANDLERS.get(args.command)
    if handler is None:  # pragma: no cover, argparse constrains the command.
        raise ValueError(f"Unsupported app hash command: {args.command}")
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(exc)
        raise SystemExit(1) from exc
