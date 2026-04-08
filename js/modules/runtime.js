/**
 * Read a value from localStorage, returning a fallback on failure.
 * @param {string} key
 * @param {string|null} [fallbackValue=null]
 * @returns {string|null}
 */
export function readStorage(key, fallbackValue = null) {
  try {
    const value = window.localStorage.getItem(key);
    return value ?? fallbackValue;
  } catch (_error) {
    return fallbackValue;
  }
}

/**
 * Write a value to localStorage, returning success status.
 * @param {string} key
 * @param {string} value
 * @returns {boolean}
 */
export function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch (_error) {
    return false;
  }
}

/** Extract a human-readable message from an error of any shape. */
function normalizeErrorMessage(error) {
  if (error instanceof Error && error.message) {
    return error.message;
  }

  if (typeof error === 'string' && error) {
    return error;
  }

  if (error && typeof error === 'object' && 'message' in error && error.message) {
    return String(error.message);
  }

  return 'Unknown runtime error';
}

/** Normalize console output into a single comparable line. */
function normalizeConsoleMessage(message) {
  return String(message).replace(/\s+/g, ' ').trim();
}

/** Ignore expected bootstrap validation noise that is already surfaced in the UI. */
function shouldIgnoreRuntimeError(message) {
  const normalizedMessage = normalizeConsoleMessage(message).toLowerCase();
  return normalizedMessage.includes('window.artifacts_data must be an array');
}

/** Build a copyable diagnostics summary for the latest runtime error. */
function buildErrorSummary(errorRecord, documentObj, windowObj) {
  const locationHref = windowObj?.location?.href || '';
  const userAgent = windowObj?.navigator?.userAgent || '';
  const theme = documentObj?.documentElement?.dataset?.theme || '';
  const runtimeStatus = documentObj?.documentElement?.dataset?.runtimeStatus || '';
  const summary = [
    `Context: ${errorRecord.context}`,
    `Message: ${errorRecord.message}`,
    `Fatal: ${errorRecord.fatal ? 'yes' : 'no'}`,
    `Timestamp: ${errorRecord.timestamp}`
  ];

  if (locationHref) {
    summary.push(`URL: ${locationHref}`);
  }
  if (theme) {
    summary.push(`Theme: ${theme}`);
  }
  if (runtimeStatus) {
    summary.push(`Runtime status: ${runtimeStatus}`);
  }
  if (userAgent) {
    summary.push(`User agent: ${userAgent}`);
  }

  return summary.join('\n');
}

/** Sync the runtime error details UI to the latest captured error. */
function updateRuntimeDiagnostics(documentObj, state) {
  if (typeof documentObj.getElementById !== 'function') {
    return;
  }
  const details = documentObj.getElementById('runtime-error-details');
  const output = documentObj.getElementById('runtime-error-output');
  const copyButton = documentObj.getElementById('runtime-error-copy');
  const summary = state.lastError?.summary || '';
  const hasSummary = Boolean(summary);

  if (details) {
    details.hidden = !hasSummary;
  }
  if (output) {
    output.textContent = summary;
  }
  if (copyButton) {
    copyButton.hidden = !hasSummary;
    if (!hasSummary) {
      copyButton.textContent = 'Copy error details';
      copyButton.removeAttribute('data-copy-state');
    }
  }
}

/** Copy the latest runtime diagnostics summary when clipboard access is available. */
async function copyRuntimeDiagnostics(state, windowObj, documentObj) {
  const summary = state.lastError?.summary || '';
  if (!summary) {
    return false;
  }

  const writeText = windowObj?.navigator?.clipboard?.writeText;
  if (typeof writeText !== 'function') {
    return false;
  }

  try {
    await writeText.call(windowObj.navigator.clipboard, summary);
    const copyButton = documentObj.getElementById('runtime-error-copy');
    if (copyButton) {
      copyButton.textContent = 'Copied';
      copyButton.setAttribute('data-copy-state', 'copied');
    }
    return true;
  } catch (_error) {
    return false;
  }
}

/**
 * Create a runtime instance providing error reporting, storage access, and lifecycle status.
 * @param {{ consoleObj?: Console, documentObj?: Document, windowObj?: Window }} [options={}]
 *   Injected browser globals for startup and tests.
 * @returns {{
 *   markReady: () => void,
 *   readStorage: (key: string, fallbackValue?: string|null) => string|null,
 *   reportError: (error: *, context: string, options?: { fatal?: boolean }) => void,
 *   setupGlobalErrorHandlers: () => void,
 *   state: {
 *     ready: boolean,
 *     lastError: ({ context: string, message: string, fatal: boolean, timestamp: string, summary: string }|null)
 *   },
 *   writeStorage: (key: string, value: string) => boolean
 * }} Runtime API.
 */
export function createRuntime({ consoleObj = console, documentObj = document, windowObj = window } = {}) {
  const state = {
    ready: false,
    lastError: null
  };
  const runtimeErrorBanner = documentObj.getElementById('runtime-error');

  windowObj.__ARTIFACTS_RUNTIME__ = state;
  documentObj.documentElement.dataset.runtimeStatus = 'booting';
  if (typeof documentObj.addEventListener === 'function' && !windowObj.__ARTIFACTS_DIAGNOSTICS_BOUND__) {
    windowObj.__ARTIFACTS_DIAGNOSTICS_BOUND__ = true;
    documentObj.addEventListener('click', (event) => {
      const copyButton = event.target?.closest?.('#runtime-error-copy');
      if (!copyButton) {
        return;
      }
      void copyRuntimeDiagnostics(state, windowObj, documentObj);
    });
  }

  const setStatus = (value) => {
    documentObj.documentElement.dataset.runtimeStatus = value;
  };

  const reportError = (error, context, { fatal = false } = {}) => {
    state.lastError = {
      context,
      message: normalizeErrorMessage(error),
      fatal,
      timestamp: new Date().toISOString(),
      summary: ''
    };
    state.lastError.summary = buildErrorSummary(state.lastError, documentObj, windowObj);
    updateRuntimeDiagnostics(documentObj, state);

    if (fatal) {
      setStatus('error');
      if (runtimeErrorBanner) {
        runtimeErrorBanner.classList.remove('visually-hidden');
        runtimeErrorBanner.classList.remove('hidden');
      }
    }

    const consoleMessage = `[Artifacts] ${context}: ${state.lastError.message}`;
    if (!shouldIgnoreRuntimeError(consoleMessage)) {
      consoleObj.error(consoleMessage, error);
    }
  };

  return {
    markReady() {
      state.ready = true;
      setStatus('ready');
    },

    readStorage(key, fallbackValue = null) {
      try {
        const value = windowObj.localStorage.getItem(key);
        return value ?? fallbackValue;
      } catch (error) {
        reportError(error, `localStorage read (${key})`);
        return fallbackValue;
      }
    },

    reportError,

    setupGlobalErrorHandlers() {
      if (windowObj.__ARTIFACTS_ERROR_HANDLERS_BOUND__) {
        return;
      }

      windowObj.__ARTIFACTS_ERROR_HANDLERS_BOUND__ = true;

      windowObj.addEventListener('error', (event) => {
        reportError(event.error || event.message, 'window error', { fatal: !state.ready });
      });

      windowObj.addEventListener('unhandledrejection', (event) => {
        reportError(event.reason, 'unhandled rejection', { fatal: !state.ready });
      });
    },

    state,

    writeStorage(key, value) {
      try {
        windowObj.localStorage.setItem(key, value);
        return true;
      } catch (error) {
        reportError(error, `localStorage write (${key})`);
        return false;
      }
    }
  };
}
