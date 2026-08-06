import{getPageNumbers as F}from"./catalog.js";import{escapeHtml as r}from"../html-escape.js";export{r as escapeHtml};import{ICONS as f}from"./icons.js";const N=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],L=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],x=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],S=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function M(a){return N[a%N.length]}function V(a){const e=a%x.length;return{noteRotate:x[e],noteHoverRotate:S[e]}}const y=new Map;let p=null;function w(){if(!p){p=[...L];for(let a=p.length-1;a>0;a-=1){const e=Math.floor(Math.random()*(a+1));[p[a],p[e]]=[p[e],p[a]]}}return p}function u({active:a=!1,className:e,color:t,datasetName:l,datasetValue:s,label:i,rotate:d=null,surface:c}){const n=d!==null?` data-rotate="${d}"`:"";return`<button class="${e}${a?" is-active":""}" data-filter-surface="${c}" ${l}="${r(s)}" data-chip-color="${r(t)}"${n} type="button" aria-controls="artifacts-grid" aria-pressed="${a}">${r(i)}</button>`}function E(a){return y.get(a)||"var(--color-capsule-default)"}function A(a,e,t=""){return!Array.isArray(a)||a.length===0?t:`
    <div class="${e}">
      ${a.slice(0,3).map(l=>`<span class="${e}-item" data-capsule-bg="${r(E(l))}">${r(l)}</span>`).join("")}
    </div>
  `}export function buildFilterNotes({tools:a,tags:e,activeTools:t,activeTags:l,toolLabel:s,tagLabel:i}){let d=1;const c=()=>{const o=Math.sin(d++)*1e4;return o-Math.floor(o)},n=w(),g=o=>n[(o+1)%n.length],C=a.length+1,m=o=>n[(C+o)%n.length],h=t.length>0,$=l.length>0,k=[u({active:!h,className:"desk-note",color:n[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...a.map((o,b)=>{const v=g(b);return y.set(o,v),u({active:t.includes(o),className:"desk-note",color:v,datasetName:"data-filter-tool",datasetValue:o,label:s(o),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],R=[u({active:!$,className:"desk-note",color:n[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...e.map((o,b)=>{const v=m(b);return y.set(o,v),u({active:l.includes(o),className:"desk-note",color:v,datasetName:"data-filter-tag",datasetValue:o,label:i(o),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],O=[u({active:!h,className:"mobile-filter-chip",color:n[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All tools",surface:"mobile"}),...a.map((o,b)=>u({active:t.includes(o),className:"mobile-filter-chip",color:g(b),datasetName:"data-filter-tool",datasetValue:o,label:s(o),surface:"mobile"}))],T=[u({active:!$,className:"mobile-filter-chip",color:n[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All tags",surface:"mobile"}),...e.map((o,b)=>u({active:l.includes(o),className:"mobile-filter-chip",color:m(b),datasetName:"data-filter-tag",datasetValue:o,label:i(o),surface:"mobile"}))];return`
    <div class="desk-notes-left">${k.join("")}</div>
    <div class="desk-notes-right">${R.join("")}</div>
    <div class="mobile-filter-stack">
      <section class="mobile-filter-group" aria-label="Tool filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tools</span>
          <span class="mobile-filter-summary" data-filter-summary="tools">${h?`${t.length} active`:"All tools"}</span>
        </div>
        <div class="mobile-filter-chip-row">${O.join("")}</div>
      </section>
      <section class="mobile-filter-group" aria-label="Tag filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tags</span>
          <span class="mobile-filter-summary" data-filter-summary="tags">${$?`${l.length} active`:"All tags"}</span>
        </div>
        <div class="mobile-filter-chip-row">${T.join("")}</div>
      </section>
    </div>
  `}export function createDetailContent(a){const e=a.thumbnail?`<img class="detail-media" src="${r(a.thumbnail)}" alt="${r(a.name)} preview">`:'<div class="detail-media-placeholder"></div>',t=a.description||"Open the artifact to explore the interactive experience.",l=A(a.tags,"detail-meta-tags"),s=A(a.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${f.close}
    </button>
    <div class="detail-media-wrap">
      ${e}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${r(a.name)}</h2>
      <p id="detail-description" class="detail-description">${r(t)}</p>
      ${l||s?`<div class="detail-meta">${l}${s}</div>`:""}
      <a class="detail-open-link" href="${r(a.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${f.open}
      </a>
    </div>
  `}export function handleThumbnailError(a){const e=a.target;if(!e||e.tagName!=="IMG"||!e.classList.contains("card-thumbnail"))return;const t=e.closest(".card-photo-frame"),l=t?.parentNode;if(!t||!l)return;const s=t.ownerDocument.createElement("div");s.className="card-thumbnail-placeholder",l.replaceChild(s,t)}export function registerThumbnailFallback(a){a.addEventListener("error",handleThumbnailError,!0)}function H(a,e,t){const l=M(t),s=a.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${r(a.thumbnail)}" alt="${r(a.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',i=V(t);return`
    <button class="artifact-card ${e?"expanded":""}" data-id="${r(a.id)}" data-card-color="${r(l)}" data-note-rotate="${r(i.noteRotate)}" data-note-hover-rotate="${r(i.noteHoverRotate)}" type="button"
      aria-label="View details for ${r(a.name)}" aria-expanded="${e}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${s}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${r(a.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(a,e){const t=a.map((i,d)=>H(i,e===i.id,d)),l=t.filter((i,d)=>d%2===0),s=t.filter((i,d)=>d%2!==0);return`
    <section class="artifact-page-slice artifact-page-left" aria-label="Left book page">
      ${l.join("")}
    </section>
    <section class="artifact-page-slice artifact-page-right" aria-label="Right book page">
      ${s.join("")}
    </section>
  `}export function applyDynamicStyles(a){a.querySelectorAll("[data-chip-color]").forEach(e=>{const t=e,l=t.dataset.chipColor||"";t.style.setProperty("--chip-color",l),t.style.setProperty("--note-color",l),t.dataset.rotate&&t.style.setProperty("--rotate",`${t.dataset.rotate}deg`)}),a.querySelectorAll("[data-capsule-bg]").forEach(e=>{const t=e;t.style.setProperty("--capsule-bg",t.dataset.capsuleBg||"")}),a.querySelectorAll("[data-card-color]").forEach(e=>{const t=e;t.style.setProperty("--card-bg-color",t.dataset.cardColor||""),t.style.setProperty("--note-rotate",t.dataset.noteRotate||""),t.style.setProperty("--note-hover-rotate",t.dataset.noteHoverRotate||"")})}export function renderPagination(a,e,t){if(t<=1){a.innerHTML="";return}const l=F(e,t),s=e===1,i=e===t,d=l.map(n=>{if(n==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const g=n===e;return`<button class="page-btn ${g?"active":""}" data-page="${n}" type="button" ${g?'aria-current="page"':""} aria-label="Page ${n}"><span class="page-btn-paper"></span><span class="page-btn-number">${n}</span></button>`}).join("");let c="";c+=`<button class="page-btn page-btn-nav" data-page="1" type="button" ${s?"disabled":""} aria-label="First page"><span class="page-btn-paper"></span>${f.chevronFirst}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${e-1}" type="button" ${s?"disabled":""} aria-label="Previous page"><span class="page-btn-paper"></span>${f.chevronLeft}</button>`,c+=d,c+=`<button class="page-btn page-btn-nav" data-page="${e+1}" type="button" ${i?"disabled":""} aria-label="Next page"><span class="page-btn-paper"></span>${f.chevronRight}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${t}" type="button" ${i?"disabled":""} aria-label="Last page"><span class="page-btn-paper"></span>${f.chevronLast}</button>`,a.innerHTML=c}
