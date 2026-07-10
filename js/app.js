import { initializeGalleryApp as initializeGalleryAppModule } from './modules/gallery/gallery-app.js';
import { validateGalleryBootstrapData as validateGalleryBootstrapDataModule } from './modules/gallery/config.js';
import { createRuntime as createRuntimeModule } from './modules/runtime.js';

/**
 * @typedef {{
 *   createRuntime?: typeof createRuntimeModule,
 *   initializeGalleryApp?: typeof initializeGalleryAppModule,
 *   validateGalleryBootstrapData?: typeof validateGalleryBootstrapDataModule
 * }} AppTestHooks
 * @typedef {Window & { __APP_TEST_HOOKS__?: AppTestHooks }} BootstrapWindow
 * @typedef {typeof globalThis & { __APP_TEST_HOOKS__?: AppTestHooks }} BootstrapGlobal
 */

/**
 * Resolve runtime dependencies, allowing tests to provide bootstrap hooks.
 * @param {Window} [windowObj=window] - Window-like object to read hooks from.
 */
function getBootstrapDependencies(windowObj = window) {
  const bootstrapWindow = /** @type {BootstrapWindow} */ (windowObj);
  const bootstrapGlobal = /** @type {BootstrapGlobal} */ (globalThis);
  const hooks = bootstrapWindow.__APP_TEST_HOOKS__ || bootstrapGlobal.__APP_TEST_HOOKS__ || {};
  return {
    createRuntime: hooks.createRuntime || createRuntimeModule,
    initializeGalleryApp: hooks.initializeGalleryApp || initializeGalleryAppModule,
    validateGalleryBootstrapData: hooks.validateGalleryBootstrapData || validateGalleryBootstrapDataModule
  };
}

/** Bootstrap the gallery: validate data, initialize the app, and set up error handlers. */
document.addEventListener('DOMContentLoaded', () => {
  const {
    createRuntime,
    initializeGalleryApp,
    validateGalleryBootstrapData
  } = getBootstrapDependencies(window);
  const runtime = createRuntime();
  runtime.setupGlobalErrorHandlers();

  try {
    validateGalleryBootstrapData(window);
    initializeGalleryApp({ runtime });
    runtime.markReady();
  } catch (error) {
    runtime.reportError(error, 'gallery initialization', { fatal: true });
    throw error;
  }
});
