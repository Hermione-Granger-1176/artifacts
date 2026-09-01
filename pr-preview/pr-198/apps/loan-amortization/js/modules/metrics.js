import{escapeAttribute as c}from"../../../../js/modules/html-escape.js";function e(s){const t=c(s);return`<button type="button" class="info-tip" data-tip="${t}" aria-label="${t}">?</button>`}export function buildMetricsMarkup({base:s,extra:t,savings:l,periodsSaved:d,totalPaid:v,costRatio:n,label:a},i){return`
    <div class="stat">
      ${e(`Fixed payment amount each ${a.toLowerCase()}, excluding extra payments`)}
      <div class="stat-label">${a}ly EMI</div>
      <div class="stat-value">${i(s.emi)}</div>
    </div>
    <div class="stat">
      ${e("Interest without extras vs with extras applied")}
      <div class="stat-label">Total interest</div>
      <div class="stat-value">${i(t.totalInterest)}</div>
      ${l>1?`<div class="stat-sub"><span class="chip is-green">Save ${i(l)}</span></div>`:""}
      <div class="stat-sub">Without extras: ${i(s.totalInterest)}</div>
    </div>
    <div class="stat">
      ${e(`Number of ${a.toLowerCase()}s until the loan is fully paid off`)}
      <div class="stat-label">Payoff in</div>
      <div class="stat-value">${t.periods} ${a.toLowerCase()}s</div>
      ${d>0?`<div class="stat-sub"><span class="chip is-green">${d} earlier</span></div>`:""}
    </div>
    <div class="stat">
      ${e("Principal plus total interest. The real cost of your loan.")}
      <div class="stat-label">Total paid</div>
      <div class="stat-value">${i(v)}</div>
      <div class="stat-sub">Interest is ${((n-1)*100).toFixed(1)}% of loan</div>
    </div>
    <div class="stat">
      ${e(`The first ${a.toLowerCase()} when cumulative principal paid from EMI and extras meets or exceeds cumulative interest`)}
      <div class="stat-label">Break-even</div>
      <div class="stat-value">${t.breakEven?`${a} ${t.breakEven}`:"N/A"}</div>
      <div class="stat-sub">Principal (EMI + extras) &gt;= interest</div>
    </div>
  `}export function renderMetrics(s,t,l){s.innerHTML=buildMetricsMarkup(t,l)}
