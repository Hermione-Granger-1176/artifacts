"""Shared fixtures for the ``scripts.gh`` test suite."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from scripts.gh import gh_runner

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _fresh_graphql_verdict() -> Iterator[None]:
    """Start and end every test with GraphQL assumed reachable.

    A GraphQL-unavailable verdict is remembered for the life of the process, so
    a test that triggers one would otherwise send every later test down the REST
    path.
    """
    gh_runner.reset_graphql_availability()
    yield
    gh_runner.reset_graphql_availability()


@pytest.fixture(autouse=True)
def _no_repo_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a ``GH_REPO`` set in the developer's shell from redirecting test calls."""
    monkeypatch.delenv("GH_REPO", raising=False)
