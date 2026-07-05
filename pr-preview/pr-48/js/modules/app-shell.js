import{writeStorage as b}from"./runtime.js";const k=/^[./a-zA-Z0-9_-]+$/,x=`
  <header class="app-header">
    <div class="app-header-inner">
      <div class="app-nav">
        <button id="back-button" class="icon-button" type="button" aria-label="Go back" title="Go back">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m15 18-6-6 6-6"></path>
          </svg>
        </button>
        <a href="__HOME_PATH__" class="brand-link" aria-label="Go to Artifacts home">
          <svg class="brand-mark" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128" aria-hidden="true">
            <rect fill="rgb(217, 119, 6)" x="14" y="20" width="84" height="92" rx="18"></rect>
            <rect fill="rgb(243, 214, 166)" x="26" y="12" width="84" height="92" rx="18"></rect>
            <line x1="42" y1="32" x2="94" y2="32" stroke="rgb(196, 168, 130)" stroke-width="4" stroke-linecap="round"></line>
            <line x1="42" y1="52" x2="94" y2="52" stroke="rgb(196, 168, 130)" stroke-width="4" stroke-linecap="round"></line>
            <line x1="42" y1="72" x2="86" y2="72" stroke="rgb(196, 168, 130)" stroke-width="4" stroke-linecap="round"></line>
          </svg>
          <span class="brand-name">Artifacts</span>
        </a>
      </div>
      <button id="theme-toggle" class="icon-button" type="button" aria-label="Switch to dark theme" aria-pressed="false" title="Switch to dark theme">
        <svg class="icon-sun" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="5"></circle>
          <line x1="12" y1="1" x2="12" y2="3"></line>
          <line x1="12" y1="21" x2="12" y2="23"></line>
          <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
          <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
          <line x1="1" y1="12" x2="3" y2="12"></line>
          <line x1="21" y1="12" x2="23" y2="12"></line>
          <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
          <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
        </svg>
        <svg class="icon-moon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
        </svg>
      </button>
    </div>
  </header>
`,v=`
  <div id="runtime-error" class="runtime-error visually-hidden" role="alert" aria-live="assertive">
    <p>The app failed to initialize correctly. Reload the page, or try again later.</p>
    <details id="runtime-error-details" class="runtime-error-details" hidden>
      <summary>Technical details</summary>
      <pre id="runtime-error-output" class="runtime-error-output"></pre>
      <button id="runtime-error-copy" class="runtime-error-copy" type="button" hidden>Copy error details</button>
    </details>
  </div>
`,_=`
  <button id="scroll-top" class="scroll-top" type="button" aria-label="Scroll to top" aria-hidden="true" tabindex="-1">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <polyline points="18 15 12 9 6 15"></polyline>
    </svg>
  </button>
`;function c(t,n){!t||t.childElementCount>0||(t.innerHTML=n.trim())}export function renderAppShell({documentObj:t=document,homePath:n="../../"}={}){c(t.querySelector('[data-app-shell="header"]'),x.replaceAll("__HOME_PATH__",k.test(n)?n:"../../")),c(t.querySelector('[data-app-shell="runtime-error"]'),v),c(t.querySelector('[data-app-shell="scroll-top"]'),_)}export function initAppShell({homePath:t="../../",metaThemeColors:n={dark:"rgb(30, 26, 20)",light:"rgb(245, 239, 230)"},onThemeChange:w=()=>{}}={}){renderAppShell({documentObj:document,homePath:t});const d=document.documentElement,u=document.getElementById("back-button"),i=document.getElementById("theme-toggle"),o=document.getElementById("scroll-top"),h=document.querySelector('meta[name="theme-color"]'),g=window.matchMedia("(prefers-reduced-motion: reduce)");function l(){return window.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(d.getAttribute("data-theme"))}function p(e){h&&h.setAttribute("content",n[e]||n.light)}function a(){if(!i)return;const e=l(),r=e==="dark"?"light":"dark";i.setAttribute("aria-pressed",String(e==="dark")),i.setAttribute("aria-label",`Switch to ${r} theme`),i.setAttribute("title",`Switch to ${r} theme`)}function m(e){const r=window.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(e);d.setAttribute("data-theme",r),p(r),a(),b("theme",r),w(r)}function y(){const e=()=>{window.location.href=t};if(!document.referrer){e();return}let r;try{r=new URL(document.referrer)}catch{e();return}if(r.origin!==window.location.origin||window.history.length<=1){e();return}window.history.back()}function s(){if(!o)return;const e=window.scrollY>280;o.classList.toggle("is-visible",e),o.setAttribute("aria-hidden",String(!e)),o.tabIndex=e?0:-1}return u&&u.addEventListener("click",y),i&&i.addEventListener("click",()=>{m(l()==="dark"?"light":"dark")}),o&&(o.addEventListener("click",()=>{const e=g.matches?"auto":"smooth";window.scrollTo({top:0,behavior:e})}),window.addEventListener("scroll",s,{passive:!0}),s()),p(l()),a(),{applyTheme:m,syncThemeToggle:a,updateScrollTopVisibility:s}}
