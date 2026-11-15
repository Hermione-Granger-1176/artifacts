/**
 * @typedef {typeof import('../runtime.js').createRuntime} CreateRuntime
 * @typedef {typeof import('./gallery-app.js').initializeGalleryApp} InitializeGalleryApp
 * @typedef {typeof import('./config.js').validateGalleryBootstrapData} ValidateGalleryBootstrapData
 */

/**
 * Boot the gallery: create the runtime and its global error handlers, validate
 * the generated globals, initialize the app, and mark the runtime ready. A
 * failure is reported once as fatal, which shows the runtime error banner.
 * @param {{
 *   createRuntime: CreateRuntime,
 *   initializeGalleryApp: InitializeGalleryApp,
 *   validateGalleryBootstrapData: ValidateGalleryBootstrapData,
 *   windowObj: Window
 * }} dependencies - Runtime factory, gallery entry points, and the window holding the generated globals.
 * @returns {ReturnType<CreateRuntime>} The runtime.
 */
export function bootstrapGallery({ createRuntime, initializeGalleryApp, validateGalleryBootstrapData, windowObj }) {
  const runtime = createRuntime();
  runtime.setupGlobalErrorHandlers();

  try {
    validateGalleryBootstrapData(windowObj);
    initializeGalleryApp({ runtime });
    runtime.markReady();
  } catch (error) {
    runtime.reportError(error, 'gallery initialization', { fatal: true });
  }

  return runtime;
}
