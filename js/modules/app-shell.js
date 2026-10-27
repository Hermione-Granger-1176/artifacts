import { createFrameScheduler } from "./frame-scheduler.js";
import { writeStorage } from "./runtime.js";

/**
 * @typedef {{
 *   applyDocumentTheme: (documentObject: Document, theme: string | null | undefined) => string,
 *   defaultTheme: string,
 *   normalizeTheme: (theme: string | null | undefined) => string,
 *   readStoredTheme: () => string | null,
 *   storageKey: string
 * }} AppThemeBootstrap
 * @typedef {Window & { __ARTIFACTS_APP_THEME_BOOTSTRAP__: AppThemeBootstrap }} AppShellWindow
 */

const SAFE_RELATIVE_PATH_RE = /^[./a-zA-Z0-9_-]+$/;

const APP_HEADER_MARKUP = `
  <header class="app-header">
    <div class="app-header-inner">
      <div class="app-nav">
        <button id="back-button" class="icon-button" type="button" aria-label="Go back" title="Go back">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m15 18-6-6 6-6"></path>
          </svg>
        </button>
        <a href="__HOME_PATH__" class="brand-link" aria-label="Go to Artifacts home">
          <svg class="brand-mark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" aria-hidden="true">
            <rect fill="rgb(217, 119, 6)" x="14" y="20" width="84" height="92" rx="18"></rect>
            <rect fill="rgb(243, 214, 166)" x="26" y="12" width="84" height="92" rx="18"></rect>
            <line x1="42" y1="32" x2="94" y2="32" stroke="rgb(196, 168, 130)" stroke-width="4" stroke-linecap="round"></line>
            <line x1="42" y1="52" x2="94" y2="52" stroke="rgb(196, 168, 130)" stroke-width="4" stroke-linecap="round"></line>
            <line x1="42" y1="72" x2="86" y2="72" stroke="rgb(196, 168, 130)" stroke-width="4" stroke-linecap="round"></line>
          </svg>
          <span class="brand-name">Artifacts</span>
        </a>
      </div>
      <button id="theme-toggle" class="icon-button" type="button" aria-label="Switch to dark theme" aria-pressed="false" title="Switch to dark theme">
        <svg class="icon-sun" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
        <svg class="icon-moon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      </button>
    </div>
  </header>
`;

const APP_RUNTIME_ERROR_MARKUP = `
  <div id="runtime-error" class="runtime-error visually-hidden" role="alert" aria-live="assertive">
    <p>The app failed to initialize correctly. Reload the page, or try again later.</p>
    <details id="runtime-error-details" class="runtime-error-details" hidden>
      <summary>Technical details</summary>
      <pre id="runtime-error-output" class="runtime-error-output"></pre>
      <button id="runtime-error-copy" class="runtime-error-copy" type="button" hidden>Copy error details</button>
    </details>
  </div>
`;

const APP_SCROLL_TOP_MARKUP = `
  <button id="scroll-top" class="scroll-top" type="button" aria-label="Scroll to top" aria-hidden="true" tabindex="-1">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <line x1="12" y1="19" x2="12" y2="5"></line>
      <polyline points="5 12 12 5 19 12"></polyline>
    </svg>
  </button>
`;

/**
 * Fill a placeholder slot with the given markup when the slot has no element children.
 * @param {Element | null | undefined} slot - Placeholder element to fill.
 * @param {string} markup - HTML markup to insert.
 */
function renderMarkupSlot(slot, markup) {
  if (!slot || slot.childElementCount > 0) {
    return;
  }

  slot.innerHTML = markup.trim();
}

/**
 * Inject shared shell markup into the `[data-app-shell]` slots named "header",
 * "runtime-error", and "scroll-top". Missing or already filled slots are skipped.
 * A `homePath` with characters outside `./a-zA-Z0-9_-` falls back to "../../" in the header link.
 * @param {{ documentObj?: Document, homePath?: string }} [options={}]
 * @returns {void}
 */
export function renderAppShell({
  documentObj = document,
  homePath = "../../"
} = {}) {
  renderMarkupSlot(
    documentObj.querySelector('[data-app-shell="header"]'),
    APP_HEADER_MARKUP.replaceAll("__HOME_PATH__", SAFE_RELATIVE_PATH_RE.test(homePath) ? homePath : "../../")
  );
  renderMarkupSlot(
    documentObj.querySelector('[data-app-shell="runtime-error"]'),
    APP_RUNTIME_ERROR_MARKUP
  );
  renderMarkupSlot(
    documentObj.querySelector('[data-app-shell="scroll-top"]'),
    APP_SCROLL_TOP_MARKUP
  );
}

/**
 * Render the shell slots, then wire the theme toggle, back button, and
 * scroll-to-top button. Requires app-theme.js to have run first, because theme
 * values are normalized through `window.__ARTIFACTS_APP_THEME_BOOTSTRAP__`.
 * @param {{
 *   homePath?: string,
 *   metaThemeColors?: {dark: string, light: string},
 *   onThemeChange?: (theme: string) => void
 * }} [options={}]
 * @returns {{
 *   applyTheme: (theme: string) => void,
 *   syncThemeToggle: () => void,
 *   updateScrollTopVisibility: () => void
 * }} `applyTheme` normalizes the theme, sets `data-theme`, the theme-color meta
 *   tag, and the toggle label, saves the theme to localStorage under "theme",
 *   and calls `onThemeChange`. `syncThemeToggle` re-reads `data-theme` into the
 *   toggle. `updateScrollTopVisibility` shows the scroll-to-top button once
 *   `scrollY` passes 280px.
 */
export function initAppShell({
  homePath = "../../",
  metaThemeColors = {
    dark: "rgb(20, 20, 20)",
    light: "rgb(248, 248, 246)"
  },
  onThemeChange = () => {}
} = {}) {
  renderAppShell({ documentObj: document, homePath });
  const windowObj = /** @type {AppShellWindow} */ (/** @type {unknown} */ (window));
  const html = document.documentElement;
  const backButton = document.getElementById("back-button");
  const themeToggle = document.getElementById("theme-toggle");
  const scrollTop = document.getElementById("scroll-top");
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function currentTheme() {
    return windowObj.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(
      html.getAttribute("data-theme")
    );
  }

  /** @param {string} theme - Active theme name. */
  function syncThemeColor(theme) {
    if (!themeColorMeta) {
      return;
    }

    themeColorMeta.setAttribute(
      "content",
      theme === "dark" ? metaThemeColors.dark : metaThemeColors.light
    );
  }

  function syncThemeToggle() {
    if (!themeToggle) {
      return;
    }

    const theme = currentTheme();
    const nextTheme = theme === "dark" ? "light" : "dark";
    themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
    themeToggle.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
    themeToggle.setAttribute("title", `Switch to ${nextTheme} theme`);
  }

  // Bumped on every theme change so only the latest change removes the class.
  let themeSwitchId = 0;

  /**
   * Turn CSS transitions off while the theme changes, so every themed color
   * flips together instead of fading at its own speed. Add the shared
   * .theme-switching class now and remove it after two animation frames, once
   * the new colors have painted.
   */
  function suspendTransitions() {
    const switchId = ++themeSwitchId;
    html.classList.add("theme-switching");
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        if (switchId === themeSwitchId) {
          html.classList.remove("theme-switching");
        }
      });
    });
  }

  /** @param {string} theme - Requested theme name. */
  function applyTheme(theme) {
    const normalizedTheme =
      windowObj.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(theme);
    suspendTransitions();
    html.setAttribute("data-theme", normalizedTheme);
    syncThemeColor(normalizedTheme);
    syncThemeToggle();
    writeStorage("theme", normalizedTheme);
    onThemeChange(normalizedTheme);
  }

  // Go back in history only when the referrer is a same-origin page and the
  // history has an earlier entry. Otherwise go to homePath.
  function handleBackClick() {
    const navigateHome = () => {
      window.location.href = homePath;
    };

    if (!document.referrer) {
      navigateHome();
      return;
    }

    let referrerUrl;
    try {
      referrerUrl = new URL(document.referrer);
    } catch (_error) {
      navigateHome();
      return;
    }

    if (
      referrerUrl.origin !== window.location.origin ||
      window.history.length <= 1
    ) {
      navigateHome();
      return;
    }

    window.history.back();
  }

  // Visibility last written; null until the first write. Skip DOM writes
  // while the visibility is unchanged.
  let scrollTopVisible = /** @type {boolean | null} */ (null);

  function updateScrollTopVisibility() {
    if (!scrollTop) {
      return;
    }

    const isVisible = window.scrollY > 280;
    if (isVisible === scrollTopVisible) {
      return;
    }
    scrollTopVisible = isVisible;
    scrollTop.classList.toggle("is-visible", isVisible);
    scrollTop.setAttribute("aria-hidden", String(!isVisible));
    scrollTop.tabIndex = isVisible ? 0 : -1;
  }

  if (backButton) {
    backButton.addEventListener("click", handleBackClick);
  }

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      applyTheme(currentTheme() === "dark" ? "light" : "dark");
    });
  }

  if (scrollTop) {
    scrollTop.addEventListener("click", () => {
      const behavior = prefersReducedMotion.matches ? "auto" : "smooth";
      window.scrollTo({ top: 0, behavior });
    });
    window.addEventListener("scroll", createFrameScheduler(updateScrollTopVisibility), {
      passive: true
    });
    updateScrollTopVisibility();
  }

  syncThemeColor(currentTheme());
  syncThemeToggle();

  return {
    applyTheme,
    syncThemeToggle,
    updateScrollTopVisibility
  };
}
