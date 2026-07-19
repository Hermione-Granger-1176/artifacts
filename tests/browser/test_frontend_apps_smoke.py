from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import expect

from tests.browser.frontend_helpers import (
    REPO_ROOT,
    MonitoredPage,
    StaticServer,
    app_scope_skipif,
    build_real_site,
    selected_app_slugs,
)

if TYPE_CHECKING:
    from tests.browser.conftest import AppBrowserHarness


def _app_name(slug: str) -> str:
    return (REPO_ROOT / "apps" / slug / "name.txt").read_text(encoding="utf-8").strip()


def _app_path(slug: str) -> str:
    return f"/apps/{slug}/"


@pytest.mark.parametrize("slug", selected_app_slugs())
def test_app_smoke_pages_load_cleanly(app_browser: AppBrowserHarness, slug: str) -> None:
    """Test app smoke pages load cleanly."""
    app_name = _app_name(slug)

    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name=f"app-smoke-{slug}",
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto(_app_path(slug))
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        expect(page.locator("#theme-toggle")).to_be_visible()
        expect(page.locator(".app-header")).to_be_visible()
        expect(page.locator(".page-shell")).to_be_visible()
        assert app_name in page.title()


@app_scope_skipif("tokenizer-explorer")
def test_app_runtime_error_banner_is_visible_when_bootstrap_fails(
    tmp_path, monkeypatch, app_browser: AppBrowserHarness
) -> None:
    """Test app runtime error banner is visible when bootstrap fails."""
    deploy_root = build_real_site(tmp_path, monkeypatch)
    app_script = deploy_root / "apps" / "tokenizer-explorer" / "js" / "app.js"
    original = app_script.read_text(encoding="utf-8")
    broken_script = re.sub(
        r"run:\s*\(\)\s*=>\s*\{",
        "run:()=>{throw new Error('broken startup');",
        original,
        count=1,
    )
    app_script.write_text(broken_script, encoding="utf-8")

    with (
        StaticServer(deploy_root) as server,
        MonitoredPage(
            app_browser.playwright,
            server.url,
            name="app-runtime-error-tokenizer",
            browser=app_browser.browser,
            allowed_console_errors=("broken startup",),
            allowed_page_errors=("broken startup",),
            bypass_csp=True,
        ) as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/apps/tokenizer-explorer/")

        expect(page.locator("html")).to_have_attribute("data-runtime-status", "error")
        expect(page.locator("#runtime-error")).to_be_visible()
