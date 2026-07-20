import { applyDynamicStyles, createDetailContent } from './render.js';

/**
 * Minimum scale factors for card-to-detail expand/collapse animations.
 * These prevent the detail panel from shrinking below a readable size
 * when the originating card is much smaller than the overlay.
 */
const MIN_SCALE_X = 0.36;
const MIN_SCALE_Y = 0.24;

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
   * @param {DOMRect | null} originRect - Bounding rect of the trigger card.
   * @param {DOMRect} panelRect - Bounding rect of the detail panel.
   * @returns {void}
   */
  function applyDetailMotion(originRect, panelRect) {
    clearDetailMotion();
    if (motion.prefersReducedMotion() || !originRect || !panelRect.width || !panelRect.height) {
      return;
    }

    const panelCenterX = panelRect.left + panelRect.width / 2;
    const panelCenterY = panelRect.top + panelRect.height / 2;
    const originCenterX = originRect.left + originRect.width / 2;
    const originCenterY = originRect.top + originRect.height / 2;
    const scaleX = Math.max(MIN_SCALE_X, Math.min(1, originRect.width / panelRect.width));
    const scaleY = Math.max(MIN_SCALE_Y, Math.min(1, originRect.height / panelRect.height));

    detailPanel.style.setProperty('--detail-from-x', `${originCenterX - panelCenterX}px`);
    detailPanel.style.setProperty('--detail-from-y', `${originCenterY - panelCenterY}px`);
    detailPanel.style.setProperty('--detail-from-scale-x', `${scaleX}`);
    detailPanel.style.setProperty('--detail-from-scale-y', `${scaleY}`);
  }

  function clearDetailMotion() {
    detailPanel.style.removeProperty('--detail-from-x');
    detailPanel.style.removeProperty('--detail-from-y');
    detailPanel.style.removeProperty('--detail-from-scale-x');
    detailPanel.style.removeProperty('--detail-from-scale-y');
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

    const panelRect = detailPanel.getBoundingClientRect();
    const originRect = lastExpandedTrigger ? lastExpandedTrigger.getBoundingClientRect() : null;
    applyDetailMotion(originRect, panelRect);

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

    const panelRect = detailPanel.getBoundingClientRect();
    const originRect = fallbackCard ? fallbackCard.getBoundingClientRect() : null;
    applyDetailMotion(originRect, panelRect);
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
