#!/usr/bin/env python3
"""Scaffold a new artifact directory under `apps/`.

Create a new artifact directory under ``apps/`` with the required metadata
files and a minimal HTML starting point.

Usage:
    python scripts/scaffold_artifact.py <artifact-name>
"""

from __future__ import annotations

import sys
from pathlib import Path

from scripts.generate_index import (
    APPS_DIR,
    DESCRIPTION_FILE,
    INDEX_FILE,
    NAME_FILE,
    TAGS_FILE,
    TOOLS_FILE,
    is_kebab_case,
)


def _title_from_slug(slug: str) -> str:
    """Convert a kebab-case slug to a human-readable title."""
    return " ".join(word.capitalize() for word in slug.split("-"))


def _index_template(title: str) -> str:
    """Return a minimal HTML starting point for a new artifact."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
</head>
<body>
    <main>
        <h1>{title}</h1>
        <p>Replace this scaffold with your artifact.</p>
</main>
</body>
</html>
"""


def scaffold_artifact(name: str) -> Path:
    """Create a new artifact scaffold and return the artifact directory path."""
    if not name:
        raise ValueError("Artifact name is required")
    if not is_kebab_case(name):
        raise ValueError("Artifact name must use kebab-case")

    APPS_DIR.mkdir(parents=True, exist_ok=True)
    artifact_dir = APPS_DIR / name
    if artifact_dir.exists():
        raise FileExistsError(f"Artifact directory already exists: {artifact_dir}")

    title = _title_from_slug(name)
    artifact_dir.mkdir()
    (artifact_dir / INDEX_FILE).write_text(_index_template(title), encoding="utf-8")
    (artifact_dir / NAME_FILE).write_text(title + "\n", encoding="utf-8")
    (artifact_dir / DESCRIPTION_FILE).write_text("\n", encoding="utf-8")
    (artifact_dir / TAGS_FILE).write_text("\n", encoding="utf-8")
    (artifact_dir / TOOLS_FILE).write_text("\n", encoding="utf-8")
    return artifact_dir


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for artifact scaffolding."""
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        raise ValueError("Usage: scaffold_artifact.py <artifact-name>")

    artifact_dir = scaffold_artifact(args[0])
    print(f"Created artifact scaffold: {artifact_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except (FileExistsError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
