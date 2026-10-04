from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

from playwright.sync_api import expect

from tests.browser.frontend_helpers import (
    MonitoredPage,
    app_scope_skipif,
)

if TYPE_CHECKING:
    from tests.browser.conftest import AppBrowserHarness


@app_scope_skipif("loan-amortization")
def test_loan_amortization_flow_covers_theme_and_schedule(app_browser: AppBrowserHarness) -> None:
    """Test loan amortization flow covers theme and schedule."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-flow-loan",
        viewport=(1100, 720),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/loan-amortization/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        for canvas_id in (
            "balanceChart",
            "compChart",
            "savingsChart",
            "cumulChart",
            "periodChart",
        ):
            expect(page.locator(f"#{canvas_id}")).to_be_visible()
        expect(page.locator("#metrics .loan-hero-value")).to_contain_text("$")
        expect(page.locator("#metrics .stat")).to_have_count(4)

        expect(page.locator(".loan-inputs")).to_have_css("position", "sticky")
        inputs_box = page.locator(".loan-inputs").bounding_box()
        results_box = page.locator(".loan-results").bounding_box()
        assert inputs_box is not None
        assert results_box is not None
        assert inputs_box["x"] + inputs_box["width"] <= results_box["x"]
        assert abs(inputs_box["y"] - results_box["y"]) < 1

        expect(page.locator("#biweeklyMode")).to_be_hidden()
        page.locator("#selFreq").select_option("biweekly")
        expect(page.locator("#biweeklyMode")).to_be_visible()
        page.locator("#selFreq").select_option("monthly")
        expect(page.locator("#biweeklyMode")).to_be_hidden()

        expect(page.locator(".extra-empty")).to_be_visible()

        initial_metrics = page.locator("#metrics").text_content() or ""
        page.locator("#slPrincipal").evaluate(
            """(element) => {
                    element.value = '80000';
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
        )
        page.wait_for_function(
            "previous => document.querySelector('#metrics').textContent !== previous",
            arg=initial_metrics,
        )

        page.locator("#btnTable").click()
        expect(page.locator("#periodTableWrap")).to_be_visible()

        page.locator("#btnAdd").click()
        expect(page.locator(".extra-item")).to_have_count(1)
        expect(page.locator(".extra-empty")).to_be_hidden()
        expect(page.locator(".extra-summary")).to_contain_text("Pays $500 every month")
        page.locator('.extra-item [data-field="amount"]').fill("1000")
        expect(page.locator(".extra-summary")).to_contain_text("Pays $1,000 every month")
        expect(page.locator("#metrics .chip")).to_contain_text("Saves")

        page.locator("#selFreq").select_option("weekly")
        expect(page.locator("#metrics")).to_contain_text("Weekly EMI")

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")

        page.evaluate("window.scrollTo(0, 900)")
        page.wait_for_timeout(100)
        expect(page.locator("#scroll-top")).to_have_attribute("aria-hidden", "false")


def _box(page, selector: str) -> dict[str, float]:
    box = page.locator(selector).first.bounding_box()
    assert box is not None, f"{selector} has no layout box"
    return box


def _assert_shared_edges(page, selectors: list[str]) -> None:
    """Every selector must start and end on the same x edges as the first one."""
    reference = _box(page, selectors[0])
    for selector in selectors[1:]:
        box = _box(page, selector)
        assert abs(box["x"] - reference["x"]) <= 1, f"{selector} left edge drifts"
        assert abs((box["x"] + box["width"]) - (reference["x"] + reference["width"])) <= 1, (
            f"{selector} right edge drifts"
        )


@app_scope_skipif("tokenizer-explorer")
def test_tokenizer_explorer_flow_covers_sampling_and_theme(app_browser: AppBrowserHarness) -> None:
    """Test tokenizer explorer flow covers sampling and theme."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-flow-tokenizer",
        viewport=(1280, 900),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/tokenizer-explorer/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        # Two top-aligned columns; below the workbench the sections reuse the outer edges.
        main_box = _box(page, ".tk-main")
        settings_box = _box(page, ".tk-settings")
        assert main_box["x"] + main_box["width"] <= settings_box["x"]
        assert abs(main_box["y"] - settings_box["y"]) <= 1
        assert 280 <= settings_box["width"] <= 320
        tokens_box = _box(page, ".tokenization-card")
        assert abs(tokens_box["x"] - main_box["x"]) <= 1
        assert (
            abs(
                (tokens_box["x"] + tokens_box["width"])
                - (settings_box["x"] + settings_box["width"])
            )
            <= 1
        )

        # One left and right edge inside each card.
        _assert_shared_edges(
            page,
            [".tk-card-head", ".tk-prompt", ".tk-next", ".tk-actions"],
        )
        _assert_shared_edges(
            page,
            [
                ".tk-settings .tk-card-head",
                "#scenario-select",
                "#temp-slider",
                "#topp-slider",
                "#sampling-presets",
                ".tk-key",
                ".tk-disclosure",
            ],
        )
        control_heights = {
            round(_box(page, selector)["height"])
            for selector in ("#scenario-select", "#sampling-presets", "#pick-token")
        }
        assert len(control_heights) == 1, control_heights

        # The completion blank rides inline at the end of the prompt line.
        last_chip = _box(page, ".tk-prompt .prompt-chip >> nth=-1")
        blank = _box(page, "#sentence-completion")
        assert abs(last_chip["y"] - blank["y"]) <= 2
        assert blank["x"] >= last_chip["x"] + last_chip["width"]

        # Candidate rows: one per token, with the cut shown by label and strike-through.
        expect(page.locator("#candidate-list .tk-row:not(.tk-list-head)")).to_have_count(8)
        expect(page.locator("#candidate-list .tk-cut-label:visible")).to_have_count(1)
        expect(page.locator("#candidate-list .is-cut .tk-draw").first).to_have_text("cut")

        initial_sentence = page.locator("#sentence-prefix").text_content() or ""
        page.locator("#scenario-select").select_option(index=2)
        page.wait_for_function(
            "previous => document.querySelector('#sentence-prefix').textContent !== previous",
            arg=initial_sentence,
        )
        expect(page.locator("#scenario-select option:checked")).to_have_text("Code")

        initial_temp_value = page.locator("#temp-val").text_content() or ""
        page.locator("#temp-slider").evaluate(
            """(element) => {
                    element.value = '20';
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
        )
        page.wait_for_function(
            "previous => document.querySelector('#temp-val').textContent !== previous",
            arg=initial_temp_value,
        )

        initial_cut_count = page.locator("#candidate-list .is-cut").count()
        initial_topp_note = page.locator("#topp-note").text_content() or ""
        page.locator("#topp-slider").evaluate(
            """(element) => {
                    element.value = '20';
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
        )
        page.wait_for_timeout(100)
        assert page.locator("#candidate-list .is-cut").count() != initial_cut_count
        assert page.locator("#topp-note").text_content() != initial_topp_note

        page.locator("#sampling-presets button").nth(2).click()
        expect(page.locator("#sampling-presets button").nth(2)).to_have_class(
            re.compile(r"\bactive\b")
        )
        expect(page.locator("#temp-val")).to_have_text("1.2")
        expect(page.locator("#topp-val")).to_have_text("0.95")

        page.locator("#pick-token").click()
        expect(page.locator("#sentence-completion")).not_to_have_text("")
        expect(page.locator("#candidate-list .is-picked")).to_have_count(1)

        page.locator("#sample-hundred").click()
        expect(page.locator("#sample-status")).to_contain_text("tally from 100 draws")
        expect(page.locator("#candidate-list .tk-list-head .tk-seen")).to_be_visible()

        # Screen readers get four columns, and a phone keeps the Seen tally readable.
        table = page.get_by_role("table", name="Next-token candidates")
        expect(table.get_by_role("columnheader")).to_have_count(4)
        desktop_viewport = page.viewport_size
        assert desktop_viewport is not None
        page.set_viewport_size({"width": 390, "height": 844})
        seen_header = table.get_by_role("columnheader", name="Seen")
        expect(seen_header).to_have_count(1)
        expect(seen_header).to_have_css("position", "absolute")
        page.set_viewport_size(desktop_viewport)

        page.locator("#reset-samples").click()
        expect(page.locator("#sample-status")).to_contain_text("Run 100 draws")
        expect(page.locator("#candidate-list .tk-list-head .tk-seen")).to_be_hidden()

        page.locator(".tk-disclosure summary").click()
        expect(page.locator(".tk-code")).to_be_visible()
        _assert_shared_edges(page, [".tk-disclosure", ".tk-code"])

        page.locator("#whitespace-toggle").click()
        expect(page.locator("#whitespace-toggle")).to_have_attribute("aria-pressed", "true")
        expect(
            page.locator("#token-examples .token-chip").filter(has_text="·").first
        ).to_be_visible()
        expect(page.locator(".tk-prompt .prompt-chip").filter(has_text="·").first).to_be_visible()

        page.locator(".card-trigger").first.click()
        expect(page.locator(".card").first).to_have_class(re.compile(r"\bopen\b"))

        expect(page.locator(".section-nav")).to_be_visible()
        assert page.locator("#nav-nodes .section-nav-node").count() == 4
        page.locator("#nav-nodes .section-nav-node").last.click()
        page.wait_for_function("window.scrollY > 0")

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")

        # Below 900px the settings stack above the main card.
        page.set_viewport_size({"width": 800, "height": 900})
        page.evaluate("window.scrollTo(0, 0)")
        stacked_settings = _box(page, ".tk-settings")
        stacked_main = _box(page, ".tk-main")
        assert stacked_settings["y"] + stacked_settings["height"] <= stacked_main["y"] + 1
        assert abs(stacked_settings["x"] - stacked_main["x"]) <= 1
        assert abs(stacked_settings["width"] - stacked_main["width"]) <= 1


@app_scope_skipif("prompt-caching")
def test_prompt_caching_flow_covers_calculator_attention_and_embeddings(
    app_browser: AppBrowserHarness,
) -> None:
    """Test prompt caching calculator, attention walkthrough, and embedding output changes."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-flow-prompt-caching",
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/prompt-caching/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        initial_savings = page.locator("#calcSavings").text_content() or ""
        page.locator("#calcReq").evaluate(
            """(element) => {
                    element.value = '5000';
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
        )
        page.wait_for_function(
            "previous => document.querySelector('#calcSavings').textContent !== previous",
            arg=initial_savings,
        )
        expect(page.locator("#calcReqVal")).to_have_text("5,000")

        initial_attention_title = page.locator("#attnStepTitle").text_content() or ""
        page.locator("#attnStepper button").nth(1).click()
        page.wait_for_function(
            "previous => document.querySelector('#attnStepTitle').textContent !== previous",
            arg=initial_attention_title,
        )
        initial_dot_product = page.locator("#dotProduct").text_content() or ""
        page.locator("#attnStepVisual .pc-matrix-cell.clickable").first.click()
        page.wait_for_function(
            "previous => document.querySelector('#dotProduct').textContent !== previous",
            arg=initial_dot_product,
        )

        initial_similarity = page.locator("#embSimilarity").text_content() or ""
        page.get_by_role("button", name="Compare happy and submarine").click()
        page.wait_for_function(
            "previous => document.querySelector('#embSimilarity').textContent !== previous",
            arg=initial_similarity,
        )
        expect(page.locator("#embSelA")).to_have_text("happy")
        expect(page.locator("#embSelB")).to_have_text("submarine")


@app_scope_skipif("bond-price-vs-rate")
def test_bond_price_vs_rate_flow_covers_rail_chapters_and_curve_apply(
    app_browser: AppBrowserHarness,
) -> None:
    """Test bond price vs rate flow covers rail, chapters, and curve apply."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-flow-bond",
        viewport=(1280, 800),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/bond-price-vs-rate/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        # Two columns: the pinned rail holds the price, the curve, and all three
        # sliders, and sits left of the story. The story is numbered chapters.
        rail = page.locator(".br-rail")
        expect(rail).to_have_css("position", "sticky")
        rail_ids = (
            "#priceValue",
            "#regimeBadge",
            "#priceRateChart",
            "#slRate",
            "#slCoupon",
            "#slYears",
        )
        for control_id in rail_ids:
            expect(rail.locator(control_id)).to_be_visible()
        expect(page.locator(".br-chapter")).to_have_count(7)
        expect(page.locator(".br-chapter-num")).to_have_text(["1", "2", "3", "4", "5", "6", "7"])
        rail_box = rail.bounding_box()
        story_box = page.locator("#brStory").bounding_box()
        assert rail_box is not None
        assert story_box is not None
        assert rail_box["x"] + rail_box["width"] <= story_box["x"]
        assert abs(rail_box["y"] - story_box["y"]) < 1

        # The first chapter starts current and the rest are muted: their charts
        # fade while body text keeps full contrast.
        chapters = page.locator(".br-chapter")
        expect(chapters.nth(0)).to_have_class(re.compile(r"\bis-current\b"))
        expect(page.locator("#brStory")).to_have_class(re.compile(r"\bis-tracking\b"))
        expect(page.locator("#yieldCurveChart").locator("..")).to_have_css("opacity", "0.55")

        # Scrolling a later chapter into the reading band highlights it, and
        # the rail stays inside the window the whole way down.
        page.evaluate(
            """() => {
                const chapter = document.querySelectorAll('.br-chapter')[3];
                window.scrollTo(0, chapter.getBoundingClientRect().top + window.scrollY - 220);
            }"""
        )
        expect(chapters.nth(3)).to_have_class(re.compile(r"\bis-current\b"))
        expect(page.locator("#yieldCurveChart").locator("..")).to_have_css("opacity", "1")
        expect(page.locator("#sensitivityChart").locator("..")).to_have_css("opacity", "0.55")
        expect(chapters.nth(0)).not_to_have_class(re.compile(r"\bis-current\b"))
        pinned = rail.bounding_box()
        assert pinned is not None
        assert pinned["y"] >= 0, pinned
        assert pinned["y"] + pinned["height"] <= 800, pinned

        # The apply button moves the slider that lives in the rail.
        page.locator("#btnCurveInverted").click()
        expect(page.locator("#btnCurveInverted")).to_have_attribute("aria-pressed", "true")
        slider_before = page.locator("#slRate").input_value()
        page.locator("#btnApplyCurve").click()
        expect(page.locator("#slRate")).not_to_have_value(slider_before)
        applied_rate = float(page.locator("#slRate").input_value())
        expect(page.locator("#rateValue")).to_have_text(f"{applied_rate:.1f}%")
        expect(rail.locator("#rateValue")).to_be_in_viewport()

        # Below 960px the rail stops pinning and stacks above the story.
        page.set_viewport_size({"width": 800, "height": 900})
        page.evaluate("window.scrollTo(0, 0)")
        expect(rail).to_have_css("position", "static")
        stacked_rail = rail.bounding_box()
        first_chapter = chapters.nth(0).bounding_box()
        assert stacked_rail is not None
        assert first_chapter is not None
        assert stacked_rail["y"] + stacked_rail["height"] <= first_chapter["y"]
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


@app_scope_skipif("vendor-docs-generator")
def test_vendor_docs_generator_flow_covers_preview_overlay_and_exports(
    app_browser: AppBrowserHarness,
) -> None:
    """Test vendor docs generator flow covers preview, overlay and exports."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-flow-vendor-docs",
        viewport=(1400, 900),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/vendor-docs-generator/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        # The fitted preview must show the whole page without ever scrolling:
        # that is the entire reason the frame clips and the overlay exists.
        fit = page.evaluate(
            """() => {
                const frame = document.querySelector('#vdPaperFrame');
                const paper = document.querySelector('#vdPaper');
                return {
                    overflowX: frame.scrollWidth - frame.clientWidth,
                    overflowY: frame.scrollHeight - frame.clientHeight,
                    paperBottom: paper.getBoundingClientRect().bottom,
                    frameBottom: frame.getBoundingClientRect().bottom
                };
            }"""
        )
        assert fit["overflowX"] == 0, "the fitted preview should not scroll sideways"
        assert fit["overflowY"] == 0, "the fitted preview should not scroll vertically"
        assert fit["paperBottom"] <= fit["frameBottom"] + 1, "the whole page should be in view"
        expect(page.locator("#vdZoomLevel")).to_have_text(re.compile(r"^\d+%$"))

        # The studio has one toolbar, one stage, and one Output panel. The
        # vendor is a dropdown, the type is six pills, and exactly one primary
        # button is on screen: the export button pinned to the panel's foot.
        assert page.locator("#vdVendor").evaluate("el => el.tagName") == "SELECT"
        expect(page.locator("#vdDocType button")).to_have_count(6)
        expect(page.locator("#vdDegradePreset button")).to_have_count(5)
        expect(page.locator(".vd-workbench .btn-primary:visible")).to_have_count(1)
        expect(page.locator("#vdExport")).to_have_text("Download")
        expect(page.locator("#vdBatchOptions")).to_be_hidden()
        expect(page.locator("#vdBatchStop")).to_be_hidden()
        expect(page.locator("#vdFormatJson")).to_be_hidden()
        expect(page.locator("#vdPairLabel")).to_be_hidden()

        # The three label switches are one ladder, and it opens on JSON.
        expect(page.locator('#vdLabels [data-labels="json"]')).to_have_class("active")

        # The output panel is capped to the window, so the export button is
        # always reachable, and it pins beside the page while the window scrolls.
        # Checked at several depths rather than one, because a sticky item can
        # only travel as far as its own grid area and a single sample would
        # pass just as well against an element that had already let go.
        for depth in (150, 300):
            page.evaluate(f"window.scrollTo(0, {depth})")
            page.wait_for_timeout(150)
            pinned = page.evaluate(
                """() => {
                    const output = document.querySelector('.vd-output').getBoundingClientRect();
                    const button = document.querySelector('#vdExport').getBoundingClientRect();
                    return {
                        outputTop: output.top,
                        outputHeight: output.height,
                        buttonBottom: button.bottom,
                        viewport: window.innerHeight
                    };
                }"""
            )
            assert pinned["outputHeight"] <= pinned["viewport"], (depth, pinned)
            assert pinned["buttonBottom"] <= pinned["viewport"], (depth, pinned)

        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(150)

        # Batch mode reveals its rows and renames the one primary button; the
        # panel stays inside the window even with the fine-tune knobs open.
        page.locator('#vdMode [data-mode="batch"]').click()
        expect(page.locator("#vdBatchOptions")).to_be_visible()
        expect(page.locator("#vdFormatJson")).to_be_visible()
        expect(page.locator("#vdExport")).to_have_text("Generate ZIP")
        expect(page.locator(".vd-workbench .btn-primary:visible")).to_have_count(1)
        page.locator("#vdDegradeCustom > summary").click()
        expect(page.locator("#vdKnobs")).to_be_visible()
        panel = page.evaluate(
            """() => ({
                output: document.querySelector('.vd-output').getBoundingClientRect().height,
                viewport: window.innerHeight,
                body: document.querySelector('.vd-output-body').scrollHeight,
                bodyClient: document.querySelector('.vd-output-body').clientHeight
            })"""
        )
        assert panel["output"] <= panel["viewport"], panel
        page.locator("#vdDegradeCustom > summary").click()
        page.locator('#vdMode [data-mode="page"]').click()
        expect(page.locator("#vdBatchOptions")).to_be_hidden()

        # Below about 1000px the studio stacks (toolbar, page, output), and below
        # 700px the type pills give way to the dropdown.
        page.set_viewport_size({"width": 900, "height": 900})
        page.wait_for_timeout(150)
        stacked = page.evaluate(
            """() => ({
                stageBottom: document.querySelector('.vd-stage').getBoundingClientRect().bottom,
                outputTop: document.querySelector('.vd-output').getBoundingClientRect().top,
                overflow: document.documentElement.scrollWidth
                    - document.documentElement.clientWidth
            })"""
        )
        assert stacked["outputTop"] >= stacked["stageBottom"] - 1, stacked
        assert stacked["overflow"] <= 0, stacked
        page.set_viewport_size({"width": 600, "height": 900})
        page.wait_for_timeout(150)
        expect(page.locator("#vdDocType")).to_be_hidden()
        expect(page.locator("#vdDocTypeSelect")).to_be_visible()
        page.locator("#vdDocTypeSelect").select_option("receipt")
        expect(page.locator('#vdDocType [data-type="receipt"]')).to_have_class("active")
        page.locator("#vdDocTypeSelect").select_option("invoice")
        page.set_viewport_size({"width": 1400, "height": 900})
        page.wait_for_timeout(150)
        expect(page.locator("#vdDocType")).to_be_visible()

        # Selection drives the preview and the caption, and the swatch next to
        # the vendor dropdown carries that vendor's accent through CSSOM.
        page.locator("#vdVendor").select_option("ironwood")
        page.locator('#vdDocType [data-type="statement"]').click()
        expect(page.locator("#vdCaptionVendor")).to_have_text("Ironwood Construction Materials")
        expect(page.locator("#vdCaptionType")).to_have_text("Statement of account")
        assert (
            page.locator("#vdVendorSwatch").evaluate("el => getComputedStyle(el).backgroundColor")
            == "rgb(180, 83, 9)"
        )

        # No ledger row may read as a negative balance, and no amount may print
        # its minus sign inside the currency symbol.
        balances = page.locator("#vdPaper tbody tr td:last-child").all_text_contents()
        assert balances, "the statement should have ledger rows"
        assert all(not text.strip().startswith("-") for text in balances), balances
        assert "$-" not in (page.locator("#vdPaper").text_content() or "")

        # The dense treatment is invoice-only.
        expect(page.locator("#vdLayout button").nth(1)).to_be_disabled()
        page.locator('#vdDocType [data-type="invoice"]').click()
        page.locator("#vdLayout button").nth(1).click()
        expect(page.locator("#vdCaptionType")).to_have_text("Invoice (dense)")
        page.locator("#vdLayout button").nth(0).click()

        seed_before = page.locator("#vdChipSeed").text_content()
        page.locator("#vdGenerate").click()
        page.wait_for_function(
            "previous => document.querySelector('#vdChipSeed').textContent !== previous",
            arg=seed_before,
        )

        # The overlay shows the page at 100% and hands it back on close.
        page.locator("#vdFullOpen").click()
        expect(page.locator("#vdFullscreen")).to_have_attribute("open", "")
        assert page.evaluate(
            "() => document.querySelector('#vdFullscreenBody').contains("
            "document.querySelector('#vdPaper'))"
        )
        paper_width = page.evaluate(
            "() => document.querySelector('#vdPaper').getBoundingClientRect().width"
        )
        assert paper_width == 794, paper_width
        # The dialog queues its close event, so the hand-back is not synchronous.
        page.locator("#vdFullClose").click()
        page.wait_for_function(
            "() => document.querySelector('#vdPaperFrame').contains("
            "document.querySelector('#vdPaper'))"
        )

        # Exports run the real vendored jsPDF, html2canvas and JSZip, so this is
        # the only place the produced files are known to be well-formed.
        # A page export can produce two files, the page and its sidecar, and
        # expect_download only catches what fires inside its own block. A
        # standing listener catches both however they are ordered.
        collected: list = []

        def remember(item: object) -> None:
            collected.append(item)

        page.on("download", remember)

        def download_all(selector: str, expected: int = 1) -> dict[str, bytes]:
            collected.clear()
            page.locator(selector).click()

            for _ in range(600):
                if len(collected) >= expected:
                    break
                page.wait_for_timeout(100)

            names = [item.suggested_filename for item in collected]
            assert len(collected) == expected, names
            return {
                item.suggested_filename.rsplit(".", 1)[-1]: Path(item.path()).read_bytes()
                for item in collected
            }

        def download_bytes(selector: str) -> bytes:
            return next(iter(download_all(selector).values()))

        exported = download_all("#vdExport", expected=2)
        text_pdf = exported["pdf"]
        assert text_pdf.startswith(b"%PDF-"), text_pdf[:16]
        assert b"Ironwood" in text_pdf or b"FlateDecode" in text_pdf

        # The sidecar rides along with the page and describes that same page.
        sidecar = json.loads(exported["json"])
        assert sidecar["schema_version"] == "1.1"
        assert sidecar["degradation"] is None, "the default scan preset is clean"
        assert sidecar["vendor_id"] == "ironwood"
        assert sidecar["fields"]["vendor_name"]["value"] == "Ironwood Construction Materials"
        assert sidecar["fields"]["po_number"] is None, "a clean invoice prints no PO number"
        assert sidecar["boxes"] is None, "boxes are off until asked for"
        line_sum = sum(item["amount"]["value"] for item in sidecar["line_items"])
        assert round(line_sum, 2) == sidecar["fields"]["subtotal"]["value"]

        page.locator('#vdPdfMode [data-pdf-mode="image"]').click()
        image_pdf = download_all("#vdExport", expected=2)["pdf"]
        assert image_pdf.startswith(b"%PDF-")
        # A rasterised page carries an embedded image, so it is far heavier than
        # the same page as a text layer.
        assert len(image_pdf) > len(text_pdf)

        page.locator('#vdFormat [data-format="png"]').click()
        expect(page.locator("#vdPdfModeField")).to_be_hidden()
        png = download_all("#vdExport", expected=2)["png"]
        assert png.startswith(b"\x89PNG\r\n\x1a\n"), png[:8]

        # With boxes on, the JSON button alone carries the geometry.
        page.locator('#vdLabels [data-labels="fields"]').click()
        boxed = json.loads(download_bytes("#vdDownloadJson"))
        assert boxed["boxes_apply_to"] == ["png", "pdf_raster"]
        assert boxed["boxes"]["page"] == {"width": 794, "height": 1123, "unit": "normalised"}
        regions = boxed["boxes"]["regions"]
        assert len(regions) > 12, len(regions)
        assert all(0 <= value <= 1 for region in regions for value in region["box"])
        assert any(region["field"] == "grand_total" for region in regions)
        assert all("words" not in region for region in regions)

        page.locator('#vdLabels [data-labels="words"]').click()
        worded = json.loads(download_bytes("#vdDownloadJson"))
        assert all("words" in region for region in worded["boxes"]["regions"])
        page.locator('#vdLabels [data-labels="json"]').click()

        page.locator('#vdMode [data-mode="batch"]').click()
        page.locator("#vdBatchCount").fill("1")
        page.locator('#vdFormat [data-format="pdf"]').click()
        zip_bytes = download_bytes("#vdExport")
        assert zip_bytes.startswith(b"PK"), zip_bytes[:4]
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            # JSZip writes the folder entries too, so only the files are counted.
            entries = [item.filename for item in archive.infolist() if not item.is_dir()]
            pages = [name for name in entries if name.endswith(".pdf")]
            labels = [name for name in entries if name.endswith(".json")]
            assert len(pages) == 1, entries
            assert len(labels) == 1, entries
            assert pages[0].startswith("ironwood/invoice/")
            assert archive.read(pages[0]).startswith(b"%PDF-")
            assert "manifest.jsonl" in entries
            assert "README.txt" in entries
            manifest = archive.read("manifest.jsonl").decode().strip().splitlines()
            assert len(manifest) == 1
            assert json.loads(manifest[0])["schema_version"] == "1.1"
            assert b"Ground truth" in archive.read("README.txt")

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")


@app_scope_skipif("vendor-docs-generator")
def test_vendor_docs_generator_batch_can_be_stopped_mid_run(
    app_browser: AppBrowserHarness,
) -> None:
    """A stop click lands while the batch is running and keeps what finished."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-flow-vendor-docs-stop",
        viewport=(1400, 900),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/vendor-docs-generator/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        page.locator('#vdMode [data-mode="batch"]').click()
        expect(page.locator("#vdBatchStop")).to_be_hidden()

        # Text PDF across the whole cross product. jsPDF is synchronous, so this
        # is the format whose loop never awaits anything: it is precisely the
        # run that used to hold the main thread from the first document to the
        # last. 900 documents take about 4.5 seconds, which is long enough that
        # a stop click has somewhere to land.
        page.locator('#vdFormat [data-format="pdf"]').click()
        page.locator('#vdInclude [data-include="all"]').click()
        page.locator("#vdBatchCount").fill("25")
        planned = 6 * 6 * 25

        downloads: list = []

        def remember(item: object) -> None:
            downloads.append(item)

        page.on("download", remember)

        page.locator("#vdExport").click()
        expect(page.locator("#vdBatchStop")).to_be_visible()
        # The run's controls live in the panel's pinned footer, inside the window.
        expect(page.locator("#vdProgress")).to_be_visible()
        footer = page.evaluate(
            """() => ({
                stop: document.querySelector('#vdBatchStop').getBoundingClientRect().bottom,
                viewport: window.innerHeight
            })"""
        )
        assert footer["stop"] <= footer["viewport"], footer

        # Wait for the run to be genuinely under way, then click. If the loop
        # never yielded, this click would sit in the queue until the whole batch
        # had already been written and the assertions below would see a full run.
        page.wait_for_function(
            "planned => {"
            "  const match = document.querySelector('#vdBatchStatus')"
            "    .textContent.match(/generating (\\d+) of/);"
            "  return match && Number(match[1]) >= 20 && Number(match[1]) < planned;"
            "}",
            arg=planned,
            timeout=30000,
        )
        page.locator("#vdBatchStop").click()

        for _ in range(600):
            if downloads:
                break
            page.wait_for_timeout(100)

        assert downloads, "a stopped run still hands over what it finished"
        name = downloads[0].suggested_filename
        assert name.endswith("_partial.zip"), name

        expect(page.locator("#vdBatchStop")).to_be_hidden()
        status = page.locator("#vdBatchStatus").text_content() or ""
        assert re.match(rf"^Stopped\. \d+ of {planned} documents in [\d.]+s\.$", status), status

        payload = Path(downloads[0].path()).read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = [item.filename for item in archive.infolist() if not item.is_dir()]
            labels = [item for item in entries if item.endswith(".json")]
            assert 0 < len(labels) < planned, len(labels)
            manifest = archive.read("manifest.jsonl").decode().strip().splitlines()
            assert len(manifest) == len(labels), (len(manifest), len(labels))
            readme = archive.read("README.txt").decode()
            assert f"Documents: {len(labels)} (run stopped early; {planned} were planned)" in readme

        # The workbench is usable again, not left in the busy state.
        expect(page.locator("#vdExport")).to_be_enabled()
        expect(page.locator("#vdExport")).to_have_text("Generate ZIP")
        expect(page.locator("#vdProgress")).to_be_hidden()


@app_scope_skipif("vendor-docs-generator")
def test_vendor_docs_generator_pdf_never_overprints_itself(
    app_browser: AppBrowserHarness,
) -> None:
    """Every combination must lay out without overlapping or off-page text.

    The PDF renderer positions in A4 points and cannot borrow the DOM's layout,
    so anything drawn at a fixed offset has to be measured against its
    neighbour. Two places were not: the vendor name overprinted the document
    title by 15pt on every Ironwood challan, and a long `Reason` value
    overprinted its own label on a quarter of credit notes. Both were invisible
    to the preview tests because the preview lays out in CSS and wraps.
    """
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-vendor-docs-pdf-geometry",
        viewport=(1200, 800),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/vendor-docs-generator/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        problems = page.evaluate(
            """async () => {
                const base = './js/modules/';
                const { buildDocument } = await import(base + 'document-model.js');
                const { renderPdf } = await import(base + 'pdf-render.js');
                const { VENDORS, DOCUMENT_TYPES } = await import(base + 'vendors.js');

                const Real = window.jspdf.jsPDF;
                let draws = [];

                // jsPDF hangs text() off each instance rather than a prototype,
                // so wrapping the constructor is the only way to observe it.
                function Recording(...args) {
                    const doc = new Real(...args);
                    const original = doc.text.bind(doc);
                    doc.text = (text, x, y, options) => {
                        const size = doc.getFontSize();
                        for (const [i, line] of (Array.isArray(text) ? text : [text]).entries()) {
                            if (typeof line !== 'string' || !line.trim()) { continue; }
                            const w = doc.getTextWidth(line);
                            const align = (options && options.align) || 'left';
                            draws.push({
                                t: line,
                                x: align === 'right' ? x - w : align === 'center' ? x - w / 2 : x,
                                y: y + i * size * 1.15 - size * 0.75,
                                w,
                                h: size,
                                pw: doc.internal.pageSize.getWidth(),
                                page: doc.internal.getCurrentPageInfo().pageNumber
                            });
                        }
                        return original(text, x, y, options);
                    };
                    return doc;
                }

                const found = [];
                for (const vendor of VENDORS) {
                    for (const type of DOCUMENT_TYPES) {
                        const styles = type.id === 'invoice' ? ['clean', 'dense'] : ['clean'];
                        for (const style of styles) {
                            for (let step = 0; step < 12; step += 1) {
                                const seed = 1000 + step * 37;
                                draws = [];
                                renderPdf(
                                    buildDocument({
                                        vendorId: vendor.id, docTypeId: type.id, style, seed
                                    }),
                                    Recording
                                );
                                const tag = `${vendor.id}/${type.id}/${style}/${seed}`;
                                for (let i = 0; i < draws.length; i += 1) {
                                    const a = draws[i];
                                    if (a.x < 20 || a.x + a.w > a.pw - 20) {
                                        found.push(`${tag} off page: ${a.t}`);
                                    }
                                    for (let j = i + 1; j < draws.length; j += 1) {
                                        const b = draws[j];
                                        if (a.page !== b.page) { continue; }
                                        const ax2 = a.x + a.w, bx2 = b.x + b.w;
                                        const ay2 = a.y + a.h, by2 = b.y + b.h;
                                        const ox = Math.min(ax2, bx2) - Math.max(a.x, b.x);
                                        const oy = Math.min(ay2, by2) - Math.max(a.y, b.y);
                                        if (ox > 1.5 && oy > 1.5) {
                                            found.push(`${tag} overprint: "${a.t}" >< "${b.t}"`);
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                return found.slice(0, 10);
            }"""
        )

        assert problems == [], problems


def test_vendor_docs_generator_boxes_land_on_the_ink_they_name(
    app_browser: AppBrowserHarness,
) -> None:
    """Every reported box must actually cover the value it claims to.

    The Node tests measure a fake layout, so they can only prove the walk and
    the arithmetic. Whether a normalised box lands on the right pixels is a
    question about a real browser laying out a real page, and the only honest
    way to ask it is to convert each box back to viewport coordinates and see
    what is underneath the middle of it.
    """
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-vendor-docs-boxes",
        viewport=(1400, 1000),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/vendor-docs-generator/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        problems = page.evaluate(
            """async () => {
                const base = './js/modules/';
                const { buildDocument } = await import(base + 'document-model.js');
                const { renderPaper } = await import(base + 'paper-render.js');
                const { collectBoxes } = await import(base + 'annotate-boxes.js');
                const { buildAnnotations } = await import(base + 'annotations.js');
                const { VENDORS, DOCUMENT_TYPES } = await import(base + 'vendors.js');

                const paper = document.getElementById('vdPaper');
                paper.scrollIntoView({ block: 'center' });
                const found = [];

                for (const vendor of VENDORS) {
                    for (const type of DOCUMENT_TYPES) {
                        const styles = type.id === 'invoice' ? ['clean', 'dense'] : ['clean'];
                        for (const style of styles) {
                            const seed = 3300 + vendor.id.length * 17 + type.id.length;
                            const model = buildDocument({
                                vendorId: vendor.id, docTypeId: type.id, style, seed
                            });
                            renderPaper(paper, model);
                            const boxes = collectBoxes(paper, { words: true });
                            const payload = buildAnnotations(model, boxes);
                            const tag = `${vendor.id}/${type.id}/${style}`;
                            const rect = paper.getBoundingClientRect();

                            if (boxes.regions.length < 12) {
                                found.push(`${tag} only ${boxes.regions.length} regions`);
                            }

                            for (const region of boxes.regions) {
                                const [x, y, w, h] = region.box;
                                if (x < 0 || y < 0 || x + w > 1.001 || y + h > 1.001) {
                                    found.push(`${tag} ${region.field} outside the page`);
                                    continue;
                                }
                                if (w <= 0 || h <= 0) {
                                    found.push(`${tag} ${region.field} has no area`);
                                    continue;
                                }

                                const cx = rect.left + (x + w / 2) * rect.width;
                                const cy = rect.top + (y + h / 2) * rect.height;
                                if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) {
                                    continue;
                                }

                                const owner = document.elementFromPoint(cx, cy);
                                const named = owner && owner.closest('[data-field]');
                                if (!named) {
                                    found.push(`${tag} ${region.field}: nothing there`);
                                } else if (named.getAttribute('data-field') !== region.field) {
                                    found.push(
                                        `${tag} ${region.field}: centre lands on ` +
                                        named.getAttribute('data-field')
                                    );
                                }

                                for (const word of region.words) {
                                    const [wx, wy, ww, wh] = word.box;
                                    const where = `${tag} ${region.field}: "${word.text}"`;
                                    if (wx < x - 0.002 || wx + ww > x + w + 0.002) {
                                        found.push(`${where} escapes its region`);
                                    }
                                    if (wy < y - 0.002 || wy + wh > y + h + 0.002) {
                                        found.push(`${where} sits off its line`);
                                    }
                                }
                            }

                            for (const region of boxes.regions) {
                                const parts = region.field.split('.');
                                const annotation = parts.length === 1
                                    ? payload.fields[region.field]
                                    : payload[parts[0]][Number(parts[1])][parts[2]];
                                if (!annotation) {
                                    found.push(`${tag} ${region.field} has no sidecar entry`);
                                } else if (!annotation.text.includes(region.text)) {
                                    found.push(
                                        `${tag} ${region.field}: page "${region.text}" ` +
                                        `vs sidecar "${annotation.text}"`
                                    );
                                }
                            }
                        }
                    }
                }
                return found.slice(0, 12);
            }"""
        )

        assert problems == [], problems


def test_vendor_docs_generator_degraded_boxes_follow_the_ink(
    app_browser: AppBrowserHarness,
) -> None:
    """Tilting the page must move the labels with it, not leave them behind.

    Degradation and boxes both pass their own tests in isolation, which is
    exactly how a feature that silently corrupts another one ships. The only
    check that catches it is this one: rasterise a real page, tilt it, and count
    the ink actually inside each transformed box against the ink still inside
    the box it started from.
    """
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-vendor-docs-degrade",
        viewport=(1400, 1000),
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/vendor-docs-generator/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        report = page.evaluate(
            """async () => {
                const base = './js/modules/';
                const { buildDocument } = await import(base + 'document-model.js');
                const { renderPaper } = await import(base + 'paper-render.js');
                const { collectBoxes, transformBoxes } = await import(base + 'annotate-boxes.js');
                const degrade = await import(base + 'degrade.js');

                const paper = document.getElementById('vdPaper');
                document.getElementById('vdPaperScale').style.setProperty('--vd-zoom', '1');
                renderPaper(paper, buildDocument({
                    vendorId: 'ironwood', docTypeId: 'invoice', style: 'clean', seed: 4242
                }));

                const clean = collectBoxes(paper);
                // Geometry only. Grain and blur would blunt the ink test without
                // telling us anything about whether the boxes moved correctly.
                const settings = { ...degrade.resolveSettings('clean'), rotation: 3, skew: 1 };
                const plan = degrade.planDegradation({
                    width: paper.offsetWidth,
                    height: paper.offsetHeight,
                    preset: 'custom',
                    seed: 4242,
                    settings
                });
                const source = await window.html2canvas(paper, {
                    backgroundColor: '#ffffff', logging: false, scale: 1, useCORS: true
                });
                const canvas = degrade.degradeCanvas(source, plan);
                const image = canvas.getContext('2d')
                    .getImageData(0, 0, canvas.width, canvas.height).data;
                const moved = transformBoxes(clean, plan.transform);

                const inkIn = ([x, y, w, h]) => {
                    const left = Math.max(0, Math.round(x * canvas.width));
                    const top = Math.max(0, Math.round(y * canvas.height));
                    const right = Math.min(canvas.width, Math.round((x + w) * canvas.width));
                    const bottom = Math.min(canvas.height, Math.round((y + h) * canvas.height));
                    let dark = 0;
                    for (let py = top; py < bottom; py += 1) {
                        for (let px = left; px < right; px += 1) {
                            if (image[(py * canvas.width + px) * 4] < 128) { dark += 1; }
                        }
                    }
                    return dark;
                };

                const problems = [];
                let movedInk = 0;
                let staleInk = 0;
                let empty = 0;

                for (let index = 0; index < clean.regions.length; index += 1) {
                    const before = clean.regions[index];
                    const after = moved.regions[index];

                    if (!after.quad) { problems.push(`${after.field} lost its quad`); continue; }
                    if (after.quad.some((value) => value < -0.01 || value > 1.01)) {
                        problems.push(`${after.field} was transformed off the page`);
                    }

                    const here = inkIn(after.box);
                    movedInk += here;
                    staleInk += inkIn(before.box);
                    if (here === 0) { empty += 1; }
                }

                return {
                    regions: clean.regions.length,
                    rotation: plan.applied.rotation,
                    problems: problems.slice(0, 8),
                    movedInk,
                    staleInk,
                    empty
                };
            }"""
        )

        assert report["problems"] == [], report["problems"]
        assert report["regions"] > 20, report
        assert abs(report["rotation"]) > 2, report
        # Every transformed box should still sit on ink. A handful of thin or
        # near-empty values is tolerable; a systematic miss is not.
        assert report["empty"] <= 2, report
        # And the transform has to be doing real work: the boxes left where the
        # DOM put them cover measurably less of the tilted page's ink.
        assert report["movedInk"] > report["staleInk"] * 1.05, report
