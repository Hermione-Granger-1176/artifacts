import { initializeGalleryApp } from './modules/gallery-app.js';
import { validateGalleryBootstrapData } from './modules/config.js';
import { createRuntime } from './modules/runtime.js';

/** Bootstrap the gallery: validate data, initialize the app, and set up error handlers. */
document.addEventListener('DOMContentLoaded', () => {
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
