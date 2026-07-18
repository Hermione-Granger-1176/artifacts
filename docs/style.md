# Style Guide

Editor and language conventions for the artifacts workspace. These rules are enforced by tooling where possible and by review otherwise.

## Editor configuration

The `.editorconfig` file at the repository root defines per-filetype settings. Most editors and IDEs support it natively or through a plugin. `make editorconfig-check` enforces the supported rules for covered repository files in automation, while `make lint` layers language-specific linters on top. Both targets are discoverable through `make help`.

Summary of settings:

- All files use UTF-8 encoding, LF line endings, and a trailing newline
- Trailing whitespace is trimmed (except in markdown, where trailing spaces can be significant)
- Indentation varies by file type (see below)
- `apps/**/*.js`, `apps/**/*.css`, `apps/**/*.html`, and `apps/**/*.md` now follow the same indentation rules as the rest of the workspace

## Python

- **Indent:** 4 spaces
- **Line length:** 100 characters
- **Linter:** ruff, configured in `pyproject.toml`
- **Rule sets:** ARG, B, C4, D, E, F, I, PTH, RUF, SIM, TC, UP, and W
- **Target:** Python 3.12+
- **Docstrings:** required on all public functions, one-line or multi-line Google style
- **Type hints:** mypy runs in strict mode over `scripts/`; use `from __future__ import annotations` for modern syntax
- **Imports:** sorted by isort (enforced by ruff rule I)
- **Private functions:** prefix with a leading underscore
- **Entry points:** guard `if __name__ == "__main__":` blocks with `# pragma: no cover`

Run `make lint`, `make typecheck-py`, `make dead-code-py`, `make format-py-check`, or `make check-local` to check. Those targets also run the EditorConfig validation used in CI.

## JavaScript

- **Indent:** 2 spaces
- **Line length:** not enforced, but keep lines readable
- **Linter:** ESLint 10 (flat config), configured in `config/eslint.config.js`
- **Formatter:** Prettier covers supported JSON, YAML, markdown, config, and tooling script files that are not excluded by `config/prettierignore`
- **Type checks:** TypeScript runs the web typecheck target from `config/jsconfig.json`
- **Module format:** ES modules (`import`/`export`), no CommonJS
- **JSDoc:** required on all exported functions and significant private functions
- **Naming:** camelCase for variables and functions, PascalCase for classes
- **Patterns:**
  - Factory functions returning plain objects (see `createRuntime`, `createMotionHelper`)
  - Pure functions for data transformations (see `catalog.js`)
  - Guard clauses and early returns in interaction-heavy flows
  - Switch statements or lookup maps when event or status dispatch is clearer than chained conditionals
  - HTML escaping via `escapeHtml()` for all dynamic content in templates
  - Dependency injection via function parameters, not globals
- **DOM access:** use `documentObj`/`windowObj` parameters for testability
- **No `eval`**, no `document.write`, no `innerHTML` with unescaped user input

Run `make lint`, `make typecheck-web`, `make dead-code-js`, `make coverage-js`, or `make check-local` to check. `make coverage-js` enforces the current baseline across all source files imported by tests. Thresholds and exclusions are configured in `package.json`.

## CSS

- **Indent:** 2 spaces
- **Shared stylesheet sources:** `css/src/` provides gallery styles, app tokens, shell rules, reusable app components, utilities, and responsive rules in numeric load order
- **Shared public stylesheet:** generated `css/style.css` is the single stylesheet loaded by the gallery and mature apps. Rebuild it with `make styles`; do not edit it directly
- **App stylesheet:** `apps/<slug>/css/app.css` provides app-specific composition and layout selectors scoped by `body.app-<slug>`
- **Linter:** stylelint, configured in `config/stylelint.config.js`
- **Conventions:**
  - BEM-inspired class names (e.g., `.artifact-card`, `.detail-close`)
  - CSS custom properties for theming and shared geometry (for example `--color-bg-primary`, `--text-primary`, `--accent`, `--book-sheet-min-height`, `--gallery-*`, `--desk-note-*`, and the shared app-shell tokens)
  - Mature apps use the bookmark-note palette as the shared source of truth for light and dark themes
  - Authored app colors should use `rgb()` and `rgba()` values instead of hex literals
  - Keep shared rules in the matching ordered source partial: `01-tokens.css`, `02-gallery.css`, `03-artifact-shell.css`, `04-artifact-components.css`, `05-accessibility-and-utilities.css`, or `06-responsive-and-motion.css`
  - Use descriptive section headers in long stylesheets. Group app rules by the visualisation or page region they support
  - `prefers-reduced-motion` respected for transitions and animations
  - Desktop-first responsive breakpoints

Run `make lint-css` or `make lint` to check.

## Design tokens and shared app components

The shared design system lives in `css/src/` and is bundled into `css/style.css`. Authored app CSS should build on the tokens and components below rather than restating colors, geometry, or component foundations.

### Token families and scopes

- Gallery tokens live in `:root` (with a `[data-theme="dark"]` override) in `css/src/01-tokens.css`: backgrounds, text, accent, borders, the bookmark-note palette, card colors, `--radius-*`, shadows, and gallery layout variables. They apply to the gallery and cascade into apps.
- Artifact-app tokens live under `body.artifact-app` (with a `[data-theme="dark"] body.artifact-app` override) in the same partial:
  - Hue tokens `--color-{blue,green,red,amber,purple}`, each with a matching `-text` and `-emphasis` variant
  - Note pastels `--note-{yellow,red,blue,green,amber,purple}`
  - Surface, border, text, chart, and tooltip tokens plus `--color-text-on-accent`
  - A type scale (`--font-size-xs`, `-2xs`, `-sm`, `-control`, `-md`, `-base`, `-lg`) and the label tracking token `--tracking-label`
  - A spacing scale (`--space-1` through `--space-6`, plus `--space-8`), radii (`--radius-xs`, `-sm`, `-md`, `-pill`), and `--shadow-card`
- In the dark artifact scope every `--color-*-text` remaps to its `--color-*-emphasis` value and the note pastels get dark remaps, so rules that reference the tokens follow the theme automatically.

### Color rule

- Authored app colors use the shared tokens or `rgb()` / `rgba()` values, never hex literals. A `color-mix()` over a token is fine
- Prefer a token over a raw color whenever one fits, so a theme change stays a single-file edit in `css/src/01-tokens.css`

### Shared components versus app-local CSS

- Reach for the shared component families in `css/src/04-artifact-components.css` before writing app CSS: `.control-field` (with `-head`, `-hints`, `-note`), `.stat-grid` / `.stat` (modifiers `.is-center`, `.stat-label.is-caps`, `.stat-value.is-mono`), `.chip` (hue tones `.is-*`, `.is-mono`, solid `.is-solid-*`), `.segmented` (`.is-fused`, `.active`), `.meter` / `.meter-fill` (tone modifiers), `.app-callout` (hue tones), `.section-kicker`, plus the shared buttons, inputs, tables, code windows, and `.section-nav`
- Keep `apps/<slug>/css/app.css` focused on app-specific dimensions, grids, visualisations, and component variants built on those tokens and families. It retains its `body.app-<slug>` scope
- A change to a shared component or token is intentional shared work in `css/src/`, not an app-local edit

### Token lint

`make lint-app-css-tokens` guards `apps/*/css/*.css` against drift. It forbids hex colors and literal `rgb()` / `rgba()` colors, and requires tokens for `border-radius` (px literals of 6px and up), `font-size`, and `letter-spacing`. Sub-token decorative radii of 1px through 5px, `clamp()` and em / rem / % font sizes, and `normal` letter-spacing stay allowed, alongside a few documented allowlist entries in the checker.

## HTML

- **Indent:** 2 spaces
- **Artifacts:** `index.html` remains the entry point, and mature apps should import `../../css/style.css` followed by `./css/app.css` while keeping app-local behavior in `js/app.js`
- **Accessibility:** semantic elements, ARIA attributes, keyboard navigation, focus management
- **External links:** always include `rel="noopener noreferrer"`

## Mature app contract

- Shared app tokens live in `css/src/01-tokens.css`
- Shared mature-app theme bootstrap lives in `js/app-theme.js`, and `js/modules/app-shell.js` owns the reusable shell markup plus shell behavior
- Mature apps should import the shared stylesheet first, then `./css/app.css`, and use `artifact-app` plus an `app-<slug>` body class
- Reusable colours, controls, surfaces, and callouts live in the relevant `css/src/` partial and are bundled into `css/style.css`. App-specific layout selectors live in `apps/<slug>/css/app.css` and retain their `body.app-<slug>` scope
- Mature app HTML should keep app-specific body content local, while shell placeholders (`data-app-shell`) let the shared module render the common header, runtime-error banner, and scroll-to-top control
- App headers should reuse the Artifacts logo, back button, theme toggle, and app-styled scroll-to-top pattern
- App content containers should stay near `1000px` wide unless a product requirement clearly needs more space

## YAML

- **Indent:** 2 spaces
- **Linter:** yamllint with repository overrides in `.yamllint.yml`
- **GitHub Actions:** pin third-party actions to full commit SHAs with a version comment (e.g., `actions/checkout@abc123 # v6`)

Run `make lint-yaml` for YAML structure/format checks and `make lint-workflows` for workflow-specific action linting.

## Makefile

- **Indent:** tabs (required by Make)
- **Variables:** uppercase with `?=` defaults. `PYTHON` auto-detects a supported interpreter and can be overridden when needed

## Markdown

- **Indent:** 2 spaces for nested lists
- **Tables:** align pipe characters vertically using `make align-tables`
- **Punctuation:**
  - Use standard dashes (`-`) for list items and horizontal rules
  - Do not use em dashes or en dashes in prose
  - Use commas, semicolons, or parentheses instead
- **Line length:** not enforced, but wrap at natural sentence boundaries when practical
- **Code blocks:** use fenced blocks with language identifiers (e.g., ` ```python `)
- **Links:** prefer relative paths for in-repo references

## Logo and favicon

- Logo and favicon assets live in `assets/icons/`
- The social share preview image lives at `assets/social/share-preview.png`
- `icon.svg` is the canonical vector logo with dark/light mode via `prefers-color-scheme`
- Raster icons (`favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`) are checked-in derivatives of the SVG design
- The share preview image should stay stable at 1200x630 so deploy-time Open Graph and Twitter metadata remain valid
- `manifest.webmanifest` defines PWA metadata; `start_url` is patched by `prepare_site.py` at deploy time
- The header uses an inline SVG copy of the logo (not a reference to the file) to avoid an extra network request

## Commit messages

- Subject line: imperative, sentence case, no Conventional Commit prefix
- Keep the subject concise and action-focused
- For non-trivial commits, include a short bullet list body with `- ` bullets
- One blank line between subject and body
- One blank line before any trailers

## File organization

- Python scripts in `scripts/`, tests in `tests/`
- JS modules in `js/modules/`, tests grouped under `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, `tests/js/tooling/`, and `tests/js/workflows/`
- Documentation in `docs/`
- CI workflows in `.github/workflows/`, composite actions in `.github/actions/`
- Lock files at the repo root: `uv.lock` for Python, `package-lock.json` for npm
