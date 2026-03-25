# Artifacts

A collection of interactive HTML artifacts built with AI tools (Claude, ChatGPT, Gemini, etc.). Each artifact is a self-contained web application with its own page.

**Live site:** <!-- AUTO:SITE_URL -->https://hermione-granger-1176.github.io/artifacts/<!-- /AUTO:SITE_URL -->

<!-- AUTO:TOTAL_BADGE --><img src="https://img.shields.io/badge/Total-2-D97706?style=for-the-badge" alt="Total"><!-- /AUTO:TOTAL_BADGE -->

## Topics

<!-- AUTO:TAG_BADGES_START -->
<img src="https://img.shields.io/badge/Finance-27AE60?style=flat-square" alt="Finance">&nbsp;
<img src="https://img.shields.io/badge/Calculator-2E86C1?style=flat-square" alt="Calculator">&nbsp;
<img src="https://img.shields.io/badge/Visualization-E67E22?style=flat-square" alt="Visualization">&nbsp;
<img src="https://img.shields.io/badge/Education-F39C12?style=flat-square" alt="Education">&nbsp;
<img src="https://img.shields.io/badge/AI-A0C8E8?style=flat-square" alt="AI">&nbsp;
<img src="https://img.shields.io/badge/LLM-E8C8A0?style=flat-square" alt="LLM">
<!-- AUTO:TAG_BADGES_END -->

## AI Tools

<!-- AUTO:TOOL_BADGES_START -->
<img src="https://img.shields.io/badge/Claude-D97706?style=flat-square&logo=anthropic&logoColor=white" alt="Claude">
<!-- AUTO:TOOL_BADGES_END -->

## Snapshot

- <!-- AUTO:TOTAL_COUNT -->2<!-- /AUTO:TOTAL_COUNT --> artifacts published
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

Each artifact lives in its own directory under `apps/` with an `index.html` entry point. This allows future refactoring into multi-file projects without breaking URLs.

```
apps/
  artifact-name/
    index.html        # Entry point (currently single-file, can be split later)
    name.txt          # Display name
    description.txt   # Optional short description
    tags.txt          # Optional content tags (one per line)
    tools.txt         # Optional AI tools used (one per line)
    thumbnail.webp    # Auto-generated screenshot
```

## Adding a new artifact

1. Create a new scaffold with `make new name=my-artifact`, or create a kebab-case directory under `apps/` manually
2. Replace the scaffold `index.html` with your artifact and fill in the metadata files
3. Run `make validate` to catch missing required files before pushing
4. Push to `main` or trigger a manual run to let CI regenerate derived files, prepare `_site/`, and deploy the site
5. Open a PR to run the same checks and publish a live preview without modifying the source branch

CI is intentionally strict for the root publishing platform: dependency review, secret scanning, browser-based accessibility and interaction checks, preview deploys, live post-deploy browser verification, and main deploys fail closed instead of auto-healing source branches. Preview and production deploys both consume the exact verified `_site/` artifact built in CI.

## Local development

1. Bootstrap the local toolchain:

   ```bash
   make setup-local
   ```

   This installs pinned Python dependencies from `locks/requirements-dev.lock` and pinned Node dependencies from `package-lock.json` without Chromium. Run `make setup` when you also want Playwright Chromium for browser tests or thumbnail generation. Same-repo Dependabot pip PRs that update `pyproject.toml` refresh the Python lock files automatically through CI.

2. Run the fast local verification flow while you iterate:

   ```bash
   make check-local
   ```

   This runs local linting, non-browser Python and JavaScript tests, JavaScript coverage, dependency audits, and artifact validation.

3. Run browser and thumbnail checks when you touch root-gallery behavior or before shipping:

   ```bash
   make web
   ```

4. Run the full release gate before pushing when you want the CI-equivalent local flow:

   ```bash
    make check
    ```

    `make check` keeps the root-platform browser gate in one place: Playwright smoke, accessibility, and browser-flow tests run before index generation and `_site/` assembly.

5. Validate top-level artifact directories explicitly when needed:

   ```bash
   make validate
   ```

6. Regenerate derived files before pushing:

   ```bash
   make generate
   ```

7. Build the clean deployable site directory when you want to inspect the exact Pages payload:

   ```bash
   make site
   ```

8. If you prefer running commands directly, most dependency-backed targets use the `.venv` environment with the frozen dependency sets in `locks/requirements*.lock` and `package-lock.json`, while a few lightweight helper targets call `python3.12` through the `PYTHON` Make variable.

9. If you change Python dependency declarations, regenerate the Python lock files:

   ```bash
   make lock
   ```

   If you change Node dependencies, refresh `package-lock.json` with npm tooling before rerunning `npm ci`, `make check-local`, or `make check`.

10. Serve the repo root or `_site/` from a local static server when you want to verify the gallery in a browser, for example:

   ```bash
   python3 -m http.server 4173
   ```

    Then open `http://127.0.0.1:4173/`.

11. Verify a deployed preview or production URL in a real browser when needed:

    ```bash
    ARTIFACTS_LIVE_SITE_URL="https://example.com/artifacts/" make test-browser-live
    ```

## License

[MIT](LICENSE)
