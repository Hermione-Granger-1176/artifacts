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
- **Line length:** 100 characters, enforced by ruff lint and format
- **Linter:** ruff, configured in `pyproject.toml`
- **Rule sets:** E/W (pycodestyle), F (pyflakes), I (isort), B (bugbear), C4 (comprehensions), UP (pyupgrade), ARG (unused arguments), SIM (simplify), TC (type-checking imports), PTH (pathlib), RUF (ruff-specific), D (pydocstyle)
- **Target:** Python 3.12+
- **Docstrings:** required on public functions, classes, and methods (ruff D rules), one-line or multi-line Google style
- **Type hints:** use `from __future__ import annotations` for modern syntax
- **Imports:** sorted by isort (enforced by ruff rule I); imports used only in annotations move into `if TYPE_CHECKING:` blocks (ruff TC rules)
- **Dead code:** vulture checks scripts and tests at minimum confidence 60 using the shared `pyproject.toml` configuration; names that vulture cannot see used dynamically (for example TypedDict fields) live in `ignore_names`
- **Coverage:** pytest enforces 100% line and branch coverage for `scripts/`
- **Warnings:** pytest promotes warnings to errors (`filterwarnings`), so fix warnings at the source
- **Private functions:** prefix with a leading underscore
- **Entry points:** guard `if __name__ == "__main__":` blocks with `# pragma: no cover`

Run `make lint`, `make format-check`, or `make check-local` to check. Those targets also run the EditorConfig and formatting validation used in CI.

## JavaScript

- **Indent:** 2 spaces
- **Line length:** not enforced, but keep lines readable
- **Linter:** ESLint 10 (flat config), configured in `eslint.config.js`
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
- **No `eval`**, no `document.write`
- **`innerHTML`/`outerHTML`:** every interpolated value must be a literal you control or escaped via `escapeHtml()`/`escapeAttribute()` from `js/modules/html-escape.js`. Assigning a template literal directly to `innerHTML`/`outerHTML` is blocked by ESLint (`no-restricted-syntax`); build the markup in a helper that escapes, or use `textContent`/`createElement` instead

Run `make lint`, `make dead-code-js`, `make coverage-js`, or `make check-local` to check. `make coverage-js` enforces the current baseline across all source files imported by tests. Thresholds and exclusions are configured in `package.json`; Knip scope is configured in `config/knip.json`.

## CSS

- **Indent:** 2 spaces
- **Entry file:** `css/style.css`, the single stylesheet for the whole site
- **Shared app system:** app tokens, shared shell rules, and current app-specific layout selectors live in `css/style.css`
- **Linter:** stylelint, configured in `stylelint.config.js`
- **Conventions:**
  - BEM-inspired class names (e.g., `.artifact-card`, `.detail-close`)
  - CSS custom properties for theming and shared geometry (for example `--color-bg-primary`, `--text-primary`, `--accent`, `--book-sheet-min-height`, `--gallery-*`, `--desk-note-*`, and shared app-shell aliases)
  - Mature apps use the bookmark-note palette as the shared source of truth for light and dark themes
  - Authored app colors should use `rgb()` and `rgba()` values instead of hex literals
  - `prefers-reduced-motion` respected for transitions and animations
  - Desktop-first responsive breakpoints

Run `make lint-css` or `make lint` to check.

## HTML

- **Indent:** 2 spaces
- **Artifacts:** `index.html` remains the entry point, and mature apps should import `../../css/style.css` while keeping app-local behavior in `js/app.js`
- **Accessibility:** semantic elements, ARIA attributes, keyboard navigation, focus management
- **External links:** always include `rel="noopener noreferrer"`

## Mature app contract

- Shared app tokens live in `css/style.css`
- Shared mature-app theme bootstrap lives in `js/app-theme.js`, and `js/modules/app-shell.js` owns the reusable shell markup plus shell behavior
- Mature apps should import the single shared stylesheet and use `artifact-app` plus an `app-<slug>` body class
- Mature app HTML should keep app-specific body content local, while shell placeholders (`data-app-shell`) let the shared module render the common header, runtime-error banner, and scroll-to-top control
- App headers should reuse the Artifacts logo, back button, theme toggle, and app-styled scroll-to-top pattern
- App content containers should stay near `1000px` wide unless a product requirement clearly needs more space

## YAML

- **Indent:** 2 spaces
- **Linter:** yamllint with repository overrides in `.yamllint.yml`
- **GitHub Actions:** pin third-party actions to full commit SHAs with a version comment (e.g., `actions/checkout@abc123 # v6`)

Prettier also owns docs, metadata, workflow, and tooling-script formatting through `config/prettierrc.json` and `config/prettierignore`. Run `make format-check` to verify it and `make fmt-prettier` only when you intentionally want to rewrite formatted files.

Run `make lint-yaml` for YAML structure/format checks and `make lint-workflows` for workflow-specific action linting.

## Makefile

- **Indent:** tabs (required by Make)
- **Variables:** uppercase with `?=` defaults; `PYTHON` auto-detects the first available of `python3.12` (CI-pinned), `python3.13`, `python3.14`, or `python3`, and is overridable via an env var, e.g. `PYTHON=python3.13 make setup`

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
- JS modules in `js/modules/`, tests grouped under `tests/js/home/`, `tests/js/common/`, `tests/js/apps/`, and `tests/js/workflows/`
- Documentation in `docs/`
- CI workflows in `.github/workflows/`, composite actions in `.github/actions/`
- Lock files: Python locks in `locks/`, npm lock at root (`package-lock.json`)
