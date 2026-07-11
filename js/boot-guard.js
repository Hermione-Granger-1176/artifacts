(function bootGuard(globalObject) {
  // This classic script runs before the ES module bundle. It cannot import
  // from runtime.js. If the module never executes (a network blip loading
  // js/app.js, for example) the runtime status stays "booting" forever and
  // the page shows an empty grid with no banner. After a generous timeout we
  // reveal the existing #runtime-error container so the failure is visible.
  var DEFAULT_TIMEOUT_MS = 8000;

  function readRuntimeStatus(documentObject) {
    if (!documentObject || !documentObject.documentElement) {
      return "";
    }
    return documentObject.documentElement.dataset.runtimeStatus || "";
  }

  // The runtime sets data-runtime-status to "ready" on markReady() and to
  // "error" when a fatal error already surfaced its own banner. Either value
  // means the app started, so the guard should stand down.
  function isBooted(documentObject) {
    var status = readRuntimeStatus(documentObject);
    return status === "ready" || status === "error";
  }

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

    var message = banner.querySelector("p");
    if (message) {
      message.textContent =
        "The app failed to start. Check your connection and reload the page.";
    }

    if (documentObject.documentElement) {
      documentObject.documentElement.dataset.runtimeStatus = "error";
    }

    return true;
  }

  function checkBoot(documentObject) {
    if (isBooted(documentObject)) {
      return false;
    }
    return revealStartupError(documentObject);
  }

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
