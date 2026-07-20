// Ambient types for the app-defined globals the classic bootstrap scripts
// (js/app-theme.js, js/boot-guard.js) attach to the global object before the ES
// module bundle runs, plus the readiness flag the app runtime and browser tests
// read from window.
declare global {
  // eslint-disable-next-line no-var
  var __ARTIFACTS_APP_THEME_BOOTSTRAP__: {
    applyDocumentTheme: (
      documentObject: Document | null | undefined,
      theme: string | null | undefined,
    ) => string;
    defaultTheme: string;
    normalizeTheme: (theme: string | null | undefined) => string;
    readStoredTheme: () => string | null;
    storageKey: string;
  };

  // eslint-disable-next-line no-var
  var __ARTIFACTS_BOOT_GUARD__: {
    checkBoot: (documentObject: Document | null | undefined) => boolean;
    defaultTimeoutMs: number;
    isBooted: (documentObject: Document | null | undefined) => boolean;
    readRuntimeStatus: (documentObject: Document | null | undefined) => string;
    revealStartupError: (documentObject: Document | null | undefined) => boolean;
    scheduleGuard: (
      target: typeof globalThis | null | undefined,
      timeoutMs: number | undefined,
    ) => number | null;
  };

  interface Window {
    __ARTIFACT_READY__?: boolean;
  }
}

export {};
