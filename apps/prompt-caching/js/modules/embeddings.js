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

  // One set of 24 points generated in 3D. Every view is a projection of the
  // same data, so adding dimensions genuinely adds separation rather than
  // drawing a new picture.
  const groups = DIM_COLORS.map((token, gi) => {
    const cx = (gi % 4) * 0.25 + 0.125;
    const cy = gi < 4 ? 0.28 : 0.72;
    const cz = ((gi * 5) % 8) / 8 + 0.0625;
    const points = [];
    for (let p = 0; p < 6; p += 1) {
      points.push({
        x: cx + (Math.random() - 0.5) * 0.14,
        y: cy + (Math.random() - 0.5) * 0.14,
        z: cz + (Math.random() - 0.5) * 0.14,
        token
      });
    }
    return points;
  });
  const allPoints = groups.flat();

  const captions = [
    "1D: the same 24 points squashed onto one line. Clusters pile on top of each other.",
    "2D: a second axis and the 8 groups start pulling apart.",
    "3D: drag to rotate. Separation holds from every angle. Real models use 12,000+ axes."
  ];
  let currentDims = 1;
  let yaw = 0.7;
  let pitch = 0.32;
  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  function rotate(point) {
    const x = point.x - 0.5;
    const y = point.y - 0.5;
    const z = point.z - 0.5;
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const x1 = x * cosY + z * sinY;
    const z1 = z * cosY - x * sinY;
    const cosX = Math.cos(pitch);
    const sinX = Math.sin(pitch);
    return {
      px: x1,
      py: y * cosX - z1 * sinX,
      depth: y * sinX + z1 * cosX,
      token: point.token
    };
  }

  function drawDot(ctx, x, y, token, radius, alpha) {
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = cssVar(token);
    ctx.globalAlpha = alpha;
    ctx.fill();
    ctx.globalAlpha = 1;
  }

  function draw() {
    const ctx = canvas.getContext("2d");
    canvas.height = currentDims === 1 ? 90 : currentDims === 2 ? 260 : 300;
    const W = canvas.width;
    const H = canvas.height;
    const pad = 30;
    ctx.clearRect(0, 0, W, H);

    if (currentDims === 1) {
      // Project onto a diagonal axis so cluster structure exists but overlaps.
      const values = allPoints.map((p) => (p.x + p.y + p.z) / 3);
      const min = Math.min(...values);
      const range = (Math.max(...values) - min) || 1;
      ctx.strokeStyle = cssVar("--color-border-strong");
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad, H / 2);
      ctx.lineTo(W - pad, H / 2);
      ctx.stroke();
      for (let t = 0; t <= 10; t += 1) {
        const tx = pad + (t / 10) * (W - 2 * pad);
        ctx.beginPath();
        ctx.moveTo(tx, H / 2 - 4);
        ctx.lineTo(tx, H / 2 + 4);
        ctx.stroke();
      }
      allPoints.forEach((point, i) => {
        drawDot(ctx, pad + ((values[i] - min) / range) * (W - 2 * pad), H / 2, point.token, 5.5, 0.85);
      });
      return;
    }

    if (currentDims === 2) {
      for (const point of allPoints) {
        drawDot(ctx, pad + point.x * (W - 2 * pad), pad + point.y * (H - 2 * pad), point.token, 5.5, 0.85);
      }
      return;
    }

    const sc = (Math.min(W, H) - 2 * pad) * 0.8;
    const projected = allPoints.map(rotate).sort((a, b) => a.depth - b.depth);
    for (const p of projected) {
      const radius = 5.5 + p.depth * 3;
      const alpha = Math.min(0.95, Math.max(0.35, 0.7 + p.depth * 0.5));
      drawDot(ctx, W / 2 + p.px * sc, H / 2 + p.py * sc, p.token, radius, alpha);
    }
  }

  canvas.addEventListener("pointerdown", (event) => {
    if (currentDims !== 3) {
      return;
    }
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!dragging || currentDims !== 3) {
      return;
    }
    yaw += (event.clientX - lastX) * 0.01;
    pitch = Math.min(1.2, Math.max(-1.2, pitch + (event.clientY - lastY) * 0.01));
    lastX = event.clientX;
    lastY = event.clientY;
    draw();
  });
  const stopDrag = () => {
    dragging = false;
  };
  canvas.addEventListener("pointerup", stopDrag);
  canvas.addEventListener("pointerleave", stopDrag);

  initSegmented(toggle, (btn) => {
    currentDims = Number.parseInt(btn.dataset.dims, 10);
    caption.textContent = captions[currentDims - 1];
    canvas.classList.toggle("is-rotatable", currentDims === 3);
    dragging = false;
    draw();
  });

  draw();
  return { draw };
}

function initSimilarity() {
  const cloud = byId("embCloud");
  const cats = byId("embCats");
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
  let currentCat = Object.keys(EMB_CATEGORIES)[0];
  let screenPoints = [];
  let hovered = null;

  const wordEls = new Map();
  const catEls = new Map();

  if (cats) {
    for (const cat of Object.keys(EMB_CATEGORIES)) {
      const btn = makeEl("button", "pc-emb-cat", cat);
      btn.type = "button";
      btn.addEventListener("click", () => {
        currentCat = cat;
        syncCats();
        renderCloud();
      });
      cats.appendChild(btn);
      catEls.set(cat, btn);
    }
    syncCats();
  }

  function syncCats() {
    for (const [cat, el] of catEls) {
      el.classList.toggle("active", cat === currentCat);
      el.setAttribute("aria-pressed", String(cat === currentCat));
    }
  }

  function renderCloud() {
    clear(cloud);
    wordEls.clear();
    const words = cats ? EMB_CATEGORIES[currentCat] : Object.values(EMB_CATEGORIES).flat();
    for (const word of words) {
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
    highlightSelection();
  }

  function highlightSelection() {
    for (const [word, el] of wordEls) {
      el.classList.toggle("sel-a", word === selA);
      el.classList.toggle("sel-b", word === selB);
    }
  }

  renderCloud();

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
    highlightSelection();

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

    screenPoints = projected.map((p) => ({ word: p.word, ...toScreen(p) }));

    ctx.globalAlpha = 0.3;
    for (const s of screenPoints) {
      if (s.word === selA || s.word === selB) {
        continue;
      }
      ctx.beginPath();
      ctx.arc(s.sx, s.sy, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = muted;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    const sA = screenPoints.find((s) => s.word === selA) || null;
    const sB = screenPoints.find((s) => s.word === selB) || null;

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

    const hov = hovered ? screenPoints.find((s) => s.word === hovered) : null;
    if (hov) {
      ctx.beginPath();
      ctx.arc(hov.sx, hov.sy, 6, 0, Math.PI * 2);
      ctx.fillStyle = labelColor;
      ctx.fill();
      ctx.font = bodyFont("600 11px");
      ctx.textAlign = "center";
      ctx.strokeStyle = surface;
      ctx.lineWidth = 3;
      ctx.strokeText(hov.word, hov.sx, hov.sy - 12);
      ctx.fillStyle = labelColor;
      ctx.fillText(hov.word, hov.sx, hov.sy - 12);
    }

    drawMarker(ctx, sA, selA, colorA, surface);
    drawMarker(ctx, sB, selB, colorB, surface);
  }

  function hitTest(x, y) {
    let best = null;
    let bestDist = 14 * 14;
    for (const s of screenPoints) {
      if (s.word === selA || s.word === selB) {
        continue;
      }
      const dist = (s.sx - x) ** 2 + (s.sy - y) ** 2;
      if (dist < bestDist) {
        bestDist = dist;
        best = s.word;
      }
    }
    return best;
  }

  function redrawCurrent() {
    const vecA = EMB_VECS[selA];
    const vecB = EMB_VECS[selB];
    if (vecA && vecB) {
      drawCanvas(vecA, vecB);
    }
  }

  if (canvas) {
    canvas.addEventListener("pointermove", (event) => {
      const scaleX = canvas.width / (canvas.clientWidth || canvas.width);
      const scaleY = canvas.height / (canvas.clientHeight || canvas.height);
      const hit = hitTest(event.offsetX * scaleX, event.offsetY * scaleY);
      if (hit !== hovered) {
        hovered = hit;
        canvas.style.cursor = hovered ? "pointer" : "";
        redrawCurrent();
      }
    });
    canvas.addEventListener("pointerleave", () => {
      if (hovered) {
        hovered = null;
        canvas.style.cursor = "";
        redrawCurrent();
      }
    });
    canvas.addEventListener("click", () => {
      if (hovered) {
        clickWord(hovered);
      }
    });
  }

  swapBtn?.addEventListener("click", () => {
    [selA, selB] = [selB, selA];
    refresh();
  });

  refresh();
  return { refresh };
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
  ctx.textAlign = "center";
  ctx.strokeStyle = stroke;
  ctx.lineWidth = 3;
  ctx.strokeText(word, screen.sx, screen.sy - 16);
  ctx.fillStyle = color;
  ctx.fillText(word, screen.sx, screen.sy - 16);
}
