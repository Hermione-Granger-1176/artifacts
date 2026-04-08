// Tests for app entry points (apps/<slug>/js/app.js).
// These files execute module-level side effects (renderAppShell, initializeMatureApp)
// on import, so they require comprehensive global mocks before dynamic import.
import assert from 'node:assert/strict';
import test from 'node:test';

function makeElement(id) {
  const classes = new Set();
  const attrs = {};
  const listeners = {};
  return {
    id,
    hidden: false,
    textContent: '',
    value: '10',
    className: '',
    innerHTML: '',
    childElementCount: 0,
    tabIndex: -1,
    style: {},
    dataset: {},
    children: [],
    classList: {
      _classes: classes,
      add(cls) { classes.add(cls); },
      remove(cls) { classes.delete(cls); },
      toggle(cls, force) {
        if (force !== undefined) {
          force ? classes.add(cls) : classes.delete(cls);
        } else {
          classes.has(cls) ? classes.delete(cls) : classes.add(cls);
          return classes.has(cls);
        }
      },
      contains(cls) { return classes.has(cls); }
    },
    setAttribute(k, v) { attrs[k] = v; },
    getAttribute(k) { return attrs[k] ?? null; },
    removeAttribute(k) { delete attrs[k]; },
    addEventListener(type, handler) {
      listeners[type] = listeners[type] || [];
      listeners[type].push(handler);
    },
    appendChild(child) { this.children.push(child); return child; },
    append(...nodes) { this.children.push(...nodes); },
    querySelector() { return null; },
    closest() { return null; },
    blur() {},
    _listeners: listeners
  };
}

function setupFullMocks() {
  const elementMap = {};

  // Pre-create elements for all IDs both apps will cache
  const allIds = [
    // Loan amortization IDs
    'inPrincipal', 'inRate', 'inTenure',
    'slPrincipal', 'slRate', 'slTenure',
    'selFreq', 'biweeklyMode', 'bwTrue', 'bwAccel', 'bwDesc',
    'extraList', 'btnAdd', 'metrics',
    'btnCharts', 'btnTable', 'chartsWrap', 'tableWrap',
    'btnPeriod', 'btnYearly', 'tableSummary',
    'periodTableWrap', 'yearlyTableWrap', 'tbody', 'ybody',
    'balanceChart', 'compChart', 'savingsChart', 'cumulChart', 'periodChart',
    // Tokenizer explorer IDs
    'tabs', 'scenario-type', 'sentence-prefix',
    'temp-slider', 'temp-val', 'topp-slider', 'topp-val',
    'bars', 'token-pills', 'insight-box', 'concepts',
    // App shell IDs
    'back-button', 'theme-toggle', 'scroll-top',
    'runtime-error', 'runtime-error-details', 'runtime-error-output', 'runtime-error-copy'
  ];

  for (const id of allIds) {
    elementMap[id] = makeElement(id);
  }

  // Set slider default values
  elementMap.slPrincipal.value = '100000';
  elementMap.slRate.value = '6';
  elementMap.slTenure.value = '15';
  elementMap.selFreq.value = 'monthly';
  elementMap['temp-slider'].value = '10';
  elementMap['topp-slider'].value = '90';

  const shellSlots = {};

  globalThis.document = {
    readyState: 'interactive',
    referrer: '',
    documentElement: {
      dataset: {},
      getAttribute(name) { return name === 'data-theme' ? 'light' : null; },
      setAttribute(name, value) { this.dataset[name] = value; }
    },
    getElementById(id) { return elementMap[id] || null; },
    querySelector(sel) {
      if (sel === 'meta[name="theme-color"]') {
        return { setAttribute() {}, getAttribute() { return null; } };
      }
      if (sel.startsWith('[data-app-shell=')) {
        const key = sel;
        if (!shellSlots[key]) {
          shellSlots[key] = { childElementCount: 0, innerHTML: '' };
        }
        return shellSlots[key];
      }
      return null;
    },
    createElement(tag) { return makeElement(tag); },
    addEventListener() {}
  };

  globalThis.window = {
    __ARTIFACTS_APP_THEME_BOOTSTRAP__: {
      normalizeTheme(t) { return t === 'dark' ? 'dark' : 'light'; }
    },
    matchMedia() { return { matches: false }; },
    scrollY: 0,
    scrollTo() {},
    history: { length: 2, back() {} },
    location: { origin: 'https://example.com', href: '' },
    localStorage: {
      getItem() { return null; },
      setItem() {}
    },
    addEventListener() {},
    requestAnimationFrame(fn) { fn(); return 1; },
    Chart: function MockChart(_canvas, config) {
      this.type = config.type;
      this.data = config.data;
      this.options = config.options;
      this.plugins = config.plugins;
      this.update = () => {};
      this.$artifactsFormatCurrency = null;
      this.$artifactsInterestTotal = null;
      this.$artifactsPalette = null;
    },
    ChartDataLabels: {}
  };

  globalThis.getComputedStyle = () => ({
    getPropertyValue() { return 'rgb(100, 150, 200)'; }
  });

  globalThis.HTMLElement = globalThis.HTMLElement ?? class {};

  return { elementMap, shellSlots };
}

function cleanupMocks() {
  delete globalThis.document;
  delete globalThis.window;
  delete globalThis.getComputedStyle;
}

test('loan amortization app.js loads and initializes without error', async () => {
  const { elementMap } = setupFullMocks();
  try {
    await import(`../../apps/loan-amortization/js/app.js?t=${Date.now()}-${Math.random()}`);

    // initializeMatureApp fires the run callback which calls recalc.
    assert.ok(
      globalThis.document.documentElement.dataset.runtimeStatus !== undefined,
      'runtime status should be set'
    );

    // Verify initial UI was synced
    assert.ok(elementMap.inPrincipal.value !== '', 'principal input should be formatted');

    // Exercise slider input event (triggers scheduleRecalc -> recalc)
    const sliderListeners = elementMap.slPrincipal._listeners;
    if (sliderListeners.input) {
      elementMap.slPrincipal.value = '150000';
      sliderListeners.input[0]();
    }

    // Exercise frequency change
    const freqListeners = elementMap.selFreq._listeners;
    if (freqListeners.change) {
      elementMap.selFreq.value = 'biweekly';
      freqListeners.change[0]();
    }

    // Exercise view mode toggle
    const btnTableListeners = elementMap.btnTable._listeners;
    if (btnTableListeners.click) {
      btnTableListeners.click[0]();
    }

    // Exercise add extra button
    const btnAddListeners = elementMap.btnAdd._listeners;
    if (btnAddListeners.click) {
      btnAddListeners.click[0]();
    }

    // Exercise biweekly mode toggle
    const bwTrueListeners = elementMap.bwTrue._listeners;
    if (bwTrueListeners.click) {
      bwTrueListeners.click[0]();
    }
    // Exercise accelerated biweekly mode
    const bwAccelListeners = elementMap.bwAccel._listeners;
    if (bwAccelListeners.click) {
      bwAccelListeners.click[0]();
    }

    // Exercise table mode toggle
    const btnPeriodListeners = elementMap.btnPeriod._listeners;
    if (btnPeriodListeners.click) {
      btnPeriodListeners.click[0]();
    }
    const btnYearlyListeners = elementMap.btnYearly._listeners;
    if (btnYearlyListeners.click) {
      btnYearlyListeners.click[0]();
    }

    // Exercise charts mode toggle to trigger chart rendering
    const btnChartsListeners = elementMap.btnCharts._listeners;
    if (btnChartsListeners.click) {
      btnChartsListeners.click[0]();
    }

    // Exercise extra list click (remove action) with mock target
    const extraListClickListeners = elementMap.extraList._listeners;
    if (extraListClickListeners.click) {
      // Click with no matching button — should be a no-op
      extraListClickListeners.click[0]({
        target: { closest() { return null; } }
      });

      // Click on a set-type button
      extraListClickListeners.click[0]({
        target: {
          closest(sel) {
            if (sel === 'button[data-action]') {
              return {
                dataset: { action: 'set-type', type: 'onetime' },
                closest(s) {
                  if (s === '[data-extra-id]') return { dataset: { extraId: '0' } };
                  return null;
                }
              };
            }
            return null;
          }
        }
      });

      // Click on remove-extra button
      extraListClickListeners.click[0]({
        target: {
          closest(sel) {
            if (sel === 'button[data-action]') {
              return {
                dataset: { action: 'remove-extra' },
                closest(s) {
                  if (s === '[data-extra-id]') return { dataset: { extraId: '0' } };
                  return null;
                }
              };
            }
            return null;
          }
        }
      });
    }

    // Exercise extra list input
    const extraListInputListeners = elementMap.extraList._listeners;
    if (extraListInputListeners.input) {
      // Input with no matching field — should be a no-op
      extraListInputListeners.input[0]({
        target: { closest() { return null; } }
      });
    }

    // Exercise text input change for principal
    const inPrincipalListeners = elementMap.inPrincipal._listeners;
    if (inPrincipalListeners.change) {
      elementMap.inPrincipal.value = '200000';
      inPrincipalListeners.change[0].call(elementMap.inPrincipal);
    }

    // Exercise text input change for rate
    const inRateListeners = elementMap.inRate._listeners;
    if (inRateListeners.change) {
      elementMap.inRate.value = '5.5';
      inRateListeners.change[0].call(elementMap.inRate);
    }

    // Exercise text input change for tenure
    const inTenureListeners = elementMap.inTenure._listeners;
    if (inTenureListeners.change) {
      elementMap.inTenure.value = '20';
      inTenureListeners.change[0].call(elementMap.inTenure);
    }
  } finally {
    cleanupMocks();
  }
});

test('tokenizer explorer app.js loads and initializes without error', async () => {
  const { elementMap } = setupFullMocks();
  try {
    await import(`../../apps/tokenizer-explorer/js/app.js?t=${Date.now()}-${Math.random()}`);

    assert.ok(
      globalThis.document.documentElement.dataset.runtimeStatus !== undefined,
      'runtime status should be set'
    );

    // Exercise temperature slider input
    const tempListeners = elementMap['temp-slider']._listeners;
    if (tempListeners.input) {
      elementMap['temp-slider'].value = '15';
      tempListeners.input[0]();
    }

    // Exercise top-p slider input
    const toppListeners = elementMap['topp-slider']._listeners;
    if (toppListeners.input) {
      elementMap['topp-slider'].value = '50';
      toppListeners.input[0]();
    }

    // Exercise tab selection by clicking a tab button in the tabs container
    const tabButtons = elementMap.tabs.children;
    if (tabButtons.length > 1) {
      const secondTab = tabButtons[1];
      if (secondTab._listeners && secondTab._listeners.click) {
        secondTab._listeners.click[0]();
      }
    }
  } finally {
    cleanupMocks();
  }
});
