export function renderTableSummary(d,e){const a=[["Total EMI",e.totalEmi],["Principal (EMI)",e.totalPrincipal],["Total interest",e.totalInterest],["Total extras",e.totalExtras],["Periods",e.periods]];d.innerHTML="";for(const[t,n]of a){const o=document.createElement("div");o.className="summary-stat";const l=document.createElement("div");l.className="summary-label",l.textContent=t;const i=document.createElement("strong");i.textContent=n,o.append(l,i),d.appendChild(o)}}export function renderPeriodTable(d,e,a){d.innerHTML="";for(const t of e){const n=document.createElement("tr");t.extra>0&&(n.className="extra-highlight"),n.innerHTML=`
      <td>${t.period}</td>
      <td>${a(t.emi)}</td>
      <td>${a(t.principal)}</td>
      <td>${a(t.interest)}</td>
      <td>${t.extra>0?a(t.extra):"-"}</td>
      <td>${a(t.balance)}</td>
    `,d.appendChild(n)}}export function renderYearlyTable(d,e,a,t,n){d.innerHTML="";const o=Math.ceil(e.length/t);for(let l=1;l<=o;l+=1){const i=(l-1)*t,T=Math.min(l*t,e.length);let m=0,x=0,r=0,E=i===0?a:e[i-1].balance,$=E;for(let p=i;p<T;p+=1){const c=e[p];m+=c.principal,x+=c.interest,r+=c.extra,$=c.balance}const s=document.createElement("tr");s.className="year-row",s.innerHTML=`
      <td>Year ${l}</td>
      <td>${n(E)}</td>
      <td>${n(m)}</td>
      <td>${n(x)}</td>
      <td>${r>0?n(r):"-"}</td>
      <td>${n($)}</td>
    `,d.appendChild(s)}}
