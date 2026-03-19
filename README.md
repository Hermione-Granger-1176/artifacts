# Artifacts

A collection of interactive HTML artifacts built with AI tools (Claude, ChatGPT, Gemini, etc.). Each artifact is a self-contained web application with its own page.

**Live site:** <!-- AUTO:SITE_URL -->https://hermione-granger-1176.github.io/artifacts/<!-- /AUTO:SITE_URL -->

<!-- AUTO:TOTAL_BADGE --><img src="https://img.shields.io/badge/Total-1-D97706?style=for-the-badge" alt="Total"><!-- /AUTO:TOTAL_BADGE -->

## Topics

<!-- AUTO:TAG_BADGES_START -->
<img src="https://img.shields.io/badge/Finance-27AE60?style=flat-square" alt="Finance">&nbsp;
<img src="https://img.shields.io/badge/Calculator-2E86C1?style=flat-square" alt="Calculator">&nbsp;
<img src="https://img.shields.io/badge/Visualization-E67E22?style=flat-square" alt="Visualization">
<!-- AUTO:TAG_BADGES_END -->

## AI Tools

<!-- AUTO:TOOL_BADGES_START -->
<img src="https://img.shields.io/badge/Claude-D97706?style=flat-square&logo=anthropic&logoColor=white" alt="Claude">
<!-- AUTO:TOOL_BADGES_END -->

## Snapshot

- <!-- AUTO:TOTAL_COUNT -->1<!-- /AUTO:TOTAL_COUNT --> artifacts published
- Browse the live website for searchable thumbnails, multi-select filters, theme persistence, and detail overlays.

## Docs

- [`workspace.md`](docs/workspace.md): repository layout and responsibilities
- [`architecture.md`](docs/architecture.md): runtime, build, and deployment design
- [`operations.md`](docs/operations.md): local workflows, CI, and generation notes
- [`maintenance.md`](docs/maintenance.md): maintenance rules and long-term repo hygiene

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

## Local development

1. Bootstrap the local toolchain:

   ```bash
   make setup
   ```

2. Run linting, tests, and artifact validation (including the 100% Python coverage gate):

   ```bash
   make check
   ```

3. Validate top-level artifact directories before pushing:

   ```bash
   make validate
   ```

4. Regenerate derived files before pushing:

   ```bash
   make generate
   ```

5. Build the clean deployable site directory when you want to inspect the exact Pages payload:

   ```bash
   make site
   ```

6. If you prefer running commands directly, the Makefile uses `.venv` and installs dependencies from `pyproject.toml`.

7. Open `index.html` in a browser to verify the gallery locally.

## License

[MIT](LICENSE)
