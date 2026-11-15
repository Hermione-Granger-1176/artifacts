import{getPageNumbers as D}from"./catalog.js";import{escapeHtml as l}from"../html-escape.js";import{ICONS as u}from"./icons.js";export{l as escapeHtml};const A=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],I=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],y=["tape-pair","tape-center","corners","clip","tape-diagonal"],j=6,L=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],P=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function V(t){return A[t%A.length]}function B(t){let a=2166136261;for(let e=0;e<t.length;e+=1)a^=t.charCodeAt(e),a=Math.imul(a,16777619);return a>>>0}function G(t){const a=B(t);return{attach:y[a%y.length],tape:Math.floor(a/y.length)%j+1}}function q(t){const a=t%L.length;return{noteRotate:L[a],noteHoverRotate:P[a]}}const O=new Map;let g=null;function K(){if(!g){g=[...I];for(let t=g.length-1;t>0;t-=1){const a=Math.floor(Math.random()*(t+1));[g[t],g[a]]=[g[a],g[t]]}}return g}const z=10;function C({active:t=!1,className:a,color:e,datasetName:o,datasetValue:s,label:c,count:d,rotate:i=null,surface:n}){const r=i!==null?` data-rotate="${i}"`:"",p=c.length>z?" data-long":"",h=d===void 0?"":`<span class="filter-option-count" aria-hidden="true">${d}</span>`;return`<button class="${a}${t?" is-active":""}" data-filter-surface="${n}" ${o}="${l(s)}" data-chip-color="${l(e)}"${r}${p} type="button" aria-controls="artifacts-grid" aria-pressed="${t}"><span class="filter-option-label">${l(c)}</span>${h}</button>`}function R(t){return O.get(t)}function T(t,a,e=""){return!Array.isArray(t)||t.length===0?e:`
    <div class="${a}">
      ${t.slice(0,3).map(o=>`<span class="${a}-item" data-capsule-bg="${l(R(o))}">${l(o)}</span>`).join("")}
    </div>
  `}const U=8;export function buildFilterDropdowns(t){return t.map(({kind:a,heading:e,noteValue:o,values:s,activeValues:c,datasetName:d,labelFor:i,countFor:n})=>{const r=`filter-panel-${a}`,p=e.toLowerCase(),h=s.map(b=>C({active:c.includes(b),className:"filter-option",color:R(b),datasetName:d,datasetValue:b,label:i(b),count:n(b),surface:"mobile"})),$=s.length>U?`<input class="filter-panel-search" type="search" placeholder="Find ${p}..." aria-label="Find ${p}" autocomplete="off" data-filter-panel-search>`:"";return`
    <div class="filter-dropdown">
      <button class="filter-dropdown-toggle" type="button" data-filter-open="${a}" aria-haspopup="dialog" aria-controls="${r}" aria-expanded="false" aria-label="${e}">
        <span class="filter-dropdown-label" aria-hidden="true">${e}</span>
        <span class="filter-dropdown-count" data-filter-summary="${a}" aria-hidden="true">${c.length||""}</span>
        ${u.chevronDown}
      </button>
      <dialog id="${r}" class="filter-panel" aria-labelledby="${r}-title">
        <div class="filter-panel-body">
          <div class="filter-panel-head">
            <h2 id="${r}-title" class="filter-panel-title">${e}</h2>
            <button class="btn-icon filter-panel-close" type="button" data-close-filter-panel aria-label="Close ${p}">${u.close}</button>
          </div>
          ${$}
          <div class="filter-panel-options" role="group" aria-label="${e}">${h.join("")}</div>
          <div class="filter-panel-foot">
            <button class="btn-reset-link filter-panel-clear" type="button" data-filter-note="${o}" data-filter-surface="mobile" aria-controls="artifacts-grid">Clear</button>
            <button class="filter-panel-done" type="button" data-close-filter-panel>Done</button>
          </div>
        </div>
      </dialog>
    </div>`}).join("")}export function buildFilterNotes({tools:t,tags:a,activeTools:e,activeTags:o,toolLabel:s,tagLabel:c}){let d=1;const i=()=>{const f=Math.sin(d++)*1e4;return f-Math.floor(f)},n=K(),r=f=>n[(f+1)%n.length],p=t.length+1,h=f=>n[(p+f)%n.length],$=({noteValue:f,values:S,activeValues:N,datasetName:_,colorFor:M,labelFor:k})=>[C({active:N.length===0,className:"desk-note",color:n[0],datasetName:"data-filter-note",datasetValue:f,label:"All",rotate:(i()*6-3).toFixed(1),surface:"desk"}),...S.map((v,H)=>{const x=M(H);return O.set(v,x),C({active:N.includes(v),className:"desk-note",color:x,datasetName:_,datasetValue:v,label:k(v),rotate:(i()*8-4).toFixed(1),surface:"desk"})})],b={noteValue:"all-tools",values:t,activeValues:e,datasetName:"data-filter-tool",colorFor:r,labelFor:s},F={noteValue:"all-tags",values:a,activeValues:o,datasetName:"data-filter-tag",colorFor:h,labelFor:c},w=$(b),E=$(F);return`
    <div class="desk-notes-left">${w.join("")}</div>
    <div class="desk-notes-right">${E.join("")}</div>
  `}export function createDetailContent(t){const a=t.description||"Open the artifact to explore the interactive experience.",e=T(t.tags,"detail-meta-tags"),o=T(t.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${u.close}
    </button>
    <div class="detail-media-wrap">
      <img class="detail-media" src="${l(t.thumbnail)}" alt="${l(t.name)} preview">
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${l(t.name)}</h2>
      <p id="detail-description" class="detail-description">${l(a)}</p>
      ${e||o?`<div class="detail-meta">${e}${o}</div>`:""}
      <a class="detail-open-link" href="${l(t.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${u.open}
      </a>
    </div>
  `}export function handleThumbnailError(t){const a=t.target;if(!a||a.tagName!=="IMG"||!a.classList.contains("card-thumbnail"))return;const e=a.closest(".card-photo-frame"),o=e.ownerDocument.createElement("div");o.className="card-thumbnail-placeholder",e.replaceWith(o)}export function registerThumbnailFallback(t){t.addEventListener("error",handleThumbnailError,!0)}function W(t,a,e){const o=V(e),s=q(e),c=G(t.id);return`
    <button class="artifact-card ${a?"expanded":""}" data-id="${l(t.id)}" data-card-color="${l(o)}" data-attach="${c.attach}" data-tape="${c.tape}" data-note-rotate="${l(s.noteRotate)}" data-note-hover-rotate="${l(s.noteHoverRotate)}" type="button"
      aria-label="View details for ${l(t.name)}" aria-expanded="${a}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          <div class="card-photo-frame">
            <img class="card-thumbnail" src="${l(t.thumbnail)}" alt="${l(t.name)}" loading="lazy">
          </div>
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${l(t.name)}</div>
        </div>
      </div>
    </button>
    <div class="card-notes">
      ${t.description?`<p class="card-notes-text">${l(t.description)}</p>`:""}
      <a class="card-notes-open" href="${l(t.url)}" target="_blank" rel="noopener noreferrer">Open artifact <span class="visually-hidden">${l(t.name)} (opens in a new tab)</span>${u.open}</a>
    </div>
  `}export function buildGridHtml(t,a,e=1){const o=t.map((n,r)=>W(n,a===n.id,r)),s=o.filter((n,r)=>r%2===0),c=o.filter((n,r)=>r%2!==0),d=(e-1)*2+1,i=(n,r,p)=>`
    <section class="artifact-page-slice artifact-page-${n}${r.length===0?" is-empty":""}" aria-label="${n==="left"?"Left":"Right"} book page">
      ${r.join("")}
      <span class="page-number" aria-hidden="true">${p}</span>
    </section>`;return`${i("left",s,d)}${i("right",c,d+1)}
  `}export function applyDynamicStyles(t){t.querySelectorAll("[data-chip-color]").forEach(a=>{const e=a,o=e.dataset.chipColor||"";e.style.setProperty("--chip-color",o),e.style.setProperty("--note-color",o),e.dataset.rotate&&e.style.setProperty("--rotate",`${e.dataset.rotate}deg`)}),t.querySelectorAll("[data-capsule-bg]").forEach(a=>{const e=a;e.style.setProperty("--capsule-bg",e.dataset.capsuleBg||"")}),t.querySelectorAll("[data-card-color]").forEach(a=>{const e=a;e.style.setProperty("--card-bg-color",e.dataset.cardColor||""),e.style.setProperty("--note-rotate",e.dataset.noteRotate||""),e.style.setProperty("--note-hover-rotate",e.dataset.noteHoverRotate||"")})}function m({page:t,step:a,disabled:e,label:o,content:s}){const c=a===void 0?"":` data-page-step="${a}"`;return`<button class="page-btn page-btn-nav" data-page="${t}"${c} type="button" ${e?"disabled":""} aria-label="${o}"><span class="page-btn-paper"></span>${s}</button>`}export function renderPagination(t,a,e){const o=Math.max(1,e),s=`${a}/${o}`;if(t.dataset.renderKey===s)return;const c=D(a,o),d=a===1,i=a===o,n=c.map(r=>{if(r==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const p=r===a;return`<button class="page-btn ${p?"active":""}" data-page="${r}" type="button" ${p?'aria-current="page"':""} aria-label="Page ${r}"><span class="page-btn-paper"></span><span class="page-btn-number">${r}</span></button>`});o===1&&n.push('<span class="page-ellipsis page-slot-empty" aria-hidden="true"></span>'),t.innerHTML=[m({page:1,disabled:d,label:"First page",content:u.chevronFirst}),m({page:a-1,step:-1,disabled:d,label:"Prev page",content:`${u.chevronLeft}<span class="page-btn-label">Prev</span>`}),`<span class="page-counter" aria-hidden="true">${a} / ${o}</span>`,n.join(""),m({page:a+1,step:1,disabled:i,label:"Next page",content:`<span class="page-btn-label">Next</span>${u.chevronRight}`}),m({page:o,disabled:i,label:"Last page",content:u.chevronLast})].join(""),t.dataset.renderKey=s}
