import{getPageNumbers as O}from"./catalog.js";export{escapeHtml}from"../html-escape.js";import{escapeHtml as r}from"../html-escape.js";import{ICONS as f}from"./icons.js";const C=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],S=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],N=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],T=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function F(a){return C[a%C.length]}function H(a){const t=a%N.length;return{noteRotate:N[t],noteHoverRotate:T[t]}}const h=new Map;let p=null;function L(){if(!p){p=[...S];for(let a=p.length-1;a>0;a-=1){const t=Math.floor(Math.random()*(a+1));[p[a],p[t]]=[p[t],p[a]]}}return p}function u({active:a=!1,className:t,color:e,datasetName:s,datasetValue:i,label:n,rotate:d=null,surface:c}){const l=d!==null?` data-rotate="${d}"`:"";return`<button class="${t}${a?" is-active":""}" data-filter-surface="${c}" ${s}="${r(i)}" data-chip-color="${r(e)}"${l} type="button" aria-controls="artifacts-grid" aria-pressed="${a}">${r(n)}</button>`}function V(a){return h.get(a)||"var(--color-capsule-default)"}function A(a,t,e=""){return!Array.isArray(a)||a.length===0?e:`
    <div class="${t}">
      ${a.slice(0,3).map(s=>`<span class="${t}-item" data-capsule-bg="${r(V(s))}">${r(s)}</span>`).join("")}
    </div>
  `}export function buildFilterNotes({tools:a,tags:t,activeTools:e,activeTags:s,toolLabel:i,tagLabel:n}){let d=1;const c=()=>{const o=Math.sin(d++)*1e4;return o-Math.floor(o)},l=L(),g=e.length>0,m=s.length>0,$=[u({active:!g,className:"desk-note",color:l[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...a.map((o,b)=>{const v=l[(b+1)%l.length];return h.set(o,v),u({active:e.includes(o),className:"desk-note",color:v,datasetName:"data-filter-tool",datasetValue:o,label:i(o),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],y=a.length+1,x=[u({active:!m,className:"desk-note",color:l[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All",rotate:(c()*6-3).toFixed(1),surface:"desk"}),...t.map((o,b)=>{const v=l[(y+b)%l.length];return h.set(o,v),u({active:s.includes(o),className:"desk-note",color:v,datasetName:"data-filter-tag",datasetValue:o,label:n(o),rotate:(c()*8-4).toFixed(1),surface:"desk"})})],R=[u({active:!g,className:"mobile-filter-chip",color:l[0],datasetName:"data-filter-note",datasetValue:"all-tools",label:"All tools",surface:"mobile"}),...a.map((o,b)=>u({active:e.includes(o),className:"mobile-filter-chip",color:l[(b+1)%l.length],datasetName:"data-filter-tool",datasetValue:o,label:i(o),surface:"mobile"}))],k=[u({active:!m,className:"mobile-filter-chip",color:l[0],datasetName:"data-filter-note",datasetValue:"all-tags",label:"All tags",surface:"mobile"}),...t.map((o,b)=>u({active:s.includes(o),className:"mobile-filter-chip",color:l[(y+b)%l.length],datasetName:"data-filter-tag",datasetValue:o,label:n(o),surface:"mobile"}))];return`
    <div class="desk-notes-left">${$.join("")}</div>
    <div class="desk-notes-right">${x.join("")}</div>
    <div class="mobile-filter-stack">
      <section class="mobile-filter-group" aria-label="Tool filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tools</span>
          <span class="mobile-filter-summary" data-filter-summary="tools">${g?`${e.length} active`:"All tools"}</span>
        </div>
        <div class="mobile-filter-chip-row">${R.join("")}</div>
      </section>
      <section class="mobile-filter-group" aria-label="Tag filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tags</span>
          <span class="mobile-filter-summary" data-filter-summary="tags">${m?`${s.length} active`:"All tags"}</span>
        </div>
        <div class="mobile-filter-chip-row">${k.join("")}</div>
      </section>
    </div>
  `}export function createDetailContent(a){const t=a.thumbnail?`<img class="detail-media" src="${r(a.thumbnail)}" alt="${r(a.name)} preview">`:'<div class="detail-media-placeholder"></div>',e=a.description||"Open the artifact to explore the interactive experience.",s=A(a.tags,"detail-meta-tags"),i=A(a.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${f.close}
    </button>
    <div class="detail-media-wrap">
      ${t}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${r(a.name)}</h2>
      <p id="detail-description" class="detail-description">${r(e)}</p>
      ${s||i?`<div class="detail-meta">${s}${i}</div>`:""}
      <a class="detail-open-link" href="${r(a.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${f.open}
      </a>
    </div>
  `}function M(a,t,e){const s=F(e),i=a.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${r(a.thumbnail)}" alt="${r(a.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',n=H(e);return`
    <button class="artifact-card ${t?"expanded":""}" data-id="${r(a.id)}" data-card-color="${r(s)}" data-note-rotate="${r(n.noteRotate)}" data-note-hover-rotate="${r(n.noteHoverRotate)}" type="button"
      aria-label="View details for ${r(a.name)}" aria-expanded="${t}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${i}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${r(a.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(a,t){const e=a.map((n,d)=>M(n,t===n.id,d)),s=e.filter((n,d)=>d%2===0),i=e.filter((n,d)=>d%2!==0);return`
    <section class="artifact-page-slice artifact-page-left" aria-label="Left book page">
      ${s.join("")}
    </section>
    <section class="artifact-page-slice artifact-page-right" aria-label="Right book page">
      ${i.join("")}
    </section>
  `}export function applyDynamicStyles(a){a.querySelectorAll("[data-chip-color]").forEach(t=>{const e=t.dataset.chipColor;t.style.setProperty("--chip-color",e),t.style.setProperty("--note-color",e),t.dataset.rotate&&t.style.setProperty("--rotate",`${t.dataset.rotate}deg`)}),a.querySelectorAll("[data-capsule-bg]").forEach(t=>{t.style.setProperty("--capsule-bg",t.dataset.capsuleBg)}),a.querySelectorAll("[data-card-color]").forEach(t=>{t.style.setProperty("--card-bg-color",t.dataset.cardColor),t.style.setProperty("--note-rotate",t.dataset.noteRotate),t.style.setProperty("--note-hover-rotate",t.dataset.noteHoverRotate)})}export function renderPagination(a,t,e){if(e<=1){a.innerHTML="";return}const s=O(t,e),i=t===1,n=t===e,d=s.map(l=>{if(l==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const g=l===t;return`<button class="page-btn ${g?"active":""}" data-page="${l}" type="button" ${g?'aria-current="page"':""} aria-label="Page ${l}"><span class="page-btn-paper"></span><span class="page-btn-number">${l}</span></button>`}).join("");let c="";c+=`<button class="page-btn page-btn-nav" data-page="1" type="button" ${i?"disabled":""} aria-label="First page"><span class="page-btn-paper"></span>${f.chevronFirst}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${t-1}" type="button" ${i?"disabled":""} aria-label="Previous page"><span class="page-btn-paper"></span>${f.chevronLeft}</button>`,c+=d,c+=`<button class="page-btn page-btn-nav" data-page="${t+1}" type="button" ${n?"disabled":""} aria-label="Next page"><span class="page-btn-paper"></span>${f.chevronRight}</button>`,c+=`<button class="page-btn page-btn-nav" data-page="${e}" type="button" ${n?"disabled":""} aria-label="Last page"><span class="page-btn-paper"></span>${f.chevronLast}</button>`,a.innerHTML=c}
