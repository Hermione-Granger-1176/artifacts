/**
 * The reader's reduced-motion preference, read by the gallery and the apps.
 * @module motion
 */

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

/**
 * Whether the reader asked the system for reduced motion. Reads the live
 * preference on every call, so a change in system settings applies at once.
 * @param {Pick<Window, "matchMedia">} [windowObj=window] - Window to query.
 * @returns {boolean} True when `prefers-reduced-motion: reduce` matches.
 */
export function prefersReducedMotion(windowObj = window) {
  return windowObj.matchMedia(REDUCED_MOTION_QUERY).matches;
}

/**
 * The scroll behavior that respects the preference.
 * @param {Pick<Window, "matchMedia">} [windowObj=window] - Window to query.
 * @returns {ScrollBehavior} "auto" under reduced motion, "smooth" otherwise.
 */
export function scrollBehavior(windowObj = window) {
  return prefersReducedMotion(windowObj) ? "auto" : "smooth";
}
