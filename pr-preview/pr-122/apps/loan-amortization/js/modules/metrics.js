import{escapeAttribute as c}from"../../../../js/modules/html-escape.js";function e(t){const s=c(t);return`<button type="button" class="info-tip" data-tip="${s}" aria-label="${s}">?</button>`}export function buildMetricsMarkup({base:t,extra:s,savings:l,periodsSaved:d,totalPaid:v,costRatio:n,label:a},i){return`
    <div class="stat">
      ${e(`Fixed payment amount each ${a.toLowerCase()}, excluding extra payments`)}
      <div class="stat-label">${a}ly EMI</div>
      <div class="stat-value">${i(t.emi)}</div>
    </div>
    <div class="stat">
      ${e("Interest without extras vs with extras applied")}
      <div class="stat-label">Total interest</div>
      <div class="stat-value">${i(s.totalInterest)}</div>
      ${l>1?`<div class="stat-sub"><span class="chip is-green">Save ${i(l)}</span></div>`:""}
      <div class="stat-sub">Without extras: ${i(t.totalInterest)}</div>
    </div>
    <div class="stat">
      ${e(`Number of ${a.toLowerCase()}s until the loan is fully paid off`)}
      <div class="stat-label">Payoff in</div>
      <div class="stat-value">${s.periods} ${a.toLowerCase()}s</div>
      ${d>0?`<div class="stat-sub"><span class="chip is-green">${d} earlier</span></div>`:""}
    </div>
    <div class="stat">
      ${e("Principal plus total interest. The real cost of your loan.")}
      <div class="stat-label">Total paid</div>
      <div class="stat-value">${i(v)}</div>
      <div class="stat-sub">Interest is ${((n-1)*100).toFixed(1)}% of loan</div>
    </div>
    <div class="stat">
      ${e(`The ${a.toLowerCase()} when cumulative principal paid from EMI and extras surpasses cumulative interest`)}
      <div class="stat-label">Break-even</div>
      <div class="stat-value">${s.breakEven?`${a} ${s.breakEven}`:"N/A"}</div>
      <div class="stat-sub">Principal (EMI + extras) &gt; interest</div>
    </div>
  `}export function renderMetrics(t,s,l){t.innerHTML=buildMetricsMarkup(s,l)}
