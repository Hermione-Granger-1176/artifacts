"""Shared fakes for the ``scripts.gh`` test suite.

Kept in a dedicated support module (mirroring
``tests/ci/workflow_helpers_test_support.py``) so individual test modules
don't import helpers from one another.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from typing import Any


def completed_process(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Create a subprocess result for injected runners."""
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class FakeGh:
    """A dispatching fake subprocess runner that records its calls."""

    def __init__(self, routes: list[tuple[Callable[[list[str]], bool], Any]]) -> None:
        self.routes = routes
        self.calls: list[list[str]] = []

    def __call__(
        self, cmd: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        """Return the response whose predicate matches, or fail the test."""
        command = list(cmd)
        self.calls.append(command)
        for predicate, response in self.routes:
            if predicate(command):
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected command: {command}")


def has(*needles: str) -> Callable[[list[str]], bool]:
    """Build a predicate matching commands that contain all needles as arguments."""
    return lambda cmd: all(needle in cmd for needle in needles)
