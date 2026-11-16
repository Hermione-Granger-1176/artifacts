import { prefersReducedMotion, scrollBehavior } from '../motion.js';

/**
 * Bind the shared reduced-motion helpers to the gallery's window. The book scene
 * and the detail overlay receive them as one injected dependency.
 * @param {Pick<Window, 'matchMedia' | 'scrollTo'>} windowObj - Window to query and scroll.
 * @returns {{
 *   prefersReducedMotion: () => boolean,
 *   getScrollBehavior: () => ScrollBehavior,
 *   scrollToTop: () => void
 * }} Motion helper methods.
 */
export function createMotionHelper(windowObj) {
  return {
    prefersReducedMotion: () => prefersReducedMotion(windowObj),
    getScrollBehavior: () => scrollBehavior(windowObj),
    scrollToTop: () => windowObj.scrollTo({ top: 0, behavior: scrollBehavior(windowObj) })
  };
}
