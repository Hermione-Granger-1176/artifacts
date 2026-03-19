#!/usr/bin/env python3
"""
Verify Published Deployments

Fetches a deployed root or preview URL and waits for the expected deploy version
marker to appear in the HTML. This gives CI a post-deploy check without adding
extra dependencies or relying on GitHub Pages-specific APIs.

Usage:
    python scripts/verify_deploy.py --expected-substring "?v=<sha>"
    python scripts/verify_deploy.py --url https://example.test/pr-preview/pr-42/ \
        --expected-substring "?v=<sha>"
"""

from __future__ import annotations

import argparse
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


def verify_deploy(
    url: str,
    expected_substring: str,
    *,
    attempts: int = DEFAULT_ATTEMPTS,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> None:
    """Wait until the deployed HTML contains the expected marker."""

    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last_error: str | None = None
    for attempt in range(1, attempts + 1):
        parsed = urllib.parse.urlsplit(url)
        query = urllib.parse.parse_qs(parsed.query)
        query["artifacts-deploy-check"] = [str(attempt)]
        cache_busted_url = urllib.parse.urlunsplit(
            parsed._replace(query=urllib.parse.urlencode(query, doseq=True))
        )
        try:
            status_code, body = _fetch_text(cache_busted_url, timeout_seconds)
            if status_code != 200:
                raise RuntimeError(f"returned HTTP {status_code}")
            if expected_substring not in body:
                raise RuntimeError(
                    f"did not contain expected marker: {expected_substring}"
                )

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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    url = _normalize_site_url(args.url) if args.url else _load_site_url()
    verify_deploy(
        url,
        args.expected_substring,
        attempts=args.attempts,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except (FileNotFoundError, RuntimeError, ValueError, urllib.error.URLError) as exc:
        logger.error("Deploy verification failed: %s", exc)
        sys.exit(1)
