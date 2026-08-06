"""Shared failure classification and retry backoff for GitHub CLI calls.

Both the workflow helpers and the interactive GitHub CLI wrappers invoke
``gh``. Keeping their retry decisions here makes rate-limit handling
consistent: rate limits always fail fast, transient infrastructure failures
can retry, and all other errors are final.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from typing import Literal

type GhFailureKind = Literal["rate_limit", "transient", "forbidden", "fatal"]
type RandomFunction = Callable[[], float]

# Rules are checked in order. A rate-limit message can also mention HTTP 403,
# so it must win before the permission-specific rule.
GH_FAILURE_CLASSIFIERS: tuple[tuple[GhFailureKind, re.Pattern[str]], ...] = (
    (
        "rate_limit",
        re.compile(
            # 429 needs the same HTTP anchoring as the server codes below: a bare
            # ``429`` also appears in run numbers and line numbers, and a false
            # rate-limit verdict aborts with a misleading "wait for the window
            # to reset" message instead of surfacing the real failure.
            r"rate limit|submitted too quickly|abuse detection|secondary rate|"
            r"\bHTTP 429\b|\b429 too many requests\b",
            re.IGNORECASE,
        ),
    ),
    (
        "transient",
        re.compile(
            # Retry 500, 502, 503, and 504: GitHub returns these for overloaded
            # or proxy-layer failures that usually clear. 501 is excluded on
            # purpose, because "Not Implemented" never becomes available by
            # retrying. Codes only count when the message marks them as an HTTP
            # status or pairs them with their reason phrase; a bare ``502`` would
            # also match line numbers, object ids, and byte counts.
            r"\bHTTP 50[0234]\b|"
            r"\b50[0234] (?:internal server error|bad gateway|"
            r"service unavailable|gateway time-?out)\b|"
            r"timed out|timeout|ECONNRESET|connection reset|"
            r"connection refused|could not resolve host|no such host|network|"
            r"tls handshake|i/o timeout|temporary failure|unexpected eof",
            re.IGNORECASE,
        ),
    ),
    ("forbidden", re.compile(r"Resource not accessible by integration", re.IGNORECASE)),
)

# Idempotent GitHub calls get two retries. The delay grows exponentially and
# includes bounded jitter so concurrent workflows do not retry in lockstep. The
# 1.0s base keeps the first retry a full second out, matching the backoff the
# gh wrappers used before this policy was extracted.
DEFAULT_GH_RETRIES = 2
RETRY_BACKOFF_BASE_SECONDS = 1.0
RETRY_BACKOFF_CAP_SECONDS = 8.0
RETRY_BACKOFF_JITTER_SECONDS = 0.5


def classify_gh_failure(message: str) -> GhFailureKind:
    """Classify a GitHub CLI failure as rate-limited, transient, forbidden, or fatal."""
    for kind, pattern in GH_FAILURE_CLASSIFIERS:
        if pattern.search(message):
            return kind
    return "fatal"


def retry_backoff_seconds(attempt: int, *, random_fn: RandomFunction = random.random) -> float:
    """Return a capped exponential retry delay for a zero-based retry ``attempt``."""
    delay = RETRY_BACKOFF_BASE_SECONDS * (2.0**attempt)
    return min(RETRY_BACKOFF_CAP_SECONDS, delay + random_fn() * RETRY_BACKOFF_JITTER_SECONDS)
