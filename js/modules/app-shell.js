import{createFrameScheduler as f}from"./frame-scheduler.js";import{writeStorage as v}from"./runtime.js";import{createThemeSwitchGuard as _}from"./theme-switching.js";const A=/^[./a-zA-Z0-9_-]+$/,T=`
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
`,S=`
  <div id="runtime-error" class="runtime-error visually-hidden" role="alert" aria-live="assertive">
    <p>The app failed to initialize correctly. Reload the page, or try again later.</p>
    <details id="runtime-error-details" class="runtime-error-details" hidden>
      <summary>Technical details</summary>
      <pre id="runtime-error-output" class="runtime-error-output"></pre>
      <button id="runtime-error-copy" class="runtime-error-copy" type="button" hidden>Copy error details</button>
    </details>
  </div>
`,E=`
  <button id="scroll-top" class="scroll-top" type="button" aria-label="Scroll to top" aria-hidden="true" tabindex="-1">
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <line x1="12" y1="19" x2="12" y2="5"></line>
      <polyline points="5 12 12 5 19 12"></polyline>
    </svg>
  </button>
`;function d(t,i){!t||t.childElementCount>0||(t.innerHTML=i.trim())}export function renderAppShell({documentObj:t=document,homePath:i="../../"}={}){d(t.querySelector('[data-app-shell="header"]'),T.replaceAll("__HOME_PATH__",A.test(i)?i:"../../")),d(t.querySelector('[data-app-shell="runtime-error"]'),S),d(t.querySelector('[data-app-shell="scroll-top"]'),E)}export function initAppShell({homePath:t="../../",metaThemeColors:i={dark:"rgb(20, 20, 20)",light:"rgb(248, 248, 246)"},onThemeChange:y=()=>{}}={}){renderAppShell({documentObj:document,homePath:t});const u=window,l=document.documentElement,h=document.getElementById("back-button"),n=document.getElementById("theme-toggle"),o=document.getElementById("scroll-top"),p=document.querySelector('meta[name="theme-color"]'),b=window.matchMedia("(prefers-reduced-motion: reduce)");function a(){return u.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(l.getAttribute("data-theme"))}function m(e){p&&p.setAttribute("content",e==="dark"?i.dark:i.light)}function s(){if(!n)return;const e=a(),r=e==="dark"?"light":"dark";n.setAttribute("aria-pressed",String(e==="dark")),n.setAttribute("aria-label",`Switch to ${r} theme`),n.setAttribute("title",`Switch to ${r} theme`)}const k=_(l,window);function w(e){const r=u.__ARTIFACTS_APP_THEME_BOOTSTRAP__.normalizeTheme(e);k(),l.setAttribute("data-theme",r),m(r),s(),v("theme",r),y(r)}function x(){const e=()=>{window.location.href=t};if(!document.referrer){e();return}let r;try{r=new URL(document.referrer)}catch{e();return}if(r.origin!==window.location.origin||window.history.length<=1){e();return}window.history.back()}let g=null;function c(){if(!o)return;const e=window.scrollY>280;e!==g&&(g=e,o.classList.toggle("is-visible",e),o.setAttribute("aria-hidden",String(!e)),o.tabIndex=e?0:-1)}return h&&h.addEventListener("click",x),n&&n.addEventListener("click",()=>{w(a()==="dark"?"light":"dark")}),o&&(o.addEventListener("click",()=>{const e=b.matches?"auto":"smooth";window.scrollTo({top:0,behavior:e})}),window.addEventListener("scroll",f(c),{passive:!0}),c()),m(a()),s(),{applyTheme:w,syncThemeToggle:s,updateScrollTopVisibility:c}}
