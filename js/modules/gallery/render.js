import{getPageNumbers as O}from"./catalog.js";export{escapeHtml}from"../html-escape.js";import{escapeHtml as s}from"../html-escape.js";import{ICONS as g}from"./icons.js";const N=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],T=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],C=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],F=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function L(a){return N[a%N.length]}function S(a){const e=a%C.length;return{noteRotate:C[e],noteHoverRotate:F[e]}}const h=new Map;let p=null;function H(){if(!p){p=[...T];for(let a=p.length-1;a>0;a-=1){const e=Math.floor(Math.random()*(a+1));[p[a],p[e]]=[p[e],p[a]]}}return p}function u({active:a=!1,className:e,color:t,datasetName:l,datasetValue:n,label:i,rotate:d=null,surface:c}){const o=d!==null?` data-rotate="${d}"`:"";return`<button class="${e}${a?" is-active":""}" data-filter-surface="${c}" ${l}="${s(n)}" data-chip-color="${s(t)}"${o} type="button" aria-controls="artifacts-grid" aria-pressed="${a}">${s(i)}</button>`}function M(a){return h.get(a)||"var(--color-capsule-default)"}function x(a,e,t=""){return!Array.isArray(a)||a.length===0?t:`
    <div class="${e}">
      ${a.slice(0,3).map(l=>`<span class="${e}-item" data-capsule-bg="${s(M(l))}">${s(l)}</span>`).join("")}
    </div>
  `}export function buildFilterNotes({tools:a,tags:e,activeTools:t,activeTags:l,toolLabel:n,tagLabel:i}){let d=1;const c=()=>{const r=Math.sin(d++)*1e4;return r-Math.floor(r)},o=H(),f=t.length>0,v=l.length>0,$=[u({active:!f,className:"desk-note",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...a.map((r,b)=>{const m=o[(b+1)%o.length];return h.set(r,m),u({active:t.includes(r),className:"desk-note",color:m,datasetName:"data-filter-tool",datasetValue:r,label:n(r),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],y=a.length+1,A=[u({active:!v,className:"desk-note",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...e.map((r,b)=>{const m=o[(y+b)%o.length];return h.set(r,m),u({active:l.includes(r),className:"desk-note",color:m,datasetName:"data-filter-tag",datasetValue:r,label:i(r),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],k=[u({active:!f,className:"mobile-filter-chip",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All tools",surface:"mobile"}),...a.map((r,b)=>u({active:t.includes(r),className:"mobile-filter-chip",color:o[(b+1)%o.length],datasetName:"data-filter-tool",datasetValue:r,label:n(r),surface:"mobile"}))],R=[u({active:!v,className:"mobile-filter-chip",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All tags",surface:"mobile"}),...e.map((r,b)=>u({active:l.includes(r),className:"mobile-filter-chip",color:o[(y+b)%o.length],datasetName:"data-filter-tag",datasetValue:r,label:i(r),surface:"mobile"}))];return`
    <div class="desk-notes-left">${$.join("")}</div>
    <div class="desk-notes-right">${A.join("")}</div>
    <div class="mobile-filter-stack">
      <section class="mobile-filter-group" aria-label="Tool filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tools</span>
          <span class="mobile-filter-summary" data-filter-summary="tools">${f?`${t.length} active`:"All tools"}</span>
        </div>
        <div class="mobile-filter-chip-row">${k.join("")}</div>
      </section>
      <section class="mobile-filter-group" aria-label="Tag filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tags</span>
          <span class="mobile-filter-summary" data-filter-summary="tags">${v?`${l.length} active`:"All tags"}</span>
        </div>
        <div class="mobile-filter-chip-row">${R.join("")}</div>
      </section>
    </div>
  `}export function createDetailContent(a){const e=a.thumbnail?`<img class="detail-media" src="${s(a.thumbnail)}" alt="${s(a.name)} preview">`:'<div class="detail-media-placeholder"></div>',t=a.description||"Open the artifact to explore the interactive experience.",l=x(a.tags,"detail-meta-tags"),n=x(a.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${g.close}
    </button>
    <div class="detail-media-wrap">
      ${e}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${s(a.name)}</h2>
      <p id="detail-description" class="detail-description">${s(t)}</p>
      ${l||n?`<div class="detail-meta">${l}${n}</div>`:""}
      <a class="detail-open-link" href="${s(a.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${g.open}
      </a>
    </div>
  `}export function handleThumbnailError(a){const e=a.target;if(!e||e.tagName!=="IMG"||!e.classList.contains("card-thumbnail"))return;const t=e.closest(".card-photo-frame"),l=t?.parentNode;if(!t||!l)return;const n=t.ownerDocument.createElement("div");n.className="card-thumbnail-placeholder",l.replaceChild(n,t)}export function registerThumbnailFallback(a){a.addEventListener("error",handleThumbnailError,!0)}function V(a,e,t){const l=L(t),n=a.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${s(a.thumbnail)}" alt="${s(a.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',i=S(t);return`
    <button class="artifact-card ${e?"expanded":""}" data-id="${s(a.id)}" data-card-color="${s(l)}" data-note-rotate="${s(i.noteRotate)}" data-note-hover-rotate="${s(i.noteHoverRotate)}" type="button"
      aria-label="View details for ${s(a.name)}" aria-expanded="${e}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${n}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${s(a.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(a,e){const t=a.map((i,d)=>V(i,e===i.id,d)),l=t.filter((i,d)=>d%2===0),n=t.filter((i,d)=>d%2!==0);return`
    <section class="artifact-page-slice artifact-page-left" aria-label="Left book page">
      ${l.join("")}
    </section>
    <section class="artifact-page-slice artifact-page-right" aria-label="Right book page">
      ${n.join("")}
    </section>
  `}export function applyDynamicStyles(a){a.querySelectorAll("[data-chip-color]").forEach(e=>{const t=e,l=t.dataset.chipColor||"";t.style.setProperty("--chip-color",l),t.style.setProperty("--note-color",l),t.dataset.rotate&&t.style.setProperty("--rotate",`${t.dataset.rotate}deg`)}),a.querySelectorAll("[data-capsule-bg]").forEach(e=>{const t=e;t.style.setProperty("--capsule-bg",t.dataset.capsuleBg||"")}),a.querySelectorAll("[data-card-color]").forEach(e=>{const t=e;t.style.setProperty("--card-bg-color",t.dataset.cardColor||""),t.style.setProperty("--note-rotate",t.dataset.noteRotate||""),t.style.setProperty("--note-hover-rotate",t.dataset.noteHoverRotate||"")})}export function renderPagination(a,e,t){if(t<=1){a.innerHTML="";return}const l=O(e,t),n=e===1,i=e===t,d=l.map(o=>{if(o==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const f=o===e;return`<button class="page-btn ${f?"active":""}" data-page="${o}" type="button" ${f?'aria-current="page"':""} aria-label="Page ${o}"><span class="page-btn-paper"></span><span class="page-btn-number">${o}</span></button>`}).join("");let c="";c+=`<button class="page-btn page-btn-nav" data-page="1" type="button" ${n?"disabled":""} aria-label="First page"><span class="page-btn-paper"></span>${g.chevronFirst}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${e-1}" type="button" ${n?"disabled":""} aria-label="Previous page"><span class="page-btn-paper"></span>${g.chevronLeft}</button>`,c+=d,c+=`<button class="page-btn page-btn-nav" data-page="${e+1}" type="button" ${i?"disabled":""} aria-label="Next page"><span class="page-btn-paper"></span>${g.chevronRight}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${t}" type="button" ${i?"disabled":""} aria-label="Last page"><span class="page-btn-paper"></span>${g.chevronLast}</button>`,a.innerHTML=c}
