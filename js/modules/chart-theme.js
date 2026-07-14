/**
 * Theme-aware helpers shared by the Chart.js-based artifact apps: reading
 * chart colors from CSS custom properties and caching the derived palette per
 * theme so chart syncs do not re-read computed styles on every frame.
 * @module chart-theme
 */

// Chart.js and its plugins load as vendor globals on window. They ship no
// local type definitions, so read them through an any-typed view of window
// resolved at call time (never a cached reference) rather than adding a
// runtime dependency.
/** @returns {any} The window object typed loosely for vendor chart globals. */
export function chartGlobal() {
  return /** @type {any} */ (window);
}

/**
 * Read a CSS custom property from the body's computed style.
 * @param {string} propertyName - Custom property name (e.g. "--color-blue").
 * @returns {string} The trimmed property value.
 */
export function cssValue(propertyName) {
  return getComputedStyle(document.body).getPropertyValue(propertyName).trim();
}

/**
 * Re-express an rgb() custom property at a given alpha. Falls back to the
 * raw value when the property does not hold three numeric channels.
 * @param {string} propertyName - Custom property name holding an rgb() color.
 * @param {number} alpha - Alpha channel for the returned color.
 * @returns {string} An rgba() color, or the raw value on fallback.
 */
export function cssAlpha(propertyName, alpha) {
  const raw = cssValue(propertyName);
  const matches = raw.match(/\d+/g);
  if (!matches || matches.length < 3) {
    return raw;
  }
  return `rgba(${matches[0]}, ${matches[1]}, ${matches[2]}, ${alpha})`;
}

/** @returns {boolean} Whether the document is currently in the dark theme. */
export function isDark() {
  return document.documentElement.getAttribute("data-theme") === "dark";
}

/**
 * Wrap a palette builder in a per-theme cache. `colors()` rebuilds only when
 * the theme changed since the last call; `refreshPalette()` drops the cache
 * and rebuilds immediately, for theme-change handlers.
 * @template T
 * @param {(helpers: { css: typeof cssValue, cssAlpha: typeof cssAlpha }) => T} buildPalette
 * @returns {{ colors: () => T, refreshPalette: () => T }}
 */
export function createPaletteCache(buildPalette) {
  let cachedPalette = /** @type {T | null} */ (null);
  let cachedTheme = /** @type {string | null} */ (null);

  function colors() {
    const theme = isDark() ? "dark" : "light";
    if (cachedPalette && cachedTheme === theme) {
      return cachedPalette;
    }

    cachedTheme = theme;
    cachedPalette = buildPalette({ css: cssValue, cssAlpha });
    return cachedPalette;
  }

  return {
    colors,
    refreshPalette() {
      cachedPalette = null;
      cachedTheme = null;
      return colors();
    }
  };
}
