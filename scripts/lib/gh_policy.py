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
            r"rate limit|submitted too quickly|abuse detection|secondary rate|\b429\b",
            re.IGNORECASE,
        ),
    ),
    (
        "transient",
        re.compile(
            r"502|503|504|timed out|timeout|ECONNRESET|connection reset|"
            r"connection refused|could not resolve host|no such host|network|"
            r"tls handshake|i/o timeout|temporary failure|unexpected eof",
            re.IGNORECASE,
        ),
    ),
    ("forbidden", re.compile(r"Resource not accessible by integration", re.IGNORECASE)),
)

# Idempotent GitHub calls get two retries. The delay grows exponentially and
# includes bounded jitter so concurrent workflows do not retry in lockstep.
DEFAULT_GH_RETRIES = 2
RETRY_BACKOFF_BASE_SECONDS = 0.5
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
