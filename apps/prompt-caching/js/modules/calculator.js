/* Savings calculator: preset workloads, sliders, and a live cost dashboard. */

import { CACHE_MIN_TOKENS, savingsMonthly } from "./math.js";
import { byId, makeEl, clear } from "./dom.js";
import { skipFirstTransition } from "../../../../js/modules/dom-sync.js";
import { formatCompact, formatCurrency, formatPercent } from "../../../../js/modules/formatting.js";

// One formatter for the slider readouts, so a drag does not build one per tick
// (which is what toLocaleString does on every call).
const COUNT_FORMAT = new Intl.NumberFormat();

// Every preset prefix is at least CACHE_MIN_TOKENS long, so each one caches.
const PRESETS = [
  { name: "Hobby", sys: 1500, req: 100, hit: 70, price: 3 },
  { name: "Startup", sys: 2000, req: 500, hit: 80, price: 3 },
  { name: "Scale", sys: 8000, req: 5000, hit: 90, price: 3 }
];

// Whole dollars once past $1,000 (grouped thousands), cents below that.
/** @param {number} value - Dollar amount. @returns {string} Formatted currency. */
function money(value) {
  return Math.abs(value) >= 1000 ? formatCurrency(value, 0) : formatCurrency(value, 2);
}

/**
 * The line under the savings figure.
 * @param {{ without: number, savings: number, cacheable: boolean }} result - savingsMonthly output.
 * @returns {string}
 */
function savingsSummary({ without, savings, cacheable }) {
  if (!cacheable) {
    return `Not cached: a prefix needs at least ${COUNT_FORMAT.format(CACHE_MIN_TOKENS)} tokens`;
  }
  const percent = formatPercent((Math.abs(savings) / without) * 100, 0);
  if (savings < 0) {
    return `${percent} more expensive: cache writes cost more than the hits save`;
  }
  return `${percent} cheaper, ${money(savings * 12)} per year`;
}

export function initCalculator() {
  const sys = /** @type {HTMLInputElement} */ (byId("calcSys"));
  const req = /** @type {HTMLInputElement} */ (byId("calcReq"));
  const hit = /** @type {HTMLInputElement} */ (byId("calcHit"));
  const price = /** @type {HTMLInputElement} */ (byId("calcPrice"));
  const presetsWrap = byId("calcPresets");
  if (!sys || !req || !hit || !price || !presetsWrap) {
    return;
  }

  const sysVal = byId("calcSysVal");
  const reqVal = byId("calcReqVal");
  const hitVal = byId("calcHitVal");
  const priceVal = byId("calcPriceVal");
  const withoutOut = byId("calcWithout");
  const withOut = byId("calcWith");
  const savingsOut = byId("calcSavings");
  const pctOut = byId("calcPct");
  const barWithout = byId("calcBarWithout");
  const barWith = byId("calcBarWith");
  const tokensOut = byId("calcTokens");
  const effOut = byId("calcEff");

  function syncPresets() {
    for (const btn of presetsWrap.querySelectorAll("button")) {
      const preset = PRESETS.find((p) => p.name === btn.textContent);
      const active = preset &&
        Number(sys.value) === preset.sys &&
        Number(req.value) === preset.req &&
        Number(hit.value) === preset.hit &&
        Number(price.value) === preset.price;
      btn.classList.toggle("active", Boolean(active));
      btn.setAttribute("aria-pressed", active ? "true" : "false");
    }
  }

  function update() {
    const sysTokens = Number.parseFloat(sys.value);
    const requests = Number.parseFloat(req.value);
    const hitFraction = Number.parseFloat(hit.value) / 100;
    const pricePerM = Number.parseFloat(price.value);

    sysVal.textContent = COUNT_FORMAT.format(sysTokens);
    reqVal.textContent = COUNT_FORMAT.format(requests);
    hitVal.textContent = formatPercent(hitFraction * 100, 0);
    priceVal.textContent = formatCurrency(pricePerM, 2);

    const { without, withCache, savings, cacheable } = savingsMonthly({
      sys: sysTokens,
      req: requests,
      hitFraction,
      price: pricePerM
    });

    withoutOut.textContent = money(without);
    withOut.textContent = money(withCache);
    savingsOut.textContent = money(savings);
    pctOut.textContent = savingsSummary({ without, savings, cacheable });

    // Bars scale from their left edge (transform, not width), so a slider drag
    // animates on the compositor and never relayouts. Cache writes cost more
    // than the base rate, so either bar can be the longer one.
    const longest = Math.max(without, withCache);
    skipFirstTransition(barWithout);
    skipFirstTransition(barWith);
    barWithout.style.transform = `scaleX(${without / longest})`;
    barWith.style.transform = `scaleX(${withCache / longest})`;

    const tokensPerMonth = sysTokens * requests * 30;
    tokensOut.textContent = formatCompact(tokensPerMonth);
    effOut.textContent = money(withCache / (tokensPerMonth / 1e6));

    syncPresets();
  }

  clear(presetsWrap);
  for (const preset of PRESETS) {
    const btn = /** @type {HTMLButtonElement} */ (makeEl("button", "", preset.name));
    btn.type = "button";
    btn.addEventListener("click", () => {
      sys.value = String(preset.sys);
      req.value = String(preset.req);
      hit.value = String(preset.hit);
      price.value = String(preset.price);
      update();
    });
    presetsWrap.appendChild(btn);
  }

  for (const input of [sys, req, hit, price]) {
    input.addEventListener("input", update);
  }
  update();
}
