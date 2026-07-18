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
    querySelectorAll() { return []; },
    closest() { return null; },
    blur() {},
    _listeners: listeners
  };
}

export function setupFullMocks() {
  const elementMap = {};
  const allIds = [
    'inPrincipal', 'inRate', 'inTenure',
    'slPrincipal', 'slRate', 'slTenure',
    'selFreq', 'biweeklyMode', 'bwTrue', 'bwAccel', 'bwDesc',
    'extraList', 'btnAdd', 'metrics',
    'viewToggle', 'btnCharts', 'btnTable', 'chartsWrap', 'tableWrap',
    'tableToggle', 'btnPeriod', 'btnYearly', 'tableSummary',
    'periodTableWrap', 'yearlyTableWrap', 'tbody', 'ybody',
    'balanceChart', 'compChart', 'savingsChart', 'cumulChart', 'periodChart',
    'slCoupon', 'slYears',
    'rateValue', 'couponValue', 'yearsValue',
    'priceCaption', 'priceValue', 'regimeBadge', 'rateArrow', 'priceArrow',
    'heroExplain', 'couponCompare', 'mechanismExplain',
    'mathLegendCoupon', 'mathLegendRate', 'mathLegendYears', 'mathLegendFace',
    'mathSchedule', 'mathExplain',
    'sensitivityChart', 'sensitivityExplain', 'priceRateChart', 'rippleExplain',
    'statCurrentYield', 'statMacaulay', 'statModified', 'statConvexity',
    'pvSplit', 'analystExplain',
    'btnCurveNormal', 'btnCurveFlat', 'btnCurveInverted', 'btnApplyCurve',
    'yieldCurveChart', 'curveExplain',
    'tabs', 'scenario-type', 'sentence-prefix', 'sentence-completion',
    'temp-slider', 'temp-val', 'temp-note', 'topp-slider', 'topp-val',
    'sampling-presets', 'pick-token', 'sample-hundred', 'reset-samples',
    'sample-status', 'probability-chart', 'token-pills', 'insight-box',
    'token-examples', 'whitespace-toggle', 'concepts',
    'nav-fill', 'nav-nodes', 'nav-label',
    'back-button', 'theme-toggle', 'scroll-top',
    'runtime-error', 'runtime-error-details', 'runtime-error-output', 'runtime-error-copy'
  ];

  Object.assign(elementMap, Object.fromEntries(allIds.map((id) => [id, makeElement(id)])));

  // Segmented toggles resolve their child buttons through querySelectorAll so
  // initSegmented can wire them the way the real DOM does.
  elementMap.viewToggle.querySelectorAll = () => [elementMap.btnCharts, elementMap.btnTable];
  elementMap.tableToggle.querySelectorAll = () => [elementMap.btnPeriod, elementMap.btnYearly];

  elementMap.slPrincipal.value = '100000';
  elementMap.slRate.value = '6';
  elementMap.slTenure.value = '15';
  elementMap.selFreq.value = 'monthly';
  elementMap.slCoupon.value = '5';
  elementMap.slYears.value = '10';
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

export function cleanupMocks() {
  delete globalThis.document;
  delete globalThis.window;
  delete globalThis.getComputedStyle;
}
