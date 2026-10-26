import { createElement, setText } from "../../../../js/modules/dom-sync.js";
import { summarizeScheduleRows } from "./schedule-summary.js";

/**
 * @typedef {{
 *   totalEmi: string,
 *   totalPrincipal: string,
 *   totalInterest: string,
 *   totalExtras: string,
 *   periods: string
 * }} TableSummary
 */

/** Summary tiles in display order: value key and tile label. */
const SUMMARY_TILES = /** @type {const} */ ([
  ["totalEmi", "Total EMI"],
  ["totalPrincipal", "Principal (EMI)"],
  ["totalInterest", "Total interest"],
  ["totalExtras", "Total extras"],
  ["periods", "Periods"]
]);

/** @type {WeakMap<HTMLElement, Record<string, HTMLElement>>} */
const summaryValues = new WeakMap();

/**
 * Create the summary tiles once and return their value nodes by key.
 *
 * @param {HTMLElement} container
 * @returns {Record<string, HTMLElement>}
 */
function getSummaryValues(container) {
  const existing = summaryValues.get(container);
  if (existing) {
    return existing;
  }

  /** @type {Record<string, HTMLElement>} */
  const values = {};
  const tiles = SUMMARY_TILES.map(([key, label]) => {
    const valueEl = createElement("div", { className: "stat-value", text: "-" });
    values[key] = valueEl;
    return createElement("div", { className: "stat" }, [
      createElement("div", { className: "stat-label", text: label }),
      valueEl
    ]);
  });
  container.replaceChildren(...tiles);
  summaryValues.set(container, values);
  return values;
}

/**
 * Render the aggregate summary cards above the amortization tables. The tiles
 * are created on the first call and only their text changes afterwards.
 *
 * @param {HTMLElement} container
 * @param {TableSummary} values - Summary totals to display.
 * @returns {void}
 */
export function renderTableSummary(container, values) {
  const valueNodes = getSummaryValues(container);
  for (const [key] of SUMMARY_TILES) {
    setText(valueNodes[key], values[key]);
  }
}

/**
 * Make a body hold exactly `items.length` rows, reusing the rows it has and
 * adding or dropping only the difference, then fill each row from its item.
 *
 * @template T
 * @param {HTMLElement} tbody
 * @param {T[]} items
 * @param {number} cellCount - Cells per row.
 * @param {(row: HTMLElement, item: T, index: number) => void} fill
 * @returns {void}
 */
function syncRows(tbody, items, cellCount, fill) {
  const rows = tbody.children;
  while (rows.length > items.length) {
    rows[rows.length - 1].remove();
  }

  const reused = rows.length;
  const added = document.createDocumentFragment();
  items.forEach((item, index) => {
    let row = /** @type {HTMLElement | undefined} */ (rows[index]);
    if (index >= reused) {
      row = document.createElement("tr");
      row.append(...Array.from({ length: cellCount }, () => document.createElement("td")));
      added.append(row);
    }
    fill(/** @type {HTMLElement} */ (row), item, index);
  });
  tbody.append(added);
}

/**
 * Write a row's class and cell texts, touching only what changed.
 *
 * @param {HTMLElement} row
 * @param {string} className
 * @param {string[]} texts - One text per cell.
 * @returns {void}
 */
function fillRow(row, className, texts) {
  if (row.className !== className) {
    row.className = className;
  }
  texts.forEach((text, index) => {
    setText(row.children[index], text);
  });
}

/**
 * Render the per-period amortization rows.
 *
 * @param {HTMLElement} tbody
 * @param {import('./amortization.js').ScheduleRow[]} rows
 * @param {(value: number) => string} formatCurrency
 * @returns {void}
 */
export function renderPeriodTable(tbody, rows, formatCurrency) {
  syncRows(tbody, rows, 6, (tr, row) => {
    fillRow(tr, row.extra > 0 ? "extra-highlight" : "", [
      String(row.period),
      formatCurrency(row.emi),
      formatCurrency(row.principal),
      formatCurrency(row.interest),
      row.extra > 0 ? formatCurrency(row.extra) : "-",
      formatCurrency(row.balance)
    ]);
  });
}

/**
 * Render yearly rollups derived from the full amortization row set.
 *
 * @param {HTMLElement} tbody
 * @param {import('./amortization.js').ScheduleRow[]} rows
 * @param {number} principal
 * @param {number} periodsPerYear
 * @param {(value: number) => string} formatCurrency
 * @returns {void}
 */
export function renderYearlyTable(tbody, rows, principal, periodsPerYear, formatCurrency) {
  const totalYears = Math.ceil(rows.length / periodsPerYear);

  syncRows(tbody, Array.from({ length: totalYears }, (_, index) => index + 1), 6, (tr, year) => {
    const start = (year - 1) * periodsPerYear;
    const yearRows = rows.slice(start, year * periodsPerYear);
    const openingBalance = start === 0 ? principal : rows[start - 1].balance;
    const closingBalance = yearRows[yearRows.length - 1].balance;
    const {
      totalPrincipal: yearlyPrincipal,
      totalInterest: yearlyInterest,
      totalExtras: yearlyExtra
    } = summarizeScheduleRows(yearRows);

    fillRow(tr, "year-row", [
      `Year ${year}`,
      formatCurrency(openingBalance),
      formatCurrency(yearlyPrincipal),
      formatCurrency(yearlyInterest),
      yearlyExtra > 0 ? formatCurrency(yearlyExtra) : "-",
      formatCurrency(closingBalance)
    ]);
  });
}
