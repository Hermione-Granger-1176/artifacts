"""Shared fixtures for the lint script tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def scanned_directories(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record every directory the lint walkers open, in scan order.

    Recording at ``os.scandir`` (which ``Path.walk`` calls once per directory it
    descends into) lets a test check that ignored directories are never opened,
    not only that their files are missing from the result.
    """
    recorded: list[Path] = []
    real_scandir = os.scandir

    def recording_scandir(path: Any = os.curdir) -> Any:
        """Record one scanned directory, then delegate to the real scandir."""
        recorded.append(Path(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", recording_scandir)
    return recorded
