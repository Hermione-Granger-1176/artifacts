from __future__ import annotations

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tests.frontend_helpers import (
    MonitoredPage,
    StaticServer,
    assert_minimum_contrast,
    assert_no_blocking_axe_violations,
    build_smoke_site,
    run_axe,
)


def _assert_root_contrast(page) -> None:
    assert_minimum_contrast(page, ".skip-link", minimum_ratio=4.5)
    assert_minimum_contrast(page, "#theme-toggle", minimum_ratio=4.5)
    assert_minimum_contrast(
        page,
        ".page-btn.active",
        minimum_ratio=4.5,
        background_selector=".page-btn.active .page-btn-paper",
    )
    assert_minimum_contrast(page, ".book-cover-sub", minimum_ratio=3.0)
    assert_minimum_contrast(page, ".book-cover-author", minimum_ratio=4.5)


def test_root_page_has_no_blocking_axe_violations_in_light_theme(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright,
            server.url,
            name="a11y-root-light",
            color_scheme="light",
            reduced_motion="reduce",
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            expect(page.locator("html")).to_have_attribute(
                "data-runtime-status", "ready"
            )
            results = run_axe(
                page,
                include=[
                    ".header",
                    ".container",
                    ".footer",
                    "#runtime-error",
                    "#detail-overlay",
                ],
                exclude=[".book-cover"],
            )
            assert_no_blocking_axe_violations(results)
            _assert_root_contrast(page)


def test_root_page_has_no_blocking_axe_violations_in_dark_theme(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright,
            server.url,
            name="a11y-root-dark",
            color_scheme="dark",
            reduced_motion="reduce",
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            page.locator("#theme-toggle").click()
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            results = run_axe(
                page,
                include=[
                    ".header",
                    ".container",
                    ".footer",
                    "#runtime-error",
                    "#detail-overlay",
                ],
                exclude=[".book-cover"],
            )
            assert_no_blocking_axe_violations(results)
            _assert_root_contrast(page)


def test_overlay_and_no_results_states_have_no_blocking_axe_violations(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright,
            server.url,
            name="a11y-overlay-no-results",
            reduced_motion="reduce",
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            page.locator(".artifact-card").first.click()
            expect(page.locator("#detail-overlay")).to_have_class(
                "detail-overlay visible open"
            )
            overlay_results = run_axe(page, include=["#detail-overlay"])
            assert_no_blocking_axe_violations(overlay_results)
            assert_minimum_contrast(page, ".detail-open-link", minimum_ratio=4.5)
            assert_minimum_contrast(page, ".detail-close", minimum_ratio=4.5)

            page.locator(".detail-close").click()
            page.wait_for_timeout(450)

            page.fill("#search-input", "artifact that does not exist")
            page.wait_for_timeout(250)
            expect(page.locator("#no-results")).not_to_have_class("no-results hidden")
            no_results = run_axe(page, include=["#no-results"])
            assert_no_blocking_axe_violations(no_results)


def test_404_page_has_no_blocking_axe_violations_and_good_contrast(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(playwright, server.url, name="a11y-404") as session:
            page = session.page
            assert page is not None
            session.goto("/404.html")

            results = run_axe(page)
            assert_no_blocking_axe_violations(results)
            assert_minimum_contrast(page, "#home-link", minimum_ratio=4.5)
