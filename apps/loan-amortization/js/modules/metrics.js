import { escapeAttribute } from "../../../../js/modules/html-escape.js";

/**
 * @param {string} copy - Tooltip copy.
 * @param {string} [modifier] - Extra class for the tip (`is-start` anchors the tooltip to its left edge).
 * @returns {string} Info-tip button HTML.
 */
function metricTip(copy, modifier = "") {
  const escapedCopy = escapeAttribute(copy);
  const className = modifier ? `info-tip ${modifier}` : "info-tip";
  return `<button type="button" class="${className}" data-tip="${escapedCopy}" aria-label="${escapedCopy}">?</button>`;
}

/**
 * @typedef {{
 *   base: import('./amortization.js').ScheduleResult,
 *   extra: import('./amortization.js').ScheduleResult,
 *   savings: number,
 *   periodsSaved: number,
 *   totalPaid: number,
 *   costRatio: number,
 *   label: string,
 *   periodsPerYear: number
 * }} LoanMetrics
 */

/**
 * Express a number of repayment periods as a short "Ny Mm" duration.
 *
 * @param {number} periods
 * @param {number} periodsPerYear
 * @returns {string}
 */
export function formatPeriodsAsDuration(periods, periodsPerYear) {
  const totalMonths = Math.round((periods * 12) / periodsPerYear);
  if (totalMonths < 1) {
    return "under 1m";
  }

  const years = Math.floor(totalMonths / 12);
  const months = totalMonths % 12;
  return [years > 0 ? `${years}y` : "", months > 0 ? `${months}m` : ""].filter(Boolean).join(" ");
}

/**
 * Build the "saves $X · Ny Mm sooner" chip shown beside the hero EMI.
 *
 * @param {Pick<LoanMetrics, "savings" | "periodsSaved" | "periodsPerYear">} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {string}
 */
function buildSavingsChip({ savings, periodsSaved, periodsPerYear }, formatCurrency) {
  const parts = [];
  if (savings > 1) {
    parts.push(`Saves ${formatCurrency(savings)}`);
  }
  if (periodsSaved > 0) {
    parts.push(`${formatPeriodsAsDuration(periodsSaved, periodsPerYear)} sooner`);
  }

  return parts.length > 0 ? `<span class="chip is-green">${parts.join(" \u00b7 ")}</span>` : "";
}

/**
 * Build the hero EMI and KPI markup for the current amortization state.
 *
 * @param {LoanMetrics} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {string}
 */
export function buildMetricsMarkup(
  { base, extra, savings, periodsSaved, totalPaid, costRatio, label, periodsPerYear },
  formatCurrency
) {
  const heroSub =
    extra.totalExtra > 0
      ? `Plus ${formatCurrency(extra.totalExtra)} in extra payments over the loan`
      : "Fixed payment, no extras";

  return `
    <div class="loan-hero">
      <div class="loan-hero-main">
        <div class="loan-hero-label">
          <span>${label}ly EMI</span>
          ${metricTip(`Fixed payment amount each ${label.toLowerCase()}, excluding extra payments`, "is-start")}
        </div>
        <div class="loan-hero-value">${formatCurrency(base.emi)}</div>
        <div class="loan-hero-sub">${heroSub}</div>
      </div>
      ${buildSavingsChip({ savings, periodsSaved, periodsPerYear }, formatCurrency)}
    </div>
    <div class="stat-grid loan-kpis">
      <div class="stat">
        ${metricTip("Interest without extras vs with extras applied")}
        <div class="stat-label">Total interest</div>
        <div class="stat-value">${formatCurrency(extra.totalInterest)}</div>
        <div class="stat-sub">Without extras: ${formatCurrency(base.totalInterest)}</div>
      </div>
      <div class="stat">
        ${metricTip(`Number of ${label.toLowerCase()}s until the loan is fully paid off`)}
        <div class="stat-label">Payoff in</div>
        <div class="stat-value">${extra.periods} ${label.toLowerCase()}s</div>
        <div class="stat-sub">${periodsSaved > 0 ? `${periodsSaved} earlier than without extras` : "Until the loan is repaid"}</div>
      </div>
      <div class="stat">
        ${metricTip("Principal plus total interest. The real cost of your loan.")}
        <div class="stat-label">Total paid</div>
        <div class="stat-value">${formatCurrency(totalPaid)}</div>
        <div class="stat-sub">Interest is ${((costRatio - 1) * 100).toFixed(1)}% of loan</div>
      </div>
      <div class="stat">
        ${metricTip(`The first ${label.toLowerCase()} when cumulative principal paid from EMI and extras meets or exceeds cumulative interest`)}
        <div class="stat-label">Break-even</div>
        <div class="stat-value">${extra.breakEven ? `${label} ${extra.breakEven}` : "N/A"}</div>
        <div class="stat-sub">Principal (EMI + extras) &gt;= interest</div>
      </div>
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
