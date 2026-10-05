export function renderTableSummary(d,e){const a=[["Total EMI",e.totalEmi],["Principal (EMI)",e.totalPrincipal],["Total interest",e.totalInterest],["Total extras",e.totalExtras],["Periods",e.periods]];d.innerHTML="";for(const[t,n]of a){const c=document.createElement("div");c.className="stat";const l=document.createElement("div");l.className="stat-label",l.textContent=t;const i=document.createElement("div");i.className="stat-value",i.textContent=n,c.append(l,i),d.appendChild(c)}}export function renderPeriodTable(d,e,a){d.innerHTML="";for(const t of e){const n=document.createElement("tr");t.extra>0&&(n.className="extra-highlight"),n.innerHTML=`
      <td>${t.period}</td>
      <td>${a(t.emi)}</td>
      <td>${a(t.principal)}</td>
      <td>${a(t.interest)}</td>
      <td>${t.extra>0?a(t.extra):"-"}</td>
      <td>${a(t.balance)}</td>
    `,d.appendChild(n)}}export function renderYearlyTable(d,e,a,t,n){d.innerHTML="";const c=Math.ceil(e.length/t);for(let l=1;l<=c;l+=1){const i=(l-1)*t,$=Math.min(l*t,e.length);let p=0,m=0,s=0,x=i===0?a:e[i-1].balance,E=x;for(const o of e.slice(i,$))p+=o.principal,m+=o.interest,s+=o.extra,E=o.balance;const r=document.createElement("tr");r.className="year-row",r.innerHTML=`
      <td>Year ${l}</td>
      <td>${n(x)}</td>
      <td>${n(p)}</td>
      <td>${n(m)}</td>
      <td>${s>0?n(s):"-"}</td>
      <td>${n(E)}</td>
    `,d.appendChild(r)}}
