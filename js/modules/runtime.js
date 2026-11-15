/**
 * @typedef {{
 *   context: string,
 *   message: string,
 *   fatal: boolean,
 *   timestamp: string,
 *   summary: string
 * }} RuntimeErrorRecord
 * @typedef {{ ready: boolean, lastError: RuntimeErrorRecord | null }} RuntimeState
 * @typedef {Window & { __ARTIFACTS_RUNTIME__?: RuntimeState }} RuntimeWindow
 */

/**
 * Write a value to localStorage, returning success status. Unlike the
 * `writeStorage` that createRuntime returns, it does not report the error.
 * @param {string} key - Storage key to write.
 * @param {string} value - Value to persist.
 * @returns {boolean} True when the write succeeds.
 */
export function writeStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
    return true;
  } catch (_error) {
    return false;
  }
}

/**
 * Extract a human-readable message from an error of any shape.
 * @param {*} error - Error-like value to normalize.
 * @returns {string} Human-readable error message.
 */
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

/**
 * Build a copyable diagnostics summary for the latest runtime error.
 * @param {RuntimeErrorRecord} errorRecord - Latest runtime error.
 * @param {Document} documentObj - Document containing runtime status.
 * @param {Window} windowObj - Window containing location and navigator details.
 * @returns {string} Diagnostics summary.
 */
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

/**
 * Sync the runtime error details UI to the latest captured error.
 * @param {Document} documentObj - Document containing diagnostics nodes.
 * @param {RuntimeState} state - Runtime state to display.
 * @returns {void}
 */
function updateRuntimeDiagnostics(documentObj, state) {
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
  if (!copyButton) {
    return;
  }

  copyButton.hidden = !hasSummary;
  if (!hasSummary) {
    copyButton.textContent = 'Copy error details';
    copyButton.removeAttribute('data-copy-state');
  }
}

/**
 * Copy the latest runtime diagnostics summary when clipboard access is available.
 * @param {RuntimeState} state - Runtime state containing the latest error.
 * @param {Window} windowObj - Window containing clipboard access.
 * @param {Document} documentObj - Document containing the copy button.
 * @returns {Promise<boolean>} Whether the summary was copied.
 */
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
 * Creating one sets `window.__ARTIFACTS_RUNTIME__` to its state, sets
 * `data-runtime-status` on the root element to "booting", and installs the
 * click handler for the "Copy error details" button. A page creates one runtime.
 * @param {{ consoleObj?: Console, documentObj?: Document, windowObj?: Window }} [options={}]
 *   Injected browser globals for startup and tests.
 * @returns {{
 *   markReady: () => void,
 *   readStorage: (key: string, fallbackValue?: string|null) => string|null,
 *   reportError: (error: *, context: string, options?: { fatal?: boolean }) => void,
 *   setupGlobalErrorHandlers: () => void,
 *   state: RuntimeState,
 *   writeStorage: (key: string, value: string) => boolean
 * }} Runtime API.
 */
export function createRuntime({ consoleObj = console, documentObj = document, windowObj = window } = {}) {
  const runtimeWindow = /** @type {RuntimeWindow} */ (windowObj);
  const state = /** @type {RuntimeState} */ ({
    ready: false,
    lastError: null
  });
  const runtimeErrorBanner = documentObj.getElementById('runtime-error');

  runtimeWindow.__ARTIFACTS_RUNTIME__ = state;
  documentObj.documentElement.dataset.runtimeStatus = 'booting';
  documentObj.addEventListener('click', (event) => {
    const target = /** @type {Element | null} */ (event.target);
    const copyButton = target?.closest?.('#runtime-error-copy');
    if (!copyButton) {
      return;
    }
    void copyRuntimeDiagnostics(state, windowObj, documentObj);
  });

  /** @param {string} value - Runtime status written to the document dataset. */
  const setStatus = (value) => {
    documentObj.documentElement.dataset.runtimeStatus = value;
  };

  const showFatalBanner = () => {
    setStatus('error');
    if (runtimeErrorBanner) {
      runtimeErrorBanner.classList.remove('visually-hidden');
      runtimeErrorBanner.classList.remove('hidden');
    }
  };

  /**
   * Record the error in `state.lastError`, refresh the diagnostics panel, and log
   * to the console. A fatal error also sets the runtime status to "error" and
   * shows the error banner.
   * @param {*} error - Arbitrary thrown value; error shapes are untyped upstream.
   * @param {string} context - Human-readable failure context.
   * @param {{ fatal?: boolean }} [options={}] - Whether the failure is fatal.
   */
  const reportError = (error, context, { fatal = false } = {}) => {
    const errorRecord = {
      context,
      message: normalizeErrorMessage(error),
      fatal,
      timestamp: new Date().toISOString(),
      summary: ''
    };
    errorRecord.summary = buildErrorSummary(errorRecord, documentObj, runtimeWindow);
    state.lastError = errorRecord;
    updateRuntimeDiagnostics(documentObj, state);

    if (fatal) {
      showFatalBanner();
    }

    consoleObj.error(`[Artifacts] ${context}: ${errorRecord.message}`, error);
  };

  // The boot guard reveals the banner when the app has not booted after its
  // timeout, and records the banner's original message. If the app boots
  // after all, hide that banner. A banner that a fatal error revealed stays.
  const dismissBootGuardBanner = () => {
    const originalMessage = runtimeErrorBanner?.dataset?.bootGuardMessage;
    if (!runtimeErrorBanner || originalMessage === undefined || state.lastError?.fatal) {
      return;
    }
    delete runtimeErrorBanner.dataset.bootGuardMessage;
    runtimeErrorBanner.classList.add('hidden');
    const message = runtimeErrorBanner.querySelector('p');
    if (message && originalMessage) {
      message.textContent = originalMessage;
    }
  };

  return {
    markReady() {
      state.ready = true;
      setStatus('ready');
      dismissBootGuardBanner();
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
      runtimeWindow.addEventListener('error', (event) => {
        reportError(event.error || event.message, 'window error', { fatal: !state.ready });
      });

      runtimeWindow.addEventListener('unhandledrejection', (event) => {
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
