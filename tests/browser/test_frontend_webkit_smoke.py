"""WebKit smoke pass over the root gallery and every mature app entry page.

This is a deliberately small cross-engine safety net: it loads each page in
WebKit, asserts the page has no console, page, or network failures (through
``MonitoredPage``), and checks the key landmark elements render. It mirrors the
load checks in ``test_frontend_smoke.py`` and ``test_frontend_apps_smoke.py``
without repeating their full interaction coverage, so CI cost stays bounded.

Select WebKit by exporting ``ARTIFACTS_BROWSER_ENGINE=webkit`` (the
``test-browser-webkit-smoke`` Make target does this).
"""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.browser.frontend_helpers import (
    REPO_ROOT,
    MonitoredPage,
    StaticServer,
    build_real_site,
    discover_app_slugs,
    launch_browser,
)

WEBKIT_ENGINE = "webkit"


@dataclass
class WebkitHarness:
    """One shared built site, static server, and WebKit browser for the smoke pass."""

    server_url: str
    playwright: Any
    browser: Any


@pytest.fixture(scope="module")
def webkit_site(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[WebkitHarness, None, None]:
    """Build and serve the real site once, then launch a single WebKit browser."""
    build_root = tmp_path_factory.mktemp("webkit-smoke-site")
    with pytest.MonkeyPatch.context() as patch:
        deploy_root = build_real_site(build_root, patch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        browser = launch_browser(playwright, engine=WEBKIT_ENGINE)
        try:
            yield WebkitHarness(
                server_url=server.url,
                playwright=playwright,
                browser=browser,
            )
        finally:
            browser.close()


def _app_name(slug: str) -> str:
    return (REPO_ROOT / "apps" / slug / "name.txt").read_text(encoding="utf-8").strip()


def test_root_gallery_loads_in_webkit(webkit_site: WebkitHarness) -> None:
    """The root gallery renders its cards cleanly in WebKit."""
    with MonitoredPage(
        webkit_site.playwright,
        webkit_site.server_url,
        name="webkit-smoke-root",
        browser=webkit_site.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/")

        expect(page.locator("html")).to_have_attribute("data-runtime-status", "ready")
        expect(page.locator("#search-input")).to_be_visible()
        assert page.locator(".artifact-card").count() > 0


@pytest.mark.parametrize("slug", discover_app_slugs())
def test_app_entry_page_loads_in_webkit(webkit_site: WebkitHarness, slug: str) -> None:
    """Each mature app entry page loads and shows its shell cleanly in WebKit."""
    with MonitoredPage(
        webkit_site.playwright,
        webkit_site.server_url,
        name=f"webkit-smoke-{slug}",
        bypass_csp=True,
        browser=webkit_site.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto(f"/apps/{slug}/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        expect(page.locator(".app-header")).to_be_visible()
        expect(page.locator(".page-shell")).to_be_visible()
        assert _app_name(slug) in page.title()
