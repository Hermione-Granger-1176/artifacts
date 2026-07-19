from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from tests.browser.frontend_helpers import (
    MonitoredPage,
    assert_minimum_contrast,
    assert_no_blocking_axe_violations,
    run_axe,
    selected_app_slugs,
)

if TYPE_CHECKING:
    from tests.browser.conftest import AppBrowserHarness


def _app_path(slug: str) -> str:
    return f"/apps/{slug}/"


@pytest.mark.parametrize("slug", selected_app_slugs())
def test_app_pages_have_no_blocking_axe_violations(
    app_browser: AppBrowserHarness, slug: str
) -> None:
    """Test app pages have no blocking axe violations."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name=f"app-a11y-{slug}",
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto(_app_path(slug))
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        results = run_axe(page, include=[".app-header", ".page-shell"])
        assert_no_blocking_axe_violations(results)
        assert_minimum_contrast(page, "#theme-toggle", minimum_ratio=4.5)

        if slug == "loan-amortization":
            assert_minimum_contrast(page, "#btnAdd", minimum_ratio=4.5)
            page.locator("#theme-toggle").click()
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            expect(page.locator('meta[name="theme-color"]')).to_have_attribute(
                "content", "rgb(20, 20, 20)"
            )
            assert_minimum_contrast(page, "#btnAdd", minimum_ratio=4.5)

        if slug == "tokenizer-explorer":
            assert_minimum_contrast(page, "#tabs button.active", minimum_ratio=4.5)
            page.locator("#pick-token").click()
            expect(page.locator("#token-pills .pill.winner")).to_be_visible()
            assert_minimum_contrast(page, "#token-pills .pill.winner", minimum_ratio=4.5)
            page.locator("#theme-toggle").click()
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            expect(page.locator('meta[name="theme-color"]')).to_have_attribute(
                "content", "rgb(20, 20, 20)"
            )
            assert_minimum_contrast(page, "#tabs button.active", minimum_ratio=4.5)
            page.locator("#pick-token").click()
            expect(page.locator("#token-pills .pill.winner")).to_be_visible()
            assert_minimum_contrast(page, "#token-pills .pill.winner", minimum_ratio=4.5)
