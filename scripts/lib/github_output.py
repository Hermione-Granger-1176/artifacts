"""Record step outputs for GitHub Actions workflows."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

GITHUB_OUTPUT_ENV = "GITHUB_OUTPUT"


def report_checked(
    output_name: str, reached_verdict: bool, *, env: Mapping[str, str] | None = None
) -> None:
    """Append ``<output_name>=true|false`` to the ``GITHUB_OUTPUT`` file when one is set.

    Local runs have no output file, so they record nothing. The value says
    whether an audit reached a trustworthy verdict, which keeps an API failure
    distinct from a failing verdict.
    """
    path = (os.environ if env is None else env).get(GITHUB_OUTPUT_ENV)
    if not path:
        return
    value = "true" if reached_verdict else "false"
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write(f"{output_name}={value}\n")
