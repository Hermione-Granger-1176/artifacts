import { escapeHtml } from "../../../../js/modules/html-escape.js";

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

const ALLOWED_EXTRA_FIELDS = new Set(["amount", "every", "startPeriod", "period"]);

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
  if (!ALLOWED_EXTRA_FIELDS.has(field)) {
    return;
  }

  const parsed = +value;
  if (Number.isNaN(parsed) || parsed < 0) {
    return;
  }
  if (["every", "startPeriod", "period"].includes(field) && parsed < 1) {
    return;
  }

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

const ICON_ATTRS =
  'class="loan-icon" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"';
const RECURRING_ICON = `<svg ${ICON_ATTRS}><path d="M13 7.5A5 5 0 0 0 4.2 4.9"/><path d="M3.5 2.75v2.5h2.5"/><path d="M3 8.5a5 5 0 0 0 8.8 2.6"/><path d="M12.5 13.25v-2.5H10"/></svg>`;
const ONETIME_ICON = `<svg ${ICON_ATTRS}><circle cx="8" cy="8" r="2.25"/></svg>`;

/**
 * Build one labelled numeric field for an extra-payment row.
 *
 * @param {{ label: string, name: string, className: string, field: string, value: number, min: number, max?: number, step?: number }} options
 * @returns {string}
 */
function extraField({ label, name, className, field, value, min, max, step }) {
  const maxAttr = max === undefined ? "" : ` max="${max}"`;
  const stepAttr = step === undefined ? "" : ` step="${step}"`;
  return `
        <label class="extra-field">
          <span>${label}</span>
          <input class="${className}" type="number" aria-label="${name}" value="${value}" min="${min}"${maxAttr}${stepAttr} data-field="${field}">
        </label>`;
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
    const isRecurring = extra.type === "recurring";
    item.className = "extra-item";
    item.dataset.extraId = String(extra.id);

    const amountField = extraField({
      label: "Amount ($)",
      name: "Extra payment amount",
      className: "amount-input",
      field: "amount",
      value: extra.amount,
      min: 0,
      step: 100
    });
    const timingFields = isRecurring
      ? extraField({
          label: "Every",
          name: `Extra payment repeats every (${periodLabel}s)`,
          className: "period-input",
          field: "every",
          value: extra.every,
          min: 1,
          max: 60
        }) +
        extraField({
          label: "From",
          name: `Extra payment starts from ${periodLabel}`,
          className: "period-input",
          field: "startPeriod",
          value: extra.startPeriod,
          min: 1,
          max: 2000
        })
      : extraField({
          label: "At",
          name: `One-time extra payment at ${periodLabel}`,
          className: "period-input",
          field: "period",
          value: extra.period,
          min: 1,
          max: 2000
        });

    // eslint-disable-next-line no-restricted-syntax -- numbers and cadence labels are controlled; the free-text summary is escaped via escapeHtml
    item.innerHTML = `
        <div class="extra-head">
          <div class="segmented is-fused is-inset">
            <button type="button"${isRecurring ? ' class="active"' : ""} data-action="set-type" data-type="recurring" aria-pressed="${isRecurring}">${RECURRING_ICON}Recurring</button>
            <button type="button"${isRecurring ? "" : ' class="active"'} data-action="set-type" data-type="onetime" aria-pressed="${!isRecurring}">${ONETIME_ICON}One-time</button>
          </div>
          <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">\u00d7</button>
        </div>
        <div class="extra-fields ${isRecurring ? "is-recurring" : "is-onetime"}">${amountField}${timingFields}
        </div>
        <div class="extra-summary">${escapeHtml(summarizeExtra(extra, periodLabel))}</div>
      `;

    container.appendChild(item);
  }
}
