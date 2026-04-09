"""Shared constants for lint scripts."""

from __future__ import annotations

SKIP_DIRECTORIES = frozenset(
    {
        ".git",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "_site",
        "build",
        "dist",
        "node_modules",
    }
)
