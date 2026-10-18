import{summarizeScheduleRows as $}from"./schedule-summary.js";export function renderTableSummary(d,e){const n=[["Total EMI",e.totalEmi],["Principal (EMI)",e.totalPrincipal],["Total interest",e.totalInterest],["Total extras",e.totalExtras],["Periods",e.periods]];d.innerHTML="";for(const[t,a]of n){const i=document.createElement("div");i.className="stat";const l=document.createElement("div");l.className="stat-label",l.textContent=t;const o=document.createElement("div");o.className="stat-value",o.textContent=a,i.append(l,o),d.appendChild(i)}}export function renderPeriodTable(d,e,n){d.innerHTML="";for(const t of e){const a=document.createElement("tr");t.extra>0&&(a.className="extra-highlight"),a.innerHTML=`
      <td>${t.period}</td>
      <td>${n(t.emi)}</td>
      <td>${n(t.principal)}</td>
      <td>${n(t.interest)}</td>
      <td>${t.extra>0?n(t.extra):"-"}</td>
      <td>${n(t.balance)}</td>
    `,d.appendChild(a)}}export function renderYearlyTable(d,e,n,t,a){d.innerHTML="";const i=Math.ceil(e.length/t);for(let l=1;l<=i;l+=1){const o=(l-1)*t,s=e.slice(o,l*t),p=o===0?n:e[o-1].balance,m=s[s.length-1].balance,{totalPrincipal:x,totalInterest:E,totalExtras:r}=$(s),c=document.createElement("tr");c.className="year-row",c.innerHTML=`
      <td>Year ${l}</td>
      <td>${a(p)}</td>
      <td>${a(x)}</td>
      <td>${a(E)}</td>
      <td>${r>0?a(r):"-"}</td>
      <td>${a(m)}</td>
    `,d.appendChild(c)}}
