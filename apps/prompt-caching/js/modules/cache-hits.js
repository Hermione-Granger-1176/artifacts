/* Cross-request cache-hit visualiser with a live TTL countdown. */

import { CHV_SYSTEM, CHV_QUERIES } from "./data.js";
import { formatTTL } from "./math.js";
import { byId, makeEl, clear, prefersReducedMotion } from "./dom.js";
import { formatPercent } from "../../../../js/modules/formatting.js";

const MAX_VISIBLE = 5;
const TTL_SECONDS = 300;
const BLOCK_DELAY_MS = 80;

export function initCacheHits() {
  const sendBtn = byId("chvSendBtn");
  const clearBtn = byId("chvClearBtn");
  const reqs = byId("chvReqs");
  const ttlLabel = byId("chvTTL");
  if (!sendBtn || !reqs || !ttlLabel) {
    return;
  }

  let reqCount = 0;
  let cachedPrefixTokens = 0;
  let ttlTimer = /** @type {number | null} */ (null);
  let ttlSec = 0;

  function stopTTL() {
    if (ttlTimer) {
      clearInterval(ttlTimer);
      ttlTimer = null;
    }
  }

  function resetTTL() {
    ttlSec = TTL_SECONDS;
    stopTTL();
    ttlTimer = setInterval(() => {
      ttlSec -= 1;
      if (ttlSec <= 0) {
        stopTTL();
        cachedPrefixTokens = 0;
      }
      ttlLabel.textContent = formatTTL(ttlSec);
    }, 1000);
  }

  /**
   * @param {Element[]} blocks - Block elements to animate.
   * @param {string} hitClass - Class applied on hit.
   * @param {() => void} [onDone] - Optional completion callback.
   * @returns {void}
   */
  function animateBlocks(blocks, hitClass, onDone) {
    if (prefersReducedMotion()) {
      // No left-to-right sweep under reduced motion: color every block at once.
      for (const block of blocks) {
        block.classList.remove("waiting");
        block.classList.add(hitClass);
      }
      onDone?.();
      return;
    }
    let i = 0;
    const timer = setInterval(() => {
      if (i >= blocks.length) {
        clearInterval(timer);
        onDone?.();
        return;
      }
      blocks[i].classList.remove("waiting");
      blocks[i].classList.add(hitClass);
      i += 1;
    }, BLOCK_DELAY_MS);
  }

  /**
   * @param {string[]} tokens - Token labels for one prompt segment.
   * @returns {HTMLElement} A row of waiting blocks, one per token.
   */
  function buildBlocks(tokens) {
    const wrap = makeEl("div", "chv-blocks");
    for (const tok of tokens) {
      wrap.appendChild(makeEl("div", "chv-block waiting", tok));
    }
    return wrap;
  }

  function send() {
    if (reqCount === 0) {
      clear(reqs);
    }

    const query = CHV_QUERIES[reqCount % CHV_QUERIES.length];
    const sysHit = cachedPrefixTokens > 0;
    const totalTokens = CHV_SYSTEM.length + query.length;
    const cachedCount = sysHit ? CHV_SYSTEM.length : 0;
    const computedCount = totalTokens - cachedCount;
    const savingsPct = cachedCount > 0 ? (cachedCount / totalTokens) * 90 : 0;

    const reqDiv = makeEl("div", "chv-req");

    const header = makeEl("div", "chv-req-header");
    header.appendChild(makeEl("span", "chv-req-label", `Request #${reqCount + 1}`));
    const statusText = sysHit
      ? `${cachedCount} cached + ${computedCount} computed (~${formatPercent(savingsPct, 0)} saved)`
      : `${cachedCount} cached + ${computedCount} computed (cold start, nothing cached yet)`;
    header.appendChild(makeEl("span", `chv-req-status ${sysHit ? "is-hit" : "is-miss"}`, statusText));
    reqDiv.appendChild(header);

    reqDiv.appendChild(makeEl(
      "div",
      "chv-row-label sys",
      `System prompt ${sysHit ? "(cache hit, reused)" : "(cache miss, computed)"}`
    ));
    const sysBlocksWrap = buildBlocks(CHV_SYSTEM);
    reqDiv.appendChild(sysBlocksWrap);

    reqDiv.appendChild(makeEl("div", "chv-divider"));
    reqDiv.appendChild(makeEl("div", "chv-row-label usr", "User query (always computed, different each time)"));
    const usrBlocksWrap = buildBlocks(query);
    reqDiv.appendChild(usrBlocksWrap);

    reqs.appendChild(reqDiv);

    const sysBlocks = Array.from(sysBlocksWrap.children);
    const usrBlocks = Array.from(usrBlocksWrap.children);
    animateBlocks(sysBlocks, sysHit ? "cached" : "miss", () => animateBlocks(usrBlocks, "miss"));

    cachedPrefixTokens = CHV_SYSTEM.length;
    reqCount += 1;
    resetTTL();

    const allReqs = reqs.querySelectorAll(".chv-req");
    if (allReqs.length > MAX_VISIBLE) {
      allReqs[0].remove();
      reqs.querySelector(".chv-evicted")?.remove();
      const evictedCount = reqCount - MAX_VISIBLE;
      const notice = makeEl(
        "div",
        "chv-evicted",
        `${evictedCount} earlier request${evictedCount > 1 ? "s" : ""} evicted (context window cleanup)`
      );
      reqs.insertBefore(notice, reqs.firstChild);
    }

    // The log has a fixed height and scrolls inside itself. Scrolling the list
    // (never scrollIntoView) keeps the page where the reader left it.
    reqs.scrollTo({ top: reqs.scrollHeight, behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }

  function clearCache() {
    cachedPrefixTokens = 0;
    reqCount = 0;
    stopTTL();
    ttlLabel.textContent = formatTTL(TTL_SECONDS);
    clear(reqs);
    reqs.appendChild(makeEl("div", "pc-empty", 'No requests yet. Click "Send request" to begin.'));
  }

  sendBtn.addEventListener("click", send);
  if (clearBtn) {
    clearBtn.addEventListener("click", clearCache);
  }
}
