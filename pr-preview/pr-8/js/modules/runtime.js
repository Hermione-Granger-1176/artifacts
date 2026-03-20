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

/** Create a runtime instance providing error reporting, storage access, and lifecycle status. */
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

    consoleObj.error(`[Artifacts] ${context}: ${state.lastError.message}`, error);
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
