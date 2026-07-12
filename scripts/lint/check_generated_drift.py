#!/usr/bin/env python3
"""Check whether canonical generated files drift from the index generator."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scripts import REPO_ROOT
from scripts.build import generate_index, generate_styles

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class FileSnapshot:
    """Original content for one generated file before a drift check."""

    path: Path
    content: str | None


def _target_files() -> tuple[Path, ...]:
    """Return the canonical generated files owned by build generators."""
    return (
        generate_index.README_FILE,
        generate_index.JS_OUTPUT_FILE,
        generate_index.JS_CONFIG_OUTPUT_FILE,
        generate_styles.OUTPUT_FILE,
    )


def _read_text(path: Path) -> str | None:
    """Read a generated file, or None when it does not exist yet."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _capture_snapshots(paths: tuple[Path, ...]) -> list[FileSnapshot]:
    """Capture original generated-file contents before running the generator."""
    return [FileSnapshot(path=path, content=_read_text(path)) for path in paths]


def _detect_drift(snapshots: list[FileSnapshot]) -> list[Path]:
    """Return generated files whose content differs after regeneration."""
    return [
        snapshot.path for snapshot in snapshots if _read_text(snapshot.path) != snapshot.content
    ]


def _restore_snapshots(snapshots: list[FileSnapshot]) -> None:
    """Restore generated files to their original state after the check."""
    for snapshot in snapshots:
        if snapshot.content is None:
            if snapshot.path.exists():
                snapshot.path.unlink()
            continue

        snapshot.path.parent.mkdir(parents=True, exist_ok=True)
        snapshot.path.write_text(snapshot.content, encoding="utf-8")


def check_generated_drift() -> list[Path]:
    """Run build generators, report drift, and restore original files."""
    snapshots = _capture_snapshots(_target_files())

    try:
        generate_index.generate()
        generate_styles.generate()
        drifted = _detect_drift(snapshots)
    except Exception:
        _restore_snapshots(snapshots)
        raise
    else:
        _restore_snapshots(snapshots)

    return drifted


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    del argv

    try:
        drifted = check_generated_drift()
    except Exception as exc:
        print(f"Generated drift check failed: {exc}")
        return 1

    if not drifted:
        print("Generated files are up to date")
        return 0

    print("Generated files would change:")
    for path in drifted:
        print(f"- {path.relative_to(REPO_ROOT).as_posix()}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
