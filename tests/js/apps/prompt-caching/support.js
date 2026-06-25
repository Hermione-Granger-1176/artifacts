/* Lightweight DOM/window harness for the Prompt Caching demos.
 *
 * Lives under tests/ so it is excluded from coverage. It provides just enough of
 * the DOM (elements with children, classList, dataset, a small querySelector
 * engine, canvas context stubs) plus controllable timers and IntersectionObserver
 * so the feature modules can be driven end-to-end without a browser. */

function ctxStub() {
  return {
    fillStyle: "", strokeStyle: "", lineWidth: 1, font: "", globalAlpha: 1, textAlign: "left",
    clearRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, stroke() {},
    arc() {}, fill() {}, fillText() {}, setLineDash() {}, save() {}, restore() {}, rect() {}
  };
}

function matchesCompound(node, compound) {
  if (!node || node.nodeType !== 1) {
    return false;
  }
  const tokenRe = /([.#][\w-]+|\[[^\]]+\]|:not\([^)]*\)|[\w-]+)/g;
  let match;
  while ((match = tokenRe.exec(compound)) !== null) {
    const tok = match[0];
    if (tok.startsWith(".")) {
      if (!node.classList.contains(tok.slice(1))) {
        return false;
      }
    } else if (tok.startsWith(":not(")) {
      if (matchesCompound(node, tok.slice(5, -1))) {
        return false;
      }
    } else if (tok.startsWith("[")) {
      const inner = tok.slice(1, -1);
      const eq = inner.indexOf("=");
      if (eq === -1) {
        const key = inner.replace(/^data-/, "");
        if (node.dataset[key] === undefined) {
          return false;
        }
      } else {
        const key = inner.slice(0, eq).replace(/^data-/, "");
        const value = inner.slice(eq + 1).replace(/^["']|["']$/g, "");
        if (node.dataset[key] !== value) {
          return false;
        }
      }
    } else if (!tok.startsWith("#")) {
      if ((node.tagName || "").toLowerCase() !== tok.toLowerCase()) {
        return false;
      }
    }
  }
  return true;
}

function collectDescendants(node, acc) {
  for (const child of node.children) {
    if (child && child.nodeType === 1) {
      acc.push(child);
      collectDescendants(child, acc);
    }
  }
  return acc;
}

function qsa(root, selector) {
  const all = collectDescendants(root, []);
  const result = [];
  for (const compound of selector.split(",").map((s) => s.trim())) {
    for (const node of all) {
      if (matchesCompound(node, compound) && !result.includes(node)) {
        result.push(node);
      }
    }
  }
  return result;
}

export function makeEl(tag = "div") {
  const classes = new Set();
  const attrs = {};
  const listeners = {};
  const node = {
    tagName: tag.toUpperCase(),
    nodeType: 1,
    id: "",
    value: "",
    innerHTML: "",
    hidden: false,
    disabled: false,
    title: "",
    tabIndex: -1,
    checked: false,
    type: "",
    min: "",
    max: "",
    step: "",
    width: 300,
    height: 150,
    dataset: {},
    style: {},
    children: [],
    parentNode: null,
    classList: {
      add: (c) => classes.add(c),
      remove: (...cs) => cs.forEach((c) => classes.delete(c)),
      toggle(c, force) {
        if (force === undefined) {
          if (classes.has(c)) {
            classes.delete(c);
            return false;
          }
          classes.add(c);
          return true;
        }
        if (force) {
          classes.add(c);
        } else {
          classes.delete(c);
        }
        return Boolean(force);
      },
      contains: (c) => classes.has(c)
    },
    get className() {
      return [...classes].join(" ");
    },
    set className(value) {
      classes.clear();
      String(value).split(/\s+/).filter(Boolean).forEach((c) => classes.add(c));
    },
    get firstChild() {
      return this.children[0] || null;
    },
    get childElementCount() {
      return this.children.length;
    },
    get textContent() {
      return this._text || "";
    },
    set textContent(value) {
      this._text = String(value);
      this.children = [];
    },
    setAttribute(key, value) {
      attrs[key] = String(value);
    },
    getAttribute(key) {
      return attrs[key] ?? null;
    },
    removeAttribute(key) {
      delete attrs[key];
    },
    addEventListener(type, fn) {
      (listeners[type] = listeners[type] || []).push(fn);
    },
    fire(type, event = {}) {
      (listeners[type] || []).forEach((fn) => fn(event));
    },
    appendChild(child) {
      if (child && typeof child === "object") {
        child.parentNode = node;
      }
      node.children.push(child);
      return child;
    },
    append(...nodes) {
      for (const child of nodes) {
        node.appendChild(child);
      }
    },
    insertBefore(child, ref) {
      child.parentNode = node;
      const idx = ref ? node.children.indexOf(ref) : -1;
      if (idx < 0) {
        node.children.push(child);
      } else {
        node.children.splice(idx, 0, child);
      }
      return child;
    },
    removeChild(child) {
      const idx = node.children.indexOf(child);
      if (idx >= 0) {
        node.children.splice(idx, 1);
      }
      child.parentNode = null;
      return child;
    },
    remove() {
      if (node.parentNode) {
        node.parentNode.removeChild(node);
      }
    },
    replaceChildren(...nodes) {
      node.children = [];
      for (const child of nodes) {
        node.appendChild(child);
      }
    },
    scrollIntoView() {},
    blur() {},
    focus() {},
    getContext() {
      return ctxStub();
    },
    querySelector(sel) {
      return qsa(node, sel)[0] || null;
    },
    querySelectorAll(sel) {
      return qsa(node, sel);
    },
    _classes: classes
  };
  return node;
}

function buttonWith(dataKey, value, active = false) {
  const btn = makeEl("button");
  btn.dataset[dataKey] = value;
  if (active) {
    btn.classList.add("active");
  }
  return btn;
}

const SIMPLE_IDS = [
  "navFill", "navLabel", "navNodes", "summaryTimeline",
  "tokenInput", "tokenOutput", "tokCount", "wordCount", "charCount",
  "dimCanvas", "dimCaption", "embCloud", "embSuggestions", "embSelA", "embSelB",
  "embSimilarity", "embDistance", "embVerdict", "embSwapBtn", "embCanvas",
  "infInput", "infGoBtn", "infResetBtn", "infTokens", "infStatus", "infCacheCount", "infCacheBar",
  "attnStepper", "attnStepTitle", "attnStepDesc", "attnStepVisual", "dotProduct",
  "attnGrid", "attnCaption", "smxSliders", "smxBars", "smxFormula",
  "cacheTokens", "kCacheVis", "vCacheVis", "cacheNarration", "cachePlayBtn", "cacheResetBtn",
  "cacheCompareVis", "cacheCompareCaption",
  "chvSendBtn", "chvClearBtn", "chvReqs", "chvTTL",
  "calcSys", "calcReq", "calcHit", "calcPrice",
  "calcSysVal", "calcReqVal", "calcHitVal", "calcPriceVal", "calcWithout", "calcWith", "calcSavings",
  "back-button", "theme-toggle", "scroll-top",
  "runtime-error", "runtime-error-details", "runtime-error-output", "runtime-error-copy"
];

const SECTION_IDS = [
  "sec-intro", "sec-loop", "sec-tokenizer", "sec-embedding", "sec-attention",
  "sec-kvcache", "sec-providers", "sec-calculator", "sec-summary"
];

export function createHarness() {
  const registry = {};
  for (const id of [...SIMPLE_IDS, ...SECTION_IDS]) {
    registry[id] = makeEl("div");
    registry[id].id = id;
  }

  // Toggle groups need their child buttons present before init runs.
  registry.tokenView = makeEl("div");
  registry.tokenView.append(buttonWith("view", "text", true), buttonWith("view", "ids"));
  registry.dimToggle = makeEl("div");
  registry.dimToggle.append(buttonWith("dims", "1", true), buttonWith("dims", "2"), buttonWith("dims", "3"));
  registry.cacheCompareToggle = makeEl("div");
  registry.cacheCompareToggle.append(buttonWith("compare", "no", true), buttonWith("compare", "yes"));
  registry.pipelineDiagram = makeEl("div");
  for (const target of ["sec-tokenizer", "sec-embedding", "sec-attention", "sec-kvcache", "sec-providers"]) {
    const node = makeEl("button");
    node.dataset.target = target;
    registry.pipelineDiagram.appendChild(node);
  }
  registry.pipelineDiagram.appendChild(makeEl("span")); // arrow without data-target

  // Canvases with realistic dimensions.
  registry.dimCanvas.width = 680;
  registry.dimCanvas.height = 260;
  registry.embCanvas.width = 400;
  registry.embCanvas.height = 300;

  // Inputs with starting values.
  registry.tokenInput.value = "How many r's in the word strawberry? 9";
  registry.infInput.value = "The meaning of";
  registry.calcSys.value = "2000";
  registry.calcReq.value = "500";
  registry.calcHit.value = "80";
  registry.calcPrice.value = "3";

  const intervals = new Map();
  const timeouts = new Map();
  const observers = [];
  let timerSeq = 0;

  const shellSlots = {};
  const themeColorMeta = { setAttribute() {}, getAttribute() { return null; } };

  const documentElement = {
    dataset: {},
    _theme: "light",
    getAttribute(name) {
      return name === "data-theme" ? this._theme : null;
    },
    setAttribute(name, value) {
      this.dataset[name] = value;
      if (name === "data-theme") {
        this._theme = value;
      }
    }
  };

  const documentMock = {
    readyState: "interactive",
    referrer: "",
    documentElement,
    getElementById(id) {
      return registry[id] || null;
    },
    createElement(tag) {
      return makeEl(tag);
    },
    createTextNode(text) {
      return { nodeType: 3, textContent: String(text), parentNode: null };
    },
    querySelector(sel) {
      if (sel === 'meta[name="theme-color"]') {
        return themeColorMeta;
      }
      if (sel.startsWith("[data-app-shell=")) {
        if (!shellSlots[sel]) {
          shellSlots[sel] = makeEl("div");
        }
        return shellSlots[sel];
      }
      return null;
    },
    addEventListener() {}
  };

  const windowMock = {
    __ARTIFACTS_APP_THEME_BOOTSTRAP__: {
      normalizeTheme(t) {
        return t === "dark" ? "dark" : "light";
      }
    },
    matchMedia() {
      return { matches: false };
    },
    scrollY: 0,
    scrollTo() {},
    history: { length: 2, back() {} },
    location: { origin: "https://example.com", href: "" },
    localStorage: { getItem() { return null; }, setItem() {} },
    addEventListener() {},
    requestAnimationFrame(fn) {
      fn();
      return 1;
    }
  };

  const saved = {};

  function install() {
    for (const key of ["document", "window", "getComputedStyle", "IntersectionObserver", "setInterval", "clearInterval", "setTimeout", "clearTimeout"]) {
      saved[key] = globalThis[key];
    }
    globalThis.document = documentMock;
    globalThis.window = windowMock;
    globalThis.getComputedStyle = () => ({
      getPropertyValue(name) {
        return name.includes("font") ? "system-ui, sans-serif" : "rgb(120, 120, 120)";
      }
    });
    globalThis.IntersectionObserver = class {
      constructor(cb) {
        this.cb = cb;
        observers.push(this);
      }
      observe() {}
      disconnect() {}
    };
    globalThis.setInterval = (fn) => {
      const id = ++timerSeq;
      intervals.set(id, fn);
      return id;
    };
    globalThis.clearInterval = (id) => {
      intervals.delete(id);
    };
    globalThis.setTimeout = (fn) => {
      const id = ++timerSeq;
      timeouts.set(id, fn);
      return id;
    };
    globalThis.clearTimeout = (id) => {
      timeouts.delete(id);
    };
  }

  function teardown() {
    for (const [key, value] of Object.entries(saved)) {
      if (value === undefined) {
        delete globalThis[key];
      } else {
        globalThis[key] = value;
      }
    }
  }

  function flushIntervals(maxRounds = 400) {
    for (let round = 0; round < maxRounds && intervals.size > 0; round += 1) {
      for (const [id, fn] of [...intervals]) {
        if (intervals.has(id)) {
          fn();
        }
      }
    }
  }

  function flushTimeouts() {
    for (const [id, fn] of [...timeouts]) {
      timeouts.delete(id);
      fn();
    }
  }

  function fireObservers(idx) {
    const target = registry[SECTION_IDS[idx]];
    for (const observer of observers) {
      observer.cb([{ isIntersecting: true, target }]);
    }
  }

  return {
    registry,
    install,
    teardown,
    flushIntervals,
    flushTimeouts,
    fireObservers,
    intervals,
    el: (id) => registry[id]
  };
}
