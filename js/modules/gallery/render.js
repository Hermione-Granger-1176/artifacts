import{getPageNumbers as D}from"./catalog.js";import{escapeHtml as s}from"../html-escape.js";import{ICONS as f}from"./icons.js";export{s as escapeHtml};const R=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],I=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],y=["tape-pair","tape-center","corners","clip","tape-diagonal"],j=6,A=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],P=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function V(t){return R[t%R.length]}function B(t){let a=2166136261;for(let e=0;e<t.length;e+=1)a^=t.charCodeAt(e),a=Math.imul(a,16777619);return a>>>0}function G(t){const a=B(t);return{attach:y[a%y.length],tape:Math.floor(a/y.length)%j+1}}function q(t){const a=t%A.length;return{noteRotate:A[a],noteHoverRotate:P[a]}}const F=new Map;let g=null;function K(){if(!g){g=[...I];for(let t=g.length-1;t>0;t-=1){const a=Math.floor(Math.random()*(t+1));[g[t],g[a]]=[g[a],g[t]]}}return g}function C({active:t=!1,className:a,color:e,datasetName:o,datasetValue:r,label:c,count:i,rotate:d=null,surface:n}){const l=d!==null?` data-rotate="${d}"`:"",p=i===void 0?"":`<span class="filter-option-count" aria-hidden="true">${i}</span>`;return`<button class="${a}${t?" is-active":""}" data-filter-surface="${n}" ${o}="${s(r)}" data-chip-color="${s(e)}"${l} type="button" aria-controls="artifacts-grid" aria-pressed="${t}"><span class="filter-option-label">${s(c)}</span>${p}</button>`}function O(t){return F.get(t)||"var(--color-capsule-default)"}function T(t,a,e=""){return!Array.isArray(t)||t.length===0?e:`
    <div class="${a}">
      ${t.slice(0,3).map(o=>`<span class="${a}-item" data-capsule-bg="${s(O(o))}">${s(o)}</span>`).join("")}
    </div>
  `}const z=8;export function buildFilterDropdowns(t){return t.map(({kind:a,heading:e,noteValue:o,values:r,activeValues:c,datasetName:i,labelFor:d,countFor:n})=>{const l=`filter-panel-${a}`,p=e.toLowerCase(),$=r.map(b=>C({active:c.includes(b),className:"filter-option",color:O(b),datasetName:i,datasetValue:b,label:d(b),count:n(b),surface:"mobile"})),h=r.length>z?`<input class="filter-panel-search" type="search" placeholder="Find ${p}..." aria-label="Find ${p}" autocomplete="off" data-filter-panel-search>`:"";return`
    <div class="filter-dropdown">
      <button class="filter-dropdown-toggle" type="button" data-filter-open="${a}" aria-haspopup="dialog" aria-controls="${l}" aria-expanded="false" aria-label="${e}">
        <span class="filter-dropdown-label" aria-hidden="true">${e}</span>
        <span class="filter-dropdown-count" data-filter-summary="${a}" aria-hidden="true">${c.length||""}</span>
        ${f.chevronDown}
      </button>
      <dialog id="${l}" class="filter-panel" aria-labelledby="${l}-title">
        <div class="filter-panel-body">
          <div class="filter-panel-head">
            <h2 id="${l}-title" class="filter-panel-title">${e}</h2>
            <button class="btn-icon filter-panel-close" type="button" data-close-filter-panel aria-label="Close ${p}">${f.close}</button>
          </div>
          ${h}
          <div class="filter-panel-options" role="group" aria-label="${e}">${$.join("")}</div>
          <div class="filter-panel-foot">
            <button class="btn-reset-link filter-panel-clear" type="button" data-filter-note="${o}" data-filter-surface="mobile" aria-controls="artifacts-grid">Clear</button>
            <button class="filter-panel-done" type="button" data-close-filter-panel>Done</button>
          </div>
        </div>
      </dialog>
    </div>`}).join("")}export function buildFilterNotes({tools:t,tags:a,activeTools:e,activeTags:o,toolLabel:r,tagLabel:c}){let i=1;const d=()=>{const u=Math.sin(i++)*1e4;return u-Math.floor(u)},n=K(),l=u=>n[(u+1)%n.length],p=t.length+1,$=u=>n[(p+u)%n.length],h=({noteValue:u,values:E,activeValues:N,datasetName:M,colorFor:_,labelFor:H})=>[C({active:N.length===0,className:"desk-note",color:n[0],datasetName:"data-filter-note",datasetValue:u,label:"All",rotate:(d()*6-3).toFixed(1),surface:"desk"}),...E.map((v,k)=>{const x=_(k);return F.set(v,x),C({active:N.includes(v),className:"desk-note",color:x,datasetName:M,datasetValue:v,label:H(v),rotate:(d()*8-4).toFixed(1),surface:"desk"})})],b={noteValue:"all-tools",values:t,activeValues:e,datasetName:"data-filter-tool",colorFor:l,labelFor:r},L={noteValue:"all-tags",values:a,activeValues:o,datasetName:"data-filter-tag",colorFor:$,labelFor:c},S=h(b),w=h(L);return`
    <div class="desk-notes-left">${S.join("")}</div>
    <div class="desk-notes-right">${w.join("")}</div>
  `}export function createDetailContent(t){const a=t.thumbnail?`<img class="detail-media" src="${s(t.thumbnail)}" alt="${s(t.name)} preview">`:'<div class="detail-media-placeholder"></div>',e=t.description||"Open the artifact to explore the interactive experience.",o=T(t.tags,"detail-meta-tags"),r=T(t.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${f.close}
    </button>
    <div class="detail-media-wrap">
      ${a}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${s(t.name)}</h2>
      <p id="detail-description" class="detail-description">${s(e)}</p>
      ${o||r?`<div class="detail-meta">${o}${r}</div>`:""}
      <a class="detail-open-link" href="${s(t.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${f.open}
      </a>
    </div>
  `}export function handleThumbnailError(t){const a=t.target;if(!a||a.tagName!=="IMG"||!a.classList.contains("card-thumbnail"))return;const e=a.closest(".card-photo-frame"),o=e?.parentNode;if(!e||!o)return;const r=e.ownerDocument.createElement("div");r.className="card-thumbnail-placeholder",o.replaceChild(r,e)}export function registerThumbnailFallback(t){t.addEventListener("error",handleThumbnailError,!0)}function U(t,a,e){const o=V(e),r=t.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${s(t.thumbnail)}" alt="${s(t.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',c=q(e),i=G(t.id);return`
    <button class="artifact-card ${a?"expanded":""}" data-id="${s(t.id)}" data-card-color="${s(o)}" data-attach="${i.attach}" data-tape="${i.tape}" data-note-rotate="${s(c.noteRotate)}" data-note-hover-rotate="${s(c.noteHoverRotate)}" type="button"
      aria-label="View details for ${s(t.name)}" aria-expanded="${a}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${r}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${s(t.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(t,a,e=1){const o=t.map((n,l)=>U(n,a===n.id,l)),r=o.filter((n,l)=>l%2===0),c=o.filter((n,l)=>l%2!==0),i=(e-1)*2+1,d=(n,l,p)=>`
    <section class="artifact-page-slice artifact-page-${n}${l.length===0?" is-empty":""}" aria-label="${n==="left"?"Left":"Right"} book page">
      ${l.join("")}
      <span class="page-number" aria-hidden="true">${p}</span>
    </section>`;return`${d("left",r,i)}${d("right",c,i+1)}
  `}export function applyDynamicStyles(t){t.querySelectorAll("[data-chip-color]").forEach(a=>{const e=a,o=e.dataset.chipColor||"";e.style.setProperty("--chip-color",o),e.style.setProperty("--note-color",o),e.dataset.rotate&&e.style.setProperty("--rotate",`${e.dataset.rotate}deg`)}),t.querySelectorAll("[data-capsule-bg]").forEach(a=>{const e=a;e.style.setProperty("--capsule-bg",e.dataset.capsuleBg||"")}),t.querySelectorAll("[data-card-color]").forEach(a=>{const e=a;e.style.setProperty("--card-bg-color",e.dataset.cardColor||""),e.style.setProperty("--note-rotate",e.dataset.noteRotate||""),e.style.setProperty("--note-hover-rotate",e.dataset.noteHoverRotate||"")})}function m({page:t,step:a,disabled:e,label:o,content:r}){const c=a===void 0?"":` data-page-step="${a}"`;return`<button class="page-btn page-btn-nav" data-page="${t}"${c} type="button" ${e?"disabled":""} aria-label="${o}"><span class="page-btn-paper"></span>${r}</button>`}export function renderPagination(t,a,e){const o=Math.max(1,e),r=`${a}/${o}`;if(t.dataset.renderKey===r)return;const c=D(a,o),i=a===1,d=a===o,n=c.map(l=>{if(l==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const p=l===a;return`<button class="page-btn ${p?"active":""}" data-page="${l}" type="button" ${p?'aria-current="page"':""} aria-label="Page ${l}"><span class="page-btn-paper"></span><span class="page-btn-number">${l}</span></button>`});o===1&&n.push('<span class="page-ellipsis page-slot-empty" aria-hidden="true"></span>'),t.innerHTML=[m({page:1,disabled:i,label:"First page",content:f.chevronFirst}),m({page:a-1,step:-1,disabled:i,label:"Prev page",content:`${f.chevronLeft}<span class="page-btn-label">Prev</span>`}),n.join(""),m({page:a+1,step:1,disabled:d,label:"Next page",content:`<span class="page-btn-label">Next</span>${f.chevronRight}`}),m({page:o,disabled:d,label:"Last page",content:f.chevronLast})].join(""),t.dataset.renderKey=r}
