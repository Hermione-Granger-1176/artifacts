# Decisions

## Why plain ES modules

The app stays browser-native and deployable without a bundler. That keeps each artifact portable and compatible with the repository contract that `index.html` remains the entry point.

## Why CDN Chart.js

The page depends on Chart.js plus two plugins. CDN delivery keeps the app self-contained without introducing a workspace bundling step.

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
