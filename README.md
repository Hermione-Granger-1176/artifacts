# Artifacts

A collection of interactive HTML artifacts built with AI tools (Claude, ChatGPT, Gemini, etc.). Each artifact is a self-contained web application with its own page.

**Live site:** <!-- AUTO:SITE_URL -->https://hermione-granger-1176.github.io/artifacts/<!-- /AUTO:SITE_URL -->

<!-- AUTO:TOTAL_BADGE --><img src="https://img.shields.io/badge/Total-3-D97706?style=for-the-badge" alt="Total"><!-- /AUTO:TOTAL_BADGE -->

## Topics

<!-- prettier-ignore-start -->
<!-- AUTO:TAG_BADGES_START -->
<img src="https://img.shields.io/badge/Finance-27AE60?style=flat-square" alt="Finance">&nbsp;
<img src="https://img.shields.io/badge/Calculator-2E86C1?style=flat-square" alt="Calculator">&nbsp;
<img src="https://img.shields.io/badge/Visualization-E67E22?style=flat-square" alt="Visualization">&nbsp;
<img src="https://img.shields.io/badge/Education-F39C12?style=flat-square" alt="Education">&nbsp;
<img src="https://img.shields.io/badge/AI-A0C8E8?style=flat-square" alt="AI">&nbsp;
<img src="https://img.shields.io/badge/LLM-E8C8A0?style=flat-square" alt="LLM">
<!-- AUTO:TAG_BADGES_END -->
<!-- prettier-ignore-end -->

## AI Tools

<!-- prettier-ignore-start -->
<!-- AUTO:TOOL_BADGES_START -->
<img src="https://img.shields.io/badge/Claude-D97706?style=flat-square&logo=anthropic&logoColor=white" alt="Claude">
<!-- AUTO:TOOL_BADGES_END -->
<!-- prettier-ignore-end -->

## Snapshot

- <!-- AUTO:TOTAL_COUNT -->3<!-- /AUTO:TOTAL_COUNT --> artifacts published
- Browse the live website for searchable thumbnails, multi-select filters, theme persistence, and detail overlays.

## Docs

- [`workspace.md`](docs/workspace.md): repository layout and responsibilities
- [`architecture.md`](docs/architecture.md): runtime, build, and deployment design
- [`docs/adr/0001-root-publishing-platform.md`](docs/adr/0001-root-publishing-platform.md): accepted decision record for the strict root publish flow
- [`docs/adr/0004-per-artifact-app-stylesheets.md`](docs/adr/0004-per-artifact-app-stylesheets.md): accepted decision record for splitting artifact CSS into app-local stylesheets
- [`frontend.md`](docs/frontend.md): JavaScript module layout and test coverage
- [`operations.md`](docs/operations.md): local workflows, CI, and generation notes
- [`maintenance.md`](docs/maintenance.md): maintenance rules and long-term repo hygiene
- [`style.md`](docs/style.md): editor configuration and language conventions
- [`CONTRIBUTING.md`](.github/CONTRIBUTING.md): contribution and dependency update workflow
- [`SECURITY.md`](.github/SECURITY.md): how to report vulnerabilities
- [`CODE_OF_CONDUCT.md`](.github/CODE_OF_CONDUCT.md): collaboration expectations

## Structure

Each artifact lives in its own directory under `apps/` with an `index.html` entry point. All pages load the shared `css/style.css`; mature apps also load their app-local `css/app.css` for layout rules, and reuse `js/app-theme.js` and `js/modules/app-shell.js` for the shared app shell.

```text
apps/
  artifact-name/
    index.html        # Required entry point
    js/
      app.js          # App-local behavior
    docs/
      architecture.md # Internal engineering notes
      verification.md # Formula and QA notes
      decisions.md    # Local design/engineering decisions
    README.md         # App-level overview and structure
    name.txt          # Display name
    description.txt   # Optional short description
    tags.txt          # Optional content tags (one per line)
    tools.txt         # Optional AI tools used (one per line)
    thumbnail.webp    # Preferred auto-generated screenshot
```

## Adding a new artifact

Both flows emit a complete artifact that passes every gate out of the box: `index.html` wired to the shared stylesheet and app shell with the self-only CSP meta, an `css/app.css` and `js/app.js` stub, a `README.md` plus `docs/` stubs, the metadata files, and a passing `tests/js/apps/<slug>/app.test.js`.

1. Scaffold the directory:
   - Fresh placeholder: `make new name=my-artifact`
   - Drop in an existing AI-generated HTML file: `make new name=my-artifact src=path/to/file.html`. The file is installed as `index.html`; the CSP meta and shared stylesheet links are injected only when absent, and any off-origin script or style references are reported so you can vendor or remove them before the security lint runs.
2. Build your artifact in `index.html` (or refine the drop-in) and fill in the metadata files
3. Run `make validate` to catch missing required files before pushing
4. Push to `main`: CI regenerates derived files, builds `_site/`, and deploys the site
5. Open a PR to run the same checks and publish a live preview

CI is intentionally strict for the root publishing platform: dependency review, secret scanning, browser-based checks, and fail-closed deploys. See [`docs/architecture.md`](docs/architecture.md) for the full pipeline, including how regenerated thumbnails flow back into PRs.

## Local development

- `make help`: the Makefile is the supported interface for setup, checks, generation, and GitHub helpers
- `make setup`: default toolchain; `make setup-all` adds Chromium for browser tests and thumbnails
- `make ci`: non-browser local gate; `make check-web` adds browser coverage; `make check` is the full CI-equivalent gate
- For the day-to-day workflow, CI behavior, and troubleshooting, see [`docs/operations.md`](docs/operations.md) and [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md)

## License

[MIT](LICENSE)
