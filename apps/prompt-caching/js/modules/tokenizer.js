/* Live BPE-style tokenizer demo: colors tokens or shows their pseudo IDs. */

import { bpeTokenize, hashToken } from "./math.js";
import { byId, makeEl, clear, initSegmented } from "./dom.js";

export function initTokenizer() {
  const input = /** @type {HTMLTextAreaElement} */ (byId("tokenInput"));
  const output = byId("tokenOutput");
  const toggle = byId("tokenView");
  const tokCount = byId("tokCount");
  const wordCount = byId("wordCount");
  const charCount = byId("charCount");
  if (!input || !output || !toggle) {
    return;
  }

  let viewMode = "text";

  // Both views live in the output at once, stacked in one grid cell, and the
  // inactive one is hidden. The box therefore always fits the taller view for
  // the current text and width, so switching views never moves what follows.
  const textLayer = makeEl("div", "pc-token-layer");
  const idsLayer = makeEl("div", "pc-token-layer");
  output.replaceChildren(textLayer, idsLayer);

  function showView() {
    const showText = viewMode === "text";
    textLayer.classList.toggle("is-hidden", !showText);
    idsLayer.classList.toggle("is-hidden", showText);
  }

  function render() {
    const text = input.value;
    const tokens = bpeTokenize(text);
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;

    tokCount.textContent = String(tokens.length);
    wordCount.textContent = String(words);
    charCount.textContent = String(Array.from(text).length);

    clear(textLayer);
    clear(idsLayer);

    tokens.forEach((tok, i) => {
      if (/^\s+$/.test(tok)) {
        textLayer.appendChild(makeEl("span", "", tok));
        return;
      }
      const span = makeEl("span", `pc-tok pc-c${i % 10}`, tok);
      span.title = `Token ${i + 1}: "${tok}" (ID: ${hashToken(tok)})`;
      textLayer.appendChild(span);

      const idSpan = makeEl("span", `pc-tokid pc-c${i % 10}`, String(hashToken(tok)));
      idSpan.title = `"${tok}"`;
      idsLayer.appendChild(idSpan);
    });
    showView();
  }

  initSegmented(toggle, (/** @type {HTMLElement} */ btn) => {
    viewMode = btn.dataset.view ?? "";
    showView();
  });

  input.addEventListener("input", render);
  render();
}
