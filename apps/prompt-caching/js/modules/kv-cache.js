/* KV cache fill animation plus the no-cache / with-cache computation compare. */

import { CACHE_TOKENS, CACHE_COMPARE_TOKENS } from "./data.js";
import { byId, makeEl, clear, initSegmented } from "./dom.js";

const STEP_INTERVAL_MS = 900;

function randomVec() {
  const part = () => (Math.random() * 2 - 1).toFixed(2);
  return `[${part()}, ${part()}, ${part()}]`;
}

function initCacheAnimation() {
  const tokensWrap = byId("cacheTokens");
  const kVis = byId("kCacheVis");
  const vVis = byId("vCacheVis");
  const narration = byId("cacheNarration");
  const playBtn = /** @type {HTMLButtonElement} */ (byId("cachePlayBtn"));
  const resetBtn = byId("cacheResetBtn");
  if (!tokensWrap || !kVis || !vVis || !playBtn) {
    return;
  }

  let step = -1;
  let timer = /** @type {number | null} */ (null);

  /** @param {HTMLElement} target - Container to render rows into. */
  function renderCacheRows(target) {
    if (step < 0) {
      clear(target);
      target.appendChild(makeEl("span", "pc-empty", "Empty, press Play"));
      return;
    }
    clear(target);
    for (let i = 0; i <= step; i += 1) {
      const row = makeEl("div", `cache-row${i === step ? " is-new" : ""}`);
      row.appendChild(makeEl("span", "tok-name", CACHE_TOKENS[i]));
      row.appendChild(makeEl("span", "tok-vals", randomVec()));
      target.appendChild(row);
    }
  }

  function renderState() {
    clear(tokensWrap);
    CACHE_TOKENS.forEach((tok, i) => {
      const cached = i <= step;
      const isNew = i === step;
      let cls = "chip is-mono pc-cache-chip";
      if (isNew) {
        cls += " is-solid-blue";
      } else if (cached) {
        cls += " is-solid-amber";
      }
      tokensWrap.appendChild(makeEl("span", cls, tok));
    });

    renderCacheRows(kVis);
    renderCacheRows(vVis);

    if (step < 0) {
      narration.textContent = "Press Play to watch the cache build up one token at a time.";
    } else if (step < CACHE_TOKENS.length - 1) {
      const plural = step === 1 ? "" : "s";
      narration.replaceChildren(
        document.createTextNode("Processing "),
        makeEl("span", "pc-hl-warm", `"${CACHE_TOKENS[step]}"`),
        document.createTextNode(`. Only this token's K and V rows were computed. The ${step} previous row${plural} came straight from cache.`)
      );
    } else {
      narration.replaceChildren(
        makeEl("span", "pc-hl-teal", `Done. All ${CACHE_TOKENS.length} tokens are cached. If you send another request starting with the same prefix, all of this is reused. Zero recalculation.`)
      );
    }
  }

  function play() {
    if (timer) {
      clearInterval(timer);
    }
    step = -1;
    renderState();
    playBtn.disabled = true;
    timer = setInterval(() => {
      step += 1;
      renderState();
      if (step >= CACHE_TOKENS.length - 1) {
        clearInterval(/** @type {number} */ (timer));
        timer = null;
        playBtn.disabled = false;
      }
    }, STEP_INTERVAL_MS);
  }

  function reset() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    step = -1;
    playBtn.disabled = false;
    renderState();
  }

  playBtn.addEventListener("click", play);
  if (resetBtn) {
    resetBtn.addEventListener("click", reset);
  }
  renderState();
}

function initCacheCompare() {
  const toggle = byId("cacheCompareToggle");
  const vis = byId("cacheCompareVis");
  const caption = byId("cacheCompareCaption");
  if (!toggle || !vis || !caption) {
    return;
  }

  let mode = "no";

  function render() {
    clear(vis);
    const wrap = makeEl("div", "pc-row");

    if (mode === "no") {
      for (const tok of CACHE_COMPARE_TOKENS) {
        wrap.appendChild(makeEl("span", "chip is-mono pc-pill is-red", `${tok} (Q,K,V)`));
      }
      vis.appendChild(wrap);
      caption.replaceChildren(
        makeEl("strong", "pc-hl-rose", "15 matrix multiplications"),
        document.createTextNode(" (3 projections x 5 tokens). Every token recomputed from scratch, every iteration.")
      );
      return;
    }

    CACHE_COMPARE_TOKENS.forEach((tok, i) => {
      const last = i === CACHE_COMPARE_TOKENS.length - 1;
      wrap.appendChild(makeEl("span", `chip is-mono pc-pill ${last ? "is-blue" : "is-green"}`, `${tok} ${last ? "(Q,K,V)" : "(cached)"}`));
    });
    vis.appendChild(wrap);
    caption.replaceChildren(
      makeEl("strong", "pc-hl-teal", "3 matrix multiplications"),
      document.createTextNode(" (only the new token). 4 tokens' K and V read from cache. That is an "),
      makeEl("strong", "pc-hl-accent", "80% reduction"),
      document.createTextNode(" in compute.")
    );
  }

  initSegmented(toggle, (/** @type {HTMLElement} */ btn) => {
    mode = btn.dataset.compare ?? "";
    render();
  });
  render();
}

export function initKvCache() {
  initCacheAnimation();
  initCacheCompare();
}
