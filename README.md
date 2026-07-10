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
- [`frontend.md`](docs/frontend.md): JavaScript module layout and test coverage
- [`operations.md`](docs/operations.md): local workflows, CI, and generation notes
- [`maintenance.md`](docs/maintenance.md): maintenance rules and long-term repo hygiene
- [`style.md`](docs/style.md): editor configuration and language conventions
- [`CONTRIBUTING.md`](.github/CONTRIBUTING.md): contribution and dependency update workflow
- [`SECURITY.md`](.github/SECURITY.md): how to report vulnerabilities
- [`CODE_OF_CONDUCT.md`](.github/CODE_OF_CONDUCT.md): collaboration expectations

## Structure

Each artifact lives in its own directory under `apps/` with an `index.html` entry point. All pages share the single site stylesheet at `css/style.css`. Mature apps keep their own JavaScript and docs while reusing `js/app-theme.js` and `js/modules/app-shell.js` for the shared app shell.

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

1. Create a new scaffold with `make new name=my-artifact`, or create a kebab-case directory under `apps/` manually. The scaffold also creates `tests/js/apps/<slug>/` so app-specific Node tests have a matching home.
2. Replace the scaffold `index.html` with your artifact and fill in the metadata files
3. Run `make validate` to catch missing required files before pushing
4. Push to `main` or trigger a manual run to let CI regenerate derived files, prepare `_site/`, and deploy the site
5. Open a PR to run the same checks and publish a live preview; trusted same-repo PRs may also save regenerated thumbnails back to the source branch when CI renders a new `thumbnail.webp`

CI is intentionally strict for the root publishing platform: dependency review, secret scanning, browser-based accessibility and interaction checks, preview deploys, live post-deploy browser verification, and main deploys fail closed. Preview and production deploys both consume the exact verified `_site/` artifact built in CI. Trusted same-repo PRs can write regenerated thumbnails back to the same PR branch, while trusted `main` pushes open or update a follow-up thumbnail PR instead of writing directly to `main`.

## Local development

- Run `make help` first; the Makefile is the supported interface for local setup, checks, generation, and GitHub workflow helpers.
- Use `make setup` for the default local toolchain, or `make setup-all` when you also need Chromium for browser tests and thumbnail generation.
- Use `make ci` or `make check-local` for the non-browser local gate, including formatting, linting, tests, coverage, dead-code checks, dependency audits, validation, and canonical generated-file drift checks. Use `make check-web` when browser coverage or thumbnails matter, and `make check` for the full CI-equivalent local gate.
- Use `make validate`, `make generate`, `make site`, and `make lock` when you need explicit structure checks, derived-file refreshes, deploy-payload inspection, or Python lock refreshes.
- For the full day-to-day workflow, CI behavior, dependency expectations, and troubleshooting, see [`docs/operations.md`](docs/operations.md), [`docs/workspace.md`](docs/workspace.md), and [`.github/CONTRIBUTING.md`](.github/CONTRIBUTING.md).

## License

[MIT](LICENSE)
