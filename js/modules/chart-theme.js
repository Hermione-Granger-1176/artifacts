/**
 * Theme-aware helpers shared by the Chart.js-based artifact apps: reading
 * chart colors from CSS custom properties and caching the derived palette per
 * theme so chart syncs do not re-read computed styles on every frame.
 * @module chart-theme
 */

// Chart.js and its plugins load as vendor globals on window. The runtime
// depends only on those UMD globals; the ambient ChartVendorGlobals type in
// config/types/chart-vendor.d.ts gives this view real Chart.js types (sourced
// from the types-only devDependencies) without adding a runtime dependency.
// Resolve at call time (never a cached reference).
/** @returns {ChartVendorGlobals} The window view of the vendor chart globals. */
export function chartGlobal() {
  return /** @type {ChartVendorGlobals} */ (/** @type {unknown} */ (window));
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
  return withAlpha(cssValue(propertyName), alpha);
}

/**
 * @param {string} raw - A color value, normally rgb().
 * @param {number} alpha - Alpha channel for the returned color.
 * @returns {string} An rgba() color, or the raw value when it does not hold three numeric channels.
 */
function withAlpha(raw, alpha) {
  const matches = raw.match(/\d+/g);
  if (!matches || matches.length < 3) {
    return raw;
  }
  return `rgba(${matches[0]}, ${matches[1]}, ${matches[2]}, ${alpha})`;
}

/**
 * A cssAlpha that reads each property and builds each alpha color once. The
 * palette's alpha methods run on every chart sync, and every uncached read is a
 * getComputedStyle call that can also force a style recalculation.
 * @returns {typeof cssAlpha} The caching reader, valid for one theme.
 */
function createAlphaReader() {
  /** @type {Map<string, string>} */
  const built = new Map();
  return (propertyName, alpha) => {
    const key = `${propertyName}|${alpha}`;
    let color = built.get(key);
    if (color === undefined) {
      color = cssAlpha(propertyName, alpha);
      built.set(key, color);
    }
    return color;
  };
}

/** @returns {boolean} Whether the document is currently in the dark theme. */
export function isDark() {
  return document.documentElement.getAttribute("data-theme") === "dark";
}

/**
 * Wrap a palette builder in a per-theme cache. `colors()` rebuilds only when
 * the theme changed since the last call; `refreshPalette()` drops the cache
 * and rebuilds immediately, for theme-change handlers. The builder's cssAlpha
 * also caches, so palette methods that take an alpha read styles once per theme.
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
    cachedPalette = buildPalette({ css: cssValue, cssAlpha: createAlphaReader() });
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
