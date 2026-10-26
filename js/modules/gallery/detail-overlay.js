import { applyDynamicStyles, createDetailContent } from './render.js';

/**
 * Smallest scale for the card-to-detail expand/collapse animation.
 * It keeps the detail panel from shrinking below a readable size
 * when the originating card is much smaller than the overlay.
 */
const MIN_SCALE = 0.36;

/**
 * Create a detail overlay controller managing the expanded artifact panel lifecycle,
 * including open/close animation, focus trapping, and background inert management.
 * @param {{
 *   detailOverlay: HTMLElement,
 *   detailPanel: HTMLElement,
 *   grid: HTMLElement,
 *   documentObj: Document,
 *   windowObj: Window,
 *   motion: { prefersReducedMotion: () => boolean },
 *   setBackgroundContentInert: (elements: HTMLElement[], isInert: boolean) => void,
 *   backgroundElements: HTMLElement[],
 *   detailCloseDelay: number
 * }} options - Overlay DOM dependencies and injected helpers.
 * @returns {{
 *   getExpandedId: () => string | null,
 *   getCardById: (id: string | null | undefined) => HTMLElement | null,
 *   updateExpandedCardState: () => void,
 *   trapFocus: (event: KeyboardEvent) => boolean,
 *   open: (id: string, triggerCard: HTMLElement | null, artifactById: Map<string, *>) => void,
 *   close: (options?: { restoreFocus?: boolean, immediate?: boolean }) => void,
 *   toggle: (id: string, triggerCard: HTMLElement | null, artifactById: Map<string, *>) => void
 * }} Overlay controller methods.
 */
export function createDetailOverlay({
  detailOverlay,
  detailPanel,
  grid,
  documentObj,
  windowObj,
  motion,
  setBackgroundContentInert,
  backgroundElements,
  detailCloseDelay
}) {
  /** @type {string | null} */
  let expandedId = null;
  /** @type {HTMLElement | null} */
  let lastExpandedTrigger = null;
  /** @type {number | undefined} */
  let overlayResetTimer;

  function getExpandedId() {
    return expandedId;
  }

  /**
   * @param {string | null | undefined} id - Artifact id.
   * @returns {HTMLElement | null} The card element for the id, if present.
   */
  function getCardById(id) {
    return id
      ? /** @type {HTMLElement | null} */ (grid.querySelector(`.artifact-card[data-id="${CSS.escape(id)}"]`))
      : null;
  }

  function updateExpandedCardState() {
    for (const element of grid.querySelectorAll('.artifact-card')) {
      const card = /** @type {HTMLElement} */ (element);
      const isExpanded = card.dataset.id === expandedId;
      card.classList.toggle('expanded', isExpanded);
      card.setAttribute('aria-expanded', String(isExpanded));
    }
  }

  /**
   * The panel's settled box. The layout size and the overlay's centre are used, not the
   * panel's own bounding rect, because that rect includes the closed-state transform
   * (the panel is centred in the overlay and sits scaled down until it opens).
   * @returns {{ centerX: number, centerY: number, width: number, height: number }} Panel centre and size.
   */
  function measurePanel() {
    const overlayRect = detailOverlay.getBoundingClientRect();
    return {
      centerX: overlayRect.left + overlayRect.width / 2,
      centerY: overlayRect.top + overlayRect.height / 2,
      width: detailPanel.offsetWidth,
      height: detailPanel.offsetHeight
    };
  }

  /**
   * Start the panel from the card's centre at one uniform scale, so it never squashes.
   * @param {DOMRect | null} originRect - Bounding rect of the trigger card.
   * @param {{ centerX: number, centerY: number, width: number, height: number }} panel - Settled panel box.
   * @returns {void}
   */
  function applyDetailMotion(originRect, panel) {
    clearDetailMotion();
    if (motion.prefersReducedMotion() || !originRect || !panel.width || !panel.height) {
      return;
    }

    const originCenterX = originRect.left + originRect.width / 2;
    const originCenterY = originRect.top + originRect.height / 2;
    const fit = Math.max(originRect.width / panel.width, originRect.height / panel.height);
    const scale = Math.max(MIN_SCALE, Math.min(1, fit));

    detailPanel.style.setProperty('--detail-from-x', `${originCenterX - panel.centerX}px`);
    detailPanel.style.setProperty('--detail-from-y', `${originCenterY - panel.centerY}px`);
    detailPanel.style.setProperty('--detail-from-scale', `${scale}`);
  }

  function clearDetailMotion() {
    detailPanel.style.removeProperty('--detail-from-x');
    detailPanel.style.removeProperty('--detail-from-y');
    detailPanel.style.removeProperty('--detail-from-scale');
  }

  /** @param {KeyboardEvent} event - Keydown event to trap within the overlay. */
  function trapFocus(event) {
    if (!expandedId) {
      return false;
    }

    const focusableSelectors = [
      'a[href]',
      'button:not([disabled])',
      'input:not([disabled])',
      'select:not([disabled])',
      'textarea:not([disabled])',
      '[tabindex]:not([tabindex="-1"])'
    ].join(',');

    const focusableElements = /** @type {HTMLElement[]} */ (
      [...detailPanel.querySelectorAll(focusableSelectors)].filter(
        (element) => !element.hasAttribute('hidden') && element.getAttribute('aria-hidden') !== 'true'
      )
    );

    if (focusableElements.length === 0) {
      event.preventDefault();
      detailPanel.focus({ preventScroll: true });
      return true;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    const activeElement = documentObj.activeElement;
    const activeElementOutsidePanel = !detailPanel.contains(activeElement);

    if (event.shiftKey && (activeElement === firstElement || activeElementOutsidePanel)) {
      event.preventDefault();
      lastElement.focus({ preventScroll: true });
      return true;
    }

    if (!event.shiftKey && (activeElement === lastElement || activeElementOutsidePanel)) {
      event.preventDefault();
      firstElement.focus({ preventScroll: true });
      return true;
    }

    return false;
  }

  /**
   * @param {string} id - Artifact id to open.
   * @param {HTMLElement | null} triggerCard - Card that triggered the overlay.
   * @param {Map<string, import("./catalog.js").ArtifactRecord>} artifactById - Artifact lookup.
   * @returns {void}
   */
  function open(id, triggerCard, artifactById) {
    const item = artifactById.get(id);
    if (!item) {
      return;
    }

    clearTimeout(overlayResetTimer);
    expandedId = id;
    lastExpandedTrigger = triggerCard || getCardById(id);
    detailPanel.innerHTML = createDetailContent(item);
    applyDynamicStyles(detailPanel);
    detailPanel.setAttribute('aria-describedby', 'detail-description');
    const cardBgColor = triggerCard ? triggerCard.dataset.cardColor || '' : '';
    detailPanel.style.setProperty('--detail-accent', cardBgColor || 'var(--color-page-paper)');
    detailOverlay.classList.add('visible');
    detailOverlay.setAttribute('aria-hidden', 'false');
    documentObj.body.classList.add('detail-open');
    setBackgroundContentInert(backgroundElements, true);
    updateExpandedCardState();

    const originRect = lastExpandedTrigger ? lastExpandedTrigger.getBoundingClientRect() : null;
    applyDetailMotion(originRect, measurePanel());

    windowObj.requestAnimationFrame(() => {
      detailOverlay.classList.add('open');
      const closeButton = /** @type {HTMLElement | null} */ (detailPanel.querySelector('.detail-close'));
      if (closeButton) {
        closeButton.focus({ preventScroll: true });
      }
    });
  }

  function close({ restoreFocus = true, immediate = false } = {}) {
    if (!expandedId && !detailOverlay.classList.contains('visible')) {
      return;
    }

    const closingId = expandedId;
    const fallbackCard = lastExpandedTrigger && documentObj.body.contains(lastExpandedTrigger)
      ? lastExpandedTrigger
      : getCardById(closingId);

    expandedId = null;
    updateExpandedCardState();
    detailOverlay.classList.remove('open');
    detailOverlay.setAttribute('aria-hidden', 'true');
    documentObj.body.classList.remove('detail-open');

    const finishClose = () => {
      detailOverlay.classList.remove('visible');
      detailPanel.innerHTML = '';
      detailPanel.removeAttribute('aria-describedby');
      clearDetailMotion();
      setBackgroundContentInert(backgroundElements, false);
      if (restoreFocus && fallbackCard) {
        fallbackCard.focus({ preventScroll: true });
      }
      lastExpandedTrigger = null;
    };

    clearTimeout(overlayResetTimer);
    if (immediate || motion.prefersReducedMotion()) {
      clearDetailMotion();
      finishClose();
      return;
    }

    const originRect = fallbackCard ? fallbackCard.getBoundingClientRect() : null;
    applyDetailMotion(originRect, measurePanel());
    overlayResetTimer = windowObj.setTimeout(finishClose, detailCloseDelay);
  }

  /**
   * @param {string} id - Artifact id to toggle.
   * @param {HTMLElement | null} triggerCard - Card that triggered the overlay.
   * @param {Map<string, import("./catalog.js").ArtifactRecord>} artifactById - Artifact lookup.
   * @returns {void}
   */
  function toggle(id, triggerCard, artifactById) {
    if (expandedId === id) {
      close();
      return;
    }

    open(id, triggerCard, artifactById);
  }

  return {
    getExpandedId,
    getCardById,
    updateExpandedCardState,
    trapFocus,
    open,
    close,
    toggle
  };
}
