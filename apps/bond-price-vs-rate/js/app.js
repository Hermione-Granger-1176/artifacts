import {
  YIELD_CURVES,
  bondAnalytics,
  bondPrice,
  bondSchedule,
  curveYieldPct,
  priceRegime
} from "./modules/bond-math.js";
import { refreshPalette, renderCharts } from "./modules/charts.js";
import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";
import { bindEvents } from "./modules/interactions.js";
import { formatCurrency, formatDollarTick, formatPercent } from "./modules/formatting.js";
import { renderNarrative } from "./modules/narrative.js";
import {
  cacheElements,
  getChartElements,
  syncCurveButtons,
  syncSliderLabels
} from "./modules/ui.js";

const FACE_VALUE = 1000;
const FREQUENCY = 1;
const RATE_AXIS_MIN = 1;
const RATE_AXIS_MAX = 12;
const RATE_AXIS_STEP = 0.1;
const YEARS_MIN = 1;
const YEARS_MAX = 30;
const SENSITIVITY_MATURITIES = [2, 5, 10, 20, 30];
const RATE_SHOCK = 1;

let elements = /** @type {Record<string, any>} */ ({});
let charts = /** @type {Record<string, any>} */ ({});
let pendingRecalcFrame = /** @type {number | null} */ (null);
let selectedCurveKey = /** @type {keyof typeof YIELD_CURVES} */ ("normal");

renderAppShell();

initializeMatureApp({
  onErrorContext: "bonds vs interest rates initialization",
  run: () => {
    elements = cacheElements();
    initAppShell({
      onThemeChange: () => {
        refreshPalette();
        recalc();
      }
    });
    bindEvents({
      elements,
      onSliderInput: () => {
        syncSliderLabels(elements);
        scheduleRecalc();
      },
      onCurveSelect: (curveKey) => {
        selectedCurveKey = /** @type {keyof typeof YIELD_CURVES} */ (curveKey);
        syncCurveButtons(elements, selectedCurveKey);
        scheduleRecalc();
      },
      onApplyCurveRate: applyCurveRate
    });
    syncSliderLabels(elements);
    syncCurveButtons(elements, selectedCurveKey);
    recalc();
  }
});

/** Read the current bond terms from the three sliders and the fixed constants. */
function readBond() {
  return {
    faceValue: FACE_VALUE,
    couponRatePct: +elements.slCoupon.value,
    years: +elements.slYears.value,
    annualYieldPct: +elements.slRate.value,
    frequency: FREQUENCY
  };
}

/** Sample price against the market rate and mark the bond's current point. */
function buildPriceRateSeries(bond) {
  const curve = [];
  for (let rate = RATE_AXIS_MIN; rate <= RATE_AXIS_MAX + 1e-9; rate += RATE_AXIS_STEP) {
    const rounded = Math.round(rate * 100) / 100;
    curve.push({ x: rounded, y: bondPrice({ ...bond, annualYieldPct: rounded }) });
  }
  return { curve, current: { x: bond.annualYieldPct, y: bondPrice(bond) } };
}

/** Sample the selected yield curve across maturities and mark the bond's maturity. */
function buildYieldCurveSeries(bond) {
  const shape = YIELD_CURVES[selectedCurveKey];
  const curve = [];
  for (let years = YEARS_MIN; years <= YEARS_MAX; years += 1) {
    curve.push({ x: years, y: curveYieldPct(shape, years) });
  }
  return {
    curve,
    current: { x: bond.years, y: curveYieldPct(shape, bond.years) }
  };
}

/** Push the selected curve's rate at the bond's maturity into the market-rate slider. */
function applyCurveRate() {
  const bond = readBond();
  const ratePct = curveYieldPct(YIELD_CURVES[selectedCurveKey], bond.years);
  const clamped = Math.min(RATE_AXIS_MAX, Math.max(RATE_AXIS_MIN, ratePct));
  elements.slRate.value = String(Math.round(clamped * 10) / 10);
  syncSliderLabels(elements);
  scheduleRecalc();
}

/** Percent price change for a one-point rate rise at a given maturity. */
function shockPct(bond, years) {
  const atRate = bondPrice({ ...bond, years, annualYieldPct: bond.annualYieldPct });
  const atShock = bondPrice({ ...bond, years, annualYieldPct: bond.annualYieldPct + RATE_SHOCK });
  return (atShock / atRate - 1) * 100;
}

/** Compare the one-point price hit across maturities, highlighting the current one. */
function buildSensitivity(bond) {
  const maturities = Array.from(new Set([...SENSITIVITY_MATURITIES, bond.years]))
    .filter((maturity) => maturity >= YEARS_MIN && maturity <= YEARS_MAX)
    .sort((a, b) => a - b);

  return {
    labels: maturities.map(String),
    values: maturities.map((maturity) => shockPct(bond, maturity)),
    currentIndex: maturities.indexOf(bond.years),
    currentPct: shockPct(bond, bond.years),
    shortPct: shockPct(bond, 2),
    longPct: shockPct(bond, 30)
  };
}

function scheduleRecalc() {
  if (pendingRecalcFrame !== null) {
    return;
  }

  pendingRecalcFrame = window.requestAnimationFrame(() => {
    pendingRecalcFrame = null;
    recalc();
  });
}

function recalc() {
  const bond = readBond();
  const price = bondPrice(bond);
  const regime = priceRegime(bond.couponRatePct, bond.annualYieldPct);
  const priceRate = buildPriceRateSeries(bond);
  const sensitivity = buildSensitivity(bond);
  const yieldCurve = buildYieldCurveSeries(bond);

  const state = {
    bond,
    price,
    regime,
    schedule: bondSchedule(bond),
    analytics: bondAnalytics(bond),
    sensitivity: {
      currentPct: sensitivity.currentPct,
      shortPct: sensitivity.shortPct,
      longPct: sensitivity.longPct
    },
    curve: {
      key: selectedCurveKey,
      label: YIELD_CURVES[selectedCurveKey].label,
      atMaturityPct: yieldCurve.current.y
    }
  };

  renderNarrative(elements, state, { formatCurrency, formatPercent });

  charts = renderCharts({
    charts,
    elements: getChartElements(elements),
    priceRate,
    sensitivity: {
      labels: sensitivity.labels,
      values: sensitivity.values,
      currentIndex: sensitivity.currentIndex
    },
    yieldCurve,
    formatDollarTick
  });
}
