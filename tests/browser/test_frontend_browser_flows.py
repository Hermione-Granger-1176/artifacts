from __future__ import annotations

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tests.browser.frontend_helpers import MonitoredPage, StaticServer, build_smoke_site


def test_keyboard_only_flow_keeps_focus_visible_and_restores_trigger(
    tmp_path: Path, monkeypatch
) -> None:
    """Test keyboard only flow keeps focus visible and restores trigger."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-keyboard-flow") as session,
    ):
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

        expect(page.locator("#detail-overlay")).to_have_class("detail-overlay visible open")
        expect(page.locator(".detail-close")).to_be_focused()

        page.keyboard.press("Shift+Tab")
        expect(page.locator(".detail-open-link")).to_be_focused()
        page.keyboard.press("Tab")
        expect(page.locator(".detail-close")).to_be_focused()

        page.keyboard.press("Escape")
        page.wait_for_timeout(450)
        expect(page.locator("#detail-overlay")).not_to_have_class("detail-overlay visible open")
        expect(first_card).to_be_focused()


def test_mobile_viewport_flow_keeps_gallery_usable(tmp_path: Path, monkeypatch) -> None:
    """Test mobile viewport flow keeps gallery usable."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright,
            server.url,
            name="browser-mobile-flow",
            viewport=(390, 844),
        ) as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")

        expect(page.locator(".desk-notes-left")).not_to_be_visible()
        expect(page.locator(".desk-notes-right")).not_to_be_visible()
        expect(page.locator(".mobile-filter-stack")).to_be_visible()
        page.locator('.mobile-filter-chip[data-filter-tool="chatgpt"]').click()
        expect(page.locator(".artifact-card")).to_have_count(4)

        page.get_by_role("button", name="Page 2").click()
        expect(page.locator(".artifact-card")).to_have_count(4)

        page.locator(".artifact-card").first.click()
        expect(page.locator("#detail-title")).to_be_visible()
        page.locator(".detail-close").click()
        page.wait_for_timeout(450)

        page.evaluate("window.scrollTo(0, 900)")
        page.wait_for_timeout(100)
        expect(page.locator("#scroll-top")).to_have_attribute("aria-hidden", "false")


def test_reduced_motion_flow_persists_theme_and_closes_overlay_immediately(
    tmp_path: Path, monkeypatch
) -> None:
    """Test reduced motion flow persists theme and closes overlay immediately."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright,
            server.url,
            name="browser-reduced-motion-theme",
            reduced_motion="reduce",
        ) as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        page.reload(wait_until="networkidle")
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")

        page.locator(".artifact-card").first.click()
        expect(page.locator("#detail-overlay")).to_have_class("detail-overlay visible open")
        page.locator(".detail-close").click()
        expect(page.locator("#detail-overlay")).to_have_attribute("aria-hidden", "true")
        expect(page.locator("#detail-overlay")).not_to_have_class("detail-overlay visible open")


def test_large_catalog_fixture_exercises_filtering_and_pagination(
    tmp_path: Path, monkeypatch
) -> None:
    """Test large catalog fixture exercises filtering and pagination."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch, artifact_count=57)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-large-catalog") as session,
    ):
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


# --- Scrapbook book scene: opening, leaf turns, drag, queueing ----------------

LEAF_OBSERVER = """() => {
    window.__leafAdds = 0;
    new MutationObserver((records) => {
        for (const record of records) {
            for (const node of record.addedNodes) {
                if (node.classList && node.classList.contains('book-leaf')) {
                    window.__leafAdds += 1;
                }
            }
        }
    }).observe(document.getElementById('book-sheet'), { childList: true });
}"""

DIRTY_BOOK_STATE = """() => {
    const dirty = [];
    for (const element of document.querySelectorAll('#book-shell *')) {
        if (element.style.transform || element.style.opacity || element.style.visibility) {
            dirty.push(`${element.className || element.id}: ${element.getAttribute('style')}`);
        }
    }
    const animations = document.getAnimations().filter(
        (animation) => !(animation instanceof CSSTransition) && !(animation instanceof CSSAnimation)
    );
    return {
        dirty,
        animations: animations.length,
        strays: document.querySelectorAll('.book-leaf, .book-ghost').length,
        turning: document.getElementById('book-sheet').classList.contains('is-turning'),
    };
}"""


def _wait_for_open_book(page) -> None:
    expect(page.locator("#book-shell")).to_have_attribute("data-scene-intro", "open", timeout=12000)


def _assert_clean_book(page) -> None:
    state = page.evaluate(DIRTY_BOOK_STATE)
    assert state["dirty"] == [], state["dirty"]
    assert state["animations"] == 0
    assert state["strays"] == 0
    assert state["turning"] is False


def _box(page, selector: str) -> dict[str, float]:
    box = page.locator(selector).bounding_box()
    assert box is not None, selector
    return box


def test_book_opens_to_a_centred_full_spread_with_a_narrow_seam(
    tmp_path: Path, monkeypatch
) -> None:
    """The cover opens by itself and the settled spread has no leftover animation state."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-open") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/", wait_until="commit")
        page.wait_for_selector("#book-cover")

        stage = _box(page, ".book-stage")
        cover = _box(page, "#book-cover")
        stage_center = stage["x"] + stage["width"] / 2
        assert abs((cover["x"] + cover["width"] / 2) - stage_center) < 3, "closed book is centred"

        _wait_for_open_book(page)
        expect(page.locator("#book-shell")).to_have_class("book-shell is-open")
        expect(page.locator(".artifact-card")).to_have_count(4)
        _assert_clean_book(page)

        sheet = _box(page, "#book-sheet")
        assert abs((sheet["x"] + sheet["width"] / 2) - stage_center) < 3, "open book is centred"
        left = _box(page, ".artifact-page-left")
        right = _box(page, ".artifact-page-right")
        assert abs((left["x"] + left["width"]) - right["x"]) < 1, "pages meet at the spine"
        assert abs(left["width"] - right["width"]) < 1
        assert left["width"] > 250
        for side in ("left", "right"):
            selector = f".artifact-page-{side} .artifact-card"
            expect(page.locator(selector).first).to_be_visible()

        # One ruled paper everywhere: endpaper, both pages, and (below) the leaf faces.
        papers = page.evaluate(
            """() => {
                const bg = (selector, pseudo) =>
                    getComputedStyle(document.querySelector(selector), pseudo).backgroundImage;
                return [
                    bg('.book-endpaper'),
                    bg('.book-inner', '::before'),
                    bg('.book-inner', '::after'),
                ];
            }"""
        )
        assert len(set(papers)) == 1
        assert "repeating-linear-gradient" in papers[0]


def test_next_and_previous_turn_one_leaf_that_matches_the_page_box(
    tmp_path: Path, monkeypatch
) -> None:
    """Buttons turn a single leaf whose box equals the settled page box, then clean up."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-turn") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)
        page.evaluate(LEAF_OBSERVER)
        before = (_box(page, ".artifact-page-left"), _box(page, ".artifact-page-right"))

        measure = page.evaluate(
            """async () => {
                document.querySelector('[aria-label="Next page"]').click();
                const frame = () => new Promise((resolve) => requestAnimationFrame(resolve));
                await frame();
                await frame();
                const leaf = document.querySelector('.book-leaf');
                const slice = document.querySelector('.artifact-page-right');
                const style = (element) => getComputedStyle(element);
                const faces = [...leaf.querySelectorAll('.book-leaf-face')].map(
                    (face) => style(face).backgroundImage
                );
                return {
                    leaf: ['width', 'height'].map((key) => parseFloat(style(leaf)[key])),
                    slice: ['width', 'height'].map((key) => parseFloat(style(slice)[key])),
                    leafTop: leaf.offsetTop,
                    sliceTop:
                        slice.getBoundingClientRect().top
                        - leaf.offsetParent.getBoundingClientRect().top,
                    faces,
                    endpaper: style(document.querySelector('.book-endpaper')).backgroundImage,
                    inert: leaf.inert,
                    hidden: leaf.getAttribute('aria-hidden'),
                };
            }"""
        )
        assert abs(measure["leaf"][0] - measure["slice"][0]) < 0.6
        assert abs(measure["leaf"][1] - measure["slice"][1]) < 0.6
        assert abs(measure["leafTop"] - measure["sliceTop"]) < 0.6
        assert measure["faces"] == [measure["endpaper"], measure["endpaper"]]
        assert measure["inert"] is True
        assert measure["hidden"] == "true"

        expect(page.locator(".book-leaf")).to_have_count(0, timeout=5000)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("2")
        _assert_clean_book(page)
        assert page.evaluate("window.__leafAdds") == 1
        after = (_box(page, ".artifact-page-left"), _box(page, ".artifact-page-right"))
        for was, now in zip(before, after, strict=True):
            assert abs(was["x"] - now["x"]) < 0.6 and abs(was["width"] - now["width"]) < 0.6

        page.get_by_role("button", name="Previous page").click()
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=5000)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("1")
        _assert_clean_book(page)
        assert page.evaluate("window.__leafAdds") == 2


def test_keyboard_next_keeps_focus_and_rapid_presses_end_on_the_right_page(
    tmp_path: Path, monkeypatch
) -> None:
    """Enter on Next repeats without losing focus or input, even mid-turn."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-keyboard") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)
        page.evaluate(LEAF_OBSERVER)

        next_button = page.get_by_role("button", name="Next page")
        next_button.focus()
        page.keyboard.press("Enter")
        page.keyboard.press("Enter")
        expect(next_button).to_be_focused()
        expect(page.locator("#pagination .page-btn.active")).to_have_text("3")

        expect(page.locator(".book-leaf")).to_have_count(0, timeout=6000)
        expect(page.locator("#gallery-status")).to_contain_text("page 3 of 4")
        _assert_clean_book(page)

        page.keyboard.press("Enter")
        expect(page.locator("#pagination .page-btn.active")).to_have_text("4")
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=6000)
        _assert_clean_book(page)
        expect(page.locator(".artifact-card")).to_have_count(1)


def test_rapid_next_clicks_and_page_jumps_never_drop_input(tmp_path: Path, monkeypatch) -> None:
    """Many quick clicks coalesce into few leaves and end on the requested page."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-rapid") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)
        page.evaluate(LEAF_OBSERVER)

        for _ in range(3):
            page.get_by_role("button", name="Next page").click()
        expect(page.locator("#pagination .page-btn.active")).to_have_text("4")
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=8000)
        expect(page.locator("#gallery-status")).to_contain_text("page 4 of 4")
        assert page.evaluate("window.__leafAdds") <= 2
        _assert_clean_book(page)

        page.evaluate("window.__leafAdds = 0")
        page.get_by_role("button", name="Page 1").click()
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=8000)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("1")
        assert page.evaluate("window.__leafAdds") == 1, "a multi-page jump is one leaf"
        _assert_clean_book(page)

        page.get_by_role("button", name="Next page").click()
        page.get_by_role("button", name="Previous page").click()
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=8000)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("1")
        expect(page.locator("#gallery-status")).to_contain_text("page 1 of 4")
        _assert_clean_book(page)


def test_dragging_a_page_edge_scrubs_the_leaf_then_completes_or_springs_back(
    tmp_path: Path, monkeypatch
) -> None:
    """A drag from the outer edge moves the leaf with the pointer; release decides."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-drag") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)

        # Touch browsers leave horizontal drags to the book but still scroll and zoom.
        expect(page.locator("#book-sheet")).to_have_css("touch-action", "pan-y pinch-zoom")

        grid = _box(page, "#artifacts-grid")
        y = grid["y"] + grid["height"] / 2
        edge_x = grid["x"] + grid["width"] - 12
        center_x = grid["x"] + grid["width"] / 2

        # Spring back: drag a quarter of the way and let go.
        page.mouse.move(edge_x, y)
        page.mouse.down()
        page.mouse.move(grid["x"] + grid["width"] * 0.8, y, steps=6)
        expect(page.locator(".book-leaf")).to_have_count(1)
        leaf_transform = page.locator(".book-leaf").evaluate("(leaf) => leaf.style.transform")
        assert leaf_transform.startswith("rotateY(-") and leaf_transform != "rotateY(0deg)"
        page.mouse.up()
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=3000)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("1")
        assert page.url.endswith("/") and "page=" not in page.url
        _assert_clean_book(page)

        # Complete: drag past the middle and let go.
        page.mouse.move(edge_x, y)
        page.mouse.down()
        page.mouse.move(center_x - 60, y, steps=8)
        page.mouse.up()
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=3000)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("2")
        assert "page=2" in page.url
        _assert_clean_book(page)

        # Drag the left edge back to the first page.
        page.mouse.move(grid["x"] + 12, y)
        page.mouse.down()
        page.mouse.move(center_x + 60, y, steps=8)
        page.mouse.up()
        expect(page.locator(".book-leaf")).to_have_count(0, timeout=3000)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("1")
        _assert_clean_book(page)

        # Cards stay clickable: a press on a card never starts a drag.
        page.locator(".artifact-card").first.click()
        expect(page.locator("#detail-overlay")).to_have_class("detail-overlay visible open")
        page.keyboard.press("Escape")

        # Phones turn by button only, so the sheet hands every gesture back.
        page.set_viewport_size({"width": 390, "height": 844})
        expect(page.locator("#book-sheet")).to_have_css("touch-action", "auto")


def test_reduced_motion_book_cross_fades_without_a_leaf(tmp_path: Path, monkeypatch) -> None:
    """Reduced motion opens and turns with fades only: no rotation, no leaf."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright, server.url, name="browser-book-reduced", reduced_motion="reduce"
        ) as session,
    ):
        page = session.page
        assert page is not None
        page.add_init_script(
            """window.__rotations = [];
            new MutationObserver(() => {
                document.querySelectorAll('#book-shell *').forEach((element) => {
                    if (/rotate/.test(element.style.transform)) {
                        window.__rotations.push(element.className);
                    }
                });
            }).observe(document, {
                subtree: true, attributes: true, attributeFilter: ['style'],
            });"""
        )
        session.goto("/")
        _wait_for_open_book(page)
        _assert_clean_book(page)

        page.evaluate(LEAF_OBSERVER)
        page.get_by_role("button", name="Next page").click()
        expect(page.locator("#pagination .page-btn.active")).to_have_text("2")
        expect(page.locator("#gallery-status")).to_contain_text("page 2 of 4", timeout=3000)
        expect(page.locator(".book-inner")).not_to_have_attribute(
            "style", "opacity: 0.5", timeout=1500
        )
        page.wait_for_timeout(400)
        _assert_clean_book(page)
        assert page.evaluate("window.__leafAdds") == 0
        assert page.evaluate("window.__rotations") == []


def test_mobile_book_turns_with_a_fade_and_leaves_no_inline_state(
    tmp_path: Path, monkeypatch
) -> None:
    """The single-column mobile book opens and turns without a leaf."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright, server.url, name="browser-book-mobile", viewport=(390, 844)
        ) as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)
        _assert_clean_book(page)
        expect(page.locator("#book-cover")).to_be_hidden()
        expect(page.locator(".artifact-card")).to_have_count(4)
        expect(page.locator(".book-peel").first).to_be_hidden()

        page.evaluate(LEAF_OBSERVER)
        page.get_by_role("button", name="Next page").click()
        expect(page.locator("#pagination .page-btn.active")).to_have_text("2")
        expect(page.locator("#gallery-status")).to_contain_text("page 2 of 4", timeout=3000)
        page.wait_for_timeout(500)
        _assert_clean_book(page)
        assert page.evaluate("window.__leafAdds") == 0


def test_dark_theme_keeps_the_cover_colour_and_the_same_ruled_paper(
    tmp_path: Path, monkeypatch
) -> None:
    """The cover is one physical colour in both themes; paper rules stay consistent."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright, server.url, name="browser-book-dark", reduced_motion="reduce"
        ) as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)

        cover_color = """() =>
            getComputedStyle(document.querySelector('.book-cover-face')).backgroundColor"""
        rule_color = """() =>
            getComputedStyle(document.documentElement)
                .getPropertyValue('--paper-rule-color')
                .trim()"""
        light_cover = page.evaluate(cover_color)
        light_rule = page.evaluate(rule_color)
        assert light_cover == "rgb(56, 50, 45)"

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")
        assert page.evaluate(cover_color) == light_cover
        dark_rule = page.evaluate(rule_color)
        assert dark_rule != light_rule
        papers = page.evaluate(
            """() => [
                getComputedStyle(document.querySelector('.book-endpaper')).backgroundImage,
                getComputedStyle(document.querySelector('.book-inner'), '::before').backgroundImage,
                getComputedStyle(document.querySelector('.book-inner'), '::after').backgroundImage,
            ]"""
        )
        assert len(set(papers)) == 1


def test_resize_across_the_mobile_breakpoint_mid_turn_leaves_no_leaf_or_inline_style(
    tmp_path: Path, monkeypatch
) -> None:
    """Shrinking the window during a turn settles on the requested page cleanly."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-resize") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)

        page.get_by_role("button", name="Next page").click()
        expect(page.locator(".book-leaf")).to_have_count(1)
        page.set_viewport_size({"width": 500, "height": 900})
        expect(page.locator(".book-leaf")).to_have_count(0)
        expect(page.locator("#gallery-status")).to_contain_text("page 2 of 4")
        _assert_clean_book(page)
        page.wait_for_timeout(900)
        _assert_clean_book(page)
        expect(page.locator("#pagination .page-btn.active")).to_have_text("2")


def test_search_during_a_page_turn_renders_the_new_results(tmp_path: Path, monkeypatch) -> None:
    """A filter change mid-turn drops the leaf and shows the right cards."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-search") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/")
        _wait_for_open_book(page)

        page.get_by_role("button", name="Next page").click()
        expect(page.locator(".book-leaf")).to_have_count(1)
        page.fill("#search-input", "Artifact 13")
        expect(page.locator(".book-leaf")).to_have_count(0)
        expect(page.locator(".artifact-card")).to_have_count(1, timeout=2000)
        page.wait_for_timeout(900)
        expect(page.locator(".artifact-card")).to_have_count(1)
        expect(page.locator("#gallery-status")).to_contain_text("Showing 1 artifact")
        _assert_clean_book(page)


def test_filter_and_search_during_the_intro_render_the_right_cards(
    tmp_path: Path, monkeypatch
) -> None:
    """Changing filters while the cover is still opening shows the filtered cards once open."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(playwright, server.url, name="browser-book-intro-filter") as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/", wait_until="commit")
        page.wait_for_selector(".artifact-card", state="attached")
        page.get_by_role("button", name="Page 2").click()
        page.fill("#search-input", "Artifact 12")
        _wait_for_open_book(page)
        expect(page.locator(".artifact-card")).to_have_count(1)
        expect(page.locator(".artifact-card")).to_contain_text("Artifact 12")
        _assert_clean_book(page)


def test_book_fits_laptop_screens_without_scrolling(tmp_path: Path, monkeypatch) -> None:
    """The open book and its pagination fit common laptop viewports and keep the page shape."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        for width, height in ((1280, 720), (1366, 768), (1536, 864), (1920, 1080)):
            with MonitoredPage(
                playwright, server.url, name="browser-book-fit", viewport=(width, height)
            ) as session:
                page = session.page
                assert page is not None
                session.goto("/")
                _wait_for_open_book(page)

                sheet = _box(page, "#book-sheet")
                pagination = _box(page, "#pagination")
                label = f"{width}x{height}"
                assert pagination["y"] + pagination["height"] <= height, label
                assert 460 <= sheet["height"] <= 800, label
                ratio = sheet["width"] / sheet["height"]
                assert 1.3 < ratio < 1.35, label


def test_search_note_shows_a_match_count_and_a_labelled_sort_note(
    tmp_path: Path, monkeypatch
) -> None:
    """The sticky-note search writes its match count, and sort says which order it uses."""
    deploy_root = build_smoke_site(tmp_path, monkeypatch)
    sort_label = """() =>
        getComputedStyle(document.querySelector('#sort-toggle'), '::after').content"""

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        for width, height in ((1366, 768), (390, 844)):
            with MonitoredPage(
                playwright, server.url, name="browser-search-note", viewport=(width, height)
            ) as session:
                page = session.page
                assert page is not None
                session.goto("/")
                _wait_for_open_book(page)
                label = f"{width}x{height}"

                # The note stays one row tall, including the stacked phone layout.
                assert _box(page, ".search-wrapper")["height"] < 90, label
                expect(page.locator("#search-count")).to_have_text("")

                page.keyboard.press("/")
                expect(page.locator("#search-input")).to_be_focused()
                page.keyboard.type("Artifact 1")
                expect(page.locator("#search-count")).to_have_text("4 found")
                page.fill("#search-input", "no such artifact")
                expect(page.locator("#search-count")).to_have_text("nothing yet")
                page.click("#search-clear")
                expect(page.locator("#search-count")).to_have_text("")

                assert page.evaluate(sort_label) == '"newest"', label
                page.click("#sort-toggle")
                expect(page.locator("#sort-toggle")).to_have_attribute("aria-pressed", "true")
                assert page.evaluate(sort_label) == '"oldest"', label
