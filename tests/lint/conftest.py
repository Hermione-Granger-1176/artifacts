"""Shared fixtures for the lint script tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def scanned_directories(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record every directory the lint walkers open, in scan order.

    Asserting on returned paths only proves ignored files were filtered out of
    the result. It cannot tell a walker that never entered ``node_modules``
    apart from one that read the whole tree and discarded it afterwards, and
    reading the tree is the expensive half. Recording at ``os.scandir`` (which
    ``Path.walk`` calls once per directory it descends into) makes the skip
    itself observable.
    """
    recorded: list[Path] = []
    real_scandir = os.scandir

    def recording_scandir(path: Any = os.curdir) -> Any:
        """Record one scanned directory, then delegate to the real scandir."""
        recorded.append(Path(path))
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", recording_scandir)
    return recorded
