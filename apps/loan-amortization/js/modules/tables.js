/** @param {HTMLElement} container @param {object} values - Summary totals to display. */
export function renderTableSummary(container, values) {
  const items = [
    ["Total EMI", values.totalEmi],
    ["Principal (EMI)", values.totalPrincipal],
    ["Total interest", values.totalInterest],
    ["Total extras", values.totalExtras],
    ["Periods", values.periods]
  ];

  container.innerHTML = items
    .map(
      ([label, value]) => `
        <div class="summary-stat">
          <div class="summary-label">${label}</div>
          <strong>${value}</strong>
        </div>
      `
    )
    .join("");
}

/** @param {HTMLElement} tbody @param {Array} rows @param {Function} formatCurrency */
export function renderPeriodTable(tbody, rows, formatCurrency) {
  tbody.innerHTML = "";

  for (const row of rows) {
    const tr = document.createElement("tr");
    if (row.extra > 0) {
      tr.className = "extra-highlight";
    }
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

/** @param {HTMLElement} tbody @param {Array} rows @param {number} principal @param {number} periodsPerYear @param {Function} formatCurrency */
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

    for (let index = start; index < end; index += 1) {
      const row = rows[index];
      yearlyPrincipal += row.principal;
      yearlyInterest += row.interest;
      yearlyExtra += row.extra;
      closingBalance = row.balance;
    }

    const tr = document.createElement("tr");
    tr.className = "year-row";
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
