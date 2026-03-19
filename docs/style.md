# Style Guide

Editor and language conventions for the artifacts workspace. These rules are
enforced by tooling where possible and by review otherwise.

## Editor configuration

The `.editorconfig` file at the repository root defines per-filetype settings.
Most editors and IDEs support it natively or through a plugin.

Summary of settings:

- All files use UTF-8 encoding, LF line endings, and a trailing newline
- Trailing whitespace is trimmed (except in markdown, where trailing spaces
  can be significant)
- Indentation varies by file type (see below)

## Python

- **Indent:** 4 spaces
- **Line length:** 88 characters (black-compatible)
- **Linter:** ruff, configured in `pyproject.toml`
- **Rule sets:** B (bugbear), E (pycodestyle), F (pyflakes), I (isort), UP (pyupgrade), W (warnings)
- **Target:** Python 3.12+
- **Docstrings:** required on all public functions, one-line or multi-line Google style
- **Type hints:** use `from __future__ import annotations` for modern syntax
- **Imports:** sorted by isort (enforced by ruff rule I)
- **Private functions:** prefix with a leading underscore
- **Entry points:** guard `if __name__ == "__main__":` blocks with `# pragma: no cover`

Run `make lint` to check. Ruff is enforced in CI.

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
  - HTML escaping via `escapeHtml()` for all dynamic content in templates
  - Dependency injection via function parameters, not globals
- **DOM access:** use `documentObj`/`windowObj` parameters for testability
- **No `eval`**, no `document.write`, no `innerHTML` with unescaped user input

Run `make lint` to check. ESLint is enforced in CI.

## CSS

- **Indent:** 2 spaces
- **File:** single `css/style.css` for the root gallery
- **Conventions:**
  - BEM-inspired class names (e.g., `.artifact-card`, `.detail-close`)
  - CSS custom properties for theming (`--bg`, `--text`, `--accent`)
  - `prefers-reduced-motion` respected for transitions and animations
  - Mobile-first responsive breakpoints

## HTML

- **Indent:** 2 spaces
- **Artifacts:** self-contained `index.html` with inline CSS/JS or CDN dependencies
- **Accessibility:** semantic elements, ARIA attributes, keyboard navigation, focus management
- **External links:** always include `rel="noopener noreferrer"`

## YAML

- **Indent:** 2 spaces
- **GitHub Actions:** pin third-party actions to full commit SHAs with a version comment
  (e.g., `actions/checkout@abc123 # v6`)

## Makefile

- **Indent:** tabs (required by Make)
- **Variables:** uppercase with `?=` defaults (e.g., `PYTHON ?= python3.12`)

## Markdown

- **Indent:** 2 spaces for nested lists
- **Tables:** align pipe characters vertically using `python scripts/align_tables.py`
- **Punctuation:**
  - Use standard dashes (`-`) for list items and horizontal rules
  - Do not use em dashes or en dashes in prose
  - Use commas, semicolons, or parentheses instead
- **Line length:** not enforced, but wrap at natural sentence boundaries when practical
- **Code blocks:** use fenced blocks with language identifiers (e.g., ` ```python `)
- **Links:** prefer relative paths for in-repo references

## Logo and favicon

- Logo and favicon assets live in `assets/icons/`
- `icon.svg` is the canonical vector logo with dark/light mode via `prefers-color-scheme`
- Raster icons (`favicon.ico`, `apple-touch-icon.png`, `icon-192.png`, `icon-512.png`) are generated from the SVG design using Pillow
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
- JS modules in `js/modules/`, tests in `tests/js/`
- Documentation in `docs/`
- CI workflows in `.github/workflows/`, composite actions in `.github/actions/`
- Lock files: Python locks in `locks/`, npm lock at root (`package-lock.json`)
