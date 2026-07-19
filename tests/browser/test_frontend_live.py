from __future__ import annotations

import os
import time
import tomllib
from pathlib import Path
from urllib.parse import urljoin

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import expect, sync_playwright

from tests.browser.frontend_helpers import MonitoredPage

LIVE_SITE_URL_ENV = "ARTIFACTS_LIVE_SITE_URL"
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
SHARE_IMAGE_PATH = "assets/social/share-preview.png"
GOTO_ATTEMPTS = 4
GOTO_RETRY_PAUSE_SECONDS = 10.0


def _require_live_site_url() -> str:
    value = os.environ.get(LIVE_SITE_URL_ENV, "").strip()
    if not value:
        pytest.skip(f"Set {LIVE_SITE_URL_ENV} to run live browser verification")
    return value


def _load_canonical_site_url() -> str:
    pyproject = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))
    return pyproject["tool"]["artifacts"]["site_url"].rstrip("/") + "/"


def _goto_until_served(session: MonitoredPage, path: str) -> None:
    """Navigate with retries until the live deployment actually serves the page.

    A freshly published GitHub Pages deployment can time out or serve a 404 or
    its 503 maintenance page for a short window while the CDN warms up, so a
    single navigation right after a deploy is racy. Success requires an actual
    response below 400; a missing response or any error status is retried.
    Failures the monitor recorded during an unserved attempt are dropped before
    the next attempt, so only the attempt that serves the page is judged by
    ``assert_clean()`` at context exit.
    """
    last_failure = "navigation was not attempted"
    for attempt in range(GOTO_ATTEMPTS):
        if attempt:
            time.sleep(GOTO_RETRY_PAUSE_SECONDS)
            session.monitor.reset()
        try:
            response = session.goto(path)
        except PlaywrightError as error:
            last_failure = str(error)
            continue
        if response is not None and response.status < 400:
            return
        last_failure = (
            "no navigation response was returned"
            if response is None
            else f"status {response.status} for {response.url}"
        )
    pytest.fail(f"Live page {path!r} was not served after {GOTO_ATTEMPTS} attempts: {last_failure}")


def test_live_root_page_behaves_correctly() -> None:
    """Test live root page behaves correctly."""
    base_url = _require_live_site_url()
    canonical_site_url = _load_canonical_site_url()
    share_image_prefix = urljoin(canonical_site_url, SHARE_IMAGE_PATH) + "?v="

    with (
        sync_playwright() as playwright,
        MonitoredPage(playwright, base_url, name="live-root-smoke") as session,
    ):
        page = session.page
        assert page is not None
        _goto_until_served(session, "/")

        expect(page.locator("html")).to_have_attribute("data-runtime-status", "ready")
        expect(page.locator('link[rel="canonical"]')).to_have_attribute("href", canonical_site_url)
        expect(page.locator('meta[property="og:url"]')).to_have_attribute(
            "content", canonical_site_url
        )
        expect(page.locator("#search-input")).to_be_visible()
        expect(page.locator(".artifact-card").first).to_be_visible()

        share_image = page.locator('meta[property="og:image"]').get_attribute("content")
        secure_share_image = page.locator('meta[property="og:image:secure_url"]').get_attribute(
            "content"
        )
        twitter_share_image = page.locator('meta[name="twitter:image"]').get_attribute("content")
        assert share_image is not None
        assert secure_share_image is not None
        assert twitter_share_image is not None
        assert share_image.startswith(share_image_prefix)
        assert secure_share_image == share_image
        assert twitter_share_image == share_image

        page.locator(".artifact-card").first.click()
        expect(page.locator("#detail-overlay")).to_have_class("detail-overlay visible open")
        expect(page.locator("#detail-title")).not_to_be_empty()


def test_live_404_page_points_back_to_gallery() -> None:
    """Test live 404 page points back to gallery."""
    base_url = _require_live_site_url()

    with (
        sync_playwright() as playwright,
        MonitoredPage(playwright, base_url, name="live-404-smoke") as session,
    ):
        page = session.page
        assert page is not None
        _goto_until_served(session, "/404.html")

        expect(page.locator("#home-link")).to_be_visible()
        href = page.locator("#home-link").get_attribute("href")
        assert href is not None
        assert href.endswith("/")
