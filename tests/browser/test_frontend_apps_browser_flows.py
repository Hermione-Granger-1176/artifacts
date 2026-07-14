from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from tests.browser.frontend_helpers import (
    MonitoredPage,
    StaticServer,
    app_scope_skipif,
    build_real_site,
)


@app_scope_skipif("loan-amortization")
def test_loan_amortization_flow_covers_theme_and_schedule(tmp_path: Path, monkeypatch) -> None:
    """Test loan amortization flow covers theme and schedule."""
    deploy_root = build_real_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright,
            server.url,
            name="app-flow-loan",
            viewport=(1100, 720),
            bypass_csp=True,
        ) as session,
    ):
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
def test_tokenizer_explorer_flow_covers_sampling_and_theme(tmp_path: Path, monkeypatch) -> None:
    """Test tokenizer explorer flow covers sampling and theme."""
    deploy_root = build_real_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright, server.url, name="app-flow-tokenizer", bypass_csp=True
        ) as session,
    ):
        page = session.page
        assert page is not None
        session.goto("/apps/tokenizer-explorer/")
        page.wait_for_function("window.__ARTIFACT_READY__ === true")

        initial_sentence = page.locator("#sentence-prefix").text_content() or ""
        page.locator("#tabs .tab").nth(2).click()
        page.wait_for_function(
            "previous => document.querySelector('#sentence-prefix').textContent !== previous",
            arg=initial_sentence,
        )

        initial_width = page.locator(".bar-fill").first.evaluate(
            "element => getComputedStyle(element).width"
        )
        page.locator("#temp-slider").evaluate(
            """(element) => {
                    element.value = '20';
                    element.dispatchEvent(new Event('input', { bubbles: true }));
                }"""
        )
        page.wait_for_function(
            "previous => getComputedStyle(document.querySelector('.bar-fill')).width !== previous",
            arg=initial_width,
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

        page.locator(".card-trigger").first.click()
        expect(page.locator(".card").first).to_have_class(re.compile(r"\bopen\b"))

        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "dark")


@app_scope_skipif("prompt-caching")
def test_prompt_caching_flow_covers_calculator_attention_and_embeddings(
    tmp_path: Path, monkeypatch
) -> None:
    """Test prompt caching calculator, attention walkthrough, and embedding output changes."""
    deploy_root = build_real_site(tmp_path, monkeypatch)

    with (
        StaticServer(deploy_root) as server,
        sync_playwright() as playwright,
        MonitoredPage(
            playwright, server.url, name="app-flow-prompt-caching", bypass_csp=True
        ) as session,
    ):
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
