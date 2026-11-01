/**
 * Hold chart redraws while a canvas is off screen and run the latest one when
 * it scrolls near the viewport, so a slider drag only repaints what a reader
 * can see. Shared by the apps that keep several Chart.js charts on one page.
 * @module offscreen-draws
 */

/**
 * @typedef {{
 *   draw: (target: Element, run: () => void, force?: boolean) => void
 * }} OffscreenDraws
 */

/**
 * Watch the given canvases. A canvas counts as on screen until the observer
 * reports otherwise. Without IntersectionObserver, every canvas always counts as on screen.
 * @param {Element[]} targets - Canvases to watch.
 * @param {string} [rootMargin="200px 0px"] - How far outside the viewport still counts as on screen.
 * @returns {OffscreenDraws} `draw` runs `run` now when its target is on screen
 *   (or `force` is set) and otherwise keeps only the latest `run` until it is.
 */
export function createOffscreenDraws(targets, rootMargin = "200px 0px") {
  /** @type {Set<Element>} */
  const offscreen = new Set();
  /** @type {Map<Element, () => void>} */
  const pending = new Map();

  if (typeof IntersectionObserver === "function") {
    const observer = new IntersectionObserver(
      (entries) => {
        for (const { target, isIntersecting } of entries) {
          if (!isIntersecting) {
            offscreen.add(target);
            continue;
          }
          offscreen.delete(target);
          const run = pending.get(target);
          pending.delete(target);
          run?.();
        }
      },
      { rootMargin }
    );
    targets.forEach((target) => observer.observe(target));
  }

  return {
    draw(target, run, force = false) {
      if (!force && offscreen.has(target)) {
        pending.set(target, run);
        return;
      }
      pending.delete(target);
      run();
    }
  };
}
