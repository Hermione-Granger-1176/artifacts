"""Shared failure classification and retry backoff for GitHub CLI calls.

Both the workflow helpers and the interactive GitHub CLI wrappers invoke
``gh``. Rate limits fail fast, transient infrastructure failures retry, and all
other errors are final. A blocked GraphQL endpoint is its own kind, and the
interactive wrappers switch to REST instead of retrying.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from typing import Literal

type GhFailureKind = Literal["graphql_unavailable", "rate_limit", "transient", "forbidden", "fatal"]
type RandomFunction = Callable[[], float]

# Rules are checked in order, and the first match wins. GraphQL-unavailable text is
# matched first, and rate-limit text before the forbidden rule, since a rate-limit
# message can also mention HTTP 403.
GH_FAILURE_CLASSIFIERS: tuple[tuple[GhFailureKind, re.Pattern[str]], ...] = (
    ("graphql_unavailable", re.compile(r"GraphQL is not available", re.IGNORECASE)),
    (
        "rate_limit",
        re.compile(
            # Match 429 only as an HTTP status, like the server codes below. A bare
            # 429 also appears in run and line numbers.
            r"rate limit|submitted too quickly|abuse detection|secondary rate|"
            r"\bHTTP 429\b|\b429 too many requests\b",
            re.IGNORECASE,
        ),
    ),
    (
        "transient",
        re.compile(
            # Retries 500, 502, 503, and 504. 501 is not retried. A code matches only
            # as an HTTP status or with its reason phrase, so a bare number such as
            # 502 does not match.
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

# Idempotent GitHub calls get two retries. The delay grows exponentially, with
# bounded jitter.
DEFAULT_GH_RETRIES = 2
RETRY_BACKOFF_BASE_SECONDS = 1.0
RETRY_BACKOFF_CAP_SECONDS = 8.0
RETRY_BACKOFF_JITTER_SECONDS = 0.5


def classify_gh_failure(message: str) -> GhFailureKind:
    """Classify a GitHub CLI failure.

    The kinds are GraphQL-unavailable, rate-limited, transient, forbidden, or fatal.
    """
    for kind, pattern in GH_FAILURE_CLASSIFIERS:
        if pattern.search(message):
            return kind
    return "fatal"


def retry_backoff_seconds(attempt: int, *, random_fn: RandomFunction = random.random) -> float:
    """Return a capped exponential retry delay for a zero-based retry ``attempt``."""
    delay = RETRY_BACKOFF_BASE_SECONDS * (2.0**attempt)
    return min(RETRY_BACKOFF_CAP_SECONDS, delay + random_fn() * RETRY_BACKOFF_JITTER_SECONDS)
