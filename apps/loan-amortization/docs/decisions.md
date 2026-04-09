# Decisions

## Why plain ES modules

The app stays browser-native and deployable without a bundler. That keeps each artifact portable and compatible with the repository contract that `index.html` remains the entry point.

## Why vendored Chart.js

The page depends on Chart.js 4.4.1 plus two plugins (chartjs-plugin-annotation 3.0.1, chartjs-plugin-datalabels 2.2.0). These are self-hosted in `js/vendor/` rather than loaded from a CDN.

- **Cold-load performance**: CDN delivery added 1-3 seconds per page load due to external DNS resolution, TLS handshake, and download. Vendoring serves all scripts from the same GitHub Pages origin over an existing HTTP/2 connection.
- **Resilience**: no runtime dependency on CDN availability or URL stability.
- **Full UMD builds**: Chart.js offers tree-shakeable ESM imports (~50-70 KB vs ~200 KB UMD), but that requires a JS bundler. The project uses plain `<script>` tags to stay portable, so the UMD build is the right trade-off.
- **Stability over freshness**: versions are pinned and upgraded manually. No automated update bot — intentional to avoid surprise breakage.

## Why inline SVG logo in the header

The shared Artifacts mark is part of the navigation shell and should render immediately without relying on additional image requests.

## Why `data-theme` plus localStorage

The root gallery already uses this model. Reusing it keeps theme state consistent when users move between the gallery and individual apps.

## Why the app exposes a ready signal

`window.__ARTIFACT_READY__` is set during the initial render so thumbnail generation can wait for charts, metrics, and tables to finish drawing before capturing the page.

## Why note-surface text stays dark in both themes

The bookmark-note surfaces stay bright in dark mode, so buttons, pills, and other note-tinted surfaces keep dark readable text. Separate emphasis tokens handle chart labels that sit directly on dark backgrounds.

## Deferred items

- User-facing theme preference controls beyond the shared toggle
- Additional chart views or export actions
- Stronger formula snapshots in automated browser tests
