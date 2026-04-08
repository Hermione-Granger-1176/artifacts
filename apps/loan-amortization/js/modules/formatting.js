export function formatCurrency(value) {
  return `$${Math.round(value).toLocaleString("en-US")}`;
}

export function formatDollarTick(value) {
  const absoluteValue = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (absoluteValue >= 1000000) {
    return `${sign}$${(absoluteValue / 1000000).toFixed(1)}M`;
  }

  if (absoluteValue >= 10000) {
    return `${sign}$${Math.round(absoluteValue / 1000)}k`;
  }

  if (absoluteValue >= 1000) {
    return `${sign}$${(absoluteValue / 1000).toFixed(1)}k`;
  }

  return `${sign}$${Math.round(absoluteValue)}`;
}

export function parseNumber(value) {
  return +String(value).replace(/[^0-9.\-]/g, "");
}

export function escapeAttribute(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
