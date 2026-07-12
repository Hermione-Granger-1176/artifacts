import{escapeAttribute as v}from"./formatting.js";function a(e){const i=v(e);return`<button type="button" class="info-tip metric-tip" data-tip="${i}" aria-label="${i}">?</button>`}export function buildMetricsMarkup({base:e,extra:i,savings:c,periodsSaved:r,totalPaid:d,costRatio:l,label:s},t){return`
    <div class="page-card metric">
      ${a(`Fixed payment amount each ${s.toLowerCase()}, excluding extra payments`)}
      <div class="metric-label">${s}ly EMI</div>
      <div class="metric-value">${t(e.emi)}</div>
    </div>
    <div class="page-card metric">
      ${a("Interest without extras vs with extras applied")}
      <div class="metric-label">Total interest</div>
      <div class="metric-value">${t(i.totalInterest)}</div>
      ${c>1?`<div class="metric-sub"><span class="savings-pill">Save ${t(c)}</span></div>`:""}
      <div class="metric-sub is-muted">Without extras: ${t(e.totalInterest)}</div>
    </div>
    <div class="page-card metric">
      ${a(`Number of ${s.toLowerCase()}s until the loan is fully paid off`)}
      <div class="metric-label">Payoff in</div>
      <div class="metric-value">${i.periods} ${s.toLowerCase()}s</div>
      ${r>0?`<div class="metric-sub"><span class="savings-pill">${r} earlier</span></div>`:""}
    </div>
    <div class="page-card metric">
      ${a("Principal plus total interest. The real cost of your loan.")}
      <div class="metric-label">Total paid</div>
      <div class="metric-value">${t(d)}</div>
      <div class="metric-sub">Interest is ${((l-1)*100).toFixed(1)}% of loan</div>
    </div>
    <div class="page-card metric">
      ${a(`The ${s.toLowerCase()} when cumulative principal paid from EMI and extras surpasses cumulative interest`)}
      <div class="metric-label">Break-even</div>
      <div class="metric-value">${i.breakEven?`${s} ${i.breakEven}`:"N/A"}</div>
      <div class="metric-sub">Principal (EMI + extras) &gt; interest</div>
    </div>
  `}export function renderMetrics(e,i,c){e.innerHTML=buildMetricsMarkup(i,c)}
