from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.browser.frontend_helpers import (
    MonitoredPage,
    StaticServer,
    assert_minimum_contrast,
    assert_no_blocking_axe_violations,
    build_real_site,
    run_axe,
    selected_app_slugs,
)


def _app_path(slug: str) -> str:
    return f"/apps/{slug}/"


@pytest.mark.parametrize("slug", selected_app_slugs())
def test_app_pages_have_no_blocking_axe_violations(tmp_path: Path, monkeypatch, slug: str) -> None:
    """Test app pages have no blocking axe violations."""
    deploy_root = build_real_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name=f"app-a11y-{slug}", bypass_csp=True) as session,
    ):
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
            assert_minimum_contrast(page, "#tabs .tab.active", minimum_ratio=4.5)
            assert_minimum_contrast(page, "#token-pills .pill.winner", minimum_ratio=4.5)
            page.locator("#theme-toggle").click()
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            expect(page.locator('meta[name="theme-color"]')).to_have_attribute(
                "content", "rgb(20, 20, 20)"
            )
            assert_minimum_contrast(page, "#tabs .tab.active", minimum_ratio=4.5)
            assert_minimum_contrast(page, "#token-pills .pill.winner", minimum_ratio=4.5)
