import { escapeAttribute } from "../../../../js/modules/html-escape.js";

function metricTip(copy) {
  const escapedCopy = escapeAttribute(copy);
  return `<button type="button" class="info-tip" data-tip="${escapedCopy}" aria-label="${escapedCopy}">?</button>`;
}

/**
 * @typedef {{
 *   base: import('./amortization.js').ScheduleResult,
 *   extra: import('./amortization.js').ScheduleResult,
 *   savings: number,
 *   periodsSaved: number,
 *   totalPaid: number,
 *   costRatio: number,
 *   label: string
 * }} LoanMetrics
 */

/**
 * Build the metric card markup for the current amortization state.
 *
 * @param {LoanMetrics} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {string}
 */
export function buildMetricsMarkup(
  { base, extra, savings, periodsSaved, totalPaid, costRatio, label },
  formatCurrency
) {
  return `
    <div class="stat">
      ${metricTip(`Fixed payment amount each ${label.toLowerCase()}, excluding extra payments`)}
      <div class="stat-label">${label}ly EMI</div>
      <div class="stat-value">${formatCurrency(base.emi)}</div>
    </div>
    <div class="stat">
      ${metricTip("Interest without extras vs with extras applied")}
      <div class="stat-label">Total interest</div>
      <div class="stat-value">${formatCurrency(extra.totalInterest)}</div>
      ${
        savings > 1
          ? `<div class="stat-sub"><span class="chip is-green">Save ${formatCurrency(savings)}</span></div>`
          : ""
      }
      <div class="stat-sub">Without extras: ${formatCurrency(base.totalInterest)}</div>
    </div>
    <div class="stat">
      ${metricTip(`Number of ${label.toLowerCase()}s until the loan is fully paid off`)}
      <div class="stat-label">Payoff in</div>
      <div class="stat-value">${extra.periods} ${label.toLowerCase()}s</div>
      ${
        periodsSaved > 0
          ? `<div class="stat-sub"><span class="chip is-green">${periodsSaved} earlier</span></div>`
          : ""
      }
    </div>
    <div class="stat">
      ${metricTip("Principal plus total interest. The real cost of your loan.")}
      <div class="stat-label">Total paid</div>
      <div class="stat-value">${formatCurrency(totalPaid)}</div>
      <div class="stat-sub">Interest is ${((costRatio - 1) * 100).toFixed(1)}% of loan</div>
    </div>
    <div class="stat">
      ${metricTip(`The ${label.toLowerCase()} when cumulative principal paid from EMI and extras surpasses cumulative interest`)}
      <div class="stat-label">Break-even</div>
      <div class="stat-value">${extra.breakEven ? `${label} ${extra.breakEven}` : "N/A"}</div>
      <div class="stat-sub">Principal (EMI + extras) &gt; interest</div>
    </div>
  `;
}

/**
 * Render the metric card grid into the app shell.
 *
 * @param {HTMLElement} container
 * @param {LoanMetrics} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {void}
 */
export function renderMetrics(container, metrics, formatCurrency) {
  container.innerHTML = buildMetricsMarkup(metrics, formatCurrency);
}
