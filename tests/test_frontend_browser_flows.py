from __future__ import annotations

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tests.frontend_helpers import MonitoredPage, StaticServer, build_smoke_site


def test_keyboard_only_flow_keeps_focus_visible_and_restores_trigger(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright, server.url, name="browser-keyboard-flow"
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            page.keyboard.press("Tab")
            expect(page.locator(".skip-link")).to_be_focused()
            page.keyboard.press("Enter")
            expect(page.locator("#search-input")).to_be_focused()

            first_card = page.locator(".artifact-card").first
            first_card.focus()
            expect(first_card).to_be_focused()
            page.keyboard.press("Space")

            expect(page.locator("#detail-overlay")).to_have_class(
                "detail-overlay visible open"
            )
            expect(page.locator(".detail-close")).to_be_focused()

            page.keyboard.press("Shift+Tab")
            expect(page.locator(".detail-open-link")).to_be_focused()
            page.keyboard.press("Tab")
            expect(page.locator(".detail-close")).to_be_focused()

            page.keyboard.press("Escape")
            page.wait_for_timeout(450)
            expect(page.locator("#detail-overlay")).not_to_have_class(
                "detail-overlay visible open"
            )
            expect(first_card).to_be_focused()


def test_mobile_viewport_flow_keeps_gallery_usable(tmp_path: Path, monkeypatch) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright,
            server.url,
            name="browser-mobile-flow",
            viewport=(390, 844),
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            expect(page.locator(".desk-notes-left")).not_to_be_visible()
            expect(page.locator(".desk-notes-right")).not_to_be_visible()
            expect(page.locator(".artifact-card")).to_have_count(4)

            page.get_by_role("button", name="Page 2").click()
            expect(page.locator(".artifact-card")).to_have_count(4)

            page.locator(".artifact-card").first.click()
            expect(page.locator("#detail-title")).to_be_visible()
            page.locator(".detail-close").click()
            page.wait_for_timeout(450)

            page.evaluate("window.scrollTo(0, 900)")
            page.wait_for_timeout(100)
            expect(page.locator("#scroll-top")).to_have_attribute(
                "aria-hidden", "false"
            )


def test_reduced_motion_flow_persists_theme_and_closes_overlay_immediately(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright,
            server.url,
            name="browser-reduced-motion-theme",
            reduced_motion="reduce",
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            page.locator("#theme-toggle").click()
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")
            page.reload(wait_until="networkidle")
            expect(page.locator("html")).to_have_attribute("data-theme", "dark")

            page.locator(".artifact-card").first.click()
            expect(page.locator("#detail-overlay")).to_have_class(
                "detail-overlay visible open"
            )
            page.locator(".detail-close").click()
            expect(page.locator("#detail-overlay")).to_have_attribute(
                "aria-hidden", "true"
            )
            expect(page.locator("#detail-overlay")).not_to_have_class(
                "detail-overlay visible open"
            )


def test_large_catalog_fixture_exercises_filtering_and_pagination(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch, artifact_count=57)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright, server.url, name="browser-large-catalog"
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            expect(page.locator(".artifact-card")).to_have_count(4)
            expect(page.locator("#pagination .page-ellipsis")).to_have_count(1)

            page.get_by_role("button", name="Last page").click()
            expect(page.locator(".artifact-card")).to_have_count(1)

            page.locator('.desk-note[data-filter-tool="claude"]').click()
            page.wait_for_timeout(100)
            expect(page.locator(".artifact-card")).to_have_count(4)
            status_text = page.locator("#gallery-status").text_content() or ""
            assert "Showing 28 artifacts; page 1 of 7." in status_text
