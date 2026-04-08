export function calcEMI(principal, ratePerPeriod, totalPeriods) {
  if (ratePerPeriod === 0) {
    return principal / totalPeriods;
  }

  return (
    (principal * ratePerPeriod * Math.pow(1 + ratePerPeriod, totalPeriods)) /
    (Math.pow(1 + ratePerPeriod, totalPeriods) - 1)
  );
}

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

  while (balance > 0.01 && period < 2000) {
    period += 1;
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

  let breakEven = null;
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
