import { bootstrapGallery } from './modules/gallery/bootstrap.js';
import { initializeGalleryApp } from './modules/gallery/gallery-app.js';
import { validateGalleryBootstrapData } from './modules/gallery/config.js';
import { createRuntime } from './modules/runtime.js';

document.addEventListener('DOMContentLoaded', () => {
  bootstrapGallery({ createRuntime, initializeGalleryApp, validateGalleryBootstrapData, windowObj: window });
});
