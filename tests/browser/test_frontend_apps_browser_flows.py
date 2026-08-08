from __future__ import annotations

import io
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

        page.locator("#selFreq").select_option("weekly")
        expect(page.locator("#metrics")).to_contain_text("Weekly EMI")

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")

        page.evaluate("window.scrollTo(0, 900)")
        page.wait_for_timeout(100)
        expect(page.locator("#scroll-top")).to_have_attribute("aria-hidden", "false")


@app_scope_skipif("tokenizer-explorer")
def test_tokenizer_explorer_flow_covers_sampling_and_theme(app_browser: AppBrowserHarness) -> None:
    """Test tokenizer explorer flow covers sampling and theme."""
    with MonitoredPage(
        app_browser.playwright,
        app_browser.server_url,
        name="app-flow-tokenizer",
        bypass_csp=True,
        browser=app_browser.browser,
    ) as session:
        page = session.page
        assert page is not None
        session.goto("/apps/tokenizer-explorer/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        initial_sentence = page.locator("#sentence-prefix").text_content() or ""
        page.locator("#tabs button").nth(2).click()
        page.wait_for_function(
            "previous => document.querySelector('#sentence-prefix').textContent !== previous",
            arg=initial_sentence,
        )

        expect(page.locator("#probability-chart")).to_be_visible()
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

        initial_pill_count = page.locator("#token-pills .pill").count()
        page.locator("#topp-slider").evaluate(
            """(element) => {
                    element.value = '20';
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
        )
        page.wait_for_timeout(100)
        assert page.locator("#token-pills .pill").count() != initial_pill_count

        page.locator("#pick-token").click()
        expect(page.locator("#sentence-completion")).not_to_have_text("")
        expect(page.locator("#token-pills .pill.winner")).to_be_visible()

        page.locator("#sample-hundred").click()
        expect(page.locator("#sample-status")).to_contain_text("tally from 100 draws")
        page.locator("#reset-samples").click()
        expect(page.locator("#sample-status")).to_contain_text("Run 100 draws")

        page.locator("#whitespace-toggle").click()
        expect(page.locator("#whitespace-toggle")).to_have_attribute("aria-pressed", "true")
        expect(
            page.locator("#token-examples .token-chip").filter(has_text="·").first
        ).to_be_visible()

        page.locator(".card-trigger").first.click()
        expect(page.locator(".card").first).to_have_class(re.compile(r"\bopen\b"))

        expect(page.locator(".section-nav")).to_be_visible()
        assert page.locator("#nav-nodes .section-nav-node").count() == 4
        page.locator("#nav-nodes .section-nav-node").last.click()
        page.wait_for_function("window.scrollY > 0")

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")


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

        # Selection drives the preview and the chips.
        page.locator("#vdVendor").select_option("ironwood")
        page.locator("#vdDocType").select_option("statement")
        expect(page.locator("#vdChipVendor")).to_have_text("Ironwood Construction Materials")
        expect(page.locator("#vdChipType")).to_have_text("Statement of account")

        # No ledger row may read as a negative balance, and no amount may print
        # its minus sign inside the currency symbol.
        balances = page.locator("#vdPaper tbody tr td:last-child").all_text_contents()
        assert balances, "the statement should have ledger rows"
        assert all(not text.strip().startswith("-") for text in balances), balances
        assert "$-" not in (page.locator("#vdPaper").text_content() or "")

        # The dense treatment is invoice-only.
        expect(page.locator("#vdLayout button").nth(1)).to_be_disabled()
        page.locator("#vdDocType").select_option("invoice")
        page.locator("#vdLayout button").nth(1).click()
        expect(page.locator("#vdChipType")).to_have_text("Invoice (dense)")
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
        def download_bytes(selector: str) -> bytes:
            with page.expect_download(timeout=60_000) as info:
                page.locator(selector).click()
            return Path(info.value.path()).read_bytes()

        text_pdf = download_bytes("#vdDownloadPdf")
        assert text_pdf.startswith(b"%PDF-"), text_pdf[:16]
        assert b"Ironwood" in text_pdf or b"FlateDecode" in text_pdf

        page.locator("#vdPdfMode").select_option("image")
        image_pdf = download_bytes("#vdDownloadPdf")
        assert image_pdf.startswith(b"%PDF-")
        # A rasterised page carries an embedded image, so it is far heavier than
        # the same page as a text layer.
        assert len(image_pdf) > len(text_pdf)

        png = download_bytes("#vdDownloadPng")
        assert png.startswith(b"\x89PNG\r\n\x1a\n"), png[:8]

        page.locator("#vdBatchCount").fill("1")
        page.locator("#vdBatchFormat").select_option("pdf")
        zip_bytes = download_bytes("#vdBatch")
        assert zip_bytes.startswith(b"PK"), zip_bytes[:4]
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            # JSZip writes the folder entries too, so only the files are counted.
            entries = [item for item in archive.infolist() if not item.is_dir()]
            assert len(entries) == 1, [item.filename for item in entries]
            assert entries[0].filename.startswith("ironwood/invoice/")
            assert entries[0].filename.endswith(".pdf")
            assert archive.read(entries[0]).startswith(b"%PDF-")

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")


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
