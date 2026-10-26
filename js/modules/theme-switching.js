/**
 * Shared theme-swap guard for the gallery and the artifact apps. While the
 * .theme-switching class sits on <html>, the shared rule in
 * 06-responsive-and-motion.css turns every CSS transition off, so all themed
 * colors flip together instead of fading at their own speeds.
 * @module theme-switching
 */

/**
 * Create the guard for one document root.
 * @param {HTMLElement} html - The document's root element.
 * @param {Pick<Window, "requestAnimationFrame">} windowObj - Frame source.
 * @returns {() => void} Call right before changing the theme. The class comes
 *   off two frames later, once the new colors have painted; a later call keeps
 *   it on until its own two frames have passed.
 */
export function createThemeSwitchGuard(html, windowObj) {
  // Bumped on every switch so only the latest one lifts the class.
  let switchId = 0;

  return function suspendTransitions() {
    const id = ++switchId;
    html.classList.add("theme-switching");
    windowObj.requestAnimationFrame(() => {
      windowObj.requestAnimationFrame(() => {
        if (id === switchId) {
          html.classList.remove("theme-switching");
        }
      });
    });
  };
}
