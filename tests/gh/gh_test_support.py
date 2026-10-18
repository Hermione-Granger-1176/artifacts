"""Shared fakes for the ``scripts.gh`` test suite.

Kept in a dedicated support module (mirroring
``tests/ci/workflow_helpers_test_support.py``) so individual test modules
don't import helpers from one another.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

# The refusal this sandbox returns for any call that needs GraphQL.
GRAPHQL_BLOCKED_MESSAGE = (
    "HTTP 403: GitHub GraphQL is not available from Claude Code sessions; use the REST API "
    "(gh api repos/{owner}/{repo}/...). (https://api.github.com/graphql)"
)


def completed_process(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    """Create a subprocess result for injected runners."""
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


def json_response(payload: object) -> subprocess.CompletedProcess[str]:
    """Create a successful ``gh`` result carrying ``payload`` as JSON."""
    return completed_process(0, json.dumps(payload))


def graphql_blocked() -> subprocess.CompletedProcess[str]:
    """Create the failed ``gh`` result for a GraphQL call in a sandbox that blocks it."""
    return completed_process(1, "", GRAPHQL_BLOCKED_MESSAGE)


class FakeGh:
    """A dispatching fake subprocess runner that records its calls."""

    def __init__(self, routes: list[tuple[Callable[[list[str]], bool], Any]]) -> None:
        self.routes = routes
        self.calls: list[list[str]] = []

    def __call__(self, cmd: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        """Return the response whose predicate matches, or fail the test.

        A ``gh api --input -`` call carries its fields as a JSON body on standard
        input. The fake appends them to the command as ``key=value`` arguments,
        so routes and assertions match a body field the same way as a query field.
        """
        command = list(cmd)
        if "--input" in command and isinstance(kwargs.get("input"), str):
            command += body_arguments(json.loads(str(kwargs["input"])))
        self.calls.append(command)
        for predicate, response in self.routes:
            if predicate(command):
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"unexpected command: {command}")


def body_arguments(body: dict[str, Any]) -> list[str]:
    """Return a JSON request body as ``key=value`` arguments, with ``key[]=item`` for lists."""
    arguments: list[str] = []
    for key, value in body.items():
        items = value if isinstance(value, list) else [value]
        suffix = "[]" if isinstance(value, list) else ""
        for item in items:
            text = str(item).lower() if isinstance(item, bool) else str(item)
            arguments.append(f"{key}{suffix}={text}")
    return arguments


def rest(method: str, endpoint: str, *needles: str) -> Callable[[list[str]], bool]:
    """Build a predicate matching one ``gh api`` REST call by method and endpoint."""
    return lambda cmd: (
        cmd[:2] == ["gh", "api"]
        and cmd[2:4] == ["--method", method]
        and cmd[4] == endpoint
        and all(needle in cmd for needle in needles)
    )


def sandbox_routes(slug: str = "o/r") -> list[tuple[Callable[[list[str]], bool], Any]]:
    """Build the routes of a sandbox that blocks every GraphQL-backed ``gh`` command.

    ``gh pr``, ``gh issue``, ``gh repo``, and ``gh api graphql`` all refuse with the
    GraphQL-unavailable error, while ``git remote`` names ``slug`` so the REST
    fallback can address the repository.
    """
    return [
        (
            lambda cmd: (
                cmd[:2] in (["gh", "pr"], ["gh", "issue"], ["gh", "repo"])
                or cmd[:3] == ["gh", "api", "graphql"]
            ),
            graphql_blocked(),
        ),
        (has("remote"), completed_process(0, f"https://github.com/{slug}.git\n")),
    ]


def has(*needles: str) -> Callable[[list[str]], bool]:
    """Build a predicate matching commands that contain all needles as arguments."""
    return lambda cmd: all(needle in cmd for needle in needles)
