const E=`
  <nav class="section-nav" aria-label="Section progress">
    <div class="section-nav-inner">
      <div class="section-nav-track">
        <div class="section-nav-line"></div>
        <div class="section-nav-fill" id="nav-fill"></div>
        <div class="section-nav-nodes" id="nav-nodes"></div>
      </div>
      <div class="section-nav-label" id="nav-label"></div>
    </div>
  </nav>
`;export function renderSectionNav(e){!e||e.childElementCount>0||(e.innerHTML=E.trim())}export function scrollToSection(e){const l=document.getElementById(e);if(l){const a=window.matchMedia("(prefers-reduced-motion: reduce)").matches;l.scrollIntoView({behavior:a?"auto":"smooth"})}}export function initSectionNav(e,l={}){const{nodesId:a="nav-nodes",fillId:u="nav-fill",labelId:f="nav-label"}=l,s=document.getElementById(a),d=document.getElementById(u),r=document.getElementById(f);if(e.length===0||!s||!d||!r)return;const m=d,b=r,p=e.map((n,o)=>{const t=document.createElement("button");t.type="button",t.className="section-nav-node",t.setAttribute("aria-label",n.label);const i=document.createElement("span");i.textContent=String(o+1);const c=document.createElement("span");return c.className="section-nav-tip",c.textContent=n.label,t.append(i,c),t.addEventListener("click",()=>scrollToSection(n.id)),s.appendChild(t),t});function v(n){p.forEach((t,i)=>{t.classList.toggle("done",i<n),t.classList.toggle("active",i===n)});const o=e.length>1?n/(e.length-1)*100:0;m.style.width=`${o}%`,b.textContent=e[n].label}if(v(0),typeof IntersectionObserver!="function")return;const g=new IntersectionObserver(n=>{for(const o of n){if(!o.isIntersecting)continue;const t=e.findIndex(i=>i.id===o.target.id);t>=0&&v(t)}},{threshold:.3});for(const n of e){const o=document.getElementById(n.id);o&&g.observe(o)}}
