import { createRuntime } from "./runtime.js";

/**
 * @typedef {Window & { __ARTIFACT_READY__?: boolean }} MatureAppWindow
 */

/**
 * Bootstrap one mature app after wiring the shared runtime and fatal error handling.
 *
 * @param {{
 *   documentObj?: Document,
 *   onErrorContext?: string,
 *   runtimeOptions?: object,
 *   run: (args: { runtime: ReturnType<typeof createRuntime> }) => void,
 *   windowObj?: Window
 * }} options
 * @returns {ReturnType<typeof createRuntime>} Shared runtime instance for the app.
 */
export function initializeMatureApp({
  documentObj = document,
  onErrorContext = "app initialization",
  runtimeOptions = {},
  run,
  windowObj = window
}) {
  const runApp = /** @type {(args: { runtime: ReturnType<typeof createRuntime> }) => void} */ (run);
  if (typeof runApp !== "function") {
    throw new Error("initializeMatureApp requires a run function");
  }

  const runtimeWindow = /** @type {MatureAppWindow} */ (windowObj);
  runtimeWindow.__ARTIFACT_READY__ = false;
  const runtime = createRuntime({ ...runtimeOptions, documentObj, windowObj: runtimeWindow });
  runtime.setupGlobalErrorHandlers();

  function bootstrap() {
    if (runtime.state.lastError?.fatal) {
      runtimeWindow.__ARTIFACT_READY__ = false;
      return;
    }

    try {
      runApp({ runtime });
      runtimeWindow.__ARTIFACT_READY__ = true;
      runtime.markReady();
    } catch (error) {
      runtimeWindow.__ARTIFACT_READY__ = false;
      runtime.reportError(error, onErrorContext, { fatal: true });
      throw error;
    }
  }

  if (documentObj.readyState === "loading") {
    documentObj.addEventListener("DOMContentLoaded", bootstrap);
  } else {
    bootstrap();
  }

  return runtime;
}
