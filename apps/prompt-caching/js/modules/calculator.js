/* Savings calculator: maps the slider workload onto monthly spend. */

import { savingsMonthly } from "./math.js";
import { byId } from "./dom.js";

export function initCalculator() {
  const sys = byId("calcSys");
  const req = byId("calcReq");
  const hit = byId("calcHit");
  const price = byId("calcPrice");
  if (!sys || !req || !hit || !price) {
    return;
  }

  const sysVal = byId("calcSysVal");
  const reqVal = byId("calcReqVal");
  const hitVal = byId("calcHitVal");
  const priceVal = byId("calcPriceVal");
  const withoutOut = byId("calcWithout");
  const withOut = byId("calcWith");
  const savingsOut = byId("calcSavings");

  function update() {
    const sysTokens = Number.parseFloat(sys.value);
    const requests = Number.parseFloat(req.value);
    const hitFraction = Number.parseFloat(hit.value) / 100;
    const pricePerM = Number.parseFloat(price.value);

    sysVal.textContent = sysTokens.toLocaleString();
    reqVal.textContent = requests.toLocaleString();
    hitVal.textContent = `${Math.round(hitFraction * 100)}%`;
    priceVal.textContent = `$${pricePerM.toFixed(2)}`;

    const { without, withCache, savings } = savingsMonthly({
      sys: sysTokens,
      req: requests,
      hitFraction,
      price: pricePerM
    });

    withoutOut.textContent = `$${without.toFixed(2)}`;
    withOut.textContent = `$${withCache.toFixed(2)}`;
    savingsOut.textContent = `$${savings.toFixed(2)}/mo`;
  }

  for (const input of [sys, req, hit, price]) {
    input.addEventListener("input", update);
  }
  update();
}
