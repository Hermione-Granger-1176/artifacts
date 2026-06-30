import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";
import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { initNavigation } from "./modules/navigation.js";
import { initTokenizer } from "./modules/tokenizer.js";
import { initEmbeddings } from "./modules/embeddings.js";
import { initInference } from "./modules/inference.js";
import { initAttention } from "./modules/attention.js";
import { initKvCache } from "./modules/kv-cache.js";
import { initCacheHits } from "./modules/cache-hits.js";
import { initCalculator } from "./modules/calculator.js";

renderAppShell();

initializeMatureApp({
  onErrorContext: "prompt caching initialization",
  run: () => {
    // Canvas demos resolve their colours from CSS tokens, so redraw on theme change.
    let embeddings;
    initAppShell({ onThemeChange: () => embeddings?.redraw() });

    initNavigation();
    initTokenizer();
    embeddings = initEmbeddings();
    initInference();
    initAttention();
    initKvCache();
    initCacheHits();
    initCalculator();
  }
});
