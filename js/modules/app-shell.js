import { createFrameScheduler } from "./frame-scheduler.js";
import { scrollBehavior } from "./motion.js";
import { writeStorage } from "./runtime.js";
import { createThemeSwitchGuard } from "./theme-switching.js";

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

/** Every app lives at apps/<slug>/, two levels below the gallery. */
const HOME_PATH = "../../";

const APP_HEADER_MARKUP = `
  <header class="app-header">
    <div class="app-header-inner">
      <div class="app-nav">
        <button id="back-button" class="icon-button" type="button" aria-label="Go back" title="Go back">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m15 18-6-6 6-6"></path>
          </svg>
        </button>
        <a href="${HOME_PATH}" class="brand-link" aria-label="Go to Artifacts home">
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
  <div id="runtime-error" class="runtime-error hidden" role="alert" aria-live="assertive">
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
 * Fill a placeholder slot with the given markup.
 * @param {Element} slot - Placeholder element to fill.
 * @param {string} markup - HTML markup to insert.
 */
function renderMarkupSlot(slot, markup) {
  slot.innerHTML = markup.trim();
}

/**
 * Inject shared shell markup into the empty `[data-app-shell]` slots named
 * "header", "runtime-error", and "scroll-top" that every app page ships. Apps
 * call it once at module load, before the runtime looks up the error banner.
 * @param {{ documentObj?: Document }} [options={}]
 * @returns {void}
 */
export function renderAppShell({ documentObj = document } = {}) {
  /** @param {string} name - Slot name. */
  const slot = (name) => /** @type {Element} */ (documentObj.querySelector(`[data-app-shell="${name}"]`));
  renderMarkupSlot(slot("header"), APP_HEADER_MARKUP);
  renderMarkupSlot(slot("runtime-error"), APP_RUNTIME_ERROR_MARKUP);
  renderMarkupSlot(slot("scroll-top"), APP_SCROLL_TOP_MARKUP);
}

/**
 * Wire the theme toggle, back button, and scroll-to-top button that
 * renderAppShell injected. Requires app-theme.js to have run first, because
 * theme values are normalized through `window.__ARTIFACTS_APP_THEME_BOOTSTRAP__`.
 * @param {{
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
  metaThemeColors = {
    dark: "rgb(20, 20, 20)",
    light: "rgb(248, 248, 246)"
  },
  onThemeChange = () => {}
} = {}) {
  const windowObj = /** @type {AppShellWindow} */ (/** @type {unknown} */ (window));
  const html = document.documentElement;
  const backButton = /** @type {HTMLElement} */ (document.getElementById("back-button"));
  const themeToggle = /** @type {HTMLElement} */ (document.getElementById("theme-toggle"));
  const scrollTop = /** @type {HTMLElement} */ (document.getElementById("scroll-top"));
  const themeColorMeta = /** @type {Element} */ (document.querySelector('meta[name="theme-color"]'));

  function currentTheme() {
    return windowObj.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(
      html.getAttribute("data-theme")
    );
  }

  /** @param {string} theme - Active theme name. */
  function syncThemeColor(theme) {
    themeColorMeta.setAttribute(
      "content",
      theme === "dark" ? metaThemeColors.dark : metaThemeColors.light
    );
  }

  function syncThemeToggle() {
    const theme = currentTheme();
    const nextTheme = theme === "dark" ? "light" : "dark";
    themeToggle.setAttribute("aria-pressed", String(theme === "dark"));
    themeToggle.setAttribute("aria-label", `Switch to ${nextTheme} theme`);
    themeToggle.setAttribute("title", `Switch to ${nextTheme} theme`);
  }

  // Turn CSS transitions off while the theme changes, so every themed color
  // flips together instead of fading at its own speed.
  const suspendTransitions = createThemeSwitchGuard(html, window);

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
  // history has an earlier entry. Otherwise go to the gallery. A non-empty
  // document.referrer is always an absolute URL.
  function handleBackClick() {
    if (
      !document.referrer ||
      new URL(document.referrer).origin !== window.location.origin ||
      window.history.length <= 1
    ) {
      window.location.href = HOME_PATH;
      return;
    }

    window.history.back();
  }

  // Visibility last written; null until the first write. Skip DOM writes
  // while the visibility is unchanged.
  let scrollTopVisible = /** @type {boolean | null} */ (null);

  function updateScrollTopVisibility() {
    const isVisible = window.scrollY > 280;
    if (isVisible === scrollTopVisible) {
      return;
    }
    scrollTopVisible = isVisible;
    scrollTop.classList.toggle("is-visible", isVisible);
    scrollTop.setAttribute("aria-hidden", String(!isVisible));
    scrollTop.tabIndex = isVisible ? 0 : -1;
  }

  backButton.addEventListener("click", handleBackClick);

  themeToggle.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
  });

  scrollTop.addEventListener("click", () => {
    window.scrollTo({ top: 0, behavior: scrollBehavior() });
  });
  window.addEventListener("scroll", createFrameScheduler(updateScrollTopVisibility), {
    passive: true
  });
  updateScrollTopVisibility();

  syncThemeColor(currentTheme());
  syncThemeToggle();

  return {
    applyTheme,
    syncThemeToggle,
    updateScrollTopVisibility
  };
}
