#!/usr/bin/env python3
"""Shared helpers for reading ``[tool.artifacts]`` settings from ``pyproject.toml``."""

from __future__ import annotations

import tomllib
from pathlib import Path


def load_artifacts_config(pyproject_file: Path) -> dict[str, object]:
    """Load the ``[tool.artifacts]`` table from a ``pyproject.toml`` file."""
    if not pyproject_file.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {pyproject_file}")

    pyproject = tomllib.loads(pyproject_file.read_text(encoding="utf-8"))

    tool_config = pyproject.get("tool")
    if not isinstance(tool_config, dict):
        return {}

    artifacts_config = tool_config.get("artifacts")
    if artifacts_config is None:
        return {}

    if not isinstance(artifacts_config, dict):
        raise ValueError("[tool.artifacts] must be a table in pyproject.toml")

    return artifacts_config


def load_artifacts_setting(pyproject_file: Path, key: str) -> str:
    """Load one string setting from ``[tool.artifacts]``."""
    artifacts_config = load_artifacts_config(pyproject_file)
    try:
        value = artifacts_config[key]
    except KeyError as exc:
        raise ValueError(f"Missing tool.artifacts.{key} in pyproject.toml") from exc

    if not isinstance(value, str):
        raise ValueError(f"tool.artifacts.{key} must be a string")

    return value
