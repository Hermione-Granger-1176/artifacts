import{escapeAttribute as s}from"../../../../js/modules/html-escape.js";export function createExtra(t){return{id:t,type:"recurring",amount:500,every:1,startPeriod:1,period:1}}export function removeExtraById(t,n){return t.filter(e=>e.id!==n)}export function setExtraType(t,n,e){const a=t.find(r=>r.id===n);a&&(a.type=e)}const u=new Set(["amount","every","startPeriod","period"]);export function updateExtraField(t,n,e,a){if(!u.has(e))return;const r=+a;if(Number.isNaN(r)||r<0||(e==="every"||e==="startPeriod"||e==="period")&&r<1)return;const i=t.find(o=>o.id===n);i&&(i[e]=r)}export function summarizeExtra(t,n){return t.type==="recurring"?`Pays $${t.amount.toLocaleString()} every ${t.every===1?n:`${t.every} ${n}s`} starting from ${n} ${t.startPeriod}`:`One-time payment of $${t.amount.toLocaleString()} at ${n} ${t.period}`}export function renderExtras({container:t,extras:n,periodLabel:e}){t.innerHTML="";for(const a of n){const r=document.createElement("div"),i=summarizeExtra(a,e);r.className="extra-item",r.dataset.extraId=String(a.id),a.type==="recurring"?r.innerHTML=`
        <button type="button" class="info-tip card-tip" data-tip="${s(i)}" aria-label="${s(i)}">?</button>
        <div class="segmented is-fused">
          <button type="button" class="active" data-action="set-type" data-type="recurring" aria-pressed="true">Recurring</button>
          <button type="button" data-action="set-type" data-type="onetime" aria-pressed="false">One-time</button>
        </div>
        <div class="amt-group">
          <span>$</span>
          <input class="amount-input" type="number" value="${a.amount}" min="0" step="100" data-field="amount">
        </div>
        <div class="param-group">
          <span>every</span>
          <input class="period-input" type="number" value="${a.every}" min="1" max="60" data-field="every">
          <span>${e}(s)</span>
        </div>
        <div class="param-group">
          <span>from</span>
          <input class="period-input" type="number" value="${a.startPeriod}" min="1" max="2000" data-field="startPeriod">
        </div>
        <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">x</button>
      `:r.innerHTML=`
        <button type="button" class="info-tip card-tip" data-tip="${s(i)}" aria-label="${s(i)}">?</button>
        <div class="segmented is-fused">
          <button type="button" data-action="set-type" data-type="recurring" aria-pressed="false">Recurring</button>
          <button type="button" class="active" data-action="set-type" data-type="onetime" aria-pressed="true">One-time</button>
        </div>
        <div class="amt-group">
          <span>$</span>
          <input class="amount-input" type="number" value="${a.amount}" min="0" step="100" data-field="amount">
        </div>
        <div class="param-group">
          <span>at ${e}</span>
          <input class="period-input" type="number" value="${a.period}" min="1" max="2000" data-field="period">
        </div>
        <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">x</button>
      `,t.appendChild(r)}}
