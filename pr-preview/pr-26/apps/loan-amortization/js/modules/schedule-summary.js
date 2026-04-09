import { calcEMI } from "./amortization.js";

const FREQUENCY_PARAMS = {
  yearly: { periodsPerYear: 1, label: "Year" },
  halfyearly: { periodsPerYear: 2, label: "Half-year" },
  quarterly: { periodsPerYear: 4, label: "Quarter" },
  monthly: { periodsPerYear: 12, label: "Month" },
  biweekly: { periodsPerYear: 26, label: "Bi-week" },
  weekly: { periodsPerYear: 52, label: "Week" }
};

/**
 * Resolve the cadence metadata for the selected repayment frequency.
 *
 * @param {string} frequency
 * @returns {{ periodsPerYear: number, label: string }}
 */
export function getFrequencyParams(frequency) {
  return FREQUENCY_PARAMS[frequency];
}

/**
 * Derive the accelerated bi-weekly EMI override when selected.
 *
 * @param {object} options
 * @param {number} options.principal
 * @param {number} options.annualRate
 * @param {number} options.years
 * @param {string} options.frequency
 * @param {string} options.bwMode
 * @returns {number | null}
 */
export function getBiweeklyEmiOverride({ principal, annualRate, years, frequency, bwMode }) {
  if (frequency !== "biweekly" || bwMode !== "accelerated") {
    return null;
  }

  const monthlyRate = annualRate / 100 / 12;
  const monthlyPeriods = years * 12;
  return calcEMI(principal, monthlyRate, monthlyPeriods) / 2;
}

/**
 * Aggregate table totals from a computed amortization schedule.
 *
 * @param {Array<{emi: number, principal: number, interest: number, extra: number}>} rows
 * @returns {{ totalEmi: number, totalPrincipal: number, totalInterest: number, totalExtras: number }}
 */
export function summarizeScheduleRows(rows) {
  return rows.reduce(
    (totals, row) => ({
      totalEmi: totals.totalEmi + row.emi,
      totalPrincipal: totals.totalPrincipal + row.principal,
      totalInterest: totals.totalInterest + row.interest,
      totalExtras: totals.totalExtras + row.extra
    }),
    {
      totalEmi: 0,
      totalPrincipal: 0,
      totalInterest: 0,
      totalExtras: 0
    }
  );
}
