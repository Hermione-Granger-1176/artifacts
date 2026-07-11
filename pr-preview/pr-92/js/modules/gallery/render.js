import{getPageNumbers as O}from"./catalog.js";export{escapeHtml}from"../html-escape.js";import{escapeHtml as r}from"../html-escape.js";import{ICONS as f}from"./icons.js";const C=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],S=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],N=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],T=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function F(a){return C[a%C.length]}function H(a){const e=a%N.length;return{noteRotate:N[e],noteHoverRotate:T[e]}}const h=new Map;let p=null;function L(){if(!p){p=[...S];for(let a=p.length-1;a>0;a-=1){const e=Math.floor(Math.random()*(a+1));[p[a],p[e]]=[p[e],p[a]]}}return p}function u({active:a=!1,className:e,color:t,datasetName:l,datasetValue:i,label:n,rotate:d=null,surface:c}){const o=d!==null?` data-rotate="${d}"`:"";return`<button class="${e}${a?" is-active":""}" data-filter-surface="${c}" ${l}="${r(i)}" data-chip-color="${r(t)}"${o} type="button" aria-controls="artifacts-grid" aria-pressed="${a}">${r(n)}</button>`}function V(a){return h.get(a)||"var(--color-capsule-default)"}function A(a,e,t=""){return!Array.isArray(a)||a.length===0?t:`
    <div class="${e}">
      ${a.slice(0,3).map(l=>`<span class="${e}-item" data-capsule-bg="${r(V(l))}">${r(l)}</span>`).join("")}
    </div>
  `}export function buildFilterNotes({tools:a,tags:e,activeTools:t,activeTags:l,toolLabel:i,tagLabel:n}){let d=1;const c=()=>{const s=Math.sin(d++)*1e4;return s-Math.floor(s)},o=L(),g=t.length>0,m=l.length>0,$=[u({active:!g,className:"desk-note",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...a.map((s,b)=>{const v=o[(b+1)%o.length];return h.set(s,v),u({active:t.includes(s),className:"desk-note",color:v,datasetName:"data-filter-tool",datasetValue:s,label:i(s),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],y=a.length+1,x=[u({active:!m,className:"desk-note",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...e.map((s,b)=>{const v=o[(y+b)%o.length];return h.set(s,v),u({active:l.includes(s),className:"desk-note",color:v,datasetName:"data-filter-tag",datasetValue:s,label:n(s),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],R=[u({active:!g,className:"mobile-filter-chip",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All tools",surface:"mobile"}),...a.map((s,b)=>u({active:t.includes(s),className:"mobile-filter-chip",color:o[(b+1)%o.length],datasetName:"data-filter-tool",datasetValue:s,label:i(s),surface:"mobile"}))],k=[u({active:!m,className:"mobile-filter-chip",color:o[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All tags",surface:"mobile"}),...e.map((s,b)=>u({active:l.includes(s),className:"mobile-filter-chip",color:o[(y+b)%o.length],datasetName:"data-filter-tag",datasetValue:s,label:n(s),surface:"mobile"}))];return`
    <div class="desk-notes-left">${$.join("")}</div>
    <div class="desk-notes-right">${x.join("")}</div>
    <div class="mobile-filter-stack">
      <section class="mobile-filter-group" aria-label="Tool filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tools</span>
          <span class="mobile-filter-summary" data-filter-summary="tools">${g?`${t.length} active`:"All tools"}</span>
        </div>
        <div class="mobile-filter-chip-row">${R.join("")}</div>
      </section>
      <section class="mobile-filter-group" aria-label="Tag filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tags</span>
          <span class="mobile-filter-summary" data-filter-summary="tags">${m?`${l.length} active`:"All tags"}</span>
        </div>
        <div class="mobile-filter-chip-row">${k.join("")}</div>
      </section>
    </div>
  `}export function createDetailContent(a){const e=a.thumbnail?`<img class="detail-media" src="${r(a.thumbnail)}" alt="${r(a.name)} preview">`:'<div class="detail-media-placeholder"></div>',t=a.description||"Open the artifact to explore the interactive experience.",l=A(a.tags,"detail-meta-tags"),i=A(a.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${f.close}
    </button>
    <div class="detail-media-wrap">
      ${e}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${r(a.name)}</h2>
      <p id="detail-description" class="detail-description">${r(t)}</p>
      ${l||i?`<div class="detail-meta">${l}${i}</div>`:""}
      <a class="detail-open-link" href="${r(a.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${f.open}
      </a>
    </div>
  `}function M(a,e,t){const l=F(t),i=a.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${r(a.thumbnail)}" alt="${r(a.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',n=H(t);return`
    <button class="artifact-card ${e?"expanded":""}" data-id="${r(a.id)}" data-card-color="${r(l)}" data-note-rotate="${r(n.noteRotate)}" data-note-hover-rotate="${r(n.noteHoverRotate)}" type="button"
      aria-label="View details for ${r(a.name)}" aria-expanded="${e}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${i}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${r(a.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(a,e){const t=a.map((n,d)=>M(n,e===n.id,d)),l=t.filter((n,d)=>d%2===0),i=t.filter((n,d)=>d%2!==0);return`
    <section class="artifact-page-slice artifact-page-left" aria-label="Left book page">
      ${l.join("")}
    </section>
    <section class="artifact-page-slice artifact-page-right" aria-label="Right book page">
      ${i.join("")}
    </section>
  `}export function applyDynamicStyles(a){a.querySelectorAll("[data-chip-color]").forEach(e=>{const t=e,l=t.dataset.chipColor||"";t.style.setProperty("--chip-color",l),t.style.setProperty("--note-color",l),t.dataset.rotate&&t.style.setProperty("--rotate",`${t.dataset.rotate}deg`)}),a.querySelectorAll("[data-capsule-bg]").forEach(e=>{const t=e;t.style.setProperty("--capsule-bg",t.dataset.capsuleBg||"")}),a.querySelectorAll("[data-card-color]").forEach(e=>{const t=e;t.style.setProperty("--card-bg-color",t.dataset.cardColor||""),t.style.setProperty("--note-rotate",t.dataset.noteRotate||""),t.style.setProperty("--note-hover-rotate",t.dataset.noteHoverRotate||"")})}export function renderPagination(a,e,t){if(t<=1){a.innerHTML="";return}const l=O(e,t),i=e===1,n=e===t,d=l.map(o=>{if(o==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const g=o===e;return`<button class="page-btn ${g?"active":""}" data-page="${o}" type="button" ${g?'aria-current="page"':""} aria-label="Page ${o}"><span class="page-btn-paper"></span><span class="page-btn-number">${o}</span></button>`}).join("");let c="";c+=`<button class="page-btn page-btn-nav" data-page="1" type="button" ${i?"disabled":""} aria-label="First page"><span class="page-btn-paper"></span>${f.chevronFirst}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${e-1}" type="button" ${i?"disabled":""} aria-label="Previous page"><span class="page-btn-paper"></span>${f.chevronLeft}</button>`,c+=d,c+=`<button class="page-btn page-btn-nav" data-page="${e+1}" type="button" ${n?"disabled":""} aria-label="Next page"><span class="page-btn-paper"></span>${f.chevronRight}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${t}" type="button" ${n?"disabled":""} aria-label="Last page"><span class="page-btn-paper"></span>${f.chevronLast}</button>`,a.innerHTML=c}
