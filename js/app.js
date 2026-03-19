import { initializeGalleryApp } from './modules/gallery-app.js';
import { createRuntime } from './modules/runtime.js';

document.addEventListener('DOMContentLoaded', () => {
  const runtime = createRuntime();
  runtime.setupGlobalErrorHandlers();

  try {
    initializeGalleryApp({ runtime });
    runtime.markReady();
  } catch (error) {
    runtime.reportError(error, 'gallery initialization', { fatal: true });
    throw error;
  }
});
