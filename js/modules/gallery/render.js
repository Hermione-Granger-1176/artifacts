import{getPageNumbers as I}from"./catalog.js";import{escapeHtml as r}from"../html-escape.js";import{ICONS as h}from"./icons.js";export{r as escapeHtml};const M=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],B=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],T=["tape-pair","tape-center","corners","clip","tape-diagonal"],G=6,k=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],K=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function P(t){return M[t%M.length]}function q(t){let a=2166136261;for(let e=0;e<t.length;e+=1)a^=t.charCodeAt(e),a=Math.imul(a,16777619);return a>>>0}function z(t){const a=q(t);return{attach:T[a%T.length],tape:Math.floor(a/T.length)%G+1}}function U(t){const a=t%k.length;return{noteRotate:k[a],noteHoverRotate:K[a]}}const E=new Map;let u=null;function Y(){if(!u){u=[...B];for(let t=u.length-1;t>0;t-=1){const a=Math.floor(Math.random()*(t+1));[u[t],u[a]]=[u[a],u[t]]}}return u}function y({active:t=!1,className:a,color:e,datasetName:o,datasetValue:n,label:i,rotate:c=null,surface:p}){const l=c!==null?` data-rotate="${c}"`:"";return`<button class="${a}${t?" is-active":""}" data-filter-surface="${p}" ${o}="${r(n)}" data-chip-color="${r(e)}"${l} type="button" aria-controls="artifacts-grid" aria-pressed="${t}">${r(i)}</button>`}function J(t){return E.get(t)||"var(--color-capsule-default)"}function _(t,a,e=""){return!Array.isArray(t)||t.length===0?e:`
    <div class="${a}">
      ${t.slice(0,3).map(o=>`<span class="${a}-item" data-capsule-bg="${r(J(o))}">${r(o)}</span>`).join("")}
    </div>
  `}export function buildFilterNotes({tools:t,tags:a,activeTools:e,activeTags:o,toolLabel:n,tagLabel:i}){let c=1;const p=()=>{const d=Math.sin(c++)*1e4;return d-Math.floor(d)},l=Y(),s=d=>l[(d+1)%l.length],b=t.length+1,x=d=>l[(b+d)%l.length],L=e.length>0,H=o.length>0,O=({noteValue:d,values:C,activeValues:v,datasetName:m,colorFor:N,labelFor:A})=>[y({active:v.length===0,className:"desk-note",color:l[0],datasetName:"data-filter-note",datasetValue:d,label:"All",rotate:(p()*6-3).toFixed(1),surface:"desk"}),...C.map((g,f)=>{const $=N(f);return E.set(g,$),y({active:v.includes(g),className:"desk-note",color:$,datasetName:m,datasetValue:g,label:A(g),rotate:(p()*8-4).toFixed(1),surface:"desk"})})],R=({noteValue:d,allLabel:C,values:v,activeValues:m,datasetName:N,colorFor:A,labelFor:g})=>[y({active:m.length===0,className:"mobile-filter-chip",color:l[0],datasetName:"data-filter-note",datasetValue:d,label:C,surface:"mobile"}),...v.map((f,$)=>y({active:m.includes(f),className:"mobile-filter-chip",color:A($),datasetName:N,datasetValue:f,label:g(f),surface:"mobile"}))],S={noteValue:"all-tools",values:t,activeValues:e,datasetName:"data-filter-tool",colorFor:s,labelFor:n},F={noteValue:"all-tags",values:a,activeValues:o,datasetName:"data-filter-tag",colorFor:x,labelFor:i},w=O(S),V=O(F),j=R({...S,allLabel:"All tools"}),D=R({...F,allLabel:"All tags"});return`
    <div class="desk-notes-left">${w.join("")}</div>
    <div class="desk-notes-right">${V.join("")}</div>
    <div class="mobile-filter-stack">
      <section class="mobile-filter-group" aria-label="Tool filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tools</span>
          <span class="mobile-filter-summary" data-filter-summary="tools">${L?`${e.length} active`:"All tools"}</span>
        </div>
        <div class="mobile-filter-chip-row">${j.join("")}</div>
      </section>
      <section class="mobile-filter-group" aria-label="Tag filters">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">Tags</span>
          <span class="mobile-filter-summary" data-filter-summary="tags">${H?`${o.length} active`:"All tags"}</span>
        </div>
        <div class="mobile-filter-chip-row">${D.join("")}</div>
      </section>
    </div>
  `}export function createDetailContent(t){const a=t.thumbnail?`<img class="detail-media" src="${r(t.thumbnail)}" alt="${r(t.name)} preview">`:'<div class="detail-media-placeholder"></div>',e=t.description||"Open the artifact to explore the interactive experience.",o=_(t.tags,"detail-meta-tags"),n=_(t.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${h.close}
    </button>
    <div class="detail-media-wrap">
      ${a}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${r(t.name)}</h2>
      <p id="detail-description" class="detail-description">${r(e)}</p>
      ${o||n?`<div class="detail-meta">${o}${n}</div>`:""}
      <a class="detail-open-link" href="${r(t.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${h.open}
      </a>
    </div>
  `}export function handleThumbnailError(t){const a=t.target;if(!a||a.tagName!=="IMG"||!a.classList.contains("card-thumbnail"))return;const e=a.closest(".card-photo-frame"),o=e?.parentNode;if(!e||!o)return;const n=e.ownerDocument.createElement("div");n.className="card-thumbnail-placeholder",o.replaceChild(n,e)}export function registerThumbnailFallback(t){t.addEventListener("error",handleThumbnailError,!0)}function Q(t,a,e){const o=P(e),n=t.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${r(t.thumbnail)}" alt="${r(t.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',i=U(e),c=z(t.id);return`
    <button class="artifact-card ${a?"expanded":""}" data-id="${r(t.id)}" data-card-color="${r(o)}" data-attach="${c.attach}" data-tape="${c.tape}" data-note-rotate="${r(i.noteRotate)}" data-note-hover-rotate="${r(i.noteHoverRotate)}" type="button"
      aria-label="View details for ${r(t.name)}" aria-expanded="${a}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${n}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${r(t.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(t,a,e=1){const o=t.map((l,s)=>Q(l,a===l.id,s)),n=o.filter((l,s)=>s%2===0),i=o.filter((l,s)=>s%2!==0),c=(e-1)*2+1,p=(l,s,b)=>`
    <section class="artifact-page-slice artifact-page-${l}${s.length===0?" is-empty":""}" aria-label="${l==="left"?"Left":"Right"} book page">
      ${s.join("")}
      <span class="page-number" aria-hidden="true">${b}</span>
    </section>`;return`${p("left",n,c)}${p("right",i,c+1)}
  `}export function applyDynamicStyles(t){t.querySelectorAll("[data-chip-color]").forEach(a=>{const e=a,o=e.dataset.chipColor||"";e.style.setProperty("--chip-color",o),e.style.setProperty("--note-color",o),e.dataset.rotate&&e.style.setProperty("--rotate",`${e.dataset.rotate}deg`)}),t.querySelectorAll("[data-capsule-bg]").forEach(a=>{const e=a;e.style.setProperty("--capsule-bg",e.dataset.capsuleBg||"")}),t.querySelectorAll("[data-card-color]").forEach(a=>{const e=a;e.style.setProperty("--card-bg-color",e.dataset.cardColor||""),e.style.setProperty("--note-rotate",e.dataset.noteRotate||""),e.style.setProperty("--note-hover-rotate",e.dataset.noteHoverRotate||"")})}export function renderPagination(t,a,e){if(e<=1){t.innerHTML="",delete t.dataset.renderKey;return}const o=`${a}/${e}`;if(t.dataset.renderKey===o)return;const n=I(a,e),i=a===1,c=a===e,p=n.map(s=>{if(s==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const b=s===a;return`<button class="page-btn ${b?"active":""}" data-page="${s}" type="button" ${b?'aria-current="page"':""} aria-label="Page ${s}"><span class="page-btn-paper"></span><span class="page-btn-number">${s}</span></button>`}).join("");let l="";l+=`<button class="page-btn page-btn-nav" data-page="1" type="button" ${i?"disabled":""} aria-label="First page"><span class="page-btn-paper"></span>${h.chevronFirst}</button>`,l+=`<button class="page-btn page-btn-nav" data-page="${a-1}" data-page-step="-1" type="button" ${i?"disabled":""} aria-label="Previous page"><span class="page-btn-paper"></span>${h.chevronLeft}<span class="page-btn-label">Prev</span></button>`,l+=p,l+=`<button class="page-btn page-btn-nav" data-page="${a+1}" data-page-step="1" type="button" ${c?"disabled":""} aria-label="Next page"><span class="page-btn-paper"></span><span class="page-btn-label">Next</span>${h.chevronRight}</button>`,l+=`<button class="page-btn page-btn-nav" data-page="${e}" type="button" ${c?"disabled":""} aria-label="Last page"><span class="page-btn-paper"></span>${h.chevronLast}</button>`,t.innerHTML=l,t.dataset.renderKey=o}
