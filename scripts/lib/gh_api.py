from __future__ import annotations

import json
import re
import subprocess
import sys
import time

GH_API_TIMEOUT_SECONDS = 15
GH_API_MAX_ATTEMPTS = 3
GH_API_RETRY_DELAY_SECONDS = 0.5
GH_API_RETRYABLE_ERROR_PATTERN = re.compile(
    r"429|502|503|504|timed out|timeout|ECONNRESET|connection reset|network",
    re.IGNORECASE,
)


def is_retryable_gh_api_failure(message: str) -> bool:
    """Return True when ``gh api`` failed with a likely transient error."""
    return bool(GH_API_RETRYABLE_ERROR_PATTERN.search(message))


def run_gh_api(
    endpoint: str,
    *,
    paginate: list[str],
    jq_expr: str,
    description: str,
    max_attempts=GH_API_MAX_ATTEMPTS,
    retry_delay_seconds=GH_API_RETRY_DELAY_SECONDS,
    sleep_fn=time.sleep,
    subprocess_module=subprocess,
    timeout_seconds=GH_API_TIMEOUT_SECONDS,
) -> str:
    """Run ``gh api`` with bounded retries, timeout, and contextual failures."""
    command = ["gh", "api", endpoint, *paginate, "--jq", jq_expr]
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
            last_error = (
                f"timed out after {timeout_seconds} seconds while {description}"
            )
            if attempt < max_attempts:
                print(
                    f"Retrying gh api for {description} after attempt "
                    f"{attempt}/{max_attempts} timed out.",
                    file=sys.stderr,
                )
                sleep_fn(retry_delay_seconds * attempt)
                continue
            raise RuntimeError(f"gh api {description} failed: {last_error}") from exc

        if result.returncode == 0:
            return result.stdout

        stderr = (
            result.stderr.strip() or result.stdout.strip() or "unknown gh api error"
        )
        last_error = stderr
        if attempt < max_attempts and is_retryable_gh_api_failure(stderr):
            print(
                f"Retrying gh api for {description} after attempt "
                f"{attempt}/{max_attempts} failed: {stderr}",
                file=sys.stderr,
            )
            sleep_fn(retry_delay_seconds * attempt)
            continue

        raise RuntimeError(f"gh api {description} failed: {stderr}")

    raise RuntimeError(f"gh api {description} failed: {last_error or 'unknown error'}")


def run_gh_api_json(
    endpoint: str,
    *,
    description: str,
    run_gh_api_fn=run_gh_api,
) -> object:
    """Fetch JSON from ``gh api`` and parse it into a Python object."""
    raw = run_gh_api_fn(endpoint, paginate=[], jq_expr=".", description=description)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gh api {description} returned invalid JSON") from exc
