from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)

SleepFunction = Callable[[float], object]
RunGhApiFunction = Callable[..., str]


class SubprocessModule(Protocol):
    """Structural type for the ``subprocess`` module seam used in retries."""

    def run(
        self,
        args: list[str],
        *,
        capture_output: bool,
        text: bool,
        check: bool,
        timeout: float,
    ) -> subprocess.CompletedProcess[str]:
        """Run a command and return its completed process, matching ``subprocess.run``."""
        raise NotImplementedError(args, capture_output, text, check, timeout)


GH_API_TIMEOUT_SECONDS = 15
GH_API_MAX_ATTEMPTS = 3
GH_API_RETRY_DELAY_SECONDS = 0.5
GH_API_RETRYABLE_ERROR_PATTERN = re.compile(
    r"429|502|503|504|timed out|timeout|ECONNRESET|connection reset|network",
    re.IGNORECASE,
)
GH_API_FORBIDDEN_ERROR_PATTERN = re.compile(
    r"Resource not accessible by integration",
    re.IGNORECASE,
)


def is_retryable_gh_api_failure(message: str) -> bool:
    """Return True when ``gh api`` failed with a likely transient error."""
    return bool(GH_API_RETRYABLE_ERROR_PATTERN.search(message))


def is_forbidden_gh_api_failure(message: str) -> bool:
    """Return True when ``gh api`` failed with a permission-related 403."""
    return bool(GH_API_FORBIDDEN_ERROR_PATTERN.search(message))


def _build_failure_message(description: str, stderr: str, required_permission: str | None) -> str:
    """Return the error message for a failed ``gh api`` call."""
    if not is_forbidden_gh_api_failure(stderr):
        return f"gh api {description} failed: {stderr}"
    if required_permission:
        return (
            f"gh api {description} failed: HTTP 403. The GitHub App minting "
            f"this token likely lacks permission '{required_permission}'. "
            f"Raw: {stderr}"
        )
    return (
        f"gh api {description} failed: HTTP 403. Token likely lacks required "
        f"permission. Raw: {stderr}"
    )


def _run_gh_command(
    command: list[str],
    *,
    description: str,
    max_attempts: int = GH_API_MAX_ATTEMPTS,
    retry_delay_seconds: float = GH_API_RETRY_DELAY_SECONDS,
    sleep_fn: SleepFunction = time.sleep,
    subprocess_module: SubprocessModule = subprocess,
    timeout_seconds: int = GH_API_TIMEOUT_SECONDS,
    required_permission: str | None = None,
) -> str:
    """Run one ``gh`` command with bounded retries and contextual failures."""
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess_module.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            last_error = f"timed out after {timeout_seconds} seconds while {description}"
            if attempt < max_attempts:
                logger.warning(
                    "Retrying gh api for %s after attempt %d/%d timed out.",
                    description,
                    attempt,
                    max_attempts,
                )
                sleep_fn(retry_delay_seconds * attempt)
                continue
            raise RuntimeError(f"gh api {description} failed: {last_error}") from exc

        if result.returncode == 0:
            return result.stdout

        stderr = result.stderr.strip() or result.stdout.strip() or "unknown gh api error"
        last_error = stderr
        if attempt < max_attempts and is_retryable_gh_api_failure(stderr):
            logger.warning(
                "Retrying gh api for %s after attempt %d/%d failed: %s",
                description,
                attempt,
                max_attempts,
                stderr,
            )
            sleep_fn(retry_delay_seconds * attempt)
            continue

        raise RuntimeError(_build_failure_message(description, stderr, required_permission))

    raise RuntimeError(f"gh api {description} failed: {last_error or 'unknown error'}")


def run_gh_api(
    endpoint: str,
    *,
    paginate: list[str],
    jq_expr: str,
    description: str,
    max_attempts: int = GH_API_MAX_ATTEMPTS,
    retry_delay_seconds: float = GH_API_RETRY_DELAY_SECONDS,
    sleep_fn: SleepFunction = time.sleep,
    subprocess_module: SubprocessModule = subprocess,
    timeout_seconds: int = GH_API_TIMEOUT_SECONDS,
    required_permission: str | None = None,
) -> str:
    """Run ``gh api`` with bounded retries, timeout, and contextual failures.

    ``required_permission`` names the GitHub App installation permission the
    endpoint needs (e.g. ``"administration: read"``). When the call fails with
    ``Resource not accessible by integration``, the permission is surfaced in
    the raised error so a 403 points directly at the missing grant.
    """
    command = ["gh", "api", endpoint, *paginate, "--jq", jq_expr]
    return _run_gh_command(
        command,
        description=description,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
        sleep_fn=sleep_fn,
        subprocess_module=subprocess_module,
        timeout_seconds=timeout_seconds,
        required_permission=required_permission,
    )


def run_gh_api_json(
    endpoint: str,
    *,
    description: str,
    run_gh_api_fn: RunGhApiFunction = run_gh_api,
    required_permission: str | None = None,
) -> object:
    """Fetch JSON from ``gh api`` and parse it into a Python object."""
    raw = run_gh_api_fn(
        endpoint,
        paginate=[],
        jq_expr=".",
        description=description,
        required_permission=required_permission,
    )
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh api {description} returned invalid JSON") from exc


def gh_escape_data_value(value: str) -> str:
    """Escape one value for ``gh api -f`` form usage.

    The GitHub CLI treats ``@`` specially for file reads. Prefix a literal ``@``
    with a backslash so titles/bodies can safely round-trip through ``gh api``.
    """
    if value.startswith("@"):
        return f"\\{value}"
    return value


def run_gh_api_form(
    endpoint: str,
    *,
    method: str,
    fields: list[tuple[str, str]],
    description: str,
    jq_expr: str = "",
    max_attempts: int = GH_API_MAX_ATTEMPTS,
    retry_delay_seconds: float = GH_API_RETRY_DELAY_SECONDS,
    sleep_fn: SleepFunction = time.sleep,
    subprocess_module: SubprocessModule = subprocess,
    timeout_seconds: int = GH_API_TIMEOUT_SECONDS,
    required_permission: str | None = None,
) -> str:
    """Run ``gh api`` with ``-f`` form fields for mutations or filtered reads.

    See :func:`run_gh_api` for the semantics of ``required_permission``; the
    same 403 enrichment applies to mutations (e.g. issue lifecycle calls that
    need ``issues: write``).
    """
    command = ["gh", "api", "-X", method, endpoint]
    for key, value in fields:
        command.extend(["-f", f"{key}={gh_escape_data_value(value)}"])
    if jq_expr:
        command.extend(["--jq", jq_expr])
    return _run_gh_command(
        command,
        description=description,
        max_attempts=max_attempts,
        retry_delay_seconds=retry_delay_seconds,
        sleep_fn=sleep_fn,
        subprocess_module=subprocess_module,
        timeout_seconds=timeout_seconds,
        required_permission=required_permission,
    )
