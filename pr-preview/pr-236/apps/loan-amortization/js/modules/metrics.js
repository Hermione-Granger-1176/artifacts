import{escapeAttribute as $}from"../../../../js/modules/html-escape.js";function u(a,t=""){const e=$(a);return`<button type="button" class="${t?`info-tip ${t}`:"info-tip"}" data-tip="${e}" aria-label="${e}">?</button>`}export function formatPeriodsAsDuration(a,t){const e=Math.round(a*12/t);if(e<1)return"under 1m";const s=Math.floor(e/12),i=e%12;return[s>0?`${s}y`:"",i>0?`${i}m`:""].filter(Boolean).join(" ")}function v({savings:a,periodsSaved:t,periodsPerYear:e},s){const i=[];return a>1&&i.push(`Saves ${s(a)}`),t>0&&i.push(`${formatPeriodsAsDuration(t,e)} sooner`),i.length>0?`<span class="chip is-green">${i.join(" \xB7 ")}</span>`:""}function l({tip:a,label:t,value:e,sub:s}){return`
      <div class="stat">
        ${u(a)}
        <div class="stat-label">${t}</div>
        <div class="stat-value">${e}</div>
        <div class="stat-sub">${s}</div>
      </div>`}export function buildMetricsMarkup({base:a,extra:t,savings:e,periodsSaved:s,totalPaid:i,costRatio:p,label:r,periodsPerYear:c},n){const o=r.toLowerCase(),d=t.totalExtra>0?`Plus ${n(t.totalExtra)} in extra payments over the loan`:"Fixed payment, no extras";return`
    <div class="loan-hero">
      <div class="loan-hero-main">
        <div class="loan-hero-label">
          <span>${r}ly EMI</span>
          ${u(`Fixed payment amount each ${o}, excluding extra payments`,"is-start")}
        </div>
        <div class="loan-hero-value">${n(a.emi)}</div>
        <div class="loan-hero-sub">${d}</div>
      </div>
      ${v({savings:e,periodsSaved:s,periodsPerYear:c},n)}
    </div>
    <div class="stat-grid loan-kpis">
      ${l({tip:"Interest without extras vs with extras applied",label:"Total interest",value:n(t.totalInterest),sub:`Without extras: ${n(a.totalInterest)}`})}
      ${l({tip:`Number of ${o}s until the loan is fully paid off`,label:"Payoff in",value:`${t.periods} ${o}s`,sub:s>0?`${s} earlier than without extras`:"Until the loan is repaid"})}
      ${l({tip:"Principal plus total interest. The real cost of your loan.",label:"Total paid",value:n(i),sub:`Interest is ${((p-1)*100).toFixed(1)}% of loan`})}
      ${l({tip:`The first ${o} when cumulative principal paid from EMI and extras meets or exceeds cumulative interest`,label:"Break-even",value:t.breakEven?`${r} ${t.breakEven}`:"N/A",sub:"Principal (EMI + extras) &gt;= interest"})}
    </div>
  `}export function renderMetrics(a,t,e){a.innerHTML=buildMetricsMarkup(t,e)}
