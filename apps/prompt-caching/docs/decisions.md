# Decisions

## Prompt caching, demystified

This artifact began as a standalone AI-generated HTML file (bespoke warm-cream palette, Google Fonts, one ~1200-line inline `<script>`, ~200 inline `style=` attributes). It was refactored to match the production app system.

### Shared design tokens

The original warm palette was light-only. We remapped every color to the shared `--color-*` tokens so the app gets automatic light/dark and visually matches the rest of the gallery. The five original accent roles map to the five shared semantic hues (accent→amber, warm→blue, teal→green, indigo→purple, rose→red).

### Shared fonts

Google Fonts (Instrument Serif / Source Sans 3 / JetBrains Mono) were dropped in favour of the shared `--font-body` / `--font-heading` / `--font-mono` stacks. This removes the only external dependency and keeps the strict `'self'` CSP intact.

### Section progress navigation

The sticky numbered navigation helps readers track their position in the long page. It uses shared tokens and sits below the app-shell header.

### Pure calculations and browser interactions

All numerical behavior was extracted into pure functions in `math.js` (with data in `data.js`) so it can be unit-tested directly. The DOM-and-animation glue stays in the feature modules and is verified in-browser; the test harness cannot mount real canvas/`IntersectionObserver`/timer behavior, and importing the glue purely to chase coverage would add brittle mocks without testing real behavior.

### Steady-state savings model

`savingsMonthly` prices cached input tokens at one tenth of the base rate, which is the ongoing cost once a prefix is already cached. It deliberately omits the one-time 25% cache-write surcharge (documented in the providers table) and sub-5-minute cache expiry. Those matter for a single cold request but wash out across a steady workload, so folding them in would add noise without changing the lesson. The calculator therefore slightly overstates savings at very low request volumes, and a note under the calculator says so.
