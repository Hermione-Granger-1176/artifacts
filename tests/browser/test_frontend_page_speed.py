"""Page-speed budget for the gallery and every app, measured in Chromium.

Each page is opened in a fresh browser context, as a first visit with an empty
cache, from the assembled site that GitHub Pages serves. A page counts as
loaded when its runtime marks the document ready
(``data-runtime-status="ready"``), which happens only after the page's own
script has rendered it. The median over several visits must stay under an
absolute budget, so a single slow visit cannot fail the check on its own.

The budget is roughly twice the calibrated time on the hosted CI runner. It
catches a page that becomes much slower, such as a blocking script, a large
synchronous computation at startup, or a render loop, without failing on
ordinary runner noise. ``make test-page-speed`` runs it; ``budget_ms=`` and
``runs=`` override the defaults for a local investigation.
"""

from __future__ import annotations

import os
import statistics
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from tests.browser.frontend_helpers import (
    StaticServer,
    build_real_site,
    discover_app_slugs,
    launch_browser,
)

BUDGET_ENV = "ARTIFACTS_PAGE_SPEED_BUDGET_MS"
RUNS_ENV = "ARTIFACTS_PAGE_SPEED_RUNS"
SUMMARY_ENV = "GITHUB_STEP_SUMMARY"
DEFAULT_BUDGET_MS = 1000.0
DEFAULT_RUNS = 5
READY_TIMEOUT_MS = 30_000

# Records the moment, relative to navigation start, at which the runtime marks
# the document ready. It runs before the <html> element exists, so it observes
# the whole document for the attribute change.
READY_PROBE = """
new MutationObserver(() => {
  if (
    document.documentElement?.dataset.runtimeStatus === "ready" &&
    window.__PAGE_READY_MS__ === undefined
  ) {
    window.__PAGE_READY_MS__ = performance.now();
  }
}).observe(document, {
  subtree: true,
  attributes: true,
  attributeFilter: ["data-runtime-status"],
});
"""


@dataclass
class SpeedHarness:
    """One built site, its static server, and a Chromium browser."""

    server_url: str
    browser: Any


def _positive_number(name: str, default: float) -> float:
    """Return a positive number from the environment, or ``default`` when unset."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    value = float(raw)
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {raw}")
    return value


@pytest.fixture(scope="module")
def speed_site(tmp_path_factory: pytest.TempPathFactory) -> Generator[SpeedHarness, None, None]:
    """Build and serve the assembled site once, then launch Chromium."""
    build_root = tmp_path_factory.mktemp("page-speed-site")
    with pytest.MonkeyPatch.context() as patch:
        deploy_root = build_real_site(build_root, patch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        browser = launch_browser(playwright, engine="chromium")
        try:
            yield SpeedHarness(server_url=server.url, browser=browser)
        finally:
            browser.close()


def time_to_ready(harness: SpeedHarness, path: str) -> float:
    """Return milliseconds from navigation start to the ready mark on a first visit."""
    context = harness.browser.new_context()
    try:
        page = context.new_page()
        page.add_init_script(READY_PROBE)
        page.goto(f"{harness.server_url}{path}", wait_until="commit")
        page.wait_for_function(
            "() => window.__PAGE_READY_MS__ !== undefined", timeout=READY_TIMEOUT_MS
        )
        return float(page.evaluate("() => window.__PAGE_READY_MS__"))
    finally:
        context.close()


def _report(path: str, timings: list[float], median: float, budget: float) -> None:
    """Print the timings, and add a row to the CI step summary when there is one."""
    runs = ", ".join(f"{timing:.0f}" for timing in timings)
    line = f"{path}: median {median:.0f} ms (budget {budget:.0f} ms; runs {runs})"
    print(line)
    summary = os.environ.get(SUMMARY_ENV, "").strip()
    if summary:
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(f"- Page speed {line}\n")


@pytest.mark.parametrize("path", ["/", *(f"/apps/{slug}/" for slug in discover_app_slugs())])
def test_page_reaches_ready_within_budget(speed_site: SpeedHarness, path: str) -> None:
    """The median first-visit time to the ready mark stays under the budget."""
    budget = _positive_number(BUDGET_ENV, DEFAULT_BUDGET_MS)
    runs = int(_positive_number(RUNS_ENV, DEFAULT_RUNS))
    timings = [time_to_ready(speed_site, path) for _ in range(runs)]
    median = statistics.median(timings)

    _report(path, timings, median, budget)

    assert median <= budget, (
        f"{path} took a median {median:.0f} ms to become ready, over the {budget:.0f} ms budget "
        f"(runs: {', '.join(f'{timing:.0f}' for timing in timings)})"
    )
