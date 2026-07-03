/* Embedding demos: the dimension explorer scatter and the similarity playground.
 * Both canvases resolve their colours from shared tokens so they re-render
 * correctly when the theme toggles. */

import { DIM_COLORS, EMB_VECS, EMB_PAIRS, EMB_CATEGORIES } from "./data.js";
import { cosineSim, eucDist, verdictForSimilarity, project2D } from "./math.js";
import { byId, cssVar, makeEl, clear, initSegmented } from "./dom.js";

// Use the prompt-specific accent tokens (not the vibrant --color-* bases): they carry
// the WCAG-AA text colours in light mode and flip to the vibrant hues in dark.
const TONE_VARS = {
  teal: "--pc-teal",
  accent: "--pc-accent",
  warm: "--pc-warm",
  secondary: "--color-text-secondary",
  tertiary: "--color-text-tertiary",
  rose: "--pc-rose"
};

function bodyFont(spec) {
  return `${spec} ${cssVar("--font-body") || "sans-serif"}`;
}

export function initEmbeddings() {
  const dims = initDimensions();
  const sim = initSimilarity();

  return {
    redraw() {
      if (dims) {
        dims.draw();
      }
      if (sim) {
        sim.refresh();
      }
    }
  };
}

function activateOnKeyboard(event, action) {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }
  event.preventDefault();
  action();
}

function initDimensions() {
  const canvas = byId("dimCanvas");
  const caption = byId("dimCaption");
  const toggle = byId("dimToggle");
  if (!canvas || !caption || !toggle || !canvas.getContext) {
    return null;
  }

  const groups = DIM_COLORS.map((token, gi) => {
    const cx = (gi % 4) * 0.25 + 0.125;
    const cy = gi < 4 ? 0.3 : 0.7;
    const cz = (gi % 3) * 0.33 + 0.17;
    const points = [];
    for (let p = 0; p < 6; p += 1) {
      points.push({
        x1: Math.random(),
        x2: cx + (Math.random() - 0.5) * 0.16,
        y2: cy + (Math.random() - 0.5) * 0.16,
        x3: cx + (Math.random() - 0.5) * 0.13,
        y3: cy + (Math.random() - 0.5) * 0.13,
        z3: cz + (Math.random() - 0.5) * 0.16,
        token
      });
    }
    return points;
  });
  const allPoints = groups.flat();

  const captions = [
    "In 1D everything sits on a line. Total jumble. Hard to see any grouping.",
    "In 2D, clusters start separating. You can spot 8 distinct groups forming.",
    "In 3D, separation is clearer. Now imagine doing this with 12,000 dimensions."
  ];
  let currentDims = 1;

  function draw() {
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    const pad = 30;
    ctx.clearRect(0, 0, W, H);

    if (currentDims === 1) {
      ctx.strokeStyle = cssVar("--color-border-strong");
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad, H / 2);
      ctx.lineTo(W - pad, H / 2);
      ctx.stroke();
    }

    for (const point of allPoints) {
      let x;
      let y;
      if (currentDims === 1) {
        x = pad + point.x1 * (W - 2 * pad);
        y = H / 2;
      } else if (currentDims === 2) {
        x = pad + point.x2 * (W - 2 * pad);
        y = pad + point.y2 * (H - 2 * pad);
      } else {
        const sc = 0.65;
        const px = point.x3 - 0.5;
        const pz = point.z3 - 0.5;
        x = W / 2 + (px - pz) * 0.866 * (W - 2 * pad) * sc;
        y = H / 2 + ((px + pz) * 0.5 - (point.y3 - 0.5)) * (H - 2 * pad) * sc;
      }
      ctx.beginPath();
      ctx.arc(x, y, 5.5, 0, Math.PI * 2);
      ctx.fillStyle = cssVar(point.token);
      ctx.globalAlpha = 0.85;
      ctx.fill();
      ctx.globalAlpha = 1;
    }
  }

  initSegmented(toggle, (btn) => {
    currentDims = Number.parseInt(btn.dataset.dims, 10);
    caption.textContent = captions[currentDims - 1];
    draw();
  });

  draw();
  return { draw };
}

function initSimilarity() {
  const cloud = byId("embCloud");
  const suggestions = byId("embSuggestions");
  const selAEl = byId("embSelA");
  const selBEl = byId("embSelB");
  const simEl = byId("embSimilarity");
  const distEl = byId("embDistance");
  const verdEl = byId("embVerdict");
  const swapBtn = byId("embSwapBtn");
  const canvas = byId("embCanvas");
  if (!cloud || !selAEl || !selBEl || !simEl) {
    return null;
  }

  let selA = "happy";
  let selB = "sad";
  let selecting = "a";

  const wordEls = new Map();
  for (const word of Object.values(EMB_CATEGORIES).flat()) {
    const span = makeEl("span", "emb-word", word);
    span.dataset.word = word;
    span.setAttribute("role", "button");
    span.setAttribute("aria-label", `Select word ${word}`);
    span.tabIndex = 0;
    span.addEventListener("click", () => clickWord(word));
    span.addEventListener("keydown", (event) => activateOnKeyboard(event, () => clickWord(word)));
    cloud.appendChild(span);
    wordEls.set(word, span);
  }

  if (suggestions) {
    for (const [a, b] of EMB_PAIRS) {
      const tag = makeEl("span", "emb-tag", `${a} / ${b}`);
      tag.setAttribute("role", "button");
      tag.setAttribute("aria-label", `Compare ${a} and ${b}`);
      tag.tabIndex = 0;
      tag.addEventListener("click", () => {
        selA = a;
        selB = b;
        selecting = "a";
        refresh();
      });
      tag.addEventListener("keydown", (event) => {
        activateOnKeyboard(event, () => {
          selA = a;
          selB = b;
          selecting = "a";
          refresh();
        });
      });
      suggestions.appendChild(tag);
    }
  }

  function clickWord(word) {
    if (selecting === "a") {
      selA = word;
      selecting = "b";
    } else {
      selB = word;
      selecting = "a";
    }
    refresh();
  }

  function refresh() {
    selAEl.textContent = selA;
    selBEl.textContent = selB;

    for (const [word, el] of wordEls) {
      el.classList.toggle("sel-a", word === selA);
      el.classList.toggle("sel-b", word === selB);
    }

    const vecA = EMB_VECS[selA];
    const vecB = EMB_VECS[selB];
    if (!vecA || !vecB) {
      simEl.textContent = "?";
      distEl.textContent = "?";
      verdEl.textContent = "Select two words";
      return;
    }

    const sim = cosineSim(vecA, vecB);
    const dist = eucDist(vecA, vecB);
    simEl.textContent = sim.toFixed(2);
    distEl.textContent = dist.toFixed(2);

    const verdict = verdictForSimilarity(sim);
    verdEl.textContent = verdict.label;
    verdEl.style.color = `var(${TONE_VARS[verdict.tone]})`;
    const simTone = sim > 0.5 ? "--pc-teal" : sim > 0 ? "--pc-warm" : "--pc-rose";
    simEl.style.color = `var(${simTone})`;

    drawCanvas(vecA, vecB);
  }

  function drawCanvas(vecA, vecB) {
    if (!canvas || !canvas.getContext) {
      return;
    }
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const projected = project2D(vecA, vecB, EMB_VECS);
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (const p of projected) {
      minX = Math.min(minX, p.x);
      maxX = Math.max(maxX, p.x);
      minY = Math.min(minY, p.y);
      maxY = Math.max(maxY, p.y);
    }

    const pad = 44;
    const rangeX = (maxX - minX) || 1;
    const rangeY = (maxY - minY) || 1;
    const scale = Math.min((W - 2 * pad) / rangeX, (H - 2 * pad) / rangeY);
    const midX = (minX + maxX) / 2;
    const midY = (minY + maxY) / 2;
    const toScreen = (p) => ({ sx: W / 2 + (p.x - midX) * scale, sy: H / 2 - (p.y - midY) * scale });

    const muted = cssVar("--color-text-tertiary");
    const labelColor = cssVar("--color-text-secondary");
    const surface = cssVar("--color-surface");
    const colorA = cssVar("--color-amber");
    const colorB = cssVar("--color-green");

    ctx.globalAlpha = 0.15;
    for (const p of projected) {
      if (p.word === selA || p.word === selB) {
        continue;
      }
      const s = toScreen(p);
      ctx.beginPath();
      ctx.arc(s.sx, s.sy, 3, 0, Math.PI * 2);
      ctx.fillStyle = muted;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    const aP = projected.find((p) => p.word === selA);
    const bP = projected.find((p) => p.word === selB);
    const sA = aP ? toScreen(aP) : null;
    const sB = bP ? toScreen(bP) : null;

    if (sA && sB) {
      ctx.beginPath();
      ctx.moveTo(sA.sx, sA.sy);
      ctx.lineTo(sB.sx, sB.sy);
      ctx.strokeStyle = cssVar("--color-border-strong");
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    if (aP && bP) {
      const context = projected
        .filter((p) => p.word !== selA && p.word !== selB)
        .sort((a, b) => nearest(a, aP, bP) - nearest(b, aP, bP))
        .slice(0, 8);
      ctx.globalAlpha = 0.45;
      ctx.font = bodyFont("500 10px");
      ctx.textAlign = "center";
      for (const p of context) {
        const s = toScreen(p);
        ctx.beginPath();
        ctx.arc(s.sx, s.sy, 4, 0, Math.PI * 2);
        ctx.fillStyle = muted;
        ctx.fill();
        ctx.fillStyle = labelColor;
        ctx.fillText(p.word, s.sx, s.sy - 9);
      }
      ctx.globalAlpha = 1;
    }

    drawMarker(ctx, sA, selA, colorA, surface);
    drawMarker(ctx, sB, selB, colorB, surface);
  }

  swapBtn?.addEventListener("click", () => {
    [selA, selB] = [selB, selA];
    refresh();
  });

  refresh();
  return { refresh };
}

function nearest(point, aP, bP) {
  return Math.min(
    (point.x - aP.x) ** 2 + (point.y - aP.y) ** 2,
    (point.x - bP.x) ** 2 + (point.y - bP.y) ** 2
  );
}

function drawMarker(ctx, screen, word, color, stroke) {
  if (!screen) {
    return;
  }
  ctx.beginPath();
  ctx.arc(screen.sx, screen.sy, 9, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 2;
  ctx.stroke();
  ctx.font = bodyFont("700 13px");
  ctx.fillStyle = color;
  ctx.textAlign = "center";
  ctx.fillText(word, screen.sx, screen.sy - 16);
}
