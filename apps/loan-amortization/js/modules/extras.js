import { escapeAttribute } from "./formatting.js";

/**
 * Create one extra-payment model with the default recurring values.
 *
 * @param {number} nextId
 * @returns {{ amount: number, every: number, id: number, period: number, startPeriod: number, type: string }}
 */
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

/**
 * Remove one extra-payment row by id.
 *
 * @param {Array<{ id: number }>} extras
 * @param {number} id
 * @returns {Array<{ id: number }>}
 */
export function removeExtraById(extras, id) {
  return extras.filter((extra) => extra.id !== id);
}

/**
 * Update the type of one extra payment in place when it exists.
 *
 * @param {Array<{ id: number, type: string }>} extras
 * @param {number} id
 * @param {string} type
 * @returns {void}
 */
export function setExtraType(extras, id, type) {
  const extra = extras.find((item) => item.id === id);
  if (extra) {
    extra.type = type;
  }
}

const ALLOWED_EXTRA_FIELDS = new Set(['amount', 'every', 'startPeriod', 'period']);

/**
 * Update one editable numeric field for an extra payment when the input is valid.
 *
 * @param {Array<Record<string, number | string>>} extras
 * @param {number} id
 * @param {string} field
 * @param {string} value
 * @returns {void}
 */
export function updateExtraField(extras, id, field, value) {
  if (!ALLOWED_EXTRA_FIELDS.has(field)) return;
  const parsed = +value;
  if (Number.isNaN(parsed) || parsed < 0) return;
  if ((field === 'every' || field === 'startPeriod' || field === 'period') && parsed < 1) return;
  const extra = extras.find((item) => item.id === id);
  if (extra) {
    extra[field] = parsed;
  }
}

/**
 * Summarize one extra payment in the tooltip voice used by the app.
 *
 * @param {{ amount: number, every: number, period: number, startPeriod: number, type: string }} extra
 * @param {string} periodLabel
 * @returns {string}
 */
export function summarizeExtra(extra, periodLabel) {
  if (extra.type === "recurring") {
    return `Pays $${extra.amount.toLocaleString()} every ${
      extra.every === 1 ? periodLabel : `${extra.every} ${periodLabel}s`
    } starting from ${periodLabel} ${extra.startPeriod}`;
  }

  return `One-time payment of $${extra.amount.toLocaleString()} at ${periodLabel} ${extra.period}`;
}

/**
 * Render the editable extra-payment rows for the current repayment cadence.
 *
 * @param {{
 *   container: HTMLElement,
 *   extras: Array<{ amount: number, every: number, id: number, period: number, startPeriod: number, type: string }>,
 *   periodLabel: string
 * }} options
 * @returns {void}
 */
export function renderExtras({ container, extras, periodLabel }) {
  container.innerHTML = "";

  for (const extra of extras) {
    const item = document.createElement("div");
    const summary = summarizeExtra(extra, periodLabel);
    item.className = "extra-item";
    item.dataset.extraId = String(extra.id);

    if (extra.type === "recurring") {
      // eslint-disable-next-line no-restricted-syntax -- numbers are controlled; the free-text summary is escaped via escapeAttribute
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
      // eslint-disable-next-line no-restricted-syntax -- numbers are controlled; the free-text summary is escaped via escapeAttribute
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
