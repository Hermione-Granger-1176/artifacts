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

  function render() {
    const text = input.value;
    const tokens = bpeTokenize(text);
    const words = text.trim() ? text.trim().split(/\s+/).length : 0;

    tokCount.textContent = String(tokens.length);
    wordCount.textContent = String(words);
    charCount.textContent = String(text.length);

    clear(output);

    if (viewMode === "text") {
      tokens.forEach((tok, i) => {
        if (/^\s+$/.test(tok)) {
          output.appendChild(makeEl("span", "", tok));
          return;
        }
        const span = makeEl("span", `pc-tok pc-c${i % 10}`, tok);
        span.title = `Token ${i + 1}: "${tok}" (ID: ${hashToken(tok)})`;
        output.appendChild(span);
      });
      return;
    }

    tokens.forEach((tok, i) => {
      if (/^\s+$/.test(tok)) {
        return;
      }
      const span = makeEl("span", `pc-tokid pc-c${i % 10}`, String(hashToken(tok)));
      span.title = `"${tok}"`;
      output.appendChild(span);
    });
  }

  initSegmented(toggle, (btn) => {
    viewMode = btn.dataset.view;
    render();
  });

  input.addEventListener("input", render);
  render();
}
