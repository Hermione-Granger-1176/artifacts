import{getPageNumbers as D}from"./catalog.js";import{escapeHtml as s}from"../html-escape.js";import{ICONS as h}from"./icons.js";export{s as escapeHtml};const M=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],I=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],L=["tape-pair","tape-center","corners","clip","tape-diagonal"],B=6,k=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],G=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function q(t){return M[t%M.length]}function K(t){let a=2166136261;for(let e=0;e<t.length;e+=1)a^=t.charCodeAt(e),a=Math.imul(a,16777619);return a>>>0}function z(t){const a=K(t);return{attach:L[a%L.length],tape:Math.floor(a/L.length)%B+1}}function U(t){const a=t%k.length;return{noteRotate:k[a],noteHoverRotate:G[a]}}const E=new Map;let u=null;function Y(){if(!u){u=[...I];for(let t=u.length-1;t>0;t-=1){const a=Math.floor(Math.random()*(t+1));[u[t],u[a]]=[u[a],u[t]]}}return u}function y({active:t=!1,className:a,color:e,datasetName:o,datasetValue:l,label:c,rotate:i=null,surface:d}){const r=i!==null?` data-rotate="${i}"`:"";return`<button class="${a}${t?" is-active":""}" data-filter-surface="${d}" ${o}="${s(l)}" data-chip-color="${s(e)}"${r} type="button" aria-controls="artifacts-grid" aria-pressed="${t}">${s(c)}</button>`}function J(t){return E.get(t)||"var(--color-capsule-default)"}function _(t,a,e=""){return!Array.isArray(t)||t.length===0?e:`
    <div class="${a}">
      ${t.slice(0,3).map(o=>`<span class="${a}-item" data-capsule-bg="${s(J(o))}">${s(o)}</span>`).join("")}
    </div>
  `}export function formatFilterSummary(t,a){return t>0?`${t} active`:a}function H({kind:t,heading:a,ariaLabel:e,allLabel:o,activeCount:l,chips:c}){return`
      <section class="mobile-filter-group" aria-label="${e}">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">${a}</span>
          <span class="mobile-filter-summary" data-filter-summary="${t}">${formatFilterSummary(l,o)}</span>
        </div>
        <div class="mobile-filter-chip-row">${c.join("")}</div>
      </section>`}export function buildFilterNotes({tools:t,tags:a,activeTools:e,activeTags:o,toolLabel:l,tagLabel:c}){let i=1;const d=()=>{const p=Math.sin(i++)*1e4;return p-Math.floor(p)},r=Y(),n=p=>r[(p+1)%r.length],g=t.length+1,O=p=>r[(g+p)%r.length],N=({noteValue:p,values:A,activeValues:v,datasetName:$,colorFor:T,labelFor:x})=>[y({active:v.length===0,className:"desk-note",color:r[0],datasetName:"data-filter-note",datasetValue:p,label:"All",rotate:(d()*6-3).toFixed(1),surface:"desk"}),...A.map((b,f)=>{const m=T(f);return E.set(b,m),y({active:v.includes(b),className:"desk-note",color:m,datasetName:$,datasetValue:b,label:x(b),rotate:(d()*8-4).toFixed(1),surface:"desk"})})],R=({noteValue:p,allLabel:A,values:v,activeValues:$,datasetName:T,colorFor:x,labelFor:b})=>[y({active:$.length===0,className:"mobile-filter-chip",color:r[0],datasetName:"data-filter-note",datasetValue:p,label:A,surface:"mobile"}),...v.map((f,m)=>y({active:$.includes(f),className:"mobile-filter-chip",color:x(m),datasetName:T,datasetValue:f,label:b(f),surface:"mobile"}))],F={noteValue:"all-tools",values:t,activeValues:e,datasetName:"data-filter-tool",colorFor:n,labelFor:l},S={noteValue:"all-tags",values:a,activeValues:o,datasetName:"data-filter-tag",colorFor:O,labelFor:c},w=N(F),P=N(S),V=R({...F,allLabel:"All tools"}),j=R({...S,allLabel:"All tags"});return`
    <div class="desk-notes-left">${w.join("")}</div>
    <div class="desk-notes-right">${P.join("")}</div>
    <div class="mobile-filter-stack">${H({kind:"tools",heading:"Tools",ariaLabel:"Tool filters",allLabel:"All tools",activeCount:e.length,chips:V})}${H({kind:"tags",heading:"Tags",ariaLabel:"Tag filters",allLabel:"All tags",activeCount:o.length,chips:j})}
    </div>
  `}export function createDetailContent(t){const a=t.thumbnail?`<img class="detail-media" src="${s(t.thumbnail)}" alt="${s(t.name)} preview">`:'<div class="detail-media-placeholder"></div>',e=t.description||"Open the artifact to explore the interactive experience.",o=_(t.tags,"detail-meta-tags"),l=_(t.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${h.close}
    </button>
    <div class="detail-media-wrap">
      ${a}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${s(t.name)}</h2>
      <p id="detail-description" class="detail-description">${s(e)}</p>
      ${o||l?`<div class="detail-meta">${o}${l}</div>`:""}
      <a class="detail-open-link" href="${s(t.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${h.open}
      </a>
    </div>
  `}export function handleThumbnailError(t){const a=t.target;if(!a||a.tagName!=="IMG"||!a.classList.contains("card-thumbnail"))return;const e=a.closest(".card-photo-frame"),o=e?.parentNode;if(!e||!o)return;const l=e.ownerDocument.createElement("div");l.className="card-thumbnail-placeholder",o.replaceChild(l,e)}export function registerThumbnailFallback(t){t.addEventListener("error",handleThumbnailError,!0)}function Q(t,a,e){const o=q(e),l=t.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${s(t.thumbnail)}" alt="${s(t.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',c=U(e),i=z(t.id);return`
    <button class="artifact-card ${a?"expanded":""}" data-id="${s(t.id)}" data-card-color="${s(o)}" data-attach="${i.attach}" data-tape="${i.tape}" data-note-rotate="${s(c.noteRotate)}" data-note-hover-rotate="${s(c.noteHoverRotate)}" type="button"
      aria-label="View details for ${s(t.name)}" aria-expanded="${a}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${l}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${s(t.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(t,a,e=1){const o=t.map((r,n)=>Q(r,a===r.id,n)),l=o.filter((r,n)=>n%2===0),c=o.filter((r,n)=>n%2!==0),i=(e-1)*2+1,d=(r,n,g)=>`
    <section class="artifact-page-slice artifact-page-${r}${n.length===0?" is-empty":""}" aria-label="${r==="left"?"Left":"Right"} book page">
      ${n.join("")}
      <span class="page-number" aria-hidden="true">${g}</span>
    </section>`;return`${d("left",l,i)}${d("right",c,i+1)}
  `}export function applyDynamicStyles(t){t.querySelectorAll("[data-chip-color]").forEach(a=>{const e=a,o=e.dataset.chipColor||"";e.style.setProperty("--chip-color",o),e.style.setProperty("--note-color",o),e.dataset.rotate&&e.style.setProperty("--rotate",`${e.dataset.rotate}deg`)}),t.querySelectorAll("[data-capsule-bg]").forEach(a=>{const e=a;e.style.setProperty("--capsule-bg",e.dataset.capsuleBg||"")}),t.querySelectorAll("[data-card-color]").forEach(a=>{const e=a;e.style.setProperty("--card-bg-color",e.dataset.cardColor||""),e.style.setProperty("--note-rotate",e.dataset.noteRotate||""),e.style.setProperty("--note-hover-rotate",e.dataset.noteHoverRotate||"")})}function C({page:t,step:a,disabled:e,label:o,content:l}){const c=a===void 0?"":` data-page-step="${a}"`;return`<button class="page-btn page-btn-nav" data-page="${t}"${c} type="button" ${e?"disabled":""} aria-label="${o}"><span class="page-btn-paper"></span>${l}</button>`}export function renderPagination(t,a,e){const o=Math.max(1,e),l=`${a}/${o}`;if(t.dataset.renderKey===l)return;const c=D(a,o),i=a===1,d=a===o,r=c.map(n=>{if(n==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const g=n===a;return`<button class="page-btn ${g?"active":""}" data-page="${n}" type="button" ${g?'aria-current="page"':""} aria-label="Page ${n}"><span class="page-btn-paper"></span><span class="page-btn-number">${n}</span></button>`});o===1&&r.push('<span class="page-ellipsis page-slot-empty" aria-hidden="true"></span>'),t.innerHTML=[C({page:1,disabled:i,label:"First page",content:h.chevronFirst}),C({page:a-1,step:-1,disabled:i,label:"Prev page",content:`${h.chevronLeft}<span class="page-btn-label">Prev</span>`}),r.join(""),C({page:a+1,step:1,disabled:d,label:"Next page",content:`<span class="page-btn-label">Next</span>${h.chevronRight}`}),C({page:o,disabled:d,label:"Last page",content:h.chevronLast})].join(""),t.dataset.renderKey=l}
