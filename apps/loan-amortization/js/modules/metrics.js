import { setAttr, setText } from "../../../../js/modules/dom-sync.js";

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
 * Build the "saves $X, Ny Mm sooner" chip text shown beside the hero EMI.
 *
 * @param {Pick<LoanMetrics, "savings" | "periodsSaved" | "periodsPerYear">} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {string} Chip text, or an empty string when nothing is saved.
 */
function buildSavingsChip({ savings, periodsSaved, periodsPerYear }, formatCurrency) {
  const parts = [];
  if (savings > 1) {
    parts.push(`Saves ${formatCurrency(savings)}`);
  }
  if (periodsSaved > 0) {
    parts.push(`${formatPeriodsAsDuration(periodsSaved, periodsPerYear)} sooner`);
  }

  return parts.join(" \u00b7 ");
}

/**
 * Text for every value slot in the metrics block, keyed by its `data-metric` name.
 * Tip slots hold tooltip copy; the rest hold visible text.
 *
 * @typedef {{
 *   heroLabel: string,
 *   heroTip: string,
 *   heroValue: string,
 *   heroSub: string,
 *   chip: string,
 *   interestValue: string,
 *   interestSub: string,
 *   payoffTip: string,
 *   payoffValue: string,
 *   payoffSub: string,
 *   paidValue: string,
 *   paidSub: string,
 *   breakTip: string,
 *   breakValue: string
 * }} MetricsView
 */

/**
 * Derive the hero EMI and KPI text for the current amortization state.
 *
 * @param {LoanMetrics} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {MetricsView}
 */
export function buildMetricsView(
  { base, extra, savings, periodsSaved, totalPaid, costRatio, label, periodsPerYear },
  formatCurrency
) {
  const period = label.toLowerCase();

  return {
    heroLabel: `${label}ly EMI`,
    heroTip: `Fixed payment amount each ${period}, excluding extra payments`,
    heroValue: formatCurrency(base.emi),
    heroSub:
      extra.totalExtra > 0
        ? `Plus ${formatCurrency(extra.totalExtra)} in extra payments over the loan`
        : "Fixed payment, no extras",
    chip: buildSavingsChip({ savings, periodsSaved, periodsPerYear }, formatCurrency),
    interestValue: formatCurrency(extra.totalInterest),
    interestSub: `Without extras: ${formatCurrency(base.totalInterest)}`,
    payoffTip: `Number of ${period}s until the loan is fully paid off`,
    payoffValue: `${extra.periods} ${period}s`,
    payoffSub:
      periodsSaved > 0 ? `${periodsSaved} earlier than without extras` : "Until the loan is repaid",
    paidValue: formatCurrency(totalPaid),
    paidSub: `Interest is ${((costRatio - 1) * 100).toFixed(1)}% of loan`,
    breakTip: `The first ${period} when cumulative principal paid from EMI and extras meets or exceeds cumulative interest`,
    breakValue: extra.breakEven ? `${label} ${extra.breakEven}` : "N/A"
  };
}

/** Slots whose value is tooltip copy: written to `data-tip` and `aria-label`. */
const TIP_SLOTS = new Set(["heroTip", "payoffTip", "breakTip"]);

/** @type {WeakMap<HTMLElement, Map<string, HTMLElement>>} */
const slotCache = new WeakMap();

/**
 * Find the `data-metric` slots inside the metrics block once per container.
 *
 * @param {HTMLElement} container
 * @returns {Map<string, HTMLElement>}
 */
function getSlots(container) {
  let slots = slotCache.get(container);
  if (!slots) {
    slots = new Map();
    for (const node of /** @type {HTMLElement[]} */ ([...container.querySelectorAll("[data-metric]")])) {
      slots.set(node.dataset.metric ?? "", node);
    }
    slotCache.set(container, slots);
  }
  return slots;
}

/**
 * Write the metrics into the slots that ship in the page markup. Nodes are
 * updated in place, so the tiles keep their size and an info tip keeps focus
 * while values change. The savings chip keeps its slot and fades instead of
 * leaving the layout.
 *
 * @param {HTMLElement} container - The `#metrics` block holding `data-metric` slots.
 * @param {LoanMetrics} metrics
 * @param {(value: number) => string} formatCurrency
 * @returns {void}
 */
export function renderMetrics(container, metrics, formatCurrency) {
  const slots = getSlots(container);
  const view = buildMetricsView(metrics, formatCurrency);

  for (const [name, text] of Object.entries(view)) {
    const slot = slots.get(name);
    if (!slot) {
      continue;
    }

    if (TIP_SLOTS.has(name)) {
      setAttr(slot, "data-tip", text);
      setAttr(slot, "aria-label", text);
    } else if (name === "chip") {
      renderChip(slot, text);
    } else {
      setText(slot, text);
    }
  }
}

/**
 * Show or hide the savings chip without changing its box. The last text stays
 * while hidden, so the chip keeps its width as it fades.
 *
 * @param {HTMLElement} chip
 * @param {string} text - Chip text, or an empty string to hide the chip.
 * @returns {void}
 */
function renderChip(chip, text) {
  if (text) {
    setText(chip, text);
  }
  chip.classList.toggle("is-empty", !text);
  setAttr(chip, "aria-hidden", text ? "false" : "true");
}
