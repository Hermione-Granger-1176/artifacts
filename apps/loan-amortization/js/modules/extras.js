import{escapeAttribute as s}from"../../../../js/modules/html-escape.js";export function createExtra(t){return{id:t,type:"recurring",amount:500,every:1,startPeriod:1,period:1}}export function removeExtraById(t,a){return t.filter(r=>r.id!==a)}export function setExtraType(t,a,r){const e=t.find(n=>n.id===a);e&&(e.type=r)}const u=new Set(["amount","every","startPeriod","period"]);export function updateExtraField(t,a,r,e){if(!u.has(r))return;const n=+e;if(Number.isNaN(n)||n<0||["every","startPeriod","period"].includes(r)&&n<1)return;const i=t.find(o=>o.id===a);i&&(i[r]=n)}export function summarizeExtra(t,a){return t.type==="recurring"?`Pays $${t.amount.toLocaleString()} every ${t.every===1?a:`${t.every} ${a}s`} starting from ${a} ${t.startPeriod}`:`One-time payment of $${t.amount.toLocaleString()} at ${a} ${t.period}`}export function renderExtras({container:t,extras:a,periodLabel:r}){t.innerHTML="";for(const e of a){const n=document.createElement("div"),i=summarizeExtra(e,r);n.className="extra-item",n.dataset.extraId=String(e.id),e.type==="recurring"?n.innerHTML=`
        <button type="button" class="info-tip card-tip" data-tip="${s(i)}" aria-label="${s(i)}">?</button>
        <div class="segmented is-fused">
          <button type="button" class="active" data-action="set-type" data-type="recurring" aria-pressed="true">Recurring</button>
          <button type="button" data-action="set-type" data-type="onetime" aria-pressed="false">One-time</button>
        </div>
        <div class="amt-group">
          <span>$</span>
          <input class="amount-input" type="number" value="${e.amount}" min="0" step="100" data-field="amount">
        </div>
        <div class="param-group">
          <span>every</span>
          <input class="period-input" type="number" value="${e.every}" min="1" max="60" data-field="every">
          <span>${r}(s)</span>
        </div>
        <div class="param-group">
          <span>from</span>
          <input class="period-input" type="number" value="${e.startPeriod}" min="1" max="2000" data-field="startPeriod">
        </div>
        <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">x</button>
      `:n.innerHTML=`
        <button type="button" class="info-tip card-tip" data-tip="${s(i)}" aria-label="${s(i)}">?</button>
        <div class="segmented is-fused">
          <button type="button" data-action="set-type" data-type="recurring" aria-pressed="false">Recurring</button>
          <button type="button" class="active" data-action="set-type" data-type="onetime" aria-pressed="true">One-time</button>
        </div>
        <div class="amt-group">
          <span>$</span>
          <input class="amount-input" type="number" value="${e.amount}" min="0" step="100" data-field="amount">
        </div>
        <div class="param-group">
          <span>at ${r}</span>
          <input class="period-input" type="number" value="${e.period}" min="1" max="2000" data-field="period">
        </div>
        <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">x</button>
      `,t.appendChild(n)}}
