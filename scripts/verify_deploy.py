#!/usr/bin/env python3
"""Verify published deployments by polling for expected HTML and metadata markers.

Fetches a deployed root or preview URL and waits for the expected deploy version
marker to appear in the HTML and the expected commit SHA to appear in
``deploy-metadata.json``. This gives CI a post-deploy check without adding
extra dependencies or relying on GitHub Pages-specific APIs.

Usage:
    python scripts/verify_deploy.py --expected-substring "?v=<sha>" \
        --expected-commit-sha <full-sha>
    python scripts/verify_deploy.py --url https://example.test/pr-preview/pr-42/ \
        --expected-substring "?v=<sha>" --expected-commit-sha <full-sha>
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
DEFAULT_ATTEMPTS = 12
DEFAULT_DELAY_SECONDS = 10.0
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_METADATA_PATH = "deploy-metadata.json"


def _normalize_site_url(value: str) -> str:
    """Return a normalized site URL with a trailing slash."""
    return value.rstrip("/") + "/"


def _load_site_url() -> str:
    """Load the configured site URL from ``pyproject.toml``."""
    if not PYPROJECT_FILE.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {PYPROJECT_FILE}")

    pyproject = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))

    try:
        site_url = pyproject["tool"]["artifacts"]["site_url"]
    except KeyError as exc:
        raise ValueError("Missing tool.artifacts.site_url in pyproject.toml") from exc

    return _normalize_site_url(site_url)


def _fetch_text(url: str, timeout_seconds: float) -> tuple[int, str]:
    """Fetch text content from a deployed URL."""
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        status_code = response.getcode()
        charset = response.headers.get_content_charset("utf-8")
        body = response.read().decode(charset, errors="replace")
    return status_code, body


def _fetch_json(url: str, timeout_seconds: float) -> tuple[int, object]:
    """Fetch JSON content from a deployed URL."""
    status_code, body = _fetch_text(url, timeout_seconds)
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"returned invalid JSON: {exc.msg}") from exc
    return status_code, payload


def _build_cache_busted_url(url: str, attempt: int) -> str:
    """Add a cache-busting query parameter for one verification attempt."""
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    query["artifacts-deploy-check"] = [str(attempt)]
    return urllib.parse.urlunsplit(
        parsed._replace(query=urllib.parse.urlencode(query, doseq=True))
    )


def _validate_deploy_response(
    status_code: int, body: str, expected_substring: str
) -> None:
    """Raise when a fetched deploy response is not the expected version."""
    if status_code != 200:
        raise RuntimeError(f"returned HTTP {status_code}")

    if expected_substring not in body:
        raise RuntimeError(f"did not contain expected marker: {expected_substring}")


def _normalize_metadata_path(value: str) -> str:
    """Return a normalized deploy metadata path without a leading slash."""
    normalized = value.strip().lstrip("/")
    if not normalized:
        raise ValueError("metadata-path must not be empty")
    return normalized


def _build_metadata_url(url: str, metadata_path: str) -> str:
    """Build the deploy metadata URL for a site root or preview URL."""
    return urllib.parse.urljoin(url, metadata_path)


def _validate_metadata_payload(payload: object, expected_commit_sha: str) -> None:
    """Raise when fetched deploy metadata does not match the expected commit SHA."""
    if not isinstance(payload, dict):
        raise RuntimeError("returned non-object deploy metadata")

    commit_sha = payload.get("commit_sha")
    if commit_sha != expected_commit_sha:
        raise RuntimeError(
            "reported commit SHA "
            f"{commit_sha!r} instead of expected {expected_commit_sha!r}"
        )


def verify_deploy(
    url: str,
    expected_substring: str,
    expected_commit_sha: str,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    metadata_path: str = DEFAULT_METADATA_PATH,
) -> None:
    """Wait until the deployed HTML and metadata match the expected deploy."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    normalized_metadata_path = _normalize_metadata_path(metadata_path)
    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        cache_busted_url = _build_cache_busted_url(url, attempt)
        metadata_url = _build_cache_busted_url(
            _build_metadata_url(url, normalized_metadata_path), attempt
        )
        try:
            status_code, body = _fetch_text(cache_busted_url, timeout_seconds)
            _validate_deploy_response(status_code, body, expected_substring)
            metadata_status, payload = _fetch_json(metadata_url, timeout_seconds)
            if metadata_status != 200:
                raise RuntimeError(f"deploy metadata returned HTTP {metadata_status}")
            _validate_metadata_payload(payload, expected_commit_sha)

            logger.info("Verified published deployment at %s", url)
            return
        except (RuntimeError, urllib.error.URLError) as exc:
            last_error = str(exc)
            logger.warning(
                "Deploy verification attempt %s/%s for %s failed: %s",
                attempt,
                attempts,
                url,
                exc,
            )
            if attempt < attempts:
                time.sleep(delay_seconds)

    raise RuntimeError(
        f"Failed to verify deployed URL {url} after {attempts} attempts: {last_error}"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Verify a published site deployment")
    parser.add_argument("--url", help="Published URL to verify")
    parser.add_argument(
        "--expected-substring",
        required=True,
        help="HTML substring that identifies the expected deployment version",
    )
    parser.add_argument(
        "--expected-commit-sha",
        required=True,
        help="Full commit SHA that must appear in deploy metadata",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=DEFAULT_ATTEMPTS,
        help=f"Number of verification attempts (default: {DEFAULT_ATTEMPTS})",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"Delay between attempts in seconds (default: {DEFAULT_DELAY_SECONDS})",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-request timeout in seconds (default: {DEFAULT_TIMEOUT_SECONDS})",
    )
    parser.add_argument(
        "--metadata-path",
        default=DEFAULT_METADATA_PATH,
        help=(
            "Relative path to deploy metadata under the published site "
            f"(default: {DEFAULT_METADATA_PATH})"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    args = parse_args(argv)
    url = _normalize_site_url(args.url) if args.url else _load_site_url()
    verify_deploy(
        url,
        args.expected_substring,
        args.expected_commit_sha,
        attempts=args.attempts,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        metadata_path=args.metadata_path,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except (FileNotFoundError, RuntimeError, ValueError, urllib.error.URLError) as exc:
        logger.error("Deploy verification failed: %s", exc)
        sys.exit(1)
