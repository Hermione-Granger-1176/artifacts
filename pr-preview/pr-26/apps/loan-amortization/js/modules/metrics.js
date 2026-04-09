import { escapeAttribute } from "./formatting.js";

function metricTip(copy) {
  const escapedCopy = escapeAttribute(copy);
  return `<button type="button" class="info-tip metric-tip" data-tip="${escapedCopy}" aria-label="${escapedCopy}">?</button>`;
}

/**
 * Build the metric card markup for the current amortization state.
 *
 * @param {object} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {string}
 */
export function buildMetricsMarkup(
  { base, extra, savings, periodsSaved, totalPaid, costRatio, label },
  formatCurrency
) {
  return `
    <div class="metric">
      ${metricTip(`Fixed payment amount each ${label.toLowerCase()}, excluding extra payments`)}
      <div class="metric-label">${label}ly EMI</div>
      <div class="metric-value">${formatCurrency(base.emi)}</div>
    </div>
    <div class="metric">
      ${metricTip("Interest without extras vs with extras applied")}
      <div class="metric-label">Total interest</div>
      <div class="metric-value">${formatCurrency(extra.totalInterest)}</div>
      ${
        savings > 1
          ? `<div class="metric-sub"><span class="savings-pill">Save ${formatCurrency(savings)}</span></div>`
          : ""
      }
      <div class="metric-sub is-muted">Without extras: ${formatCurrency(base.totalInterest)}</div>
    </div>
    <div class="metric">
      ${metricTip(`Number of ${label.toLowerCase()}s until the loan is fully paid off`)}
      <div class="metric-label">Payoff in</div>
      <div class="metric-value">${extra.periods} ${label.toLowerCase()}s</div>
      ${
        periodsSaved > 0
          ? `<div class="metric-sub"><span class="savings-pill">${periodsSaved} earlier</span></div>`
          : ""
      }
    </div>
    <div class="metric">
      ${metricTip("Principal plus total interest. The real cost of your loan.")}
      <div class="metric-label">Total paid</div>
      <div class="metric-value">${formatCurrency(totalPaid)}</div>
      <div class="metric-sub">Interest is ${((costRatio - 1) * 100).toFixed(1)}% of loan</div>
    </div>
    <div class="metric">
      ${metricTip(`The ${label.toLowerCase()} when cumulative principal paid from EMI and extras surpasses cumulative interest`)}
      <div class="metric-label">Break-even</div>
      <div class="metric-value">${extra.breakEven ? `${label} ${extra.breakEven}` : "N/A"}</div>
      <div class="metric-sub">Principal (EMI + extras) &gt; interest</div>
    </div>
  `;
}

/**
 * Render the metric card grid into the app shell.
 *
 * @param {HTMLElement} container
 * @param {object} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {void}
 */
export function renderMetrics(container, metrics, formatCurrency) {
  container.innerHTML = buildMetricsMarkup(metrics, formatCurrency);
}
