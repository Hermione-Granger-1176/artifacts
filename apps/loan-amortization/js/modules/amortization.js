/**
 * @typedef {{
 *   type: string,
 *   amount: number,
 *   period?: number,
 *   startPeriod?: number,
 *   every?: number
 * }} ExtraPayment
 * @typedef {{
 *   period: number,
 *   emi: number,
 *   principal: number,
 *   interest: number,
 *   extra: number,
 *   balance: number
 * }} ScheduleRow
 * @typedef {{
 *   emi: number,
 *   periods: number,
 *   totalInterest: number,
 *   totalExtra: number,
 *   balances: number[],
 *   principalParts: number[],
 *   interestParts: number[],
 *   extraParts: number[],
 *   cumulativePrincipal: number[],
 *   cumulativeInterest: number[],
 *   cumulativeExtra: number[],
 *   rows: ScheduleRow[],
 *   breakEven: number | null
 * }} ScheduleResult
 */

/**
 * Calculate the equated monthly installment (EMI).
 * @param {number} principal - Loan principal amount.
 * @param {number} ratePerPeriod - Interest rate per period (decimal).
 * @param {number} totalPeriods - Total number of repayment periods.
 * @returns {number} EMI amount.
 */
export function calcEMI(principal, ratePerPeriod, totalPeriods) {
  if (ratePerPeriod === 0) {
    return principal / totalPeriods;
  }

  return (
    (principal * ratePerPeriod * Math.pow(1 + ratePerPeriod, totalPeriods)) /
    (Math.pow(1 + ratePerPeriod, totalPeriods) - 1)
  );
}

/**
 * Sum extra payments applicable to a given period.
 * @param {number} period - Current repayment period.
 * @param {ExtraPayment[]} extras - Extra payment definitions.
 * @returns {number} Total extra payment for the period.
 */
export function getExtraForPeriod(period, extras) {
  let total = 0;

  for (const extra of extras) {
    switch (extra.type) {
      case "onetime":
        if (extra.period === period) {
          total += extra.amount;
        }
        break;
      case "recurring":
        if (
          extra.startPeriod !== undefined &&
          extra.every !== undefined &&
          period >= extra.startPeriod &&
          (period - extra.startPeriod) % extra.every === 0
        ) {
          total += extra.amount;
        }
        break;
      default:
        break;
    }
  }

  return total;
}

/**
 * Run a full amortization schedule and return period-by-period breakdown.
 * @param {number} principal - Loan principal amount.
 * @param {number} ratePerPeriod - Interest rate per period (decimal).
 * @param {number} totalPeriods - Total number of repayment periods.
 * @param {object} [options]
 * @param {boolean} [options.withExtras=false] - Whether to apply extra payments.
 * @param {number|null} [options.emiOverride=null] - Override the calculated EMI.
 * @param {ExtraPayment[]} [options.extras=[]] - Extra payment definitions.
 * @returns {ScheduleResult} Schedule with rows, totals, chart arrays, and breakEven period.
 */
export function runSchedule(
  principal,
  ratePerPeriod,
  totalPeriods,
  { withExtras = false, emiOverride = null, extras = [] } = {}
) {
  const emi = emiOverride || calcEMI(principal, ratePerPeriod, totalPeriods);
  let balance = principal;
  let totalInterest = 0;
  let totalExtra = 0;
  let period = 0;
  let rollingPrincipal = 0;
  let rollingInterest = 0;
  let rollingExtra = 0;

  const balances = [];
  const principalParts = [];
  const interestParts = [];
  const extraParts = [];
  const cumulativePrincipal = [];
  const cumulativeInterest = [];
  const cumulativeExtra = [];
  const rows = [];

  for (let nextPeriod = 1; balance > 0.01 && nextPeriod <= 2000; nextPeriod += 1) {
    period = nextPeriod;
    const interestPart = balance * ratePerPeriod;
    let principalPart = emi - interestPart;
    let extraAmount = withExtras ? getExtraForPeriod(period, extras) : 0;

    if (principalPart + extraAmount >= balance) {
      principalPart = Math.min(principalPart, balance);
      extraAmount = Math.min(extraAmount, balance - principalPart);
    }

    balance -= principalPart + extraAmount;

    if (balance < 0.01) {
      balance = 0;
    }

    totalInterest += interestPart;
    totalExtra += extraAmount;
    rollingPrincipal += principalPart;
    rollingInterest += interestPart;
    rollingExtra += extraAmount;

    balances.push(Math.round(balance));
    principalParts.push(Math.round(principalPart));
    interestParts.push(Math.round(interestPart));
    extraParts.push(Math.round(extraAmount));
    cumulativePrincipal.push(Math.round(rollingPrincipal));
    cumulativeInterest.push(Math.round(rollingInterest));
    cumulativeExtra.push(Math.round(rollingExtra));
    rows.push({
      period,
      emi: interestPart + principalPart,
      principal: principalPart,
      interest: interestPart,
      extra: extraAmount,
      balance
    });
  }

  let breakEven = /** @type {number | null} */ (null);
  for (let index = 1; index < cumulativePrincipal.length; index += 1) {
    if (
      cumulativePrincipal[index] + cumulativeExtra[index] >= cumulativeInterest[index] &&
      cumulativePrincipal[index - 1] + cumulativeExtra[index - 1] < cumulativeInterest[index - 1]
    ) {
      breakEven = index + 1;
      break;
    }
  }

  return {
    emi,
    periods: period,
    totalInterest,
    totalExtra,
    balances,
    principalParts,
    interestParts,
    extraParts,
    cumulativePrincipal,
    cumulativeInterest,
    cumulativeExtra,
    rows,
    breakEven
  };
}
