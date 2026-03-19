/**
 * Create a motion helper that respects the user's reduced-motion preference.
 * @returns {{ prefersReducedMotion, getScrollBehavior, scrollToTop }}
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
