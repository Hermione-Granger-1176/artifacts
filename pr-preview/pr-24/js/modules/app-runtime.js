import { createRuntime } from "./runtime.js";

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
