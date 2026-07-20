/* Savings calculator: preset workloads, sliders, and a live cost dashboard. */

import { savingsMonthly } from "./math.js";
import { byId, makeEl, clear } from "./dom.js";
import { formatCompact, formatCurrency, formatPercent } from "../../../../js/modules/formatting.js";

const PRESETS = [
  { name: "Hobby", sys: 1000, req: 100, hit: 70, price: 3 },
  { name: "Startup", sys: 2000, req: 500, hit: 80, price: 3 },
  { name: "Scale", sys: 8000, req: 5000, hit: 90, price: 3 }
];

// Whole dollars once past $1,000 (grouped thousands), cents below that.
/** @param {number} value - Dollar amount. @returns {string} Formatted currency. */
function money(value) {
  return value >= 1000 ? formatCurrency(value, 0) : formatCurrency(value, 2);
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

    sysVal.textContent = sysTokens.toLocaleString();
    reqVal.textContent = requests.toLocaleString();
    hitVal.textContent = formatPercent(hitFraction * 100, 0);
    priceVal.textContent = formatCurrency(pricePerM, 2);

    const { without, withCache, savings } = savingsMonthly({
      sys: sysTokens,
      req: requests,
      hitFraction,
      price: pricePerM
    });

    withoutOut.textContent = money(without);
    withOut.textContent = money(withCache);
    savingsOut.textContent = money(savings);

    pctOut.textContent = `${formatPercent((savings / without) * 100, 0)} cheaper, ${money(savings * 12)} per year`;
    barWithout.style.width = "100%";
    barWith.style.width = `${(withCache / without) * 100}%`;

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
