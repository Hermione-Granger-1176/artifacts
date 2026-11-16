(function bootGuard(globalObject) {
  // Classic script that runs before the ES module bundle, so it cannot import
  // runtime.js. If the module never executes, the runtime status stays
  // "booting". After the timeout, it reveals the existing #runtime-error
  // container.
  var DEFAULT_TIMEOUT_MS = 8000;

  /**
   * @param {Document | null | undefined} documentObject - Target document.
   * @returns {string} The current runtime status attribute value.
   */
  function readRuntimeStatus(documentObject) {
    if (!documentObject || !documentObject.documentElement) {
      return "";
    }
    return documentObject.documentElement.dataset.runtimeStatus || "";
  }

  // The runtime sets data-runtime-status to "ready" on markReady(), or to
  // "error" after a fatal error shows its own banner. Either value means the
  // guard stands down.
  /**
   * @param {Document | null | undefined} documentObject - Target document.
   * @returns {boolean} Whether the runtime already started.
   */
  function isBooted(documentObject) {
    var status = readRuntimeStatus(documentObject);
    return status === "ready" || status === "error";
  }

  /**
   * @param {Document | null | undefined} documentObject - Target document.
   * @returns {boolean} Whether the startup error banner was revealed.
   */
  function revealStartupError(documentObject) {
    if (!documentObject || typeof documentObject.getElementById !== "function") {
      return false;
    }

    var banner = documentObject.getElementById("runtime-error");
    if (!banner) {
      return false;
    }

    banner.classList.remove("hidden");
    banner.classList.remove("visually-hidden");

    // If the app boots after the timeout, the runtime reads this attribute,
    // hides the banner, and restores the original message.
    var message = banner.querySelector("p");
    banner.dataset.bootGuardMessage = message ? message.textContent : "";
    if (message) {
      message.textContent =
        "The app failed to start. Check your connection and reload the page.";
    }

    if (documentObject.documentElement) {
      documentObject.documentElement.dataset.runtimeStatus = "error";
    }

    return true;
  }

  /**
   * @param {Document | null | undefined} documentObject - Target document.
   * @returns {boolean} Whether the guard revealed the startup error.
   */
  function checkBoot(documentObject) {
    if (isBooted(documentObject)) {
      return false;
    }
    return revealStartupError(documentObject);
  }

  /**
   * @param {typeof globalThis | null | undefined} target - Timer host.
   * @param {number | undefined} timeoutMs - Guard delay in milliseconds.
   * @returns {number | null} The scheduled timer id, or null when unavailable.
   */
  function scheduleGuard(target, timeoutMs) {
    if (!target || typeof target.setTimeout !== "function") {
      return null;
    }

    var delay = typeof timeoutMs === "number" ? timeoutMs : DEFAULT_TIMEOUT_MS;
    return target.setTimeout(function guardTick() {
      return checkBoot(target.document);
    }, delay);
  }

  globalObject.__ARTIFACTS_BOOT_GUARD__ = {
    checkBoot: checkBoot,
    defaultTimeoutMs: DEFAULT_TIMEOUT_MS,
    isBooted: isBooted,
    readRuntimeStatus: readRuntimeStatus,
    revealStartupError: revealStartupError,
    scheduleGuard: scheduleGuard,
  };

  scheduleGuard(globalObject, DEFAULT_TIMEOUT_MS);
})(typeof window !== "undefined" ? window : globalThis);
