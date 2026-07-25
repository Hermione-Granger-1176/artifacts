"""Shared constants for lint scripts."""

from __future__ import annotations

# Directories the lint walkers never descend into. Every ignored directory in
# .gitignore belongs here: an ignored tree holds generated or vendored content
# that is not ours to lint, and walking one is slow and produces false failures
# (the extracted Debian packages under .playwright/ are hundreds of megabytes).
# tests/lint/test_skip_directories.py fails if .gitignore grows an entry that is
# missing here, so this list cannot silently fall behind.
SKIP_DIRECTORIES = frozenset(
    {
        ".artifacts",
        ".claudeplans",
        ".claudeprojects",
        ".git",
        ".idea",
        ".mypy_cache",
        ".playwright",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        ".vscode",
        "__pycache__",
        "_site",
        "build",
        "coverage",
        "dist",
        "htmlcov",
        "node_modules",
        "test-results",
        "vendor",
    }
)
