from __future__ import annotations

import re
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
