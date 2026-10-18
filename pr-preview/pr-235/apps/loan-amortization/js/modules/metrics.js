import{escapeAttribute as c}from"../../../../js/modules/html-escape.js";function l(a,t=""){const s=c(a);return`<button type="button" class="${t?`info-tip ${t}`:"info-tip"}" data-tip="${s}" aria-label="${s}">?</button>`}export function formatPeriodsAsDuration(a,t){const s=Math.round(a*12/t);if(s<1)return"under 1m";const i=Math.floor(s/12),e=s%12;return[i>0?`${i}y`:"",e>0?`${e}m`:""].filter(Boolean).join(" ")}function u({savings:a,periodsSaved:t,periodsPerYear:s},i){const e=[];return a>1&&e.push(`Saves ${i(a)}`),t>0&&e.push(`${formatPeriodsAsDuration(t,s)} sooner`),e.length>0?`<span class="chip is-green">${e.join(" \xB7 ")}</span>`:""}export function buildMetricsMarkup({base:a,extra:t,savings:s,periodsSaved:i,totalPaid:e,costRatio:r,label:n,periodsPerYear:d},o){const v=t.totalExtra>0?`Plus ${o(t.totalExtra)} in extra payments over the loan`:"Fixed payment, no extras";return`
    <div class="loan-hero">
      <div class="loan-hero-main">
        <div class="loan-hero-label">
          <span>${n}ly EMI</span>
          ${l(`Fixed payment amount each ${n.toLowerCase()}, excluding extra payments`,"is-start")}
        </div>
        <div class="loan-hero-value">${o(a.emi)}</div>
        <div class="loan-hero-sub">${v}</div>
      </div>
      ${u({savings:s,periodsSaved:i,periodsPerYear:d},o)}
    </div>
    <div class="stat-grid loan-kpis">
      <div class="stat">
        ${l("Interest without extras vs with extras applied")}
        <div class="stat-label">Total interest</div>
        <div class="stat-value">${o(t.totalInterest)}</div>
        <div class="stat-sub">Without extras: ${o(a.totalInterest)}</div>
      </div>
      <div class="stat">
        ${l(`Number of ${n.toLowerCase()}s until the loan is fully paid off`)}
        <div class="stat-label">Payoff in</div>
        <div class="stat-value">${t.periods} ${n.toLowerCase()}s</div>
        <div class="stat-sub">${i>0?`${i} earlier than without extras`:"Until the loan is repaid"}</div>
      </div>
      <div class="stat">
        ${l("Principal plus total interest. The real cost of your loan.")}
        <div class="stat-label">Total paid</div>
        <div class="stat-value">${o(e)}</div>
        <div class="stat-sub">Interest is ${((r-1)*100).toFixed(1)}% of loan</div>
      </div>
      <div class="stat">
        ${l(`The first ${n.toLowerCase()} when cumulative principal paid from EMI and extras meets or exceeds cumulative interest`)}
        <div class="stat-label">Break-even</div>
        <div class="stat-value">${t.breakEven?`${n} ${t.breakEven}`:"N/A"}</div>
        <div class="stat-sub">Principal (EMI + extras) &gt;= interest</div>
      </div>
    </div>
  `}export function renderMetrics(a,t,s){a.innerHTML=buildMetricsMarkup(t,s)}
