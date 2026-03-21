import { initializeGalleryApp as initializeGalleryAppModule } from './modules/gallery-app.js';
import { validateGalleryBootstrapData as validateGalleryBootstrapDataModule } from './modules/config.js';
import { createRuntime as createRuntimeModule } from './modules/runtime.js';

function getBootstrapDependencies(windowObj = window) {
  const hooks = windowObj.__APP_TEST_HOOKS__ || globalThis.__APP_TEST_HOOKS__ || {};
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
