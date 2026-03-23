from __future__ import annotations

import shutil
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tests.frontend_helpers import MonitoredPage, StaticServer, build_smoke_site


def test_gallery_smoke_covers_root_interactions(tmp_path: Path, monkeypatch) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright,
            server.url,
            name="frontend-smoke-root",
            viewport=(860, 1100),
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            search_box = page.locator("#search-input").bounding_box()
            sort_box = page.locator("#sort-toggle").bounding_box()
            assert search_box is not None
            assert sort_box is not None
            search_center_y = search_box["y"] + (search_box["height"] / 2)
            sort_center_y = sort_box["y"] + (sort_box["height"] / 2)
            assert abs(search_center_y - sort_center_y) < 12

            page.set_viewport_size({"width": 1100, "height": 1100})

            expect(page.locator(".artifact-card")).to_have_count(4)
            expect(page.locator("#pagination .page-btn")).to_have_count(8)
            expect(page.locator("html")).to_have_attribute(
                "data-runtime-status", "ready"
            )
            expect(page.locator('link[rel="canonical"]')).to_have_attribute(
                "href", "https://example.com/"
            )
            expect(page.locator('meta[property="og:url"]')).to_have_attribute(
                "content", "https://example.com/"
            )
            expect(page.locator('meta[property="og:image"]')).to_have_attribute(
                "content",
                "https://example.com/assets/social/share-preview.png?v=smoketest",
            )
            expect(page.locator('meta[name="twitter:image"]')).to_have_attribute(
                "content",
                "https://example.com/assets/social/share-preview.png?v=smoketest",
            )

            page.get_by_role("button", name="Page 2").click()
            expect(page.locator(".artifact-card")).to_have_count(4)

            page.locator('.desk-note[data-filter-tool="chatgpt"]').click()
            expect(page.locator(".artifact-card")).to_have_count(4)

            page.fill("#search-input", "Artifact 13")
            page.wait_for_timeout(250)
            expect(page.locator(".artifact-card")).to_have_count(1)

            page.locator(".artifact-card").first.click()
            expect(page.locator("#detail-overlay")).to_have_class(
                "detail-overlay visible open"
            )
            expect(page.locator("#detail-title")).to_have_text("Artifact 13")

            page.locator("button.detail-close").click()
            page.wait_for_timeout(450)
            expect(page.locator("#detail-overlay")).not_to_have_class(
                "detail-overlay visible open"
            )


def test_404_links_handle_root_and_preview_paths(tmp_path: Path, monkeypatch) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)
    preview_page = deploy_root / "pr-preview" / "pr-42" / "missing" / "index.html"
    preview_page.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(deploy_root / "404.html", preview_page)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright, server.url, name="frontend-smoke-404"
        ) as session:
            page = session.page
            assert page is not None

            session.goto("/404.html")
            expect(page.locator("#home-link")).to_have_attribute("href", "/")

            session.goto("/pr-preview/pr-42/missing/")
            expect(page.locator("#home-link")).to_have_attribute(
                "href", "/pr-preview/pr-42/"
            )


def test_gallery_shows_runtime_error_for_invalid_bootstrap_data(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(
        tmp_path,
        monkeypatch,
        artifacts_override={"invalid": True},
    )

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        with MonitoredPage(
            playwright,
            server.url,
            name="frontend-smoke-invalid-bootstrap",
            allowed_page_errors=("window.ARTIFACTS_DATA must be an array",),
        ) as session:
            page = session.page
            assert page is not None
            session.goto("/")

            expect(page.locator("html")).to_have_attribute(
                "data-runtime-status", "error"
            )
            expect(page.locator("#runtime-error")).not_to_have_class(
                "runtime-error hidden"
            )
            expect(page.locator(".artifact-card")).to_have_count(0)
