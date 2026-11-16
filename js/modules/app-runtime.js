import { createRuntime } from "./runtime.js";

/**
 * @typedef {Window & { __ARTIFACT_READY__?: boolean }} MatureAppWindow
 */

/**
 * Create the shared runtime, install its global error handlers, and call `run`.
 * App entries are module scripts, so the document is already parsed when `run`
 * is called.
 * `window.__ARTIFACT_READY__` is true only after `run` returns. If `run` throws,
 * the error is reported once as fatal, which shows the runtime error banner.
 *
 * @param {{
 *   documentObj?: Document,
 *   onErrorContext?: string,
 *   runtimeOptions?: object,
 *   run: (args: { runtime: ReturnType<typeof createRuntime> }) => void,
 *   windowObj?: Window
 * }} options
 * @returns {ReturnType<typeof createRuntime>} The runtime.
 */
export function initializeMatureApp({
  documentObj = document,
  onErrorContext = "app initialization",
  runtimeOptions = {},
  run,
  windowObj = window
}) {
  if (typeof run !== "function") {
    throw new Error("initializeMatureApp requires a run function");
  }

  const runtimeWindow = /** @type {MatureAppWindow} */ (windowObj);
  runtimeWindow.__ARTIFACT_READY__ = false;
  const runtime = createRuntime({ ...runtimeOptions, documentObj, windowObj: runtimeWindow });
  runtime.setupGlobalErrorHandlers();

  try {
    run({ runtime });
    runtimeWindow.__ARTIFACT_READY__ = true;
    runtime.markReady();
  } catch (error) {
    runtime.reportError(error, onErrorContext, { fatal: true });
  }

  return runtime;
}
