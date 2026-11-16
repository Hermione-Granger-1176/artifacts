/**
 * Theme-aware helpers shared by the Chart.js-based artifact apps: reading
 * chart colors from CSS custom properties and caching the derived palette per
 * theme.
 * @module chart-theme
 */

// Chart.js and its plugins load as UMD vendor globals on window. The ambient
// ChartVendorGlobals type in config/types/chart-vendor.d.ts types this view
// with the Chart.js types from the devDependencies. Read the globals at call
// time, not at module load: the vendor scripts may not have run yet.
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
 * Re-express an rgb() custom property at a given alpha. Takes the first three
 * integers in the value as the channels, and returns the raw value when it
 * holds fewer than three.
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
 * Caching variant of cssAlpha. Each property and alpha pair is read and built
 * once per reader.
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
 * Wrap a palette builder in a per-theme cache. `colors()` calls `buildPalette`
 * only when the theme (read from `data-theme` by isDark) differs from the last
 * call. `refreshPalette()` drops the cache and rebuilds at once, for handlers
 * that run after a theme change or a CSS custom property edit. The builder's
 * cssAlpha caches each color, so each alpha color is read once per theme.
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
