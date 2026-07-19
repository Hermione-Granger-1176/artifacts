/**
 * @typedef {{
 *   totalEmi: string,
 *   totalPrincipal: string,
 *   totalInterest: string,
 *   totalExtras: string,
 *   periods: string
 * }} TableSummary
 */

/**
 * Render the aggregate summary cards above the amortization tables.
 *
 * @param {HTMLElement} container
 * @param {TableSummary} values - Summary totals to display.
 * @returns {void}
 */
export function renderTableSummary(container, values) {
  /** @type {Array<[string, string]>} */
  const items = [
    ["Total EMI", values.totalEmi],
    ["Principal (EMI)", values.totalPrincipal],
    ["Total interest", values.totalInterest],
    ["Total extras", values.totalExtras],
    ["Periods", values.periods]
  ];

  container.innerHTML = "";
  for (const [label, value] of items) {
    const stat = document.createElement("div");
    stat.className = "stat";
    const labelEl = document.createElement("div");
    labelEl.className = "stat-label";
    labelEl.textContent = label;
    const valueEl = document.createElement("div");
    valueEl.className = "stat-value";
    valueEl.textContent = value;
    stat.append(labelEl, valueEl);
    container.appendChild(stat);
  }
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
  tbody.innerHTML = "";

  for (const row of rows) {
    const tr = document.createElement("tr");
    if (row.extra > 0) {
      tr.className = "extra-highlight";
    }
    // eslint-disable-next-line no-restricted-syntax -- interpolated values are controlled numbers via formatCurrency
    tr.innerHTML = `
      <td>${row.period}</td>
      <td>${formatCurrency(row.emi)}</td>
      <td>${formatCurrency(row.principal)}</td>
      <td>${formatCurrency(row.interest)}</td>
      <td>${row.extra > 0 ? formatCurrency(row.extra) : "-"}</td>
      <td>${formatCurrency(row.balance)}</td>
    `;
    tbody.appendChild(tr);
  }
}

/**
 * Render yearly rollups derived from the full amortization row set.
 *
 * @param {HTMLElement} tbody
 * @param {Array<{ balance: number, extra: number, interest: number, principal: number }>} rows
 * @param {number} principal
 * @param {number} periodsPerYear
 * @param {(value: number) => string} formatCurrency
 * @returns {void}
 */
export function renderYearlyTable(
  tbody,
  rows,
  principal,
  periodsPerYear,
  formatCurrency
) {
  tbody.innerHTML = "";
  const totalYears = Math.ceil(rows.length / periodsPerYear);

  for (let year = 1; year <= totalYears; year += 1) {
    const start = (year - 1) * periodsPerYear;
    const end = Math.min(year * periodsPerYear, rows.length);
    let yearlyPrincipal = 0;
    let yearlyInterest = 0;
    let yearlyExtra = 0;
    let openingBalance = start === 0 ? principal : rows[start - 1].balance;
    let closingBalance = openingBalance;

    for (const row of rows.slice(start, end)) {
      yearlyPrincipal += row.principal;
      yearlyInterest += row.interest;
      yearlyExtra += row.extra;
      closingBalance = row.balance;
    }

    const tr = document.createElement("tr");
    tr.className = "year-row";
    // eslint-disable-next-line no-restricted-syntax -- interpolated values are controlled numbers via formatCurrency
    tr.innerHTML = `
      <td>Year ${year}</td>
      <td>${formatCurrency(openingBalance)}</td>
      <td>${formatCurrency(yearlyPrincipal)}</td>
      <td>${formatCurrency(yearlyInterest)}</td>
      <td>${yearlyExtra > 0 ? formatCurrency(yearlyExtra) : "-"}</td>
      <td>${formatCurrency(closingBalance)}</td>
    `;
    tbody.appendChild(tr);
  }
}
