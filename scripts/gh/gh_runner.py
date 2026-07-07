"""Thin, dependency-injected wrappers around the ``gh`` and ``git`` CLIs.

Every public function accepts ``run_fn`` so tests can inject a fake subprocess
runner and exercise the logic without touching the network or a real
repository. Keeping the GitHub plumbing here means the PR and CI helpers share
one place for repository and pull-request detection, timeouts, and retries.

``gh api`` has no built-in retry and treats a single 5xx, network blip, or
rate-limit response as a hard non-zero exit, so the retry/backoff policy lives
here. Per GitHub's API guidance we retry only transient infrastructure errors
(5xx/network/timeout) with bounded exponential backoff, and we fail fast on
rate limits rather than hammering the API (which can get an integration
banned). Non-idempotent mutations (posting a reply) opt out of retries so a
lost response never double-posts.
"""

from __future__ import annotations

import json
import random
import subprocess
import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlparse

RunFunction = Callable[..., subprocess.CompletedProcess[str]]

# Timeouts (seconds). API calls should answer quickly; failed-log downloads can
# be large, so they get a longer budget.
DEFAULT_TIMEOUT = 30
LOG_TIMEOUT = 120

# Retry budget (extra attempts beyond the first) for idempotent calls, with
# bounded exponential backoff plus jitter.
DEFAULT_RETRIES = 2
BACKOFF_BASE = 1.0
BACKOFF_CAP = 8.0
BACKOFF_JITTER = 0.5

# Substrings (matched case-insensitively against stderr) that mark a response
# as a rate limit (fail fast) or a transient infrastructure error (retry).
_RATE_LIMIT_MARKERS = (
    "rate limit",
    "submitted too quickly",
    "abuse detection",
    "(http 429)",
)
_TRANSIENT_MARKERS = (
    "(http 502)",
    "(http 503)",
    "(http 504)",
    "timeout",
    "timed out",
    "connection reset",
    "connection refused",
    "no such host",
    "tls handshake",
    "i/o timeout",
    "temporary failure",
    "unexpected eof",
)


class GhError(RuntimeError):
    """Raised when a ``gh``/``git`` invocation fails or returns bad data."""


class GhRateLimitError(GhError):
    """Raised when GitHub reports a primary or secondary rate limit.

    Kept distinct from :class:`GhError` so callers never auto-retry it; the
    correct response is to stop and wait for the limit window to reset.
    """


def _label(cmd: list[str]) -> str:
    """Return a short command label for error messages (omits long payloads)."""
    return " ".join(cmd[:3])


def _sleep(seconds: float) -> None:
    """Sleep for ``seconds`` (indirection so tests can stub backoff waits)."""
    time.sleep(seconds)


def _backoff_seconds(attempt: int) -> float:
    """Return the backoff delay (seconds) for a zero-based retry ``attempt``.

    Exponential growth plus jitter, clamped so the result never exceeds
    ``BACKOFF_CAP``. The cap is applied after the jitter to keep that bound.
    """
    delay = BACKOFF_BASE * (2.0**attempt) + random.uniform(0, BACKOFF_JITTER)
    return min(BACKOFF_CAP, delay)


def _classify(detail: str) -> str:
    """Classify a failure's stderr as ``rate_limit``, ``transient``, or ``fatal``."""
    low = detail.lower()
    if any(marker in low for marker in _RATE_LIMIT_MARKERS):
        return "rate_limit"
    if any(marker in low for marker in _TRANSIENT_MARKERS):
        return "transient"
    return "fatal"


def _run(
    cmd: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Run a command with a timeout, retrying transient failures.

    Args:
        cmd: The full command vector (e.g. ``["gh", "api", ...]``).
        run_fn: Optional injected subprocess runner.
        timeout: Per-attempt timeout in seconds.
        retries: Extra attempts allowed for transient failures (5xx, network,
            timeout). Rate limits and other errors are never retried.

    Raises:
        GhRateLimitError: If GitHub reports a rate limit.
        GhError: For any other failure, including exhausted retries.
    """
    runner = run_fn or subprocess.run
    attempt = 0
    while True:
        try:
            result = runner(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            if attempt < retries:
                _sleep(_backoff_seconds(attempt))
                attempt += 1
                continue
            raise GhError(f"{_label(cmd)} timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise GhError(f"Command not found: {cmd[0]} (is it installed?)") from exc
        except OSError as exc:
            raise GhError(f"Failed to run {_label(cmd)}: {exc}") from exc

        if result.returncode == 0:
            return result

        detail = (result.stderr or result.stdout or "").strip()
        kind = _classify(detail)
        if kind == "rate_limit":
            raise GhRateLimitError(
                f"GitHub rate limit hit running {_label(cmd)}: {detail}\n"
                "Wait for the limit window to reset before retrying."
            )
        if kind == "transient" and attempt < retries:
            _sleep(_backoff_seconds(attempt))
            attempt += 1
            continue
        raise GhError(f"{_label(cmd)} failed: {detail}")


def run_gh(
    args: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> str:
    """Run ``gh`` with ``args`` and return its stdout."""
    return _run(["gh", *args], run_fn=run_fn, timeout=timeout, retries=retries).stdout


def run_git(
    args: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> str:
    """Run ``git`` with ``args`` and return its stripped stdout (local, no retry)."""
    return _run(["git", *args], run_fn=run_fn, timeout=timeout).stdout.strip()


def gh_json(
    args: list[str],
    *,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Any:
    """Run ``gh`` with ``args`` and parse its stdout as JSON."""
    stdout = run_gh(args, run_fn=run_fn, timeout=timeout, retries=retries)
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GhError(f"gh returned invalid JSON: {exc}") from exc


def graphql(
    query: str,
    *,
    variables: Mapping[str, object] | None = None,
    run_fn: RunFunction | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> Any:
    """Run a GraphQL ``query`` via ``gh api graphql`` and return its ``data``.

    Args:
        query: The GraphQL document. Reference variables as ``$name``.
        variables: Values bound to the query variables. Integers and booleans
            are passed as typed parameters (``-F``); everything else is passed
            as a string (``-f``).
        run_fn: Optional injected subprocess runner.
        timeout: Per-attempt timeout in seconds.
        retries: Extra attempts for transient failures. Pass ``0`` for
            non-idempotent mutations so a lost response never double-applies.

    Returns:
        The ``data`` object from the GraphQL response.

    Raises:
        GhRateLimitError: If the response reports a rate limit.
        GhError: If the response contains other errors or is missing ``data``.
    """
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in (variables or {}).items():
        # bool is a subclass of int, so both go through -F (typed parameters).
        # gh expects JSON booleans, so serialize bool as lowercase true/false
        # rather than Python's True/False, which gh would send as a string.
        if isinstance(value, bool):
            args += ["-F", f"{key}={str(value).lower()}"]
        elif isinstance(value, int):
            args += ["-F", f"{key}={value}"]
        else:
            args += ["-f", f"{key}={value}"]

    payload = gh_json(args, run_fn=run_fn, timeout=timeout, retries=retries)
    if not isinstance(payload, dict):
        raise GhError("Unexpected GraphQL response shape")
    # gh exits non-zero on GraphQL errors (handled above), but a 200 response
    # can still carry an errors array alongside partial data; catch that too.
    errors = payload.get("errors")
    if errors:
        message = json.dumps(errors)
        # Trust the structured error type first; fall back to string heuristics
        # only when the type is absent or unrecognized.
        rate_limited = any(
            isinstance(error, dict) and error.get("type") == "RATE_LIMITED" for error in errors
        )
        if rate_limited or _classify(message) == "rate_limit":
            raise GhRateLimitError(f"GitHub rate limit reported by GraphQL: {message}")
        raise GhError(f"GraphQL errors: {message}")
    if "data" not in payload:
        raise GhError("GraphQL response missing data")
    return payload["data"]


def resolve_repo(*, run_fn: RunFunction | None = None) -> str:
    """Return the ``owner/name`` slug for the current repository.

    Tries the GitHub-aware ``gh repo view`` first, then falls back to parsing
    the ``origin`` git remote (which also covers the rate-limited case).
    """
    try:
        slug = gh_json(["repo", "view", "--json", "nameWithOwner"], run_fn=run_fn)
        owner_name = str(slug.get("nameWithOwner", "")) if isinstance(slug, dict) else ""
    except GhError:
        owner_name = ""

    if not owner_name:
        owner_name = _repo_from_remote(run_fn=run_fn)

    if not _is_owner_name(owner_name):
        raise GhError("Could not resolve owner/name; set a GitHub remote or run inside a repo.")
    return owner_name


def _repo_from_remote(*, run_fn: RunFunction | None = None) -> str:
    """Extract ``owner/name`` from the ``origin`` remote URL.

    Handles both SSH (``git@github.com:octo/Hello.git``,
    ``ssh://git@github.com:22/octo/Hello.git``) and HTTPS forms. ``owner/name``
    are always the final two path segments, so any leading ``:`` separator or
    host port is skipped.
    """
    try:
        url = run_git(["remote", "get-url", "origin"], run_fn=run_fn)
    except GhError:
        return ""
    remote_path = _github_remote_path(url)
    if not remote_path:
        return ""
    segments = [segment for segment in remote_path.removesuffix(".git").split("/") if segment]
    if len(segments) < 2:
        return ""
    owner_name = "/".join(segments[-2:])
    return owner_name if _is_owner_name(owner_name) else ""


def _github_remote_path(url: str) -> str:
    """Return the path part from an origin URL only when it is hosted on GitHub."""
    if url.startswith("git@github.com:"):
        return url.removeprefix("git@github.com:")

    parsed = urlparse(url)
    if parsed.hostname != "github.com":
        return ""
    return parsed.path


def _is_owner_name(value: str) -> bool:
    """Return whether ``value`` looks like an ``owner/name`` slug."""
    parts = value.split("/")
    return len(parts) == 2 and all(parts)


def current_pr_number(*, run_fn: RunFunction | None = None) -> int:
    """Return the pull-request number for the current branch."""
    try:
        data = gh_json(["pr", "view", "--json", "number"], run_fn=run_fn)
    except GhRateLimitError:
        raise
    except GhError as exc:
        raise GhError("No pull request found for the current branch.") from exc
    try:
        return int(data["number"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GhError("Could not read PR number from gh output.") from exc


def current_branch(*, run_fn: RunFunction | None = None) -> str:
    """Return the current git branch name."""
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"], run_fn=run_fn)
