# CLAUDE.md

Collection of interactive HTML artifacts built with AI tools (Claude, ChatGPT, Gemini, etc.). Hosted via GitHub Pages. The canonical site URL is configured in `pyproject.toml` under `[tool.artifacts]`.

## Rules

1. **The Makefile is the only interface.** Never run `.venv/bin/*`, `pytest`, `ruff`, `mypy`, `npm run`, `npx`, `tsc`, `playwright`, or `gh` directly. Always use `make <target>`. If unsure what's available, run `make help` first. The list is auto-generated from the Makefile.
2. **Use the `make pr-*` / `make git` targets for GitHub work** instead of raw `gh` or `git` (see the Common commands table). `make pr-review-comments` prints `thread=PRRT_...` ids; pass that id straight to `make pr-reply`, `make pr-resolve`, or `make pr-address`. The PR number is auto-detected from the current branch (override with `pr_num=N`). Never pass extra flags like `--jq` to a make target, since make parses them itself and errors.
3. **If a target is missing, add it.** Put `## description` after the target name in the Makefile and it appears in `make help` automatically.
4. **Each tool has one config file.** To change what gets linted/tested/typed, edit the tool's config, nowhere else. See the tool configuration table below.
5. **Configs auto-discover from roots; never enumerate files in multiple places.** Point tools at directory roots, globs, or shared config files so new artifacts, scripts, and tests are covered automatically. Don't repeat per-file source lists; that rots the day someone adds a file and forgets. Tool config-file location pointers are fine; per-file source lists are not.
6. **Read before acting.** Read the Makefile and existing code before proposing changes. Don't reinvent what already exists.
7. **Don't run auto-fix commands** (`make align-tables`, `make fmt`, `make format`, etc.) unless the user asks.
8. **Don't commit, push, or open/merge PRs unless asked.** Make and verify changes in the working tree and stop there until the user asks for GitHub actions. For small tooling/doc tweaks, fold them into the current in-progress branch instead of opening a separate PR.

## Structure

Each artifact lives in its own directory under `apps/` with an `index.html` entry point. The root `index.html` is a gallery page with searchable thumbnails, multi-select filters, theme persistence, and detail overlays.

- `apps/<slug>/`: artifacts, each with `index.html`, `name.txt`, `description.txt`, `tags.txt`, `tools.txt`
- `scripts/{build,ci,gh,lib,lint}/`: Python tooling organized by concern, 100% test coverage enforced
- `tests/{build,ci,gh,lib,lint}/`: mirrors scripts structure; `tests/browser/` for Playwright; `tests/js/{home,common,apps,tooling,workflows}/` for Node
- `js/`, `css/`: gallery + shared app modules and styles
- `docs/`: developer documentation
- `config/`: gallery metadata, artifact contract, and security audit policy

## Adding a new artifact

Two one-command flows. Both emit a complete artifact structure. The fresh-placeholder flow passes every gate (`make validate`, ESLint, stylelint, Knip, tsc, and the JS test-coverage check) with zero hand edits. A `src=` import preserves supplied off-origin references, so its CSP gate passes only after any reported references are vendored or removed.

**Fresh placeholder:**

1. `make new name=my-artifact`: emits the full artifact. `index.html` is wired to `../../css/style.css`, `./css/app.css`, and the shared app shell with the self-only CSP meta; `css/app.css` and `js/app.js` are stubbed; `README.md` plus `docs/architecture.md`, `docs/verification.md`, and `docs/decisions.md` are stubbed; metadata files are created; and a passing `tests/js/apps/<slug>/app.test.js` is emitted.
2. Build your artifact in `index.html`, then fill in `name.txt`, `description.txt`, `tags.txt`, `tools.txt`
3. `make validate`: fail fast on incomplete directories
4. Push to `main`: CI generates thumbnails, updates gallery data, builds, and deploys
5. Trusted PRs (same-repo, non-Dependabot) get live preview links posted as comments

**Drop-in of an existing AI-generated HTML file:**

1. `make new name=my-artifact src=path/to/file.html`: installs the file as `index.html` and scaffolds the same metadata, `css/app.css`, `js/app.js`, docs, and test stub. It injects the CSP meta and the shared stylesheet links only when they are absent, and it reports (does not rewrite) any off-origin script or style references so you can vendor or remove them before the security lint runs.
2. Fill in the metadata files, then `make validate`
3. Push to `main` (steps 4-5 above)

The app-shell wiring is optional for a self-contained drop-in; keep the emitted `js/app.js` and its test, or replace them with your own module of the same name.

When adding a user-provided artifact, prefer the minimal path: scaffold with `src=`, fill metadata. Don't refactor, don't block on thumbnails (CI handles them). Verify artifact code/calculations at least once before committing.

## Local commands

**Run `make help` for command groups, then `make help-<group>` to expand one** (for example `make help-pr`). `make help-json` emits the same surface for tooling. Everything is auto-generated from `## comment` annotations and `# ─── Title @slug ───` section headers in the Makefile.

Key entry points:

- `make setup`: fast default (Python + Node deps, no Chromium). `make setup-all` adds Chromium for browser tests and thumbnails; use only when browser work is explicitly needed. Requires `uv` on PATH.
- `make ci` / `make ci-fast`: full / parallel non-browser local CI gate
- `make check`: full gate (non-browser CI + browser tests + thumbnails + index + site build); `make check-web` for just the browser half
- `make status`: workspace health check (git, deps, lock currency, generated files, PR summary)

Python dependencies and workspace metadata live in `pyproject.toml`, while frozen installs live in `uv.lock` and `package-lock.json`.

## Common commands

High-frequency loops (full surface via `make help`). PR and CI triage targets wrap the tested `scripts/gh/` helper so agents do not need raw GitHub CLI flags.

| Need | Command |
| --- | --- |
| Review threads with resolution state | `make pr-review-comments [pr_num=N]` |
| Reply to a review thread | `make pr-reply thread=PRRT_... body_file=- <<'EOF' ... EOF` |
| Reply to and resolve a review thread | `make pr-address thread=PRRT_... body_file=- <<'EOF' ... EOF` |
| Resolve a review thread | `make pr-resolve thread=PRRT_...` |
| PR overview with checks and open threads | `make pr-summary [pr_num=N]` |
| Wait for checks and a fresh Copilot review | `make pr-watch [pr_num=N]` |
| List individual review comments | `make pr-comments-list [pr_num=N]` |
| Show PR comments and timeline | `make pr-comments` |
| Watch PR checks | `make pr-checks` |
| Show failed CI logs for this branch | `make ci-failures` |
| New branch off `main` | `make branch name=my-feature` |
| New stacked branch | `make branch name=my-feature base=current-branch` |
| Full local CI gate / parallel | `make ci` / `make ci-fast` |
| Formatting and dead code checks | `make format-check` / `make dead-code` |
| Commit staged work | `make commit message_file=- <<'EOF' ... EOF` |
| Push the current branch | `make push` |
| Discover commands | `make help`, then `make help-<group>`, or `make help-json` |

For multi-line text (commit messages, PR replies, comments), pass `message_file=-` / `body_file=-` and pipe the content on stdin with a heredoc. Do not write temp message files; reserve `message_file=path` / `body_file=path` for content that already exists on disk. Short one-liners can use the inline `message="..."` / `body="..."` forms.

## Tool configuration

Each tool has one config file that owns its scope. The Makefile just calls tools. No file lists repeated anywhere.

| Tool | Config (source of truth) | What it defines |
| --- | --- | --- |
| ruff | `pyproject.toml` | Python lint/format rules; built-in excludes skip `.venv/`, `node_modules/` |
| pytest | `pyproject.toml` | Test paths, coverage target (`scripts/`), 100% threshold |
| ESLint | `config/eslint.config.js` | JS file patterns, ignores, rules |
| stylelint | `config/stylelint.config.js` | CSS rules, ignoreFiles |
| yamllint | `.yamllint.yml` | YAML rules, ignore patterns |
| JS coverage | `package.json` | Exclude patterns (`node_modules/`, `tests/`) |
| tsc (checkJs) | `config/jsconfig.json` | TypeScript checkJs gate for hand-written js/ modules |
| mypy | `pyproject.toml` | Strict Python type checking over `scripts/` |
| Prettier | `config/prettierrc.json` | Docs, metadata, workflow, and tooling formatting |
| Knip | `config/knip.json` | JS dead-code, unused exports, and unused dependency detection |
| vulture | `pyproject.toml` | Python dead-code detection |
| editorconfig | `.editorconfig` | Formatting rules per file type |
| pre-commit | `.pre-commit-config.yaml` | Local Git hook stages (whitespace, lint, format, typecheck, and test gates) |
| esbuild | `package.json` | CSS/JS minification during site assembly (`prepare_site.py`) |

To change what gets linted/tested/typed, edit the tool's config file, nowhere else.

## Auto-generated files

Do not manually edit these outputs unless updating generator logic:

- `js/data.js`, `js/gallery-config.js`: generated by `scripts/build/generate_index.py`
- `css/style.css`: generated by `scripts/build/generate_styles.py` from `css/src/`
- `apps/*/thumbnail.webp`: generated by `scripts/build/generate_thumbnails.py`
- `_site/`: assembled by `scripts/build/prepare_site.py` for deployment and previews
- Auto-managed marker sections in `README.md`

## Deployment

- GitHub Pages publishes via GitHub Actions: pushes to `main` update the live site root, and trusted PRs (same-repo, non-Dependabot) get previews under `gh-pages/pr-preview/pr-<number>/` with the link posted as a PR comment on each push
- `gh-pages` is CI-managed and should not be edited manually
- Deploys use GitHub App tokens and verified GraphQL commits; see [`docs/architecture.md`](docs/architecture.md) for the full pipeline, token model, and deployment records

## Docs

Workspace documentation lives in `docs/`:

- [`workspace.md`](docs/workspace.md): repository layout and generated files
- [`architecture.md`](docs/architecture.md): runtime, build, and deploy flow
- [`frontend.md`](docs/frontend.md): root gallery modules, bootstrap flow, and frontend tests
- [`operations.md`](docs/operations.md): local commands, CI behavior, and troubleshooting
- [`maintenance.md`](docs/maintenance.md): long-term upkeep and workflow hygiene
- [`style.md`](docs/style.md): editor configuration and language conventions
- [`adr/`](docs/adr): architecture decision records

## Conventions

- Artifact directories use kebab-case names
- Each artifact keeps `index.html` as the entry point
- The root gallery should import `css/style.css`; mature apps should import `../../css/style.css` first, then their app-local `./css/app.css`
- Mature apps should reuse `js/app-theme.js`, `js/modules/app-shell.js`, and the shared helper modules `js/modules/{formatting,segmented,section-nav,chart-theme}.js` instead of re-implementing them
- Mature apps should reach for the shared design tokens (`css/src/01-tokens.css`) and component families (`css/src/04-artifact-components.css`: `.control-field`, `.stat`, `.chip`, `.segmented`, `.meter`, `.app-callout`, `.section-kicker`, plus shared buttons, inputs, tables, and `.section-nav`) before writing app-local CSS
- App-local behavior should live in `apps/<slug>/js/app.js` plus app-local modules/docs, and `apps/<slug>/css/app.css` should hold only app-specific layout built on the shared tokens
- The bookmark-note palette is the shared color system. App CSS colors must be token-derived (`var()` or a `color-mix()` over tokens), never hex, color-function, or named-color literals; raw color values belong in the `css/src/` token definitions. `make lint-app-css-tokens` enforces this plus token usage for radius, font-size, and letter-spacing
- Before adding or modifying an artifact, always verify the artifact code or calculations at least once
