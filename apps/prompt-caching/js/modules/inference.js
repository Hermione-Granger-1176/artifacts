/* Inference simulator: streams generated tokens while the KV cache fills. */

import { INF_RESPONSES } from "./data.js";
import { byId, makeEl, clear } from "./dom.js";

const STEP_INTERVAL_MS = 700;

export function initInference() {
  const input = byId("infInput");
  const goBtn = byId("infGoBtn");
  const resetBtn = byId("infResetBtn");
  const tokensWrap = byId("infTokens");
  const status = byId("infStatus");
  const cacheCount = byId("infCacheCount");
  const cacheBar = byId("infCacheBar");
  if (!input || !goBtn || !tokensWrap) {
    return;
  }

  let timer = null;
  let step = 0;
  let promptTokens = [];
  let genTokens = [];

  function updateCache() {
    const total = promptTokens.length + step;
    cacheCount.textContent = String(total);
    clear(cacheBar);
    const maxCells = promptTokens.length + genTokens.length;
    for (let i = 0; i < maxCells; i += 1) {
      const cell = makeEl("div", "inf-cache-cell");
      if (i < promptTokens.length) {
        cell.classList.add("filled");
        cell.textContent = "K,V";
      } else if (i < total) {
        cell.classList.add(i === total - 1 ? "new" : "filled");
        cell.textContent = "K,V";
      } else {
        cell.classList.add("empty");
      }
      cacheBar.appendChild(cell);
    }
  }

  function reset() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
    step = 0;
    promptTokens = [];
    genTokens = [];
    clear(tokensWrap);
    clear(cacheBar);
    cacheCount.textContent = "0";
    status.textContent = "Press Generate to start.";
    goBtn.disabled = false;
  }

  function start() {
    reset();
    const text = input.value.trim();
    if (!text) {
      return;
    }
    promptTokens = text.split(/\s+/);
    genTokens = INF_RESPONSES[text] || INF_RESPONSES.default;

    for (const tok of promptTokens) {
      tokensWrap.appendChild(makeEl("span", "inf-tok prompt-tok", tok));
    }
    updateCache();
    status.textContent = `Prompt processed (${promptTokens.length} tokens cached). Generating...`;
    goBtn.disabled = true;

    timer = setInterval(() => {
      if (step >= genTokens.length) {
        clearInterval(timer);
        timer = null;
        const total = promptTokens.length + genTokens.length;
        status.textContent = `Done. ${total} total tokens. KV cache has ${total} rows.`;
        goBtn.disabled = false;
        const last = tokensWrap.querySelector(".inf-tok.current");
        if (last) {
          last.classList.remove("current");
          last.classList.add("gen-tok");
        }
        return;
      }

      const prev = tokensWrap.querySelector(".inf-tok.current");
      if (prev) {
        prev.classList.remove("current");
        prev.classList.add("gen-tok");
      }
      tokensWrap.appendChild(makeEl("span", "inf-tok current", genTokens[step]));

      step += 1;
      updateCache();
      const total = promptTokens.length + step;
      status.textContent =
        `Step ${step}: generated "${genTokens[step - 1]}". Only 1 new KV row computed, ${total - 1} reused from cache.`;
    }, STEP_INTERVAL_MS);
  }

  goBtn.addEventListener("click", start);
  if (resetBtn) {
    resetBtn.addEventListener("click", reset);
  }
}
