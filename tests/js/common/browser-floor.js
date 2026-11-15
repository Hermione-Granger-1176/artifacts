/**
 * Node stand-ins for the browser APIs inside the supported-browser floor
 * (docs/frontend.md, "Supported browsers"). Shared and app modules call these
 * APIs without a fallback, so a test whose code reaches one installs them first.
 */

/** An observer that watches nothing and never reports, so every target keeps its starting state. */
export class InertObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

/** @type {Record<string, unknown>} */
const FLOOR_GLOBALS = {
  IntersectionObserver: InertObserver,
  ResizeObserver: InertObserver,
  // Frames run at once, like the window stubs the app entry tests install.
  requestAnimationFrame: (/** @type {FrameRequestCallback} */ callback) => {
    callback(0);
    return 0;
  },
  cancelAnimationFrame: () => {}
};

/**
 * Define each floor API that globalThis lacks. APIs a test already stubbed are left alone.
 * @returns {() => void} Removes the APIs this call defined.
 */
export function installBrowserFloor() {
  const added = Object.keys(FLOOR_GLOBALS).filter((name) => !(name in globalThis));
  for (const name of added) {
    Reflect.set(globalThis, name, FLOOR_GLOBALS[name]);
  }
  return () => {
    for (const name of added) {
      Reflect.deleteProperty(globalThis, name);
    }
  };
}
