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

  // This classic script runs in <head> before ES modules load, so it cannot
  // import runtime.js and reads localStorage directly.
  /** @returns {string | null} The saved theme, or null when storage is empty or throws. */
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

  // app-shell.js reads these helpers from the global, so it does not duplicate them.
  globalObject.__ARTIFACTS_APP_THEME_BOOTSTRAP__ = {
    applyDocumentTheme,
    defaultTheme,
    normalizeTheme,
    readStoredTheme,
    storageKey,
  };

  applyDocumentTheme(globalObject.document, readStoredTheme());
})(globalThis);
