/* Inference simulator: streams generated tokens while the KV cache fills. */

import { INF_RESPONSES } from "./data.js";
import { byId, makeEl, clear, prefersReducedMotion, reserveSpace, longestText } from "./dom.js";

const STEP_INTERVAL_MS = 700;
const IDLE_STATUS = "Hit Generate to start.";

/** @param {number} cached - Prompt tokens in the cache. @returns {string} Status shown while generating starts. */
const promptStatus = (cached) => `Prompt processed (${cached} tokens cached). Generating...`;
/**
 * @param {number} step - One-based generation step.
 * @param {string} token - Token generated at this step.
 * @param {number} reused - Rows reused from the cache.
 * @returns {string} Status shown while a token streams.
 */
const stepStatus = (step, token, reused) =>
  `Step ${step}: generated "${token}". Only 1 new KV row computed, ${reused} reused from cache.`;
/** @param {number} total - Total tokens. @returns {string} Status shown when generation ends. */
const doneStatus = (total) => `Done. ${total} total tokens. KV cache has ${total} rows.`;

/** @param {string} prompt - Prompt text. @returns {string[]} Its tokens, one per word. */
const promptWords = (prompt) => prompt.split(/\s+/);
/** @param {string} prompt - Prompt text. @returns {string[]} The tokens the model generates for it. */
const responseFor = (prompt) => INF_RESPONSES[/** @type {keyof typeof INF_RESPONSES} */ (prompt)];

/**
 * Longest status line of each kind across every prompt, so the status box can
 * reserve the room the wordiest run needs.
 * @param {string[]} prompts - Prompt names.
 * @returns {string[]} One candidate per status kind.
 */
function statusCandidates(prompts) {
  /** @type {string[][]} */
  const [started, stepped, done] = [[], [], []];
  for (const prompt of prompts) {
    const cached = promptWords(prompt).length;
    const tokens = responseFor(prompt);
    started.push(promptStatus(cached));
    done.push(doneStatus(cached + tokens.length));
    tokens.forEach((token, i) => stepped.push(stepStatus(i + 1, token, cached + i)));
  }
  return [IDLE_STATUS, longestText(started), longestText(stepped), longestText(done)];
}

export function initInference() {
  const promptsWrap = byId("infPrompts");
  const goBtn = /** @type {HTMLButtonElement} */ (byId("infGoBtn"));
  const resetBtn = byId("infResetBtn");
  const tokensWrap = byId("infTokens");
  const status = byId("infStatus");
  const cacheCount = byId("infCacheCount");
  const cacheBar = byId("infCacheBar");
  if (!promptsWrap || !goBtn || !tokensWrap) {
    return;
  }

  const prompts = Object.keys(INF_RESPONSES);
  // The stream and the status line reserve the room of the longest run up front,
  // so no chip or status change moves the cache bar and the page below.
  reserveSpace(tokensWrap, prompts.map((prompt) => {
    const ghost = makeEl("div", "pc-inf-tokens");
    const final = [...promptWords(prompt), ...responseFor(prompt)];
    ghost.append(...final.map((tok) => makeEl("span", "chip is-mono inf-tok", tok)));
    return ghost;
  }));
  reserveSpace(status, statusCandidates(prompts).map((text) => makeEl("div", "pc-inf-status", text)));
  let selected = prompts[0];
  let timer = /** @type {number | null} */ (null);
  let step = 0;
  /** @type {string[]} */
  let promptTokens = [];
  /** @type {string[]} */
  let genTokens = [];

  const chipEls = prompts.map((prompt) => {
    const chip = /** @type {HTMLButtonElement} */ (makeEl("button", "", prompt));
    chip.type = "button";
    chip.addEventListener("click", () => {
      if (timer || prompt === selected) {
        return;
      }
      selected = prompt;
      syncChips();
      reset();
    });
    promptsWrap.appendChild(chip);
    return chip;
  });

  function syncChips() {
    prompts.forEach((prompt, i) => {
      chipEls[i].classList.toggle("active", prompt === selected);
      chipEls[i].setAttribute("aria-pressed", String(prompt === selected));
    });
  }
  syncChips();

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

  function stopTimer() {
    if (timer) {
      clearInterval(timer);
      timer = null;
    }
  }

  /** Recolor the token generated last step from "current" to settled amber. */
  function settleCurrentToken() {
    const current = tokensWrap.querySelector(".inf-tok.current");
    if (current) {
      current.classList.remove("current", "is-solid-amber");
      current.classList.add("is-amber");
    }
  }

  function reset() {
    stopTimer();
    step = 0;
    promptTokens = [];
    genTokens = [];
    clear(tokensWrap);
    clear(cacheBar);
    cacheCount.textContent = "0";
    status.textContent = IDLE_STATUS;
    goBtn.disabled = false;
  }

  /** Stream the next generated token into the chip row and the cache bar. */
  function generateToken() {
    settleCurrentToken();
    tokensWrap.appendChild(makeEl("span", "chip is-mono inf-tok is-solid-amber current", genTokens[step]));

    step += 1;
    updateCache();
    status.textContent = stepStatus(step, genTokens[step - 1], promptTokens.length + step - 1);
  }

  function finish() {
    stopTimer();
    status.textContent = doneStatus(promptTokens.length + genTokens.length);
    goBtn.disabled = false;
    settleCurrentToken();
  }

  function start() {
    reset();
    promptTokens = promptWords(selected);
    genTokens = responseFor(selected);

    for (const tok of promptTokens) {
      tokensWrap.appendChild(makeEl("span", "chip is-mono inf-tok", tok));
    }
    updateCache();
    status.textContent = promptStatus(promptTokens.length);
    goBtn.disabled = true;

    if (prefersReducedMotion()) {
      // No streaming under reduced motion: show the finished run at once.
      while (step < genTokens.length) {
        generateToken();
      }
      finish();
      return;
    }

    timer = setInterval(() => {
      if (step >= genTokens.length) {
        finish();
        return;
      }
      generateToken();
    }, STEP_INTERVAL_MS);
  }

  goBtn.addEventListener("click", start);
  if (resetBtn) {
    resetBtn.addEventListener("click", reset);
  }
}
