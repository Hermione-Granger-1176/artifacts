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

function normalizeConsoleMessage(message) {
  return String(message).replace(/\s+/g, ' ').trim();
}

function shouldIgnoreRuntimeError(message) {
  const normalizedMessage = normalizeConsoleMessage(message).toLowerCase();
  return normalizedMessage.includes('window.artifacts_data must be an array');
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
 *     lastError: ({ context: string, message: string, fatal: boolean, timestamp: string }|null)
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

  const setStatus = (value) => {
    documentObj.documentElement.dataset.runtimeStatus = value;
  };

  const reportError = (error, context, { fatal = false } = {}) => {
    state.lastError = {
      context,
      message: normalizeErrorMessage(error),
      fatal,
      timestamp: new Date().toISOString()
    };

    if (fatal) {
      setStatus('error');
      if (runtimeErrorBanner) {
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

    shouldIgnoreRuntimeError,

    setupGlobalErrorHandlers() {
      if (windowObj.__ARTIFACTS_ERROR_HANDLERS_BOUND__) {
        return;
      }

      windowObj.__ARTIFACTS_ERROR_HANDLERS_BOUND__ = true;

      windowObj.addEventListener('error', (event) => {
        reportError(event.error || event.message, 'window error');
      });

      windowObj.addEventListener('unhandledrejection', (event) => {
        reportError(event.reason, 'unhandled rejection');
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
