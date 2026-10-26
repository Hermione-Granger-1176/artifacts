const INTRO_DELAY_MS = 500;
const RIBBON_OFF_MS = 520;
// The cover starts to swing once the ribbon is this far through sliding off,
// so the two motions flow into each other with no pause between them.
const RIBBON_LEAD = 0.55;
const COVER_OPEN_MS = 1000;
const CROSSFADE_OUT_MS = 200;
const CROSSFADE_IN_MS = 250;
const LEAF_TURN_MS = 680;
const REDUCED_FADE_OUT_MS = 120;
const REDUCED_FADE_IN_MS = 160;
const MOBILE_FADE_MS = 200;
/**
 * Phones and tablets held upright get a one-page notepad bound at the top. The gallery shares this
 * query for its page size and filter dropdowns; keep it equal to the notepad block in 06-responsive-and-motion.css.
 */
export const NOTEPAD_QUERY = '(max-width: 900px)';
const FLIP_TURN_MS = 620;
const FLIP_TURN_EASING = 'cubic-bezier(0.65, 0, 0.35, 1)';
const COVER_FLIP_MS = 900;
// A notepad sheet turns like a desk calendar page: its bottom edge lifts toward the reader
// (a positive rotateX), stands straight out at 90 degrees, then swings up over the binding and
// drops behind the pad. The cover and every page share these keyframes, which only touch
// transform and opacity so the compositor can run them. The sheet's faces hide by
// backface-visibility, so its plain back shows past upright with no script involved.
/** @type {Keyframe[]} */
const FLIP_KEYFRAMES = [{ transform: 'rotateX(0deg)' }, { transform: 'rotateX(180deg)' }];
// Past 80 percent of the swing the sheet is falling behind the pad, so its back fades away.
/** @type {Keyframe[]} */
const FLIP_BACK_FADE_KEYFRAMES = [{ opacity: 1 }, { opacity: 1, offset: 0.8 }, { opacity: 0 }];
// A page darkens as it turns from the light toward upright.
/** @type {Keyframe[]} */
const FLIP_SHADE_KEYFRAMES = [{ opacity: 0 }, { opacity: 0.35, offset: 0.5 }, { opacity: 0.35 }];
const EDGE_ZONE_PX = 36;
const CORNER_ZONE_PX = 72;
const TAP_SLOP_PX = 5;
const DRAG_COMPLETE_THRESHOLD = 0.45;
const COVER_EASING = 'cubic-bezier(0.45, 0, 0.25, 1)';
// The book's ribbon runs down the cover, so it lifts, then slides off to the right.
/** @type {Keyframe[]} */
const RIBBON_OFF_KEYFRAMES = [
  { transform: 'none', opacity: 1 },
  { transform: 'translateY(-14px) rotate(-4deg)', opacity: 1, offset: 0.35 },
  { transform: 'translate(160px, 40px) rotate(14deg)', opacity: 0 }
];
const RIBBON_OFF_OPTIONS = { duration: RIBBON_OFF_MS, easing: 'cubic-bezier(0.5, 0, 0.3, 1)' };
// The notepad's band runs across the cover, so it lifts, then slides down off the bottom edge.
/** @type {Keyframe[]} */
const NOTEPAD_RIBBON_OFF_KEYFRAMES = [
  { transform: 'none', opacity: 1 },
  { transform: 'translateY(-10px) rotate(-1.5deg)', opacity: 1, offset: 0.35 },
  { transform: 'translateY(90px) rotate(3deg)', opacity: 0 }
];
// Where the shadow's mask edge ends up (see .book-shadow in 02-gallery.css).
const SHADOW_EDGE_OPEN = '-12%';

/**
 * @typedef {{ left: HTMLElement | null, right: HTMLElement | null }} PageFaces
 * @typedef {{
 *   getShownPage: () => number,
 *   getPageCount: () => number,
 *   buildFaces: (page: number) => PageFaces,
 *   select: (page: number) => void,
 *   commit: (page: number) => void
 * }} BookPages
 * @typedef {{
 *   leaf: HTMLElement,
 *   ghost: HTMLElement,
 *   frontShade: HTMLElement,
 *   backShade: HTMLElement,
 *   castLeft: HTMLElement | null,
 *   castRight: HTMLElement | null,
 *   next: boolean
 * }} LeafParts
 * @typedef {{
 *   target: number,
 *   selected: boolean,
 *   aborted: boolean,
 *   done: boolean,
 *   frameId: number | null,
 *   cancelTween: () => void,
 *   cleanup: () => void
 * }} Turn
 * @typedef {Turn & { leaf: LeafParts }} LeafTurn
 * @typedef {{ shell: HTMLElement, sheet: HTMLElement, grid: HTMLElement }} TurnParts
 * @typedef {{
 *   aborted: boolean,
 *   animations: Set<Animation>,
 *   insidePage?: HTMLElement
 * }} IntroState
 */

/** @type {BookPages} */
const NO_PAGES = {
  getShownPage: () => 1,
  getPageCount: () => 1,
  buildFaces: () => ({ left: null, right: null }),
  select: () => undefined,
  commit: () => undefined
};

/**
 * @param {number} t - Progress from 0 to 1.
 * @returns {number} Eased progress.
 */
function easeInOut(t) {
  return t < 0.5 ? 4 * t * t * t : 1 - ((-2 * t + 2) ** 3) / 2;
}

/**
 * @param {number} t - Progress from 0 to 1.
 * @returns {number} Eased progress.
 */
function easeOut(t) {
  return 1 - (1 - t) ** 3;
}

/**
 * @param {number} t - Progress from 0 to 1.
 * @returns {number} The same progress.
 */
function linear(t) {
  return t;
}

/**
 * Create book-scene helpers: the cover-opening intro, single-leaf page turns,
 * drag-to-scrub, and the queue that keeps rapid page requests from being lost.
 *
 * A page turn is one two-faced leaf hinged at the spine. The live pages are not
 * touched until the turn lands, so a spring-back needs no cleanup beyond
 * removing the leaf. Every method no-ops safely when the matching DOM is absent.
 * @param {{
 *   documentObj?: Document,
 *   windowObj?: Window,
 *   motion?: { prefersReducedMotion?: () => boolean },
 *   pages?: BookPages,
 *   onError?: (error: unknown) => void
 * }} [options={}] - Injected browser APIs, page model, and error sink.
 * @returns {{
 *   startIntro: () => Promise<void>,
 *   turnPage: (target: number) => Promise<void>,
 *   cancelTurn: () => void,
 *   setPosition: (position: { page: number, totalPages: number }) => void
 * }} Book-scene helpers.
 */
export function createBookScene({ documentObj = document, windowObj = window, motion, pages = NO_PAGES, onError } = {}) {
  /** @type {Promise<void> | null} */
  let introPromise = null;
  /** @type {(() => void) | null} */
  let abortIntro = null;
  /** @type {Turn | null} */
  let active = null;
  /** @type {Promise<void> | null} */
  let runner = null;
  /** @type {number | null} */
  let pendingTarget = null;
  // Settles once the current drag has ended and the queue after it is empty.
  /** @type {Promise<void>} */
  let dragDone = Promise.resolve();
  // Re-copies the live left page into the cover while the intro swings it open.
  /** @type {(() => void) | null} */
  let syncCover = null;

  /** @param {unknown} error - Error from an animation path. */
  function reportError(error) {
    if (typeof onError === 'function') {
      onError(error);
      return;
    }

    console.error(error);
  }

  function prefersReducedMotion() {
    if (motion && typeof motion.prefersReducedMotion === 'function') {
      return motion.prefersReducedMotion();
    }

    return windowObj.matchMedia('(prefers-reduced-motion: reduce)').matches;
  }

  const notepadQuery = windowObj.matchMedia(NOTEPAD_QUERY);

  function isMobile() {
    return notepadQuery.matches;
  }

  /**
   * @param {string} id - Element id.
   * @returns {HTMLElement | null} The element, if present.
   */
  function getElementById(id) {
    return documentObj.getElementById(id);
  }

  /**
   * @param {string} className - Class list for the new element.
   * @returns {HTMLElement} A new div.
   */
  function createDiv(className) {
    const element = documentObj.createElement('div');
    element.className = className;
    return element;
  }

  /**
   * @param {number} ms - Delay in milliseconds.
   * @returns {Promise<void>} Resolves after the delay.
   */
  function delay(ms) {
    return new Promise((resolve) => {
      windowObj.setTimeout(resolve, ms);
    });
  }

  /**
   * Keep a decorative copy of page content away from assistive tech and focus.
   * @param {HTMLElement} element - Decorative element.
   */
  function hideDecorative(element) {
    element.setAttribute('aria-hidden', 'true');
    element.inert = true;
  }

  /**
   * Create a turn record whose cleanup runs once: it stops the tween, then
   * removes whatever the turn added to the page.
   * @param {{ target: number, selected: boolean, release: () => void }} options - Turn target, selection state, and the turn-specific teardown.
   * @returns {Turn} The turn record.
   */
  function createTurn({ target, selected, release }) {
    /** @type {Turn} */
    const turn = {
      target,
      selected,
      aborted: false,
      done: false,
      frameId: null,
      cancelTween: () => undefined,
      cleanup: () => {
        if (turn.done) {
          return;
        }

        turn.done = true;
        turn.cancelTween();
        release();
      }
    };
    return turn;
  }

  /**
   * The newest page the page model has been told about but the book may not
   * show yet: a queued request, else the selected turn in flight.
   * @returns {number | null} That page, or null when nothing is in flight.
   */
  function latestSelectedTarget() {
    return pendingTarget ?? (active && active.selected ? active.target : null);
  }

  /**
   * Return the elements a page turn needs, or null when the book cannot animate
   * (not yet open, intro still running, or markup missing).
   * @returns {TurnParts | null} Turn elements.
   */
  function getTurnParts() {
    const shell = getElementById('book-shell');
    const sheet = getElementById('book-sheet');
    const grid = getElementById('artifacts-grid');
    if (!shell || !sheet || !grid || shell.dataset.sceneIntro !== 'open') {
      return null;
    }

    if (typeof windowObj.requestAnimationFrame !== 'function' || typeof windowObj.cancelAnimationFrame !== 'function') {
      return null;
    }

    return { shell, sheet, grid };
  }

  /**
   * Run a progress tween on the animation frame clock.
   * Resolves when finished or when the turn cancels it; rejects if a step throws.
   * @param {Turn} turn - Owning turn, which holds the frame id and cancel hook.
   * @param {number} from - Start value.
   * @param {number} to - End value.
   * @param {number} ms - Duration in milliseconds.
   * @param {(t: number) => number} ease - Easing function.
   * @param {(value: number) => void} step - Called with each eased value.
   * @returns {Promise<void>} Settles when the tween ends.
   */
  function tween(turn, from, to, ms, ease, step) {
    return new Promise((resolve, reject) => {
      /** @type {number | null} */
      let start = null;

      turn.cancelTween = () => {
        if (turn.frameId !== null) {
          windowObj.cancelAnimationFrame(turn.frameId);
          turn.frameId = null;
        }
        resolve();
      };

      /** @param {number} time - Frame timestamp. */
      const frame = (time) => {
        turn.frameId = null;
        if (start === null) {
          start = time;
        }

        const t = Math.min(1, Math.max(0, (time - start) / ms));
        try {
          step(from + (to - from) * ease(t));
        } catch (error) {
          reject(error);
          return;
        }

        if (t < 1) {
          turn.frameId = windowObj.requestAnimationFrame(frame);
          return;
        }

        resolve();
      };

      turn.frameId = windowObj.requestAnimationFrame(frame);
    });
  }

  /**
   * Position a leaf and its shading for a turn progress value.
   * Progress 0 is the leaf lying where the turn started and 1 is landed. A
   * previous turn is the physical reverse of a next turn, so both share one angle.
   * @param {LeafParts} parts - Leaf elements.
   * @param {number} progress - Turn progress from 0 to 1.
   */
  function setLeafProgress(parts, progress) {
    const q = parts.next ? progress : 1 - progress;
    const lift = Math.sin(Math.PI * q);
    const settling = q > 0.5;
    parts.leaf.style.transform = `rotateY(${-180 * q}deg)`;
    parts.frontShade.style.opacity = String(Math.min(1, q * 2) * 0.9);
    parts.backShade.style.opacity = String(settling ? Math.max(0, 1 - (q - 0.5) * 2) * 0.9 : 0);
    if (parts.castRight) {
      parts.castRight.style.opacity = String(settling ? 0 : lift * (parts.next ? 0.7 : 0.6));
    }
    if (parts.castLeft) {
      parts.castLeft.style.opacity = String(settling ? lift * (parts.next ? 0.6 : 0.7) : 0);
    }
  }

  /**
   * Build the leaf, the waiting page beneath it, and the turn record.
   * The live pages stay untouched until the turn lands.
   * @param {TurnParts} parts - Turn elements.
   * @param {number} from - Page currently shown.
   * @param {number} target - Page the leaf lands on.
   * @param {boolean} selected - Whether the page model already knows about this turn (false while scrubbing).
   * @returns {LeafTurn | null} The turn, or null when the faces cannot be built.
   */
  function createLeafTurn(parts, from, target, selected) {
    const { sheet, grid } = parts;
    const next = target > from;
    const faces = pages.buildFaces(target);
    const liveSlice = /** @type {HTMLElement | null} */ (
      grid.querySelector(next ? '.artifact-page-right' : '.artifact-page-left')
    );
    const front = next ? liveSlice?.cloneNode(true) : faces.right;
    const back = next ? faces.left : liveSlice?.cloneNode(true);
    const under = next ? faces.right : faces.left;
    if (!front || !back || !under) {
      return null;
    }

    const leaf = createDiv('book-leaf');
    const frontFace = createDiv('book-leaf-face book-leaf-front');
    const backFace = createDiv('book-leaf-face book-leaf-back');
    const frontShade = createDiv('book-leaf-shade');
    const backShade = createDiv('book-leaf-shade');
    const ghost = createDiv(`book-ghost book-ghost-${next ? 'right' : 'left'}`);

    frontFace.appendChild(front);
    frontFace.appendChild(frontShade);
    backFace.appendChild(back);
    backFace.appendChild(backShade);
    leaf.appendChild(frontFace);
    leaf.appendChild(backFace);
    ghost.appendChild(under);
    hideDecorative(leaf);
    hideDecorative(ghost);

    const leafParts = {
      leaf,
      ghost,
      frontShade,
      backShade,
      castLeft: /** @type {HTMLElement | null} */ (sheet.querySelector('.book-cast-left')),
      castRight: /** @type {HTMLElement | null} */ (sheet.querySelector('.book-cast-right')),
      next
    };

    sheet.appendChild(ghost);
    sheet.appendChild(leaf);
    sheet.classList.add('is-turning');
    setLeafProgress(leafParts, 0);

    const turn = createTurn({
      target,
      selected,
      release: () => {
        leaf.remove();
        ghost.remove();
        for (const cast of [leafParts.castLeft, leafParts.castRight]) {
          if (cast) {
            cast.style.opacity = '';
          }
        }
        sheet.classList.remove('is-turning');
      }
    });

    return Object.assign(turn, { leaf: leafParts });
  }

  /**
   * Put a copy of the live left page inside the opening cover, replacing any
   * earlier copy. With no left page (no results), the inside stays blank.
   * @param {IntroState} state - Intro bookkeeping.
   * @param {Element} endpaper - The inside of the cover.
   * @param {HTMLElement} grid - Page grid element.
   */
  function carryLeftPage(state, endpaper, grid) {
    state.insidePage?.remove();
    state.insidePage = undefined;
    const liveLeft = grid.querySelector('.artifact-page-left');
    if (!liveLeft) {
      return;
    }

    const inside = /** @type {HTMLElement} */ (liveLeft.cloneNode(true));
    hideDecorative(inside);
    endpaper.appendChild(inside);
    state.insidePage = inside;
  }

  /** Stop the active turn immediately without rendering it. Safe to call from any path. */
  function abortActive() {
    const turn = active;
    if (!turn) {
      return;
    }

    active = null;
    turn.aborted = true;
    turn.cleanup();
  }

  /**
   * Remove a turn's leaf or fade styling and release the book if it still holds it.
   * @param {Turn} turn - Turn that just ended.
   */
  function finishTurn(turn) {
    turn.cleanup();
    if (active === turn) {
      active = null;
    }
  }

  /**
   * Finish everything in flight at once: no animation, but the book ends on the
   * latest requested page with no leaf or inline style left behind.
   */
  function settle() {
    const finalTarget = latestSelectedTarget();
    pendingTarget = null;
    abortActive();
    if (finalTarget !== null && finalTarget !== pages.getShownPage()) {
      pages.commit(finalTarget);
    }
  }

  /**
   * Play one leaf turn from the page shown to the target page.
   * @param {TurnParts} parts - Turn elements.
   * @param {number} from - Page currently shown.
   * @param {number} target - Target page.
   * @returns {Promise<void>} Resolves when the turn has landed or been stopped.
   */
  async function playLeafTurn(parts, from, target) {
    const turn = createLeafTurn(parts, from, target, true);
    if (!turn) {
      pages.commit(target);
      return;
    }

    active = turn;
    try {
      await tween(turn, 0, 1, LEAF_TURN_MS, easeInOut, (value) => setLeafProgress(turn.leaf, value));
      if (!turn.aborted) {
        pages.commit(target);
      }
    } finally {
      finishTurn(turn);
    }
  }

  /**
   * Cross-fade the pages. Used for reduced motion.
   * @param {TurnParts} parts - Turn elements.
   * @param {number} target - Target page.
   * @returns {Promise<void>} Resolves when the fade has finished or been stopped.
   */
  async function playFadeTurn(parts, target) {
    const { sheet, grid } = parts;
    const surface = /** @type {HTMLElement} */ (sheet.querySelector('.book-inner') || grid);
    const mobile = isMobile();
    const fadeOut = mobile ? MOBILE_FADE_MS : REDUCED_FADE_OUT_MS;
    const fadeIn = mobile ? MOBILE_FADE_MS : REDUCED_FADE_IN_MS;

    const turn = createTurn({
      target,
      selected: true,
      release: () => {
        surface.style.opacity = '';
        sheet.classList.remove('is-turning');
      }
    });

    /** @param {number} value - Surface opacity. */
    const setOpacity = (value) => {
      surface.style.opacity = String(value);
    };

    active = turn;
    sheet.classList.add('is-turning');
    try {
      await tween(turn, 1, 0, fadeOut, linear, setOpacity);
      if (turn.aborted) {
        return;
      }

      pages.commit(target);
      await tween(turn, 0, 1, fadeIn, linear, setOpacity);
    } finally {
      finishTurn(turn);
    }
  }

  /**
   * Run a turn's animations together. The turn's cancel hook stops them all, and a stopped
   * set settles quietly so the turn can clean up.
   * @param {Turn} turn - Owning turn.
   * @param {Array<[Element, Keyframe[]]>} tracks - Each element with its keyframes.
   * @param {KeyframeAnimationOptions} options - Shared timing.
   * @returns {Promise<void>} Settles when every animation has finished or been stopped.
   */
  async function animateTurn(turn, tracks, options) {
    /** @type {Animation[]} */
    const animations = [];
    turn.cancelTween = () => animations.forEach((animation) => animation.cancel());
    for (const [element, keyframes] of tracks) {
      animations.push(element.animate(keyframes, { fill: 'both', ...options }));
    }
    try {
      await Promise.all(animations.map((animation) => animation.finished));
    } catch {
      // Stopped with the turn, which checks its aborted flag next.
    }
  }

  /**
   * Flip a notepad page over its binding, like a desk calendar. Going forward, a copy of the
   * shown page lifts toward the reader, swings up over the binding, and drops behind the pad,
   * uncovering the next page already in place underneath. Going back, the earlier page comes
   * back over the binding the same way in reverse, lands on the shown one, and takes its place.
   * @param {TurnParts} parts - Turn elements.
   * @param {number} from - Page currently shown.
   * @param {number} target - Target page.
   * @returns {Promise<void>} Resolves when the flip has finished or been stopped.
   */
  async function playFlipTurn(parts, from, target) {
    const { sheet, grid } = parts;
    const host = /** @type {HTMLElement} */ (sheet.querySelector('.book-inner') || grid);
    const next = target > from;
    const page = next
      ? /** @type {HTMLElement | null} */ (grid.querySelector('.artifact-page-left')?.cloneNode(true) ?? null)
      : pages.buildFaces(target).left;
    // The leaf is a two-faced sheet: the page on its front, and the plain back of the paper,
    // which shows once the sheet has swung past upright.
    const leaf = createDiv('notepad-leaf');
    const front = createDiv('notepad-leaf-face notepad-leaf-front');
    const back = createDiv('notepad-leaf-face notepad-leaf-back');
    const shade = createDiv('notepad-leaf-shade');
    if (page) {
      front.appendChild(page);
    }
    front.appendChild(shade);
    leaf.appendChild(front);
    leaf.appendChild(back);
    hideDecorative(leaf);

    const turn = createTurn({
      target,
      selected: true,
      release: () => {
        leaf.remove();
        sheet.classList.remove('is-turning');
      }
    });

    active = turn;
    sheet.classList.add('is-turning');
    try {
      if (next) {
        pages.commit(target);
      }
      host.appendChild(leaf);
      // Going back plays the same flip in reverse, so the earlier page starts over the binding.
      await animateTurn(turn, [[leaf, FLIP_KEYFRAMES], [back, FLIP_BACK_FADE_KEYFRAMES], [shade, FLIP_SHADE_KEYFRAMES]], {
        duration: FLIP_TURN_MS,
        easing: FLIP_TURN_EASING,
        direction: next ? 'normal' : 'reverse'
      });
      if (!next && !turn.aborted) {
        pages.commit(target);
      }
    } finally {
      finishTurn(turn);
    }
  }

  /**
   * Run queued page requests one transition at a time, always jumping straight
   * to the latest requested page so rapid input coalesces and is never dropped.
   * @returns {Promise<void>} Resolves when the queue is empty.
   */
  async function runQueue() {
    try {
      while (pendingTarget !== null && !active) {
        const target = pendingTarget;
        pendingTarget = null;
        const from = pages.getShownPage();
        if (target === from) {
          continue;
        }

        try {
          const parts = getTurnParts();
          if (!parts) {
            pages.commit(target);
          } else if (prefersReducedMotion()) {
            await playFadeTurn(parts, target);
          } else if (isMobile()) {
            await playFlipTurn(parts, from, target);
          } else {
            await playLeafTurn(parts, from, target);
          }
        } catch (error) {
          reportError(error);
        }
      }
    } finally {
      runner = null;
    }
  }

  /**
   * Start the queue when it is idle.
   * @returns {Promise<void>} Resolves when the queue is empty.
   */
  function kick() {
    if (runner) {
      return runner;
    }

    // Only a drag holds the book without a running queue. Its release starts
    // the queue, so a request made now settles with the drag.
    if (active) {
      return dragDone;
    }

    if (pendingTarget === null) {
      return Promise.resolve();
    }

    runner = Promise.resolve().then(runQueue);
    return runner;
  }

  /**
   * Request a page. The page model is told immediately, and the visual
   * transition follows. Requests made during a transition are queued.
   * @param {number} target - Page to show.
   * @returns {Promise<void>} Resolves when the book has settled.
   */
  function turnPage(target) {
    pages.select(target);
    if (!getTurnParts()) {
      cancelTurn();
      pages.commit(target);
      return Promise.resolve();
    }

    pendingTarget = target;
    return kick();
  }

  /**
   * Drop any turn in flight without rendering it. Call before a render that
   * replaces the pages for another reason (filters, search, back button).
   */
  function cancelTurn() {
    pendingTarget = null;
    abortActive();
  }

  /**
   * Publish where the reader is, for the page-edge stacks and corner peels.
   * The gallery calls this after every render, so it also refreshes the page
   * the cover carries while the intro is still swinging it open.
   * @param {{ page: number, totalPages: number }} position - Shown page and page count.
   */
  function setPosition({ page, totalPages }) {
    const sheet = getElementById('book-sheet');
    if (!sheet) {
      return;
    }

    syncCover?.();
    sheet.style.setProperty('--stack-left-n', String(page));
    sheet.style.setProperty('--stack-right-n', String(totalPages - page + 1));
    sheet.dataset.hasPrevious = String(page > 1);
    sheet.dataset.hasNext = String(page < totalPages);
  }

  /**
   * Which page's outer edge or bottom corner a pointer landed on, if any.
   * @param {PointerEvent} event - Pointer down event.
   * @param {HTMLElement} grid - Page grid element.
   * @returns {{ side: 'left' | 'right', corner: boolean } | null} The drag zone.
   */
  function getDragZone(event, grid) {
    const rect = grid.getBoundingClientRect();
    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;
    if (x < 0 || x > rect.width || y < 0 || y > rect.height) {
      return null;
    }

    const side = x >= rect.width / 2 ? 'right' : 'left';
    const edgeDistance = side === 'right' ? rect.width - x : x;
    const corner = edgeDistance <= CORNER_ZONE_PX && rect.height - y <= CORNER_ZONE_PX;
    if (edgeDistance > EDGE_ZONE_PX && !corner) {
      return null;
    }

    return { side, corner };
  }

  /**
   * Begin scrubbing a leaf from a page edge or corner.
   * @param {PointerEvent} event - Pointer down event.
   */
  function onPointerDown(event) {
    if (event.button !== 0) {
      return;
    }

    const parts = getTurnParts();
    const origin = /** @type {Element | null} */ (event.target);
    if (!parts || prefersReducedMotion() || isMobile() || origin?.closest('.artifact-card')) {
      return;
    }

    const zone = getDragZone(event, parts.grid);
    if (!zone) {
      return;
    }

    const latest = latestSelectedTarget() ?? pages.getShownPage();
    const target = zone.side === 'right' ? latest + 1 : latest - 1;
    if (target < 1 || target > pages.getPageCount()) {
      return;
    }

    event.preventDefault();
    settle();
    const turn = createLeafTurn(parts, pages.getShownPage(), target, false);
    if (turn) {
      beginDrag(event, parts, turn, zone.corner);
    }
  }

  /**
   * Track the pointer and drive the leaf until release.
   * @param {PointerEvent} startEvent - The pointer down event.
   * @param {TurnParts} parts - Turn elements.
   * @param {LeafTurn} turn - The drag turn.
   * @param {boolean} startedInCorner - Whether the pointer started on a page corner.
   */
  function beginDrag(startEvent, parts, turn, startedInCorner) {
    const { sheet, grid } = parts;
    const leafParts = turn.leaf;
    const rect = grid.getBoundingClientRect();
    const hinge = rect.left + rect.width / 2;
    const halfWidth = rect.width / 2;
    const { pointerId } = startEvent;
    const startX = startEvent.clientX;

    /** @param {number} clientX - Pointer x position. */
    const rawProgress = (clientX) => {
      const unit = Math.max(-1, Math.min(1, (clientX - hinge) / halfWidth));
      const q = Math.acos(unit) / Math.PI;
      return leafParts.next ? q : 1 - q;
    };
    const startProgress = rawProgress(startX);
    let progress = 0;
    let moved = 0;

    active = turn;
    try {
      sheet.setPointerCapture(pointerId);
    } catch {
      // Capture is best effort; the drag still works while the pointer stays over the sheet.
    }

    const detach = () => {
      sheet.removeEventListener('pointermove', onMove);
      sheet.removeEventListener('pointerup', onUp);
      sheet.removeEventListener('pointercancel', onCancel);
      sheet.removeEventListener('lostpointercapture', onCancel);
      if (sheet.hasPointerCapture(pointerId)) {
        sheet.releasePointerCapture(pointerId);
      }
    };

    /** @type {(settled: Promise<void>) => void} */
    let finishDrag;
    dragDone = new Promise((resolve) => {
      finishDrag = resolve;
    });
    const baseCleanup = turn.cleanup;
    turn.cleanup = () => {
      detach();
      baseCleanup();
      // Every way a drag ends runs this cleanup. One tick later the drag no
      // longer holds the book, so kick() returns the queue that follows it.
      finishDrag(Promise.resolve().then(kick));
    };

    /** @param {PointerEvent} event - Pointer move event. */
    function onMove(event) {
      if (event.pointerId !== pointerId) {
        return;
      }

      moved = Math.max(moved, Math.abs(event.clientX - startX));
      progress = Math.max(0, Math.min(1, (rawProgress(event.clientX) - startProgress) / (1 - startProgress)));
      setLeafProgress(leafParts, progress);
    }

    /** @param {PointerEvent} event - Pointer up event. */
    function onUp(event) {
      if (event.pointerId !== pointerId) {
        return;
      }

      const tapped = startedInCorner && moved < TAP_SLOP_PX;
      void release(tapped || progress > DRAG_COMPLETE_THRESHOLD);
    }

    /** @param {Event} event - Pointer cancel or lost-capture event. */
    function onCancel(event) {
      if (/** @type {PointerEvent} */ (event).pointerId !== pointerId) {
        return;
      }

      void release(false);
    }

    /**
     * Finish the drag: land the leaf or spring it back.
     * @param {boolean} complete - Whether the page turn should complete.
     * @returns {Promise<void>} Resolves when the leaf has settled.
     */
    async function release(complete) {
      detach();
      try {
        if (complete) {
          turn.selected = true;
          // A request made during the drag already selected a newer page; the
          // queue lands on it next, so this drag must not select over it.
          if (pendingTarget === null) {
            pages.select(turn.target);
          }
          await tween(turn, progress, 1, 420 * (1 - progress) + 120, easeOut, (value) => setLeafProgress(leafParts, value));
          if (!turn.aborted) {
            pages.commit(turn.target);
          }
        } else {
          await tween(turn, progress, 0, 360 * progress + 120, easeOut, (value) => setLeafProgress(leafParts, value));
        }
      } catch (error) {
        reportError(error);
      } finally {
        finishTurn(turn);
        void kick();
      }
    }

    sheet.addEventListener('pointermove', onMove);
    sheet.addEventListener('pointerup', onUp);
    sheet.addEventListener('pointercancel', onCancel);
    sheet.addEventListener('lostpointercapture', onCancel);
  }

  /**
   * Run one animation tracked by the intro so it can be cancelled together.
   * A cancelled animation settles quietly so the sequence can move on.
   * @param {IntroState} state - Intro bookkeeping.
   * @param {Element | null} element - Target element.
   * @param {Keyframe[]} keyframes - Web Animations API keyframes.
   * @param {KeyframeAnimationOptions} options - Animation options.
   * @returns {Promise<void>} Resolves when the animation finishes or is cancelled.
   */
  async function playIntro(state, element, keyframes, options) {
    if (!element || typeof element.animate !== 'function') {
      return;
    }

    const animation = element.animate(keyframes, { fill: 'both', ...options });
    state.animations.add(animation);
    try {
      await animation.finished;
    } catch {
      // Cancelled by an abort; the sequence checks the abort flag next.
    }
  }

  /**
   * @param {HTMLElement} shell - Book shell element.
   * @returns {void}
   */
  function openShell(shell) {
    shell.classList.remove('is-opening');
    shell.classList.add('is-open');
  }

  /**
   * Cross-fade from the closed book to the open one (reduced motion).
   * @param {IntroState} state - Intro bookkeeping.
   * @param {HTMLElement} shell - Book shell element.
   * @param {HTMLElement} sheet - Book sheet element.
   * @returns {Promise<void>} Resolves when the fade has finished.
   */
  async function playCrossfadeIntro(state, shell, sheet) {
    await playIntro(state, sheet, [{ opacity: 1 }, { opacity: 0 }], { duration: CROSSFADE_OUT_MS, easing: 'ease' });
    if (state.aborted) {
      return;
    }

    openShell(shell);
    await playIntro(state, sheet, [{ opacity: 0 }, { opacity: 1 }], { duration: CROSSFADE_IN_MS, easing: 'ease' });
  }

  /**
   * Slide the ribbon off, then flip the notepad's cover up over its binding, onto page one
   * already hanging underneath.
   * @param {IntroState} state - Intro bookkeeping.
   * @param {HTMLElement} shell - Book shell element.
   * @param {HTMLElement} cover - Cover element.
   * @returns {Promise<void>} Resolves when the notepad is open.
   */
  async function playFlipIntro(state, shell, cover) {
    await delay(INTRO_DELAY_MS);
    if (state.aborted) {
      return;
    }

    const ribbon = playIntro(state, cover.querySelector('.book-ribbon'), NOTEPAD_RIBBON_OFF_KEYFRAMES, RIBBON_OFF_OPTIONS);
    ribbon.catch(() => undefined);
    await delay(RIBBON_OFF_MS * RIBBON_LEAD);
    if (state.aborted) {
      return;
    }

    // The cover turns over the binding exactly like a page, its inside fading as it drops behind the pad.
    const options = { duration: COVER_FLIP_MS, easing: COVER_EASING };
    await Promise.all([
      ribbon,
      playIntro(state, cover, FLIP_KEYFRAMES, options),
      playIntro(state, cover.querySelector('.book-cover-back'), FLIP_BACK_FADE_KEYFRAMES, options)
    ]);
    if (!state.aborted) {
      openShell(shell);
    }
  }

  /**
   * Slide the ribbon off, swing the cover a full 180 degrees around the spine
   * while the book slides from centred-closed to centred-open. The inside of
   * the cover carries the first left page, so it lands already filled in.
   * @param {IntroState} state - Intro bookkeeping.
   * @param {HTMLElement} shell - Book shell element.
   * @param {HTMLElement} sheet - Book sheet element.
   * @param {HTMLElement} cover - Cover element.
   * @param {HTMLElement} grid - Page grid element.
   * @returns {Promise<void>} Resolves when the book is open.
   */
  async function playSwingIntro(state, shell, sheet, cover, grid) {
    await delay(INTRO_DELAY_MS);
    if (state.aborted) {
      return;
    }

    // Animations that run alongside the swing. Each gets a handler right away so
    // a failure is never unhandled, and the intro still awaits them all below.
    /** @type {Promise<void>[]} */
    const companions = [];
    /**
     * @param {Element | null} element - Element to animate.
     * @param {Keyframe[]} keyframes - Keyframes.
     * @param {KeyframeAnimationOptions} animationOptions - Animation options.
     */
    const alongside = (element, keyframes, animationOptions) => {
      const run = playIntro(state, element, keyframes, animationOptions);
      run.catch(() => undefined);
      companions.push(run);
    };

    alongside(cover.querySelector('.book-ribbon'), RIBBON_OFF_KEYFRAMES, RIBBON_OFF_OPTIONS);
    await delay(RIBBON_OFF_MS * RIBBON_LEAD);
    if (state.aborted) {
      return;
    }

    // The inside of the cover carries the first left page, cards already
    // attached, exactly like the back face of a turning leaf. When the cover
    // lands, the live page underneath takes over with nothing to fade in.
    // A search or filter during the swing re-renders the grid, and
    // setPosition then copies the new page so the landing still matches.
    const endpaper = cover.querySelector('.book-endpaper');
    if (endpaper) {
      syncCover = () => carryLeftPage(state, endpaper, grid);
      syncCover();
    }

    const options = { duration: COVER_OPEN_MS, easing: COVER_EASING };
    const swing = playIntro(state, cover, [
      { transform: 'rotateY(0deg)' },
      { transform: 'rotateY(-180deg)' }
    ], options);
    alongside(cover.querySelector('.book-cover-shade'), [
      { opacity: 0 },
      { opacity: 0.7, offset: 0.45 },
      { opacity: 0, offset: 0.5 },
      { opacity: 0 }
    ], options);
    alongside(sheet, [{ transform: 'translateX(-25%)' }, { transform: 'translateX(0)' }], options);
    // The shadow trails the cover's footprint, so it never shows past its edge.
    // Its box stays put and only its mask edge moves, which costs no layout.
    alongside(sheet.querySelector('.book-shadow'), [
      { '--shadow-edge': '50%' },
      { '--shadow-edge': '50%', offset: 0.5 },
      { '--shadow-edge': SHADOW_EDGE_OPEN }
    ], options);
    alongside(sheet.querySelector('.book-cast-right'), [
      { opacity: 0 },
      { opacity: 0.55, offset: 0.3 },
      { opacity: 0, offset: 0.55 },
      { opacity: 0 }
    ], options);

    // The left half stays hidden until the cover lands on it: an open book's
    // left side is the cover, so nothing pops in while it swings.
    await Promise.all([swing, ...companions]);
    if (state.aborted) {
      return;
    }

    // The cover has landed as the left board, showing the same page the live
    // grid holds, so the swap to the real left page is invisible.
    openShell(shell);
  }

  /**
   * Open the book. Runs once: the cover ribbon slides off, the cover swings open,
   * and the left page settles. The notepad flips its cover up; reduced motion cross-fades.
   * Always ends in the open state, even if an animation fails or is aborted.
   * @param {HTMLElement} shell - Book shell element.
   * @returns {Promise<void>} Resolves when the book is open.
   */
  async function runIntro(shell) {
    const sheet = getElementById('book-sheet');
    const cover = getElementById('book-cover');
    const grid = getElementById('artifacts-grid');
    /** @type {IntroState} */
    const state = { aborted: false, animations: new Set() };

    abortIntro = () => {
      state.aborted = true;
      state.animations.forEach((animation) => animation.cancel());
    };
    shell.dataset.sceneIntro = 'opening';
    shell.classList.add('is-opening');
    shell.classList.remove('is-open');

    try {
      if (!sheet || !cover || !grid) {
        return;
      }

      if (prefersReducedMotion()) {
        await playCrossfadeIntro(state, shell, sheet);
      } else if (isMobile()) {
        await playFlipIntro(state, shell, cover);
      } else {
        await playSwingIntro(state, shell, sheet, cover, grid);
      }
    } finally {
      abortIntro = null;
      syncCover = null;
      state.animations.forEach((animation) => animation.cancel());
      openShell(shell);
      shell.dataset.sceneIntro = 'open';
      state.insidePage?.remove();
    }
  }

  /**
   * Open the book cover and settle the pages.
   * @returns {Promise<void>} Resolves when the intro sequence completes.
   */
  function startIntro() {
    const shell = getElementById('book-shell');
    if (!shell || shell.dataset.sceneIntro === 'open') {
      return Promise.resolve();
    }

    if (!introPromise) {
      introPromise = runIntro(shell).finally(() => {
        introPromise = null;
      });
    }

    return introPromise;
  }

  /** Crossing the notepad breakpoint ends whatever is animating in the old layout. */
  function onLayoutChange() {
    if (active) {
      settle();
    }

    abortIntro?.();
  }

  const sheetElement = getElementById('book-sheet');
  if (sheetElement) {
    sheetElement.addEventListener('pointerdown', onPointerDown);
  }

  notepadQuery.addEventListener?.('change', onLayoutChange);

  return {
    startIntro,
    turnPage,
    cancelTurn,
    setPosition
  };
}
