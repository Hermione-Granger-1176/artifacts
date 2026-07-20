const INTRO_DELAY_MS = 500;
const PAGE_TURN_MS = 600;
const COVER_OPEN_MS = 950;
const LEFT_PAGE_IN_MS = 750;
const SHEET_SETTLE_MS = 450;
const RIGHT_PAGE_BRIGHTEN_MS = 500;
const REDUCED_MOTION_FADE_MS = 400;
const MOBILE_FADE_MS = 200;
const MOBILE_BREAKPOINT = 700;
const SCENE_PERSPECTIVE = '1600px';
const EASE_OUT_EASING = 'cubic-bezier(0.22, 1, 0.36, 1)';
const PAGE_TURN_DIRECTIONS = {
  next: {
    flipInOrigin: 'right center',
    flipOutOrigin: 'left center',
    flippingInPage: 'left',
    flippingOutPage: 'right',
    rotateInDeg: 92,
    rotateOutDeg: -92
  },
  previous: {
    flipInOrigin: 'left center',
    flipOutOrigin: 'right center',
    flippingInPage: 'right',
    flippingOutPage: 'left',
    rotateInDeg: -92,
    rotateOutDeg: 92
  }
};

/**
 * Create book-scene helpers for intro motion and page turns.
 * Every method safely no-ops when the matching DOM nodes are absent.
 * Uses the Web Animations API for the primary animation sequences, with a
 * small amount of inline style and transition orchestration.
 * @param {{
 *   documentObj?: Document,
 *   windowObj?: Window,
 *   motion?: { prefersReducedMotion?: () => boolean }
 * }} [options={}] - Injected browser APIs for DOM access and motion checks.
 * @returns {{
 *   startIntro: () => Promise<void>,
 *   turnPage: (renderNext?: () => *, options?: { direction?: ('next'|'previous') }) => Promise<*>
 * }} Book-scene helpers.
 */
export function createBookScene({ documentObj = document, windowObj = window, motion } = {}) {
  /** @type {Promise<void> | null} */
  let introPromise = null;
  let pageTurnQueue = Promise.resolve();

  function prefersReducedMotion() {
    if (motion && typeof motion.prefersReducedMotion === 'function') {
      return motion.prefersReducedMotion();
    }

    if (windowObj && typeof windowObj.matchMedia === 'function') {
      return windowObj.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    return false;
  }

  /**
   * @param {string} id - Element id.
   * @returns {HTMLElement | null} The element, if present.
   */
  function getElementById(id) {
    if (!documentObj || typeof documentObj.getElementById !== 'function') {
      return null;
    }

    return documentObj.getElementById(id);
  }

  /**
   * Run an element.animate() call and wait for it to finish.
   * Cleans up inline styles set by `fill: 'forwards'` after the animation lands.
   * @param {HTMLElement | null} element - Target element.
   * @param {Keyframe[]} keyframes - Web Animations API keyframes.
   * @param {KeyframeAnimationOptions} options - Animation options.
   * @returns {Promise<void>} Resolves when the animation finishes.
   */
  async function animateAndClean(element, keyframes, options) {
    if (!element || typeof element.animate !== 'function') {
      return;
    }

    const animation = element.animate(keyframes, options);
    await animation.finished;
    if (typeof animation.commitStyles === 'function') {
      try {
        animation.commitStyles();
      } catch (error) {
        if (!(error instanceof DOMException) || error.name !== 'InvalidStateError') {
          throw error;
        }
      }
    }
    animation.cancel();
  }

  /**
   * Clear all inline styles that may have been applied during an animation sequence.
   * @param {HTMLElement | null} element - Element to clean up.
   * @param {string[]} properties - CSS property names (camelCase) to remove.
   */
  function clearInlineStyles(element, properties) {
    if (!element) {
      return;
    }

    const style = /** @type {Record<string, string>} */ (/** @type {unknown} */ (element.style));
    for (const prop of properties) {
      style[prop] = '';
    }
  }

  /**
   * @param {HTMLElement} shell - Book shell element.
   * @param {HTMLElement | null} cover - Book cover element.
   * @returns {void}
   */
  function finalizeIntroOpen(shell, cover) {
    shell.dataset.sceneIntro = 'open';
    shell.classList.remove('is-opening');
    shell.classList.add('is-open');

    if (cover) {
      cover.style.visibility = 'hidden';
    }
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
   * @param {number} deg - Rotation in degrees.
   * @returns {string} A CSS transform string.
   */
  function getPerspectiveRotateY(deg) {
    return `perspective(${SCENE_PERSPECTIVE}) rotateY(${deg}deg)`;
  }

  /**
   * Open the book cover with a spring-overshoot flip animation, then flip the
   * left page into view.
   * @returns {Promise<void>} Resolves when the intro sequence completes.
   */
  async function startIntro() {
    const shell = getElementById('book-shell');
    const cover = getElementById('book-cover');
    const sheet = getElementById('book-sheet');
    const grid = getElementById('artifacts-grid');

    if (!shell) {
      return;
    }

    if (shell.dataset.sceneIntro === 'open') {
      return;
    }

    if (introPromise) {
      return introPromise;
    }

    introPromise = (async () => {
      shell.dataset.sceneIntro = 'opening';
      shell.classList.add('is-opening');
      shell.classList.remove('is-open');

      if (prefersReducedMotion()) {
        // Opacity-only crossfade: no rotation or translation, just a gentle
        // fade of the cover before the open state lands.
        await animateAndClean(
          cover,
          [{ opacity: 1 }, { opacity: 0 }],
          { duration: REDUCED_MOTION_FADE_MS, easing: 'ease', fill: 'forwards' }
        );
        clearInlineStyles(cover, ['opacity']);
        finalizeIntroOpen(shell, cover);
        return;
      }

      if (!cover || !sheet || !grid) {
        finalizeIntroOpen(shell, cover);
        return;
      }

      const leftPage = /** @type {HTMLElement | null} */ (grid.querySelector('.artifact-page-left'));
      const rightPage = /** @type {HTMLElement | null} */ (grid.querySelector('.artifact-page-right'));

      // Prime the cover in its starting position
      cover.style.transformOrigin = 'left center';
      cover.style.transform = getPerspectiveRotateY(0);
      cover.style.opacity = '1';

      // Dim the right page behind the cover
      if (rightPage) {
        rightPage.style.transition = `opacity ${PAGE_TURN_MS}ms ease`;
        rightPage.style.opacity = '0.82';
      }

      await delay(INTRO_DELAY_MS);

      // Phase 1: Flip the cover open. A soft drop-shadow swells while the
      // cover is mid-turn and dissipates as it clears the sheet.
      await animateAndClean(
        cover,
        [
          {
            transform: getPerspectiveRotateY(0),
            opacity: 1,
            filter: 'drop-shadow(0 4px 10px rgba(0, 0, 0, 0.12))'
          },
          {
            opacity: 0.9,
            filter: 'drop-shadow(26px 22px 36px rgba(0, 0, 0, 0.3))',
            offset: 0.55
          },
          {
            transform: getPerspectiveRotateY(-92),
            opacity: 0.3,
            filter: 'drop-shadow(0 0 0 rgba(0, 0, 0, 0))'
          }
        ],
        {
          duration: COVER_OPEN_MS,
          easing: 'cubic-bezier(0.4, 0, 0.2, 1)',
          fill: 'forwards'
        }
      );

      // Phase 2: the cover has cleared. In parallel: settle the sheet with a
      // tiny overshoot, brighten the right page back up, and flip the left
      // page in from the spine.
      if (leftPage) {
        // Keep left page hidden until we start its animation
        leftPage.style.opacity = '0';
      }

      shell.classList.add('is-open');

      const settleTasks = [
        (async () => {
          await animateAndClean(
            sheet,
            [
              { transform: 'scale(1)' },
              { transform: 'scale(1.012)', offset: 0.45 },
              { transform: 'scale(1)' }
            ],
            { duration: SHEET_SETTLE_MS, easing: EASE_OUT_EASING, fill: 'forwards' }
          );
          clearInlineStyles(sheet, ['transform']);
        })()
      ];

      if (rightPage) {
        rightPage.style.transition = '';
        settleTasks.push((async () => {
          await animateAndClean(
            rightPage,
            [{ opacity: 0.82 }, { opacity: 1 }],
            { duration: RIGHT_PAGE_BRIGHTEN_MS, easing: 'ease', fill: 'forwards' }
          );
          clearInlineStyles(rightPage, ['opacity', 'transition']);
        })());
      }

      if (leftPage) {
        leftPage.style.transformOrigin = 'right center';
        leftPage.style.position = 'relative';
        leftPage.style.zIndex = '4';

        await animateAndClean(
          leftPage,
          [
            { transform: getPerspectiveRotateY(92), opacity: 0 },
            { transform: getPerspectiveRotateY(0), opacity: 1 }
          ],
          {
            duration: LEFT_PAGE_IN_MS,
            easing: EASE_OUT_EASING,
            fill: 'forwards'
          }
        );

        clearInlineStyles(leftPage, ['transformOrigin', 'position', 'zIndex', 'opacity']);
      }

      await Promise.all(settleTasks);

      clearInlineStyles(cover, ['transformOrigin', 'transform', 'opacity', 'filter']);
      finalizeIntroOpen(shell, cover);
    })();

    try {
      await introPromise;
    } finally {
      introPromise = null;
    }
  }

  /**
   * Run a single page-turn animation sequence.
   * Desktop: 3D page flip with shadow.
   * Mobile (<=700px): simple cross-fade.
   * @param {Function} [renderNext] - Callback that renders the next page content.
   * @param {'next'|'previous'} [direction='next'] - Turn direction.
   * @returns {Promise<void>} Resolves when the turn animation completes.
   */
  async function runPageTurn(renderNext, direction) {
    const grid = getElementById('artifacts-grid');
    const render = typeof renderNext === 'function' ? renderNext : () => undefined;

    if (!grid) {
      await Promise.resolve(render());
      return;
    }

    const sheet = getElementById('book-sheet');

    if (!sheet) {
      await Promise.resolve(render());
      return;
    }

    const isMobile = windowObj && windowObj.innerWidth <= MOBILE_BREAKPOINT;
    const turnDirection = direction === 'previous' ? 'previous' : 'next';

    sheet.classList.add('is-turning');

    if (isMobile) {
      await animateAndClean(
        sheet,
        [{ opacity: 1 }, { opacity: 0 }],
        { duration: MOBILE_FADE_MS, easing: 'ease', fill: 'forwards' }
      );

      await Promise.resolve(render());

      await animateAndClean(
        sheet,
        [{ opacity: 0 }, { opacity: 1 }],
        { duration: MOBILE_FADE_MS, easing: 'ease', fill: 'forwards' }
      );

      sheet.classList.remove('is-turning');
      return;
    }

    const leftPage = /** @type {HTMLElement | null} */ (grid.querySelector('.artifact-page-left'));
    const rightPage = /** @type {HTMLElement | null} */ (grid.querySelector('.artifact-page-right'));

    if (!leftPage || !rightPage) {
      await Promise.resolve(render());
      sheet.classList.remove('is-turning');
      return;
    }

    const directionConfig = PAGE_TURN_DIRECTIONS[turnDirection];
    /** @type {Record<string, HTMLElement>} */
    const currentPages = { left: leftPage, right: rightPage };
    const flippingOutPage = currentPages[directionConfig.flippingOutPage];

    // Set perspective on the grid for 3D transforms
    grid.style.perspective = SCENE_PERSPECTIVE;
    grid.style.transformStyle = 'preserve-3d';

    // Start flip-out on the departing page
    flippingOutPage.style.transformOrigin = directionConfig.flipOutOrigin;
    flippingOutPage.style.position = 'relative';
    flippingOutPage.style.zIndex = '4';

    const flipOutAnim = flippingOutPage.animate(
      [
        { transform: getPerspectiveRotateY(0) },
        { transform: getPerspectiveRotateY(directionConfig.rotateOutDeg) }
      ],
      { duration: PAGE_TURN_MS, easing: 'cubic-bezier(0.4, 0, 0.2, 1)', fill: 'forwards' }
    );

    // At the midpoint (page is edge-on), swap content, hidden behind the moving page
    await delay(PAGE_TURN_MS * 0.45);
    await Promise.resolve(render());

    // Immediately start flip-in while flip-out is still finishing
    const newLeft = /** @type {HTMLElement | null} */ (grid.querySelector('.artifact-page-left'));
    const newRight = /** @type {HTMLElement | null} */ (grid.querySelector('.artifact-page-right'));

    if (!newLeft || !newRight) {
      await flipOutAnim.finished;
      flipOutAnim.cancel();
      sheet.classList.remove('is-turning');
      clearInlineStyles(grid, ['perspective', 'transformStyle']);
      return;
    }

    /** @type {Record<string, HTMLElement>} */
    const nextPages = { left: newLeft, right: newRight };
    const flippingInPage = nextPages[directionConfig.flippingInPage];

    flippingInPage.style.transformOrigin = directionConfig.flipInOrigin;
    flippingInPage.style.position = 'relative';
    flippingInPage.style.zIndex = '4';

    const flipInAnim = flippingInPage.animate(
      [
        { transform: getPerspectiveRotateY(directionConfig.rotateInDeg) },
        { transform: getPerspectiveRotateY(0) }
      ],
      { duration: PAGE_TURN_MS, easing: EASE_OUT_EASING, fill: 'forwards' }
    );

    await Promise.all([flipOutAnim.finished, flipInAnim.finished]);
    flipOutAnim.cancel();
    flipInAnim.cancel();

    clearInlineStyles(flippingInPage, ['transformOrigin', 'position', 'zIndex']);
    clearInlineStyles(grid, ['perspective', 'transformStyle']);

    sheet.classList.remove('is-turning');
  }

  /**
   * Queue a page turn so overlapping calls execute sequentially.
   * @param {Function} [renderNext] - Callback that renders the next page content.
   * @param {{ direction?: ('next'|'previous') }} [options={}] - Turn direction.
   * @returns {Promise<*>} Resolves when the queued turn completes.
   */
  function turnPage(renderNext, { direction = 'next' } = {}) {
    const sheet = getElementById('book-sheet');
    if (!sheet || prefersReducedMotion()) {
      const output = typeof renderNext === 'function' ? renderNext() : undefined;
      return Promise.resolve(output);
    }

    pageTurnQueue = pageTurnQueue.then(() => runPageTurn(renderNext, direction));
    return pageTurnQueue;
  }

  return {
    startIntro,
    turnPage
  };
}
