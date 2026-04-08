import { createRuntime } from "./runtime.js";

/**
 * Bootstrap one mature app after wiring the shared runtime and fatal error handling.
 *
 * @param {{
 *   documentObj?: Document,
 *   onErrorContext?: string,
 *   runtimeOptions?: object,
 *   run: ({ runtime: ReturnType<typeof createRuntime> }) => void,
 *   windowObj?: Window
 * }} [options={}]
 * @returns {ReturnType<typeof createRuntime>} Shared runtime instance for the app.
 */
export function initializeMatureApp({
  documentObj = document,
  onErrorContext = "app initialization",
  runtimeOptions = {},
  run,
  windowObj = window
} = {}) {
  if (typeof run !== "function") {
    throw new Error("initializeMatureApp requires a run function");
  }

  windowObj.__ARTIFACT_READY__ = false;
  const runtime = createRuntime({ ...runtimeOptions, documentObj, windowObj });
  runtime.setupGlobalErrorHandlers();

  function bootstrap() {
    if (runtime.state.lastError?.fatal) {
      windowObj.__ARTIFACT_READY__ = false;
      return;
    }

    try {
      run({ runtime });
      windowObj.__ARTIFACT_READY__ = true;
      runtime.markReady();
    } catch (error) {
      windowObj.__ARTIFACT_READY__ = false;
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
