# Style guide

This reference defines the workspace's editor settings and language conventions. Configuration files enforce tool rules. Review covers prose and conventions that tools do not check.

## Editor configuration

The root `.editorconfig` defines settings by file type. `make editorconfig-check` checks supported rules, and `make lint` also runs language-specific linters. Editors use `.editorconfig` through built-in support or a plugin.

The shared settings are:

- All files use UTF-8 encoding, LF line endings, and a trailing newline
- Trailing whitespace is trimmed (except in markdown, where trailing spaces can be significant)
- Indentation varies by file type (see below)
- `apps/**/*.js`, `apps/**/*.css`, `apps/**/*.html`, and `apps/**/*.md` follow the same indentation rules as the rest of the workspace

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

Run `make lint`, `make typecheck-py`, `make dead-code-py`, `make format-py-check`, or `make check-local` to check. Of these, `make lint` and `make check-local` also run the EditorConfig validation used in CI; the other targets are focused Python checks only.

## JavaScript

- **Indent:** 2 spaces
- **Line length:** not enforced, but keep lines readable
- **Linter:** ESLint 10 (flat config), configured in `config/eslint.config.js`
- **Formatter:** Prettier covers supported JSON, YAML, config, and tooling script files that are not excluded by `config/prettierignore`; Markdown table alignment is owned by `make align-tables-check`
- **Type checks:** `make typecheck-web` uses `config/jsconfig.json` with `strict: true`. Chart.js UMD globals use exact-pinned `chart.js` and plugin devDependencies for types, plus ambient declarations in `config/types/`. These packages are not bundled into the site. JSDoc identifies call-site types, such as `import("chart.js").ChartOptions` or `@this {HTMLInputElement}`. `any` is reserved for upstream values with no usable narrower type
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
- **Shared public stylesheet:** `css/style.css` is the generated shared bundle. Mature apps also load their own `css/app.css`. `make styles` rebuilds the shared bundle
- **App stylesheet:** `apps/<slug>/css/app.css` provides app-specific composition and layout selectors scoped by `body.app-<slug>`
- **Linter:** stylelint, configured in `config/stylelint.config.js`
- **Conventions:**
  - BEM-inspired class names (for example, `.artifact-card`, `.detail-close`)
  - CSS custom properties for theming and shared geometry (for example `--color-bg-primary`, `--text-primary`, `--accent`, `--book-sheet-min-height`, `--gallery-*`, `--desk-note-*`, and the shared app-shell tokens)
  - Mature apps use the bookmark-note palette as the shared source of truth for light and dark themes
  - Authored colors use `rgb()` and `rgba()` values instead of hex literals; in app stylesheets they must additionally be token-derived (see the color rule below)
  - Keep shared rules in the matching ordered source partial: `01-tokens.css`, `01-theme-light.css`, `01-theme-dark.css`, `02-gallery.css`, `03-artifact-shell.css`, `04-artifact-components.css`, `05-accessibility-and-utilities.css`, or `06-responsive-and-motion.css`
  - Use descriptive section headers in long stylesheets. Group app rules by the visualisation or page region they support
  - `prefers-reduced-motion` respected for transitions and animations
  - Desktop-first responsive breakpoints

Run `make lint-css` (stylelint rules) plus `make lint-app-css-tokens` (design-token compliance, see the token lint below) to check, or `make lint` for both.

## Design tokens and shared app components

The shared design system lives in `css/src/` and is bundled into `css/style.css`. Authored app CSS should build on the tokens and components below rather than restating colors, geometry, or component foundations.

### Token families and scopes

- Every color that changes with the theme lives in `css/src/01-theme-light.css` and `css/src/01-theme-dark.css`. The two files list the same tokens on the same lines, so a diff between them shows only the values. Add a themed token to both files at the same line.
- `css/src/01-tokens.css` holds everything that stays the same in both themes: fonts, the bookmark-note palette, card colors, the printed-document palette, radii, and gallery layout variables.
- Gallery tokens sit on `:root` and cascade into apps. The dark file uses `:root[data-theme="dark"]` and `html[data-theme="dark"] body.artifact-app`, which outrank the light selectors, so file order does not matter.
- Artifact-app tokens live under `body.artifact-app`:
  - Hue tokens `--color-{blue,green,red,amber,purple}`, each with a matching `-text` and `-emphasis` variant
  - Note pastels `--note-{yellow,red,blue,green,amber,purple}`
  - Surface, border, text, chart, and tooltip tokens plus `--color-text-on-accent`
  - A type scale (`--font-size-{2xs,xs,sm,control,md,base,lg}`) and the label tracking token `--tracking-label`
  - A spacing scale (`--space-1` through `--space-6`, plus `--space-8`), radii (`--radius-{xs,sm,md,pill}`), and `--shadow-card`
- In the dark artifact scope every `--color-*-text` remaps to its `--color-*-emphasis` value, the note pastels get dark remaps, and `--color-text-on-accent` turns dark because the dark hues are brighter. Rules that reference the tokens follow the theme without a `[data-theme="dark"]` override.
- Component and app stylesheets do not write `[data-theme="dark"]` color rules. When a component needs a different color at night, add a themed token to both theme files instead.

### Color rule

- Shared token definitions use `rgb()`, `rgba()`, or other tokens, never hex literals. In `apps/<slug>/css/*.css`, colors derive from `var()` or a `color-mix()` over tokens. Raw color values belong in the shared `css/src/` definitions. `transparent` and `currentcolor` remain allowed
- Prefer a token over a raw color whenever one fits, so a theme change stays an edit to the two theme files

### Shared components versus app-local CSS

- Reach for the shared component families in `css/src/04-artifact-components.css` before writing app CSS: `.control-field` (with `-head`, `-hints`, `-note`), `.stat-grid` / `.stat` (modifiers `.is-center`, `.stat-label.is-caps`, `.stat-value.is-mono`), `.chip` (hue tones `.is-*`, `.is-mono`, solid `.is-solid-*`), `.segmented` (`.is-fused`, the inset pill `.is-inset`, `.active`), `.meter` / `.meter-fill` (tone modifiers), `.app-callout` (hue tones), `.section-kicker`, plus the shared buttons, inputs, tables, code windows, and `.section-nav`
- Keep `apps/<slug>/css/app.css` focused on app-specific dimensions, grids, visualizations, and component variants built on those tokens and families. It retains its `body.app-<slug>` scope
- A change to a shared component or token is intentional shared work in `css/src/`, not an app-local edit

### Token lint

`make lint-app-css-tokens` checks `apps/*/css/*.css`. It rejects these values:

- Hex colors in declarations.
- Color functions whose channels do not start with `var()` or `color-mix()`. A token used only for alpha does not satisfy the rule. Functions include `rgb()`, `rgba()`, `hsl()`, `hwb()`, `lab()`, `lch()`, `oklab()`, `oklch()`, and `color()`.
- `color-mix()` calls with no `var()` token.
- Named colors in color declarations, except `transparent` and `currentcolor`.
- `border-radius` pixel literals above 5px.
- Pixel font sizes, including inside `clamp()`.
- `letter-spacing` values other than one `var(--tracking-*)` token or `normal`.

Decorative radii up to 5px remain allowed. Font sizes can use relative units or `clamp()` with tokens and relative units. The checker also contains documented exceptions scoped to their owning stylesheet.

## HTML

- **Indent:** 2 spaces
- **Artifacts:** `index.html` remains the entry point, and mature apps should import `../../css/style.css` followed by `./css/app.css` while keeping app-local behavior in `js/app.js`
- **Accessibility:** semantic elements, ARIA attributes, keyboard navigation, focus management
- **External links:** always include `rel="noopener noreferrer"`

## Mature app contract

- Shared app tokens live in `css/src/01-tokens.css`
- Shared mature-app theme bootstrap lives in `js/app-theme.js`, and `js/modules/app-shell.js` owns the reusable shell markup plus shell behavior
- Mature apps should import the shared stylesheet first, then `./css/app.css`, and use `artifact-app` plus an `app-<slug>` body class
- Reusable colors, controls, surfaces, and callouts live in the relevant `css/src/` partial and are bundled into `css/style.css`. App-specific layout selectors live in `apps/<slug>/css/app.css` and retain their `body.app-<slug>` scope
- Mature app HTML should keep app-specific body content local, while shell placeholders (`data-app-shell`) let the shared module render the common header, runtime-error banner, and scroll-to-top control
- App headers should reuse the Artifacts logo, back button, theme toggle, and app-styled scroll-to-top pattern
- App content containers should stay near `1000px` wide unless a product requirement clearly needs more space

## YAML

- **Indent:** 2 spaces
- **Linter:** yamllint with repository overrides in `.yamllint.yml`
- **GitHub Actions:** pin third-party actions to full commit SHAs with a version comment (for example, `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`)

Run `make lint-yaml` for YAML structure/format checks and `make lint-workflows` for workflow-specific action linting.

## Makefile

- **Indent:** tabs (required by Make)
- **Variables:** uppercase with `?=` defaults. `PYTHON` auto-detects a supported interpreter and can be overridden when needed

## Markdown

- **Indent:** 2 spaces for nested lists
- **Tables:** `make align-tables-check` checks pipe alignment without edits. Run `make align-tables` only when table formatting is requested
- **Punctuation:**
  - Use standard dashes (`-`) for list items and horizontal rules
  - Do not use em dashes or en dashes in prose
  - Rephrase with periods, commas, colons, or parentheses. Do not replace a dash with a hyphen
- **Prose:** keep each paragraph on one line and let the editor soft-wrap it. Do not hard-wrap prose. Tables, code blocks, and list items retain their normal line structure
- **Code blocks:** use fenced blocks with language identifiers, such as `python`
- **Links:** prefer relative paths for in-repo references

## Documentation prose

Each document has one purpose: a tutorial teaches through visible results, a how-to gives steps to a goal, a reference describes facts, and an explanation gives reasons. Index pages link readers to those documents. Agent instructions preserve mandatory rules even when they include command reference material.

- Write instructions as commands. Put the condition before the action.
- Use present tense and name the actor. Prefer active voice unless the actor does not matter.
- Keep one thought per sentence. Split dense sentences without forcing every sentence to the same length.
- Use everyday words and the real path, symbol, flag, or command name.
- Keep terminology consistent. Replace vague metaphors with the mechanism they describe.
- Remove filler, promotional claims, unnecessary adverbs, and unsupported performance numbers.
- Keep `only` beside the word it modifies. Give pronouns one clear referent.
- Use sentence case for headings and one level-one heading per page. Do not skip heading levels.
- Use numbered lists for steps and bullets for parallel facts. Introduce each list with a complete sentence.
- Format code as code and UI labels in bold. Use descriptive link text and serial commas.
- Preserve generated README sections and the meaning of policies and historical decisions.

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
