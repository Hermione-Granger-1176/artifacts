/**
 * Create a filter dropdown controller managing open/close state for tool and tag panels.
 * @returns {{ toggle, open, close, isOpen, getOpenKey }}
 */
export function createFilterDropdown(filterControls) {
  let openFilterKey = null;

  function toggle(key) {
    if (openFilterKey === key) {
      close();
      return;
    }

    open(key);
  }

  function open(key) {
    close();
    openFilterKey = key;
    const control = filterControls[key];
    control.root.classList.add('open');
    control.toggle.setAttribute('aria-expanded', 'true');
    control.panel.setAttribute('aria-hidden', 'false');
  }

  function close() {
    if (!openFilterKey) {
      return;
    }

    const control = filterControls[openFilterKey];
    control.root.classList.remove('open');
    control.toggle.setAttribute('aria-expanded', 'false');
    control.panel.setAttribute('aria-hidden', 'true');
    openFilterKey = null;
  }

  function isOpen() {
    return openFilterKey !== null;
  }

  function getOpenKey() {
    return openFilterKey;
  }

  return { toggle, open, close, isOpen, getOpenKey };
}
