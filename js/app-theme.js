(function bootstrapAppTheme(globalObject) {
  const storageKey = "theme";
  const defaultTheme = "light";

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
