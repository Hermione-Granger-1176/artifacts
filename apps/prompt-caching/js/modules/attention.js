/* Attention section: the Q/K/V step explorer with clickable dot-products, the
 * hover-able attention grid, and the interactive softmax sliders. */

import { ATTN_DATA, AGRID_WORDS, AGRID_WEIGHTS, SMX_TOKENS, SMX_INITIAL_SCORES } from "./data.js";
import { softmax } from "./math.js";
import { byId, makeEl, clear } from "./dom.js";

const fmt = (v) => (typeof v === "number" ? v.toFixed(2) : v);
const fmtRow = (row) => row.map(fmt);

function buildMatrix(id, label, rows, clickable) {
  const cols = rows[0].length;
  const wrap = makeEl("div", "pc-matrix");
  const lbl = makeEl("div", "pc-matrix-label");
  lbl.appendChild(document.createTextNode(`${label} `));
  lbl.appendChild(makeEl("span", "pc-dim", `(${rows.length}x${cols})`));
  wrap.appendChild(lbl);

  const grid = makeEl("div", "pc-matrix-grid");
  grid.style.gridTemplateColumns = `repeat(${cols}, minmax(60px, auto))`;
  rows.forEach((row, ri) => {
    row.forEach((value, ci) => {
      const cell = makeEl("div", `pc-matrix-cell${clickable ? " clickable" : ""}`, String(value));
      cell.dataset.mx = id;
      cell.dataset.r = String(ri);
      cell.dataset.c = String(ci);
      grid.appendChild(cell);
    });
  });
  wrap.appendChild(grid);
  return wrap;
}

function opNode(symbol, isText = false) {
  return makeEl("span", `pc-op${isText ? " is-text" : ""}`, symbol);
}

function term(parent, aVal, bVal, withPlus) {
  if (withPlus) {
    parent.appendChild(makeEl("span", "op-plus", " + "));
  }
  parent.appendChild(document.createTextNode("("));
  parent.appendChild(makeEl("span", "op-row", fmt(aVal)));
  parent.appendChild(makeEl("span", "op-mult", " × "));
  parent.appendChild(makeEl("span", "op-col", typeof bVal === "number" ? fmt(bVal) : bVal));
  parent.appendChild(document.createTextNode(")"));
}

function clearHighlights(visual) {
  for (const el of visual.querySelectorAll(".pc-matrix-cell.hl-row, .pc-matrix-cell.hl-col, .pc-matrix-cell.hl-result")) {
    el.classList.remove("hl-row", "hl-col", "hl-result");
  }
}

function showMatrixProduct(visual, dot, ids, coords, data) {
  const { aId, bId, outId } = ids;
  const { r, c } = coords;
  const aRow = data.a[r];
  const bCol = data.b.map((row) => row[c]);
  const result = data.result[r][c];

  clear(dot);
  const calc = makeEl("div", "pc-dotcalc");
  calc.appendChild(makeEl("div", "pc-dotcalc-hint", `Row ${r + 1} x Column ${c + 1}:`));
  const body = document.createElement("div");
  aRow.forEach((value, i) => term(body, value, bCol[i], i > 0));
  body.appendChild(document.createTextNode(" = "));
  body.appendChild(makeEl("span", "op-result", fmt(result)));
  calc.appendChild(body);
  dot.appendChild(calc);

  clearHighlights(visual);
  for (const el of visual.querySelectorAll(`[data-mx="${aId}"][data-r="${r}"]`)) {
    el.classList.add("hl-row");
  }
  for (const el of visual.querySelectorAll(`[data-mx="${bId}"][data-c="${c}"]`)) {
    el.classList.add("hl-col");
  }
  const resCell = visual.querySelector(`[data-mx="${outId}"][data-r="${r}"][data-c="${c}"]`);
  if (resCell) {
    resCell.classList.add("hl-result");
  }
}

function bindClickable(visual, outId, handler) {
  for (const cell of visual.querySelectorAll(`[data-mx="${outId}"].clickable`)) {
    cell.addEventListener("click", () => {
      handler(Number.parseInt(cell.dataset.r, 10), Number.parseInt(cell.dataset.c, 10), cell);
    });
  }
}

function defaultHint(dot) {
  clear(dot);
  dot.appendChild(makeEl("div", "pc-hint", "Click any cell in the output matrix to see how it was calculated."));
}

function initStepper() {
  const stepper = byId("attnStepper");
  const titleEl = byId("attnStepTitle");
  const descEl = byId("attnStepDesc");
  const visual = byId("attnStepVisual");
  const dot = byId("dotProduct");
  if (!stepper || !titleEl || !descEl || !visual || !dot) {
    return;
  }

  let maskOn = true;
  let current = 0;

  // Each step renders inside a shared window-style frame (same look as the
  // pseudocode cards); `frame` points at the current title and body elements.
  // Both are populated by the step builder below before any draw() runs, so
  // they are typed as non-null elements.
  const frame = /** @type {{ title: HTMLElement, body: HTMLElement }} */ (
    /** @type {unknown} */ ({ title: null, body: null })
  );

  const steps = [
    {
      title: "1. Compute Q and K",
      desc: "Multiply the embedding matrix by a learned weight matrix. Toggle between WQ and WK, click any cell in the result to see the exact dot product behind it, and scramble the weights to see why training them matters.",
      head: "Q = embeddings × WQ",
      render() {
        const K = ATTN_DATA.Kt[0].map((_, r) => ATTN_DATA.Kt.map((row) => row[r]));
        const trained = {
          Q: { W: ATTN_DATA.WQ, out: ATTN_DATA.Q },
          K: { W: ATTN_DATA.WK, out: K }
        };
        let mode = "Q";
        let scrambled = false;
        let live = trained.Q;

        const round2 = (value) => Math.round(value * 100) / 100;

        function scramble() {
          const W = ATTN_DATA.WQ.map((row) => row.map(() => round2(Math.random() * 2 - 1)));
          const out = ATTN_DATA.emb.map((row) =>
            W[0].map((_, c) => round2(row.reduce((acc, value, k) => acc + value * W[k][c], 0))));
          scrambled = true;
          live = { W, out };
          draw();
        }

        function setMode(next) {
          mode = next;
          scrambled = false;
          live = trained[next];
          draw();
        }

        function draw() {
          clear(frame.body);
          frame.title.textContent = `${mode} = embeddings × ${scrambled ? "random W" : `W${mode}`}`;

          const controls = makeEl("div", "pc-attn-controls");
          const toggle = makeEl("div", "type-toggle");
          toggle.setAttribute("role", "group");
          toggle.setAttribute("aria-label", "Projection");
          for (const m of ["Q", "K"]) {
            const btn = makeEl("button", m === mode && !scrambled ? "active" : "", `W${m} → ${m}`);
            btn.type = "button";
            btn.addEventListener("click", () => setMode(m));
            toggle.appendChild(btn);
          }
          controls.appendChild(toggle);
          const scrambleBtn = makeEl("button", "btn pc-btn-outline pc-btn-sm", "Scramble weights");
          scrambleBtn.type = "button";
          scrambleBtn.addEventListener("click", scramble);
          controls.appendChild(scrambleBtn);
          frame.body.appendChild(controls);

          const row = makeEl("div", "pc-attn-matrices");
          row.append(
            buildMatrix("emb1", "embeddings", ATTN_DATA.emb.map(fmtRow), false),
            opNode("×"),
            buildMatrix("W1", scrambled ? "random W" : `W${mode}`, live.W.map(fmtRow), false),
            opNode("="),
            buildMatrix("out1", scrambled ? `${mode} (garbage)` : mode, live.out.map(fmtRow), true)
          );
          frame.body.appendChild(row);

          if (scrambled) {
            frame.body.appendChild(makeEl(
              "div",
              "pc-attn-status",
              `Random weights produce a meaningless ${mode}. Training nudges the weights until the outputs become useful. This scramble stays in this step: steps 2 to 5 keep using the trained weights, and picking W${mode} above restores them here too.`
            ));
          }

          defaultHint(dot);
          bindClickable(visual, "out1", (r, c) => {
            showMatrixProduct(visual, dot,
              { aId: "emb1", bId: "W1", outId: "out1" },
              { r, c },
              { a: ATTN_DATA.emb, b: live.W, result: live.out });
          });
        }

        draw();
      }
    },
    {
      title: "2. Score every token pair",
      desc: "Multiply Q by the transpose of K. The result is a score for every pair of tokens. Click any score cell to see the exact dot product that produced it.",
      head: "scores = Q × Kᵀ",
      render() {
        const row = makeEl("div", "pc-attn-matrices");
        row.append(
          buildMatrix("Q2", "Q", ATTN_DATA.Q.map(fmtRow), false),
          opNode("×"),
          buildMatrix("Kt2", "Kᵀ", ATTN_DATA.Kt.map(fmtRow), false),
          opNode("="),
          buildMatrix("scores2", "scores", ATTN_DATA.scores.map(fmtRow), true)
        );
        frame.body.appendChild(row);
        defaultHint(dot);
        bindClickable(visual, "scores2", (r, c) => {
          showMatrixProduct(visual, dot,
            { aId: "Q2", bId: "Kt2", outId: "scores2" },
            { r, c },
            { a: ATTN_DATA.Q, b: ATTN_DATA.Kt, result: ATTN_DATA.scores });
        });
      }
    },
    {
      title: "3. Mask future tokens",
      desc: "Apply a triangular mask. Toggle the mask below to see before and after. Future tokens get set to negative infinity so softmax turns them into zero.",
      head: "masked = mask(scores)",
      render() {
        const display = ATTN_DATA.scores.map((row, ri) =>
          row.map((value, ci) => (maskOn && ci > ri ? "-∞" : fmt(value))));
        const label = maskOn ? "masked scores" : "raw scores (no mask)";

        const row = makeEl("div", "pc-attn-matrices");
        row.appendChild(buildMatrix("mask3", label, display, false));
        frame.body.appendChild(row);

        const toggleLabel = makeEl("label", "pc-mask-toggle pc-attn-center");
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = maskOn;
        checkbox.addEventListener("change", () => {
          maskOn = checkbox.checked;
          renderStep(2);
        });
        toggleLabel.appendChild(checkbox);
        toggleLabel.appendChild(document.createTextNode(" Apply causal mask"));
        frame.body.appendChild(toggleLabel);

        frame.body.appendChild(makeEl(
          "div",
          `pc-mask-msg ${maskOn ? "is-rose" : "is-warm"} pc-attn-center`,
          maskOn
            ? "Upper triangle → -∞ (future tokens cannot influence past)"
            : 'Without masking, token 1 can "see" tokens 2, 3, 4. That is cheating.'
        ));

        clear(dot);
        dot.appendChild(makeEl(
          "div",
          "pc-hint",
          "Toggle the checkbox to see how masking changes the scores matrix. Negative infinity ensures e^(-∞) = 0 in softmax."
        ));
      }
    },
    {
      title: "4. Softmax into weights",
      desc: "Softmax converts each row into probabilities summing to 1. Click any weight to see the e^x calculation that produced it.",
      head: "weights = softmax(masked)",
      render() {
        const maskedDisplay = ATTN_DATA.scores.map((row, ri) =>
          row.map((value, ci) => (ci > ri ? "-∞" : fmt(value))));
        const row = makeEl("div", "pc-attn-matrices");
        row.append(
          buildMatrix("masked4", "masked", maskedDisplay, false),
          opNode("softmax →", true),
          buildMatrix("wt4", "weights", ATTN_DATA.weights.map(fmtRow), true)
        );
        frame.body.appendChild(row);
        defaultHint(dot);
        bindClickable(visual, "wt4", (r, c, cell) => {
          clear(dot);
          clearHighlights(visual);
          cell.classList.add("hl-result");
          const calc = makeEl("div", "pc-dotcalc");
          if (c > r) {
            calc.appendChild(makeEl("div", "pc-dotcalc-hint", `weights[${r + 1}][${c + 1}]:`));
            const body = document.createElement("div");
            body.appendChild(document.createTextNode("e^(-∞) = 0, so this weight is "));
            body.appendChild(makeEl("span", "op-result", "0.00"));
            body.appendChild(document.createTextNode(" (masked future token)"));
            calc.appendChild(body);
            dot.appendChild(calc);
            return;
          }
          const maskedRow = ATTN_DATA.scores[r].map((value, ci) => (ci > r ? -Infinity : value));
          const sumExp = maskedRow.reduce((acc, value) => acc + Math.exp(value), 0);
          const score = ATTN_DATA.scores[r][c];
          calc.appendChild(makeEl("div", "pc-dotcalc-hint", `weights[${r + 1}][${c + 1}] = e^score / sum of all e^scores in row ${r + 1}:`));
          const body = document.createElement("div");
          body.appendChild(makeEl("span", "op-row", `e^${fmt(score)}`));
          body.appendChild(document.createTextNode(" / "));
          body.appendChild(makeEl("span", "op-col", sumExp.toFixed(3)));
          body.appendChild(document.createTextNode(" = "));
          body.appendChild(makeEl("span", "op-result", fmt(ATTN_DATA.weights[r][c])));
          calc.appendChild(body);
          dot.appendChild(calc);
        });
      }
    },
    {
      title: "5. Mix with V to get output",
      desc: "Multiply the attention weights by V. Click any output cell to see the weighted sum of V values that produced it.",
      head: "output = weights × V",
      render() {
        const row = makeEl("div", "pc-attn-matrices");
        row.append(
          buildMatrix("wt5", "weights", ATTN_DATA.weights.map(fmtRow), false),
          opNode("×"),
          buildMatrix("V5", "V", ATTN_DATA.V.map(fmtRow), false),
          opNode("="),
          buildMatrix("out5", "output", ATTN_DATA.output.map(fmtRow), true)
        );
        frame.body.appendChild(row);
        defaultHint(dot);
        bindClickable(visual, "out5", (r, c) => {
          showMatrixProduct(visual, dot,
            { aId: "wt5", bId: "V5", outId: "out5" },
            { r, c },
            { a: ATTN_DATA.weights, b: ATTN_DATA.V, result: ATTN_DATA.output });
        });
      }
    }
  ];

  function renderStep(i) {
    current = i;
    clear(stepper);
    steps.forEach((step, j) => {
      const dotBtn = makeEl("button", `pc-step-dot${j === i ? " active" : j < i ? " done" : ""}`, String(j + 1));
      dotBtn.type = "button";
      dotBtn.addEventListener("click", () => renderStep(j));
      stepper.appendChild(dotBtn);
    });
    titleEl.textContent = steps[i].title;
    descEl.textContent = steps[i].desc;
    clear(visual);
    const block = makeEl("div", "pc-code-block pc-attn-block");
    const head = makeEl("div", "pc-code-head");
    head.setAttribute("aria-hidden", "true");
    head.append(makeEl("span", "pc-code-dot"), makeEl("span", "pc-code-dot"), makeEl("span", "pc-code-dot"));
    frame.title = makeEl("span", "pc-code-title", steps[i].head);
    head.appendChild(frame.title);
    block.appendChild(head);
    frame.body = makeEl("div", "pc-attn-body");
    block.appendChild(frame.body);
    visual.appendChild(block);
    steps[i].render();
  }

  renderStep(0);
}

function paintCell(cell, value, pct, strong) {
  cell.style.background = value === 0
    ? "transparent"
    : `color-mix(in srgb, var(--color-amber) ${pct.toFixed(1)}%, transparent)`;
  cell.style.color = value === 0
    ? "var(--color-text-tertiary)"
    : strong ? "var(--color-text)" : "var(--color-text-secondary)";
  cell.style.fontWeight = strong ? "700" : "400";
}

function initGrid() {
  const table = byId("attnGrid");
  const caption = byId("attnCaption");
  if (!table || !caption) {
    return;
  }

  clear(table);
  const headRow = document.createElement("tr");
  headRow.appendChild(document.createElement("td"));
  for (const word of AGRID_WORDS) {
    headRow.appendChild(makeEl("td", "col-label", word));
  }
  table.appendChild(headRow);

  AGRID_WORDS.forEach((word, ri) => {
    const tr = document.createElement("tr");
    tr.dataset.row = String(ri);
    tr.appendChild(makeEl("td", "row-label", word));
    AGRID_WEIGHTS[ri].forEach((value) => {
      const td = makeEl("td", "", value === 0 ? "--" : value.toFixed(2));
      paintCell(td, value, value * 15, false);
      tr.appendChild(td);
    });
    table.appendChild(tr);
  });

  for (const tr of table.querySelectorAll("tr[data-row]")) {
    const trEl = /** @type {HTMLElement} */ (tr);
    trEl.addEventListener("mouseenter", () => {
      const activeRow = Number.parseInt(trEl.dataset.row ?? "", 10);
      table.querySelectorAll("tr[data-row]").forEach((row, i) => {
        row.querySelectorAll("td:not(.row-label)").forEach((cell, ci) => {
          const value = AGRID_WEIGHTS[i][ci];
          paintCell(cell, value, value * (i === activeRow ? 50 : 8), i === activeRow);
        });
      });

      const weights = AGRID_WEIGHTS[activeRow];
      const dominant = weights.indexOf(Math.max(...weights));
      const pct = (weights[dominant] * 100).toFixed(0);
      const next = activeRow < AGRID_WORDS.length - 1 ? AGRID_WORDS[activeRow + 1] : "...";
      caption.replaceChildren(
        document.createTextNode('To generate "'),
        makeEl("strong", "pc-hl-accent", next),
        document.createTextNode('", the model pays '),
        makeEl("strong", "pc-hl-teal", `${pct}%`),
        document.createTextNode(` attention to "${AGRID_WORDS[dominant]}"`)
      );
    });
  }
}

function initSoftmax() {
  const slidersWrap = byId("smxSliders");
  const barsWrap = byId("smxBars");
  const formula = byId("smxFormula");
  if (!slidersWrap || !barsWrap || !formula) {
    return;
  }

  const scores = [...SMX_INITIAL_SCORES];
  const valEls = [];

  SMX_TOKENS.forEach((tok, i) => {
    const row = makeEl("div", "pc-smx-row");
    row.appendChild(makeEl("span", "smx-label", tok));

    const input = document.createElement("input");
    input.type = "range";
    input.min = "-5";
    input.max = "5";
    input.step = "0.1";
    input.value = String(scores[i]);
    input.className = "range-input";
    input.setAttribute("aria-label", `Score for ${tok}`);
    input.addEventListener("input", () => {
      scores[i] = Number.parseFloat(input.value);
      update();
    });
    row.appendChild(input);

    const val = makeEl("span", "smx-val", scores[i].toFixed(2));
    valEls.push(val);
    row.appendChild(val);
    slidersWrap.appendChild(row);
  });

  function update() {
    const weights = softmax(scores);
    scores.forEach((score, i) => {
      valEls[i].textContent = score.toFixed(2);
    });

    clear(barsWrap);
    SMX_TOKENS.forEach((tok, i) => {
      const pct = (weights[i] * 100).toFixed(1);
      const row = makeEl("div", "pc-smx-row is-result");
      row.appendChild(makeEl("span", "smx-label", tok));
      row.appendChild(makeEl("span", "smx-val", scores[i].toFixed(2)));
      row.appendChild(makeEl("span", "smx-weight", `${pct}%`));
      const wrap = makeEl("div", "smx-bar-wrap");
      const bar = makeEl("div", "smx-bar");
      bar.style.width = `${pct}%`;
      wrap.appendChild(bar);
      row.appendChild(wrap);
      barsWrap.appendChild(row);
    });

    const max = Math.max(...weights);
    const top = SMX_TOKENS[weights.indexOf(max)];
    const sum = weights.reduce((acc, value) => acc + value, 0);
    formula.replaceChildren(
      document.createTextNode(`Row sums to: ${sum.toFixed(4)} | Highest: `),
      makeEl("strong", "", top),
      document.createTextNode(` at ${(max * 100).toFixed(1)}%`)
    );
  }

  update();
}

export function initAttention() {
  initStepper();
  initGrid();
  initSoftmax();
}
