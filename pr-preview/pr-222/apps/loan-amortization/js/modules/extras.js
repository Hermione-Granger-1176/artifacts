import{escapeHtml as l}from"../../../../js/modules/html-escape.js";export function createExtra(e){return{id:e,type:"recurring",amount:500,every:1,startPeriod:1,period:1}}export function removeExtraById(e,t){return e.filter(a=>a.id!==t)}export function setExtraType(e,t,a){const r=e.find(n=>n.id===t);r&&(r.type=a)}const p=new Set(["amount","every","startPeriod","period"]);export function updateExtraField(e,t,a,r){if(!p.has(a))return;const n=+r;if(Number.isNaN(n)||n<0||["every","startPeriod","period"].includes(a)&&n<1)return;const i=e.find(s=>s.id===t);i&&(i[a]=n)}export function summarizeExtra(e,t){return e.type==="recurring"?`Pays $${e.amount.toLocaleString()} every ${e.every===1?t:`${e.every} ${t}s`} starting from ${t} ${e.startPeriod}`:`One-time payment of $${e.amount.toLocaleString()} at ${t} ${e.period}`}const u='class="loan-icon" viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false"',v=`<svg ${u}><path d="M13 7.5A5 5 0 0 0 4.2 4.9"/><path d="M3.5 2.75v2.5h2.5"/><path d="M3 8.5a5 5 0 0 0 8.8 2.6"/><path d="M12.5 13.25v-2.5H10"/></svg>`,$=`<svg ${u}><circle cx="8" cy="8" r="2.25"/></svg>`;function d({label:e,name:t,className:a,field:r,value:n,min:i,max:s,step:o}){const c=s===void 0?"":` max="${s}"`,m=o===void 0?"":` step="${o}"`;return`
        <label class="extra-field">
          <span>${e}</span>
          <input class="${a}" type="number" aria-label="${t}" value="${n}" min="${i}"${c}${m} data-field="${r}">
        </label>`}export function renderExtras({container:e,extras:t,periodLabel:a}){e.innerHTML="";for(const r of t){const n=document.createElement("div"),i=r.type==="recurring";n.className="extra-item",n.dataset.extraId=String(r.id);const s=d({label:"Amount ($)",name:"Extra payment amount",className:"amount-input",field:"amount",value:r.amount,min:0,step:100}),o=i?d({label:"Every",name:`Extra payment repeats every (${a}s)`,className:"period-input",field:"every",value:r.every,min:1,max:60})+d({label:"From",name:`Extra payment starts from ${a}`,className:"period-input",field:"startPeriod",value:r.startPeriod,min:1,max:2e3}):d({label:"At",name:`One-time extra payment at ${a}`,className:"period-input",field:"period",value:r.period,min:1,max:2e3});n.innerHTML=`
        <div class="extra-head">
          <div class="segmented is-fused is-inset">
            <button type="button"${i?' class="active"':""} data-action="set-type" data-type="recurring" aria-pressed="${i}">${v}Recurring</button>
            <button type="button"${i?"":' class="active"'} data-action="set-type" data-type="onetime" aria-pressed="${!i}">${$}One-time</button>
          </div>
          <button type="button" class="btn-remove" data-action="remove-extra" aria-label="Remove extra payment">\xD7</button>
        </div>
        <div class="extra-fields ${i?"is-recurring":"is-onetime"}">${s}${o}
        </div>
        <div class="extra-summary">${l(summarizeExtra(r,a))}</div>
      `,e.appendChild(n)}}
