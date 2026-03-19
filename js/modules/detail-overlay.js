import { createDetailContent } from './render.js';

/**
 * Create a detail overlay controller managing the expanded artifact panel lifecycle,
 * including open/close animation, focus trapping, and background inert management.
 * @returns {{ getExpandedId, getCardById, updateExpandedCardState, trapFocus, open, close, toggle }}
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
  DETAIL_CLOSE_DELAY
}) {
  let expandedId = null;
  let lastExpandedTrigger = null;
  let overlayResetTimer = null;

  function getExpandedId() {
    return expandedId;
  }

  function getCardById(id) {
    return id ? grid.querySelector(`.artifact-card[data-id="${id}"]`) : null;
  }

  function updateExpandedCardState() {
    for (const card of grid.querySelectorAll('.artifact-card')) {
      const isExpanded = card.dataset.id === expandedId;
      card.classList.toggle('expanded', isExpanded);
      card.setAttribute('aria-expanded', String(isExpanded));
    }
  }

  function applyDetailMotion(originRect, panelRect) {
    clearDetailMotion();
    if (motion.prefersReducedMotion() || !originRect || !panelRect.width || !panelRect.height) {
      return;
    }

    const panelCenterX = panelRect.left + panelRect.width / 2;
    const panelCenterY = panelRect.top + panelRect.height / 2;
    const originCenterX = originRect.left + originRect.width / 2;
    const originCenterY = originRect.top + originRect.height / 2;
    const scaleX = Math.max(0.36, Math.min(1, originRect.width / panelRect.width));
    const scaleY = Math.max(0.24, Math.min(1, originRect.height / panelRect.height));

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

    const focusableElements = [...detailPanel.querySelectorAll(focusableSelectors)].filter(
      (element) => !element.hasAttribute('hidden') && element.getAttribute('aria-hidden') !== 'true'
    );

    if (focusableElements.length === 0) {
      event.preventDefault();
      detailPanel.focus({ preventScroll: true });
      return true;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    const activeElement = documentObj.activeElement;

    if (event.shiftKey) {
      if (activeElement === firstElement || !detailPanel.contains(activeElement)) {
        event.preventDefault();
        lastElement.focus({ preventScroll: true });
        return true;
      }

      return false;
    }

    if (activeElement === lastElement || !detailPanel.contains(activeElement)) {
      event.preventDefault();
      firstElement.focus({ preventScroll: true });
      return true;
    }

    return false;
  }

  function open(id, triggerCard, artifactById) {
    const item = artifactById.get(id);
    if (!item) {
      return;
    }

    clearTimeout(overlayResetTimer);
    expandedId = id;
    lastExpandedTrigger = triggerCard || getCardById(id);
    detailPanel.innerHTML = createDetailContent(item);
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
      const closeButton = detailPanel.querySelector('.detail-close');
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

    if (!immediate) {
      const panelRect = detailPanel.getBoundingClientRect();
      const originRect = fallbackCard ? fallbackCard.getBoundingClientRect() : null;
      applyDetailMotion(originRect, panelRect);
    } else {
      clearDetailMotion();
    }

    expandedId = null;
    updateExpandedCardState();
    detailOverlay.classList.remove('open');
    detailOverlay.setAttribute('aria-hidden', 'true');
    documentObj.body.classList.remove('detail-open');

    const finishClose = () => {
      detailOverlay.classList.remove('visible');
      detailPanel.innerHTML = '';
      clearDetailMotion();
      setBackgroundContentInert(backgroundElements, false);
      if (restoreFocus && fallbackCard) {
        fallbackCard.focus({ preventScroll: true });
      }
      lastExpandedTrigger = null;
    };

    clearTimeout(overlayResetTimer);
    if (immediate || motion.prefersReducedMotion()) {
      finishClose();
      return;
    }

    overlayResetTimer = windowObj.setTimeout(finishClose, DETAIL_CLOSE_DELAY);
  }

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
