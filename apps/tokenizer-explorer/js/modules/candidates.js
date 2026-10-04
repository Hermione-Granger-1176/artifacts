import { formatPercent } from "../../../../js/modules/formatting.js";

/**
 * @typedef {{
 *   adjustedProb: number,
 *   idx: number,
 *   prob: number,
 *   word: string
 * }} SortedToken
 * @typedef {{
 *   idx: number,
 *   word: string,
 *   kept: boolean,
 *   startsCut: boolean,
 *   picked: boolean,
 *   oddsPercent: number,
 *   drawPercent: number | null,
 *   seenCount: number | null,
 *   seenPercent: number
 * }} CandidateRow
 * @typedef {{
 *   cutLabel: HTMLElement,
 *   draw: HTMLElement,
 *   fill: HTMLElement,
 *   item: HTMLElement,
 *   odds: HTMLElement,
 *   seen: HTMLElement,
 *   seenFill: HTMLElement,
 *   token: HTMLElement
 * }} RowParts
 * @typedef {{ head: HTMLElement, order: string, parts: Map<number, RowParts> }} ListState
 */

// Smallest bar width, in percent, so a tiny but nonzero probability stays visible.
const MIN_BAR_PERCENT = 0.5;

/** @type {WeakMap<HTMLElement, ListState>} */
const listStates = new WeakMap();

/**
 * Derive one display row per candidate, in probability order. The bar always
 * shows the temperature-shaped probability: top-p never changes a bar's
 * length, it only marks the tail as cut, so the two controls stay visually
 * distinct. The renormalized draw chance rides in its own column, and the
 * observed tally (when present) turns into a count and a share.
 *
 * @param {{
 *   inTopP: Set<number>,
 *   sampleCounts: Map<number, number> | null,
 *   selectedTokenIndex: number | null,
 *   sorted: SortedToken[]
 * }} state
 * @returns {CandidateRow[]}
 */
export function buildCandidateRows(state) {
  const counts = state.sampleCounts;
  const drawTotal = counts ? [...counts.values()].reduce((sum, count) => sum + count, 0) : 0;
  let cutStarted = false;

  return state.sorted.map((token) => {
    const kept = state.inTopP.has(token.idx);
    const startsCut = !kept && !cutStarted;
    cutStarted = cutStarted || !kept;
    const seenCount = counts ? (counts.get(token.idx) ?? 0) : null;

    return {
      idx: token.idx,
      word: token.word,
      kept,
      startsCut,
      picked: token.idx === state.selectedTokenIndex,
      oddsPercent: token.prob * 100,
      drawPercent: kept ? token.adjustedProb * 100 : null,
      seenCount,
      seenPercent: seenCount !== null && drawTotal > 0 ? (seenCount / drawTotal) * 100 : 0
    };
  });
}

/**
 * @param {string} tag
 * @param {string} className
 * @param {string} [text]
 * @returns {HTMLElement}
 */
function makeCell(tag, className, text = "") {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

/** @returns {HTMLElement} The static column-label row that heads the list. */
function createHead() {
  const head = makeCell("li", "tk-row tk-list-head");
  const labels = [
    ["tk-token", "Token", "The candidate token"],
    ["tk-track-label", "After temperature", "Probability after temperature, before the top P cut"],
    ["tk-odds", "Odds", "Probability after temperature"],
    ["tk-draw", "Draw", "Chance of being drawn once top P renormalizes the survivors"],
    ["tk-seen", "Seen", "Times drawn in the last 100 samples"]
  ];
  for (const [className, text, title] of labels) {
    const cell = makeCell("span", className, text);
    cell.title = title;
    head.appendChild(cell);
  }
  return head;
}

/** @returns {RowParts} One reusable candidate row with every cell in place. */
function createRowParts() {
  const item = makeCell("li", "tk-row");
  const cutLabel = makeCell("span", "tk-cut-label", "top P cut");
  cutLabel.hidden = true;
  const token = makeCell("span", "tk-token");
  const track = makeCell("span", "tk-track");
  const fill = makeCell("span", "tk-fill");
  const seenFill = makeCell("span", "tk-seen-fill");
  track.append(fill, seenFill);
  const odds = makeCell("span", "tk-odds");
  const draw = makeCell("span", "tk-draw");
  const seen = makeCell("span", "tk-seen");
  item.append(cutLabel, token, track, odds, draw, seen);
  return { cutLabel, draw, fill, item, odds, seen, seenFill, token };
}

/**
 * @param {RowParts} parts
 * @param {CandidateRow} row
 * @returns {void}
 */
function updateRowParts(parts, row) {
  parts.item.classList.toggle("is-cut", !row.kept);
  parts.item.classList.toggle("is-picked", row.picked);
  parts.cutLabel.hidden = !row.startsCut;
  parts.token.textContent = row.word;
  parts.token.title = row.word;
  parts.fill.style.width = `${Math.max(row.oddsPercent, MIN_BAR_PERCENT)}%`;
  parts.seenFill.style.width = `${row.seenPercent}%`;
  parts.odds.textContent = formatPercent(row.oddsPercent);
  parts.draw.textContent = row.drawPercent === null ? "cut" : formatPercent(row.drawPercent);
  parts.seen.textContent = row.seenCount === null ? "" : String(row.seenCount);
  parts.seen.title = row.seenCount === null ? "" : `${row.seenCount} of 100 draws`;
}

/**
 * Render the candidate list in place. Rows are created once per list and
 * reused, so a slider move changes each bar's width on an existing element
 * and the CSS width transition can animate it. The rows are only re-inserted
 * when their order changes (a new scenario), never for temperature or top-p,
 * because moving a node would cancel its transition.
 *
 * @param {HTMLElement} list - The <ul> that holds the rows.
 * @param {CandidateRow[]} rows
 * @returns {void}
 */
export function renderCandidateList(list, rows) {
  let listState = listStates.get(list);
  if (!listState) {
    listState = { head: createHead(), order: "", parts: new Map() };
    listStates.set(list, listState);
  }
  const { parts } = listState;

  const ordered = rows.map((row) => {
    let rowParts = parts.get(row.idx);
    if (!rowParts) {
      rowParts = createRowParts();
      parts.set(row.idx, rowParts);
    }
    updateRowParts(rowParts, row);
    return rowParts.item;
  });

  const order = rows.map((row) => row.idx).join(",");
  if (listState.order !== order) {
    list.replaceChildren(listState.head, ...ordered);
    listState.order = order;
  }

  list.classList.toggle("has-samples", rows.some((row) => row.seenCount !== null));
}
