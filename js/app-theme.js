(function bootstrapAppTheme(globalObject) {
  const storageKey = "theme";
  const defaultTheme = "light";

  /**
   * @param {string | null | undefined} theme - Candidate theme value.
   * @returns {string} "dark" or the default theme.
   */
  function normalizeTheme(theme) {
    return theme === "dark" ? "dark" : defaultTheme;
  }

  // This file runs synchronously in <head> before ES modules load.
  // It cannot import from runtime.js. The inline localStorage access
  // is intentional.
  function readStoredTheme() {
    try {
      return globalObject.localStorage?.getItem(storageKey);
    } catch (_error) {
      return null;
    }
  }

  /**
   * @param {Document | null | undefined} documentObject - Target document.
   * @param {string | null | undefined} theme - Candidate theme value.
   * @returns {string} The applied normalized theme.
   */
  function applyDocumentTheme(documentObject, theme) {
    if (!documentObject?.documentElement) {
      return defaultTheme;
    }

    const normalizedTheme = normalizeTheme(theme);
    documentObject.documentElement.dataset.theme = normalizedTheme;
    return normalizedTheme;
  }

  globalObject.__ARTIFACTS_APP_THEME_BOOTSTRAP__ = {
    applyDocumentTheme,
    defaultTheme,
    normalizeTheme,
    readStoredTheme,
    storageKey,
  };

  applyDocumentTheme(globalObject.document, readStoredTheme());
})(globalThis);
