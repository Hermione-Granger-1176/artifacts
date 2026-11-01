export function setMeterValue(a,e){const t=Number.isFinite(e)?Math.min(1,Math.max(0,e)):0;return a.style.scale=`${t} 1`,t}
