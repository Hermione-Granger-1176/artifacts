import{getPageNumbers as L}from"./catalog.js";import{escapeHtml as r}from"../html-escape.js";export{r as escapeHtml};import{ICONS as h}from"./icons.js";const A=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],M=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],N=["tape-pair","tape-center","corners","clip","tape-diagonal"],E=6,x=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],F=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function _(a){return A[a%A.length]}function H(a){let t=2166136261;for(let e=0;e<a.length;e+=1)t^=a.charCodeAt(e),t=Math.imul(t,16777619);return t>>>0}function V(a){const t=H(a);return{attach:N[t%N.length],tape:Math.floor(t/N.length)%E+1}}function w(a){const t=a%x.length;return{noteRotate:x[t],noteHoverRotate:F[t]}}const C=new Map;let u=null;function j(){if(!u){u=[...M];for(let a=u.length-1;a>0;a-=1){const t=Math.floor(Math.random()*(a+1));[u[a],u[t]]=[u[t],u[a]]}}return u}function b({active:a=!1,className:t,color:e,datasetName:l,datasetValue:c,label:d,rotate:i=null,surface:p}){const o=i!==null?` data-rotate="${i}"`:"";return`<button class="${t}${a?" is-active":""}" data-filter-surface="${p}" ${l}="${r(c)}" data-chip-color="${r(e)}"${o} type="button" aria-controls="artifacts-grid" aria-pressed="${a}">${r(d)}</button>`}function I(a){return C.get(a)||"var(--color-capsule-default)"}function T(a,t,e=""){return!Array.isArray(a)||a.length===0?e:`
    <div class="${t}">
      ${a.slice(0,3).map(l=>`<span class="${t}-item" data-capsule-bg="${r(I(l))}">${r(l)}</span>`).join("")}
    </div>
  `}export function buildFilterNotes({tools:a,tags:t,activeTools:e,activeTags:l,toolLabel:c,tagLabel:d}){let i=1;const p=()=>{const s=Math.sin(i++)*1e4;return s-Math.floor(s)},o=j(),n=s=>o[(s+1)%o.length],f=a.length+1,$=s=>o[(f+s)%o.length],v=e.length>0,y=l.length>0,O=[b({active:!v,className:"desk-note",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All",rotate:(p()*6-3).toFixed(1),surface:"desk"}),...a.map((s,g)=>{const m=n(g);return C.set(s,m),b({active:e.includes(s),className:"desk-note",color:m,datasetName:"data-filter-tool",datasetValue:s,label:c(s),rotate:(p()*8-4).toFixed(1),surface:"desk"})})],R=[b({active:!y,className:"desk-note",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All",rotate:(p()*6-3).toFixed(1),surface:"desk"}),...t.map((s,g)=>{const m=$(g);return C.set(s,m),b({active:l.includes(s),className:"desk-note",color:m,datasetName:"data-filter-tag",datasetValue:s,label:d(s),rotate:(p()*8-4).toFixed(1),surface:"desk"})})],k=[b({active:!v,className:"mobile-filter-chip",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All tools",surface:"mobile"}),...a.map((s,g)=>b({active:e.includes(s),className:"mobile-filter-chip",color:n(g),datasetName:"data-filter-tool",datasetValue:s,label:c(s),surface:"mobile"}))],S=[b({active:!y,className:"mobile-filter-chip",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All tags",surface:"mobile"}),...t.map((s,g)=>b({active:l.includes(s),className:"mobile-filter-chip",color:$(g),datasetName:"data-filter-tag",datasetValue:s,label:d(s),surface:"mobile"}))];return`
    <div class="desk-notes-left">${O.join("")}</div>
    <div class="desk-notes-right">${R.join("")}</div>
    <div class="mobile-filter-stack">
      <section class="mobile-filter-group" aria-label="Tool filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tools</span>
          <span class="mobile-filter-summary" data-filter-summary="tools">${v?`${e.length} active`:"All tools"}</span>
        </div>
        <div class="mobile-filter-chip-row">${k.join("")}</div>
      </section>
      <section class="mobile-filter-group" aria-label="Tag filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tags</span>
          <span class="mobile-filter-summary" data-filter-summary="tags">${y?`${l.length} active`:"All tags"}</span>
        </div>
        <div class="mobile-filter-chip-row">${S.join("")}</div>
      </section>
    </div>
  `}export function createDetailContent(a){const t=a.thumbnail?`<img class="detail-media" src="${r(a.thumbnail)}" alt="${r(a.name)} preview">`:'<div class="detail-media-placeholder"></div>',e=a.description||"Open the artifact to explore the interactive experience.",l=T(a.tags,"detail-meta-tags"),c=T(a.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${h.close}
    </button>
    <div class="detail-media-wrap">
      ${t}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${r(a.name)}</h2>
      <p id="detail-description" class="detail-description">${r(e)}</p>
      ${l||c?`<div class="detail-meta">${l}${c}</div>`:""}
      <a class="detail-open-link" href="${r(a.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${h.open}
      </a>
    </div>
  `}export function handleThumbnailError(a){const t=a.target;if(!t||t.tagName!=="IMG"||!t.classList.contains("card-thumbnail"))return;const e=t.closest(".card-photo-frame"),l=e?.parentNode;if(!e||!l)return;const c=e.ownerDocument.createElement("div");c.className="card-thumbnail-placeholder",l.replaceChild(c,e)}export function registerThumbnailFallback(a){a.addEventListener("error",handleThumbnailError,!0)}function D(a,t,e){const l=_(e),c=a.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${r(a.thumbnail)}" alt="${r(a.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',d=w(e),i=V(a.id);return`
    <button class="artifact-card ${t?"expanded":""}" data-id="${r(a.id)}" data-card-color="${r(l)}" data-attach="${i.attach}" data-tape="${i.tape}" data-note-rotate="${r(d.noteRotate)}" data-note-hover-rotate="${r(d.noteHoverRotate)}" type="button"
      aria-label="View details for ${r(a.name)}" aria-expanded="${t}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${c}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${r(a.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(a,t,e=1){const l=a.map((o,n)=>D(o,t===o.id,n)),c=l.filter((o,n)=>n%2===0),d=l.filter((o,n)=>n%2!==0),i=(e-1)*2+1,p=(o,n,f)=>`
    <section class="artifact-page-slice artifact-page-${o}${n.length===0?" is-empty":""}" aria-label="${o==="left"?"Left":"Right"} book page">
      ${n.join("")}
      <span class="page-number" aria-hidden="true">${f}</span>
    </section>`;return`${p("left",c,i)}${p("right",d,i+1)}
  `}export function applyDynamicStyles(a){a.querySelectorAll("[data-chip-color]").forEach(t=>{const e=t,l=e.dataset.chipColor||"";e.style.setProperty("--chip-color",l),e.style.setProperty("--note-color",l),e.dataset.rotate&&e.style.setProperty("--rotate",`${e.dataset.rotate}deg`)}),a.querySelectorAll("[data-capsule-bg]").forEach(t=>{const e=t;e.style.setProperty("--capsule-bg",e.dataset.capsuleBg||"")}),a.querySelectorAll("[data-card-color]").forEach(t=>{const e=t;e.style.setProperty("--card-bg-color",e.dataset.cardColor||""),e.style.setProperty("--note-rotate",e.dataset.noteRotate||""),e.style.setProperty("--note-hover-rotate",e.dataset.noteHoverRotate||"")})}export function renderPagination(a,t,e){if(e<=1){a.innerHTML="",delete a.dataset.renderKey;return}const l=`${t}/${e}`;if(a.dataset.renderKey===l)return;const c=L(t,e),d=t===1,i=t===e,p=c.map(n=>{if(n==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const f=n===t;return`<button class="page-btn ${f?"active":""}" data-page="${n}" type="button" ${f?'aria-current="page"':""} aria-label="Page ${n}"><span class="page-btn-paper"></span><span class="page-btn-number">${n}</span></button>`}).join("");let o="";o+=`<button class="page-btn page-btn-nav" data-page="1" type="button" ${d?"disabled":""} aria-label="First page"><span class="page-btn-paper"></span>${h.chevronFirst}</button>`,o+=`<button class="page-btn page-btn-nav" data-page="${t-1}" data-page-step="-1" type="button" ${d?"disabled":""} aria-label="Previous page"><span class="page-btn-paper"></span>${h.chevronLeft}<span class="page-btn-label">Prev</span></button>`,o+=p,o+=`<button class="page-btn page-btn-nav" data-page="${t+1}" data-page-step="1" type="button" ${i?"disabled":""} aria-label="Next page"><span class="page-btn-paper"></span><span class="page-btn-label">Next</span>${h.chevronRight}</button>`,o+=`<button class="page-btn page-btn-nav" data-page="${e}" type="button" ${i?"disabled":""} aria-label="Last page"><span class="page-btn-paper"></span>${h.chevronLast}</button>`,a.innerHTML=o,a.dataset.renderKey=l}
