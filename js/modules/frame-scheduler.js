/**
 * Coalesce repeated requests into one call on the next animation frame.
 * Requests made while a frame is already pending are dropped, so a burst of
 * slider input runs the callback once per frame.
 * @param {() => void} callback - Work to run on the next frame.
 * @param {Pick<Window, "requestAnimationFrame">} [windowObj] - Frame clock; the global window, read at each request, when omitted.
 * @returns {() => void} Function that schedules the callback.
 */
export function createFrameScheduler(callback, windowObj) {
  let pendingFrame = /** @type {number | null} */ (null);

  return () => {
    if (pendingFrame !== null) {
      return;
    }

    pendingFrame = (windowObj ?? window).requestAnimationFrame(() => {
      pendingFrame = null;
      callback();
    });
  };
}
