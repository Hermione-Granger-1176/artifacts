import{getPageNumbers as I}from"./catalog.js";import{escapeHtml as n}from"../html-escape.js";import{ICONS as b}from"./icons.js";export{n as escapeHtml};const M=["var(--card-color-1)","var(--card-color-2)","var(--card-color-3)","var(--card-color-4)","var(--card-color-5)","var(--card-color-6)","var(--card-color-7)","var(--card-color-8)","var(--card-color-9)","var(--card-color-10)","var(--card-color-11)","var(--card-color-12)"],B=["var(--color-note-1)","var(--color-note-2)","var(--color-note-3)","var(--color-note-4)","var(--color-note-5)","var(--color-note-6)"],T=["tape-pair","tape-center","corners","clip","tape-diagonal"],G=6,k=["-1.4deg","0.6deg","-0.4deg","1.2deg","-0.9deg","1.5deg","0.3deg","-1.1deg","0.8deg","-0.5deg","1.3deg","-0.7deg"],K=["-0.35deg","0.2deg","-0.12deg","0.4deg","-0.25deg","0.45deg","0.1deg","-0.3deg","0.25deg","-0.15deg","0.36deg","-0.2deg"];function P(t){return M[t%M.length]}function q(t){let a=2166136261;for(let e=0;e<t.length;e+=1)a^=t.charCodeAt(e),a=Math.imul(a,16777619);return a>>>0}function z(t){const a=q(t);return{attach:T[a%T.length],tape:Math.floor(a/T.length)%G+1}}function U(t){const a=t%k.length;return{noteRotate:k[a],noteHoverRotate:K[a]}}const E=new Map;let u=null;function Y(){if(!u){u=[...B];for(let t=u.length-1;t>0;t-=1){const a=Math.floor(Math.random()*(t+1));[u[t],u[a]]=[u[a],u[t]]}}return u}function y({active:t=!1,className:a,color:e,datasetName:o,datasetValue:r,label:s,rotate:c=null,surface:p}){const l=c!==null?` data-rotate="${c}"`:"";return`<button class="${a}${t?" is-active":""}" data-filter-surface="${p}" ${o}="${n(r)}" data-chip-color="${n(e)}"${l} type="button" aria-controls="artifacts-grid" aria-pressed="${t}">${n(s)}</button>`}function J(t){return E.get(t)||"var(--color-capsule-default)"}function _(t,a,e=""){return!Array.isArray(t)||t.length===0?e:`
    <div class="${a}">
      ${t.slice(0,3).map(o=>`<span class="${a}-item" data-capsule-bg="${n(J(o))}">${n(o)}</span>`).join("")}
    </div>
  `}export function formatFilterSummary(t,a){return t>0?`${t} active`:a}function H({kind:t,heading:a,ariaLabel:e,allLabel:o,activeCount:r,chips:s}){return`
      <section class="mobile-filter-group" aria-label="${e}">
        <div class="mobile-filter-head">
          <span class="mobile-filter-heading">${a}</span>
          <span class="mobile-filter-summary" data-filter-summary="${t}">${formatFilterSummary(r,o)}</span>
        </div>
        <div class="mobile-filter-chip-row">${s.join("")}</div>
      </section>`}export function buildFilterNotes({tools:t,tags:a,activeTools:e,activeTags:o,toolLabel:r,tagLabel:s}){let c=1;const p=()=>{const d=Math.sin(c++)*1e4;return d-Math.floor(d)},l=Y(),i=d=>l[(d+1)%l.length],f=t.length+1,x=d=>l[(f+d)%l.length],O=({noteValue:d,values:N,activeValues:v,datasetName:$,colorFor:A,labelFor:L})=>[y({active:v.length===0,className:"desk-note",color:l[0],datasetName:"data-filter-note",datasetValue:d,label:"All",rotate:(p()*6-3).toFixed(1),surface:"desk"}),...N.map((g,h)=>{const m=A(h);return E.set(g,m),y({active:v.includes(g),className:"desk-note",color:m,datasetName:$,datasetValue:g,label:L(g),rotate:(p()*8-4).toFixed(1),surface:"desk"})})],R=({noteValue:d,allLabel:N,values:v,activeValues:$,datasetName:A,colorFor:L,labelFor:g})=>[y({active:$.length===0,className:"mobile-filter-chip",color:l[0],datasetName:"data-filter-note",datasetValue:d,label:N,surface:"mobile"}),...v.map((h,m)=>y({active:$.includes(h),className:"mobile-filter-chip",color:L(m),datasetName:A,datasetValue:h,label:g(h),surface:"mobile"}))],F={noteValue:"all-tools",values:t,activeValues:e,datasetName:"data-filter-tool",colorFor:i,labelFor:r},S={noteValue:"all-tags",values:a,activeValues:o,datasetName:"data-filter-tag",colorFor:x,labelFor:s},w=O(F),V=O(S),j=R({...F,allLabel:"All tools"}),D=R({...S,allLabel:"All tags"});return`
    <div class="desk-notes-left">${w.join("")}</div>
    <div class="desk-notes-right">${V.join("")}</div>
    <div class="mobile-filter-stack">${H({kind:"tools",heading:"Tools",ariaLabel:"Tool filters",allLabel:"All tools",activeCount:e.length,chips:j})}${H({kind:"tags",heading:"Tags",ariaLabel:"Tag filters",allLabel:"All tags",activeCount:o.length,chips:D})}
    </div>
  `}export function createDetailContent(t){const a=t.thumbnail?`<img class="detail-media" src="${n(t.thumbnail)}" alt="${n(t.name)} preview">`:'<div class="detail-media-placeholder"></div>',e=t.description||"Open the artifact to explore the interactive experience.",o=_(t.tags,"detail-meta-tags"),r=_(t.tools,"detail-meta-tools");return`
    <button class="detail-close" type="button" data-close-detail aria-label="Close details">
      ${b.close}
    </button>
    <div class="detail-media-wrap">
      ${a}
    </div>
    <div class="detail-content">
      <h2 id="detail-title" class="detail-title">${n(t.name)}</h2>
      <p id="detail-description" class="detail-description">${n(e)}</p>
      ${o||r?`<div class="detail-meta">${o}${r}</div>`:""}
      <a class="detail-open-link" href="${n(t.url)}" target="_blank" rel="noopener noreferrer"
        aria-label="Open artifact in a new tab">
        Open artifact <span class="visually-hidden">(opens in a new tab)</span> ${b.open}
      </a>
    </div>
  `}export function handleThumbnailError(t){const a=t.target;if(!a||a.tagName!=="IMG"||!a.classList.contains("card-thumbnail"))return;const e=a.closest(".card-photo-frame"),o=e?.parentNode;if(!e||!o)return;const r=e.ownerDocument.createElement("div");r.className="card-thumbnail-placeholder",o.replaceChild(r,e)}export function registerThumbnailFallback(t){t.addEventListener("error",handleThumbnailError,!0)}function Q(t,a,e){const o=P(e),r=t.thumbnail?`
      <div class="card-photo-frame">
        <img class="card-thumbnail" src="${n(t.thumbnail)}" alt="${n(t.name)}" loading="lazy">
      </div>
    `:'<div class="card-thumbnail-placeholder"></div>',s=U(e),c=z(t.id);return`
    <button class="artifact-card ${a?"expanded":""}" data-id="${n(t.id)}" data-card-color="${n(o)}" data-attach="${c.attach}" data-tape="${c.tape}" data-note-rotate="${n(s.noteRotate)}" data-note-hover-rotate="${n(s.noteHoverRotate)}" type="button"
      aria-label="View details for ${n(t.name)}" aria-expanded="${a}" aria-haspopup="dialog">
      <div class="card-note">
        <div class="card-thumbnail-area">
          ${r}
        </div>
        <div class="card-overlay card-note-body">
          <div class="card-name">${n(t.name)}</div>
        </div>
      </div>
    </button>
  `}export function buildGridHtml(t,a,e=1){const o=t.map((l,i)=>Q(l,a===l.id,i)),r=o.filter((l,i)=>i%2===0),s=o.filter((l,i)=>i%2!==0),c=(e-1)*2+1,p=(l,i,f)=>`
    <section class="artifact-page-slice artifact-page-${l}${i.length===0?" is-empty":""}" aria-label="${l==="left"?"Left":"Right"} book page">
      ${i.join("")}
      <span class="page-number" aria-hidden="true">${f}</span>
    </section>`;return`${p("left",r,c)}${p("right",s,c+1)}
  `}export function applyDynamicStyles(t){t.querySelectorAll("[data-chip-color]").forEach(a=>{const e=a,o=e.dataset.chipColor||"";e.style.setProperty("--chip-color",o),e.style.setProperty("--note-color",o),e.dataset.rotate&&e.style.setProperty("--rotate",`${e.dataset.rotate}deg`)}),t.querySelectorAll("[data-capsule-bg]").forEach(a=>{const e=a;e.style.setProperty("--capsule-bg",e.dataset.capsuleBg||"")}),t.querySelectorAll("[data-card-color]").forEach(a=>{const e=a;e.style.setProperty("--card-bg-color",e.dataset.cardColor||""),e.style.setProperty("--note-rotate",e.dataset.noteRotate||""),e.style.setProperty("--note-hover-rotate",e.dataset.noteHoverRotate||"")})}function C({page:t,step:a,disabled:e,label:o,content:r}){const s=a===void 0?"":` data-page-step="${a}"`;return`<button class="page-btn page-btn-nav" data-page="${t}"${s} type="button" ${e?"disabled":""} aria-label="${o}"><span class="page-btn-paper"></span>${r}</button>`}export function renderPagination(t,a,e){if(e<=1){t.innerHTML="",delete t.dataset.renderKey;return}const o=`${a}/${e}`;if(t.dataset.renderKey===o)return;const r=I(a,e),s=a===1,c=a===e,p=r.map(l=>{if(l==="...")return'<span class="page-ellipsis" aria-hidden="true"><span class="page-ellipsis-dots">&hellip;</span></span>';const i=l===a;return`<button class="page-btn ${i?"active":""}" data-page="${l}" type="button" ${i?'aria-current="page"':""} aria-label="Page ${l}"><span class="page-btn-paper"></span><span class="page-btn-number">${l}</span></button>`}).join("");t.innerHTML=[C({page:1,disabled:s,label:"First page",content:b.chevronFirst}),C({page:a-1,step:-1,disabled:s,label:"Prev page",content:`${b.chevronLeft}<span class="page-btn-label">Prev</span>`}),p,C({page:a+1,step:1,disabled:c,label:"Next page",content:`<span class="page-btn-label">Next</span>${b.chevronRight}`}),C({page:e,disabled:c,label:"Last page",content:b.chevronLast})].join(""),t.dataset.renderKey=o}
