/**
 * Create a motion helper that respects the user's reduced-motion preference.
 * @param {{ matches: boolean }} prefersReducedMotionQuery - Media-query-like object for
 * reduced-motion detection.
 * @param {{ scrollTo: (options: { top: number, behavior: ('auto'|'smooth') }) => void }} windowObj
 *   Window-like object used for scrolling.
 * @returns {{
 *   prefersReducedMotion: () => boolean,
 *   getScrollBehavior: () => ('auto'|'smooth'),
 *   scrollToTop: () => void
 * }} Motion helper methods.
 */
export function createMotionHelper(prefersReducedMotionQuery, windowObj) {
  function prefersReducedMotion() {
    return prefersReducedMotionQuery.matches;
  }

  function getScrollBehavior() {
    return prefersReducedMotion() ? 'auto' : 'smooth';
  }

  function scrollToTop() {
    windowObj.scrollTo({ top: 0, behavior: getScrollBehavior() });
  }

  return { prefersReducedMotion, getScrollBehavior, scrollToTop };
}
