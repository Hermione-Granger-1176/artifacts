#!/usr/bin/env python3
"""Repin tag-based GitHub Actions references to full commit SHAs.

This module rewrites ``uses:`` references across workflow files and composite
action definitions so every third-party action is pinned to an immutable
commit SHA (with the original tag preserved as a trailing comment). Local
``./`` actions, ``docker://`` images, expression refs, and references that are
already pinned to a 40-character SHA are left untouched.

The commit SHA for each ``owner/repo@ref`` pair is resolved through the GitHub
commits API using the token in the ``GH_TOKEN`` environment variable. Lookups
are cached per ``owner/repo@ref`` and retried a bounded number of times with a
simple linear backoff so transient network failures do not abort the refresh.

For normal use, prefer ``make refresh-action-shas`` over calling this module
directly.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast
from urllib.request import Request, urlopen

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
ACTIONS_DIR = REPO_ROOT / ".github" / "actions"

# Match ``uses:`` lines in both list form (``- uses: x@ref``) and mapping form
# (``uses: x@ref`` under a named step). The action and ref are captured so the
# ref can be rewritten to a resolved SHA while the surrounding text is kept.
USES_PATTERN = re.compile(r"^(\s*(?:-\s*)?uses:\s*)([^@\s]+)@([^\s#]+)(.*)$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")

GITHUB_API_URL = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 15
MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 0.25


class HttpResponse(Protocol):
    """Structural type for the file-like object returned by ``urlopen``."""

    def read(self, amt: int | None = ...) -> bytes:
        """Return response bytes, matching ``HTTPResponse.read``."""
        raise NotImplementedError(amt)


class ResponseContext(Protocol):
    """Structural type for the context manager ``urlopen`` returns."""

    def __enter__(self) -> HttpResponse:
        """Enter the response context and expose the readable response."""
        raise NotImplementedError

    def __exit__(self, *args: object) -> None:
        """Exit the response context."""
        raise NotImplementedError


class UrlOpenFn(Protocol):
    """Structural type for the ``urlopen`` seam used when resolving SHAs."""

    def __call__(self, request: Request, *, timeout: float) -> ResponseContext:
        """Open the request and return a response context manager."""
        raise NotImplementedError(request, timeout)


class ShaResolver(Protocol):
    """Structural type for objects that resolve an action ref to a commit SHA."""

    def resolve(self, action: str, ref: str) -> str:
        """Return the commit SHA for ``action`` at ``ref``."""
        raise NotImplementedError(action, ref)


def _default_urlopen(request: Request, *, timeout: float) -> ResponseContext:
    """Open ``request`` with the standard library ``urlopen``."""
    return cast("ResponseContext", urlopen(request, timeout=timeout))


def _commit_sha(payload: object) -> str:
    """Return the commit SHA from a GitHub commits API payload."""
    if isinstance(payload, dict) and isinstance(payload.get("sha"), str):
        return cast("str", payload["sha"])
    raise RuntimeError("GitHub commits API response did not include a commit SHA")


class ActionShaResolver:
    """Resolve ``owner/repo@ref`` pairs to commit SHAs with caching and retries."""

    def __init__(
        self,
        *,
        token: str,
        urlopen_fn: UrlOpenFn = _default_urlopen,
        sleep_fn: Callable[[float], object] = time.sleep,
        timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        max_attempts: int = MAX_ATTEMPTS,
        backoff_seconds: float = RETRY_BACKOFF_SECONDS,
    ) -> None:
        """Store the token and injectable network and retry collaborators."""
        self._token = token
        self._urlopen_fn = urlopen_fn
        self._sleep_fn = sleep_fn
        self._timeout_seconds = timeout_seconds
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds
        self._cache: dict[str, str] = {}

    def resolve(self, action: str, ref: str) -> str:
        """Return the commit SHA for ``action`` at ``ref``, caching the result."""
        repo = "/".join(action.split("/")[:2])
        key = f"{repo}@{ref}"
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        sha = self._fetch(repo, ref)
        self._cache[key] = sha
        return sha

    def _fetch(self, repo: str, ref: str) -> str:
        """Fetch the commit SHA for ``repo@ref`` with bounded retries."""
        request = Request(
            f"{GITHUB_API_URL}/repos/{repo}/commits/{ref}",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            },
        )
        last_error: object = "no attempts were made"
        for attempt in range(1, self._max_attempts + 1):
            try:
                with self._urlopen_fn(request, timeout=self._timeout_seconds) as response:
                    payload = json.load(response)
                return _commit_sha(payload)
            except Exception as error:  # any failure is retried within the attempt budget
                last_error = error
                if attempt < self._max_attempts:
                    self._sleep_fn(attempt * self._backoff_seconds)
                    continue
                raise
        raise RuntimeError(f"Failed to resolve {repo}@{ref}: {last_error}")


def _should_skip(action: str, ref: str) -> bool:
    """Return whether a ``uses:`` reference should be left unchanged."""
    if action.startswith(("./", "docker://")):
        return True
    if "${{" in action or "${{" in ref:
        return True
    return bool(SHA_PATTERN.fullmatch(ref))


def rewrite_line(line: str, resolver: ShaResolver) -> str | None:
    """Return the rewritten ``uses:`` line, or None when it is unchanged."""
    match = USES_PATTERN.match(line)
    if match is None:
        return None
    prefix, action, ref, _suffix = match.groups()
    if _should_skip(action, ref):
        return None
    sha = resolver.resolve(action, ref)
    return f"{prefix}{action}@{sha} # {ref}"


def rewrite_file(path: Path, resolver: ShaResolver) -> bool:
    """Rewrite pinned refs in one file, returning whether it changed."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    new_lines: list[str] = []
    updated = False
    for line in lines:
        rewritten = rewrite_line(line, resolver)
        if rewritten is None:
            new_lines.append(line)
        else:
            new_lines.append(rewritten)
            updated = True
    if updated:
        path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    return updated


def iter_target_files(workflows_dir: Path, actions_dir: Path) -> list[Path]:
    """Return workflow files and composite action definitions to scan."""
    workflow_files = sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml"))
    action_files = sorted(actions_dir.glob("*/action.yml")) + sorted(
        actions_dir.glob("*/action.yaml")
    )
    return workflow_files + action_files


def refresh_action_shas(
    *,
    resolver: ShaResolver,
    files: Iterable[Path],
) -> list[Path]:
    """Rewrite every target file, returning the files that changed."""
    return [path for path in files if rewrite_file(path, resolver)]


def _build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the module CLI."""
    return argparse.ArgumentParser(
        description="Repin tag-based GitHub Actions references to commit SHAs",
    )


def main(argv: list[str] | None = None) -> int:
    """Resolve and rewrite pinned action references across the repository."""
    _build_parser().parse_args(argv)
    token = os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN is required")
    resolver = ActionShaResolver(token=token)
    files = iter_target_files(WORKFLOWS_DIR, ACTIONS_DIR)
    updated = refresh_action_shas(resolver=resolver, files=files)
    for path in updated:
        print(f"Updated {path.relative_to(REPO_ROOT)}")
    if not updated:
        print("No action references needed updating")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
