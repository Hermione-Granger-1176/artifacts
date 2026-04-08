import { escapeAttribute } from "./formatting.js";

export function createExtra(nextId) {
  return {
    id: nextId,
    type: "recurring",
    amount: 500,
    every: 1,
    startPeriod: 1,
    period: 1
  };
}

export function removeExtraById(extras, id) {
  return extras.filter((extra) => extra.id !== id);
}

export function setExtraType(extras, id, type) {
  const extra = extras.find((item) => item.id === id);
  if (extra) {
    extra.type = type;
  }
}

export function updateExtraField(extras, id, field, value) {
  const extra = extras.find((item) => item.id === id);
  if (extra) {
    extra[field] = +value;
  }
}

export function summarizeExtra(extra, periodLabel) {
  if (extra.type === "recurring") {
    return `Pays $${extra.amount.toLocaleString()} every ${
      extra.every === 1 ? periodLabel : `${extra.every} ${periodLabel}s`
    } starting from ${periodLabel} ${extra.startPeriod}`;
  }

  return `One-time payment of $${extra.amount.toLocaleString()} at ${periodLabel} ${extra.period}`;
}

export function renderExtras({ container, extras, periodLabel }) {
  container.innerHTML = "";

  for (const extra of extras) {
    const item = document.createElement("div");
    const summary = summarizeExtra(extra, periodLabel);
    item.className = "extra-item";
    item.dataset.extraId = String(extra.id);

    if (extra.type === "recurring") {
      item.innerHTML = `
        <button type="button" class="info-tip card-tip" data-tip="${escapeAttribute(summary)}" aria-label="${escapeAttribute(summary)}">?</button>
        <div class="type-toggle">
          <button type="button" class="active" data-action="set-type" data-type="recurring">Recurring</button>
          <button type="button" data-action="set-type" data-type="onetime">One-time</button>
        </div>
        <div class="amt-group">
          <span>$</span>
          <input class="amount-input" type="number" value="${extra.amount}" min="0" step="100" data-field="amount">
        </div>
        <div class="param-group">
          <span>every</span>
          <input class="period-input" type="number" value="${extra.every}" min="1" max="60" data-field="every">
          <span>${periodLabel}(s)</span>
        </div>
        <div class="param-group">
          <span>from</span>
          <input class="period-input" type="number" value="${extra.startPeriod}" min="1" max="2000" data-field="startPeriod">
        </div>
        <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">x</button>
      `;
    } else {
      item.innerHTML = `
        <button type="button" class="info-tip card-tip" data-tip="${escapeAttribute(summary)}" aria-label="${escapeAttribute(summary)}">?</button>
        <div class="type-toggle">
          <button type="button" data-action="set-type" data-type="recurring">Recurring</button>
          <button type="button" class="active" data-action="set-type" data-type="onetime">One-time</button>
        </div>
        <div class="amt-group">
          <span>$</span>
          <input class="amount-input" type="number" value="${extra.amount}" min="0" step="100" data-field="amount">
        </div>
        <div class="param-group">
          <span>at ${periodLabel}</span>
          <input class="period-input" type="number" value="${extra.period}" min="1" max="2000" data-field="period">
        </div>
        <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">x</button>
      `;
    }

    container.appendChild(item);
  }
}
