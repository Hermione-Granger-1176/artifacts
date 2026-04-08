import { writeStorage } from "./runtime.js";

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
      <polyline points="18 15 12 9 6 15"></polyline>
    </svg>
  </button>
`;

function renderMarkupSlot(slot, markup) {
  if (!slot || slot.childElementCount > 0) {
    return;
  }

  slot.innerHTML = markup.trim();
}

/**
 * Inject shared shell markup (header, error banner, scroll-to-top) into placeholder slots.
 * @param {{ documentObj?: Document, homePath?: string }} [options={}]
 * @param {Document} [options.documentObj=document] - Document to query.
 * @param {string} [options.homePath='../../'] - Relative path to the gallery root.
 * @returns {void}
 */
export function renderAppShell({
  documentObj = document,
  homePath = "../../"
} = {}) {
  renderMarkupSlot(
    documentObj.querySelector('[data-app-shell="header"]'),
    APP_HEADER_MARKUP.replaceAll("__HOME_PATH__", homePath)
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
 * Initialize the shared app shell with theme toggle, back navigation, and scroll-to-top.
 * @param {{
 *   homePath?: string,
 *   metaThemeColors?: {dark: string, light: string},
 *   onThemeChange?: (theme: string) => void
 * }} [options={}]
 * @param {string} [options.homePath='../../'] - Relative path to the gallery root.
 * @param {{dark: string, light: string}} [options.metaThemeColors] - Theme-color meta values.
 * @param {(theme: string) => void} [options.onThemeChange] - Callback when theme changes.
 * @returns {{
 *   applyTheme: (theme: string) => void,
 *   syncThemeToggle: () => void,
 *   updateScrollTopVisibility: () => void
 * }}
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
  const html = document.documentElement;
  const backButton = document.getElementById("back-button");
  const themeToggle = document.getElementById("theme-toggle");
  const scrollTop = document.getElementById("scroll-top");
  const themeColorMeta = document.querySelector('meta[name="theme-color"]');
  const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  function currentTheme() {
    return window.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(
      html.getAttribute("data-theme")
    );
  }

  function syncThemeColor(theme) {
    if (!themeColorMeta) {
      return;
    }

    themeColorMeta.setAttribute(
      "content",
      metaThemeColors[theme] || metaThemeColors.light
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

  function applyTheme(theme) {
    const normalizedTheme =
      window.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(theme);
    html.setAttribute("data-theme", normalizedTheme);
    syncThemeColor(normalizedTheme);
    syncThemeToggle();
    writeStorage("theme", normalizedTheme);
    onThemeChange(normalizedTheme);
  }

  function handleBackClick() {
    if (!document.referrer) {
      window.location.href = homePath;
      return;
    }

    let referrerUrl;
    try {
      referrerUrl = new URL(document.referrer);
    } catch (_error) {
      window.location.href = homePath;
      return;
    }

    if (
      referrerUrl.origin !== window.location.origin ||
      window.history.length <= 1
    ) {
      window.location.href = homePath;
      return;
    }

    window.history.back();
  }

  function updateScrollTopVisibility() {
    if (!scrollTop) {
      return;
    }

    const isVisible = window.scrollY > 280;
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
    window.addEventListener("scroll", updateScrollTopVisibility, { passive: true });
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
