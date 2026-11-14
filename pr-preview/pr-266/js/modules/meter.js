import{skipFirstTransition as r}from"./dom-sync.js";export function setMeterValue(t,e){const i=Number.isFinite(e)?Math.min(1,Math.max(0,e)):0;return r(t),t.style.scale=`${i} 1`,i}
