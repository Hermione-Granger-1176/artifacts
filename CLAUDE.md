# CLAUDE.md

This repository contains interactive HTML artifacts built with AI tools and hosted on GitHub Pages. `pyproject.toml` defines the canonical site URL under `[tool.artifacts]`. `AGENTS.md` is a symlink to this file, so agents share one set of repository instructions.

## Required workflow

1. Use `make <target>` for workspace tools and GitHub actions. Do not run `.venv/bin/*`, `pytest`, `ruff`, `mypy`, `npm run`, `npx`, `tsc`, `playwright`, `gh`, or `git` directly. `make git` lists Git targets. Run `make help` to find command groups, then `make help-<group>` to list a group's targets.
2. If a target is missing, add it before using the tool. Add `## description` after the target name so generated help includes it.
3. Read the Makefile and existing code before proposing changes. Reuse existing behavior and helpers.
4. Keep each tool's scope in its owning configuration file. Use roots, globs, and exclusions so new files are discovered automatically. Do not duplicate source-file lists in targets, workflows, and configuration files. Configuration-file path references are allowed.
5. Run auto-fix commands only when the user asks. These include `make align-tables`, `make fmt`, and `make format`.
6. Commit, push, open PRs, or merge PRs only when the user asks. Otherwise, make and verify changes in the working tree. Keep small tooling and documentation changes on the current branch unless the user requests a separate branch or worktree.
7. Before adding or modifying an artifact, verify its behavior or calculations at least once.

## Repository structure

Each artifact has an `apps/<slug>/index.html` entry point. Metadata lives beside it in `name.txt`, `description.txt`, `tags.txt`, and `tools.txt`. The root `index.html` is the gallery, with searchable thumbnails, filters, theme persistence, and detail overlays.

The main directories are:

- `apps/`: artifact implementations, metadata, and app documentation.
- `scripts/`: Python tooling grouped under `build`, `ci`, `gh`, `lib`, `lint`, and `setup`. Tests enforce 100% line and branch coverage.
- `tests/`: matching Python groups, Playwright suites under `browser`, and Node suites under `js`.
- `js/` and `css/`: gallery code, shared app modules, and styles.
- `config/`: tool configuration, gallery metadata, the artifact contract, and audit policy.
- `docs/`: workspace documentation and architecture decision records.

[Workspace structure](docs/workspace.md) owns the full layout and file-ownership reference.

## Add an artifact

Use one of the two scaffold inputs:

1. For a new placeholder, run `make new name=my-artifact`.
2. For an existing HTML file, run `make new name=my-artifact src=path/to/file.html` instead.

Both inputs create metadata files, `css/app.css`, `js/app.js`, a README, architecture and verification docs, decision notes, and `tests/js/apps/<slug>/app.test.js`.

The placeholder includes the shared stylesheets, app shell, and self-only CSP. It passes validation, lint, dead-code, type, and JS test-import checks without manual edits.

The import preserves supplied HTML. It adds the CSP and shared stylesheet links when absent and reports off-origin script or style references. Vendor or remove those references before the CSP check. Shared app-shell wiring is optional for a self-contained import. Keep the generated `js/app.js` and its test, or replace them with your own module and test.

After the scaffold, complete these steps:

1. Build the artifact and fill in its metadata.
2. Verify its behavior or calculations.
3. Run `make validate` and the relevant checks in [Operations](docs/operations.md).

For user-provided artifacts, prefer the `src=` import and metadata edits. Avoid unrelated refactors. CI generates thumbnails, so missing local thumbnails do not block the contribution. Push only when authorized.

## Local commands

The Makefile generates help from target descriptions and section headers. `make help-json` exposes the same groups and commands as JSON.

The main entry points are:

- `make setup`: install Python and Node dependencies without Chromium. Setup requires `uv` on PATH.
- `make setup-all`: also install Chromium. Use it when browser work is required.
- `make setup-playwright-local`: prepare Chromium and local libraries on Debian or Ubuntu without sudo. `make setup-playwright-webkit-local` adds WebKit. Browser targets use the prepared libraries with `local_libs=1`.
- `make ci`: run the complete non-browser local gate.
- `make ci-fast`: run parallel non-browser checks, followed by generated-file checks. This target omits per-file JS coverage floors. Run `make coverage-js-floors` afterward to check those floors.
- `make check`: run the full local gate, including browsers, thumbnails, index generation, and site assembly. `make check-web` runs the browser and thumbnail checks.
- `make status`: inspect Git state, dependencies, lockfiles, generated files, and the PR summary.

[Operations](docs/operations.md) describes command selection, CI behavior, browser setup, and recovery.

## GitHub commands

Use the `make pr-*`, `make issue-*`, and Git targets. The PR number defaults to the current branch's PR. Override it with `pr_num=N`. Do not pass raw CLI flags such as `--jq` to Make targets.

`make pr-review-comments` prints `thread=PRRT_...` identifiers. Pass the identifier to the reply or resolution target.

The commands with less obvious argument patterns are:

| Task                    | Command                                           |
| ----------------------- | ------------------------------------------------- |
| List review threads     | `make pr-review-comments [pr_num=N]`              |
| Reply to a thread       | `make pr-reply thread=PRRT_... < reply.md`        |
| Reply and resolve       | `make pr-address thread=PRRT_... < reply.md`      |
| Resolve a thread        | `make pr-resolve thread=PRRT_...`                 |
| Comment on a PR         | `make pr-comment [pr_num=N] < comment.md`         |
| Comment on an issue     | `make issue-comment issue=N < comment.md`         |
| Create an issue branch  | `make issue-develop issue=N`                      |
| Create a stacked branch | `make branch name=my-feature base=current-branch` |
| Commit staged work      | `make commit < message.txt`                       |

Supply multiline messages on stdin through a heredoc or file redirect. Do not pass prose as Make arguments. For short fields, use environment variables such as `TITLE='...'`, `SEARCH='...'`, or `COMMENT='...'` with the relevant target.

## Tool configuration

Each tool has one configuration file that owns its scope. The Makefile calls the tools.

| Tool         | Configuration                | Scope                                        |
| ------------ | ---------------------------- | -------------------------------------------- |
| ruff         | `pyproject.toml`             | Python lint and format rules                 |
| pytest       | `pyproject.toml`             | Test paths and 100% coverage for `scripts/`  |
| ESLint       | `config/eslint.config.js`    | JS patterns, ignores, and rules              |
| stylelint    | `config/stylelint.config.js` | CSS rules and ignores                        |
| yamllint     | `.yamllint.yml`              | YAML rules and ignores                       |
| JS coverage  | `package.json`               | Thresholds and exclusions                    |
| TypeScript   | `config/jsconfig.json`       | Strict checks for authored JS                |
| mypy         | `pyproject.toml`             | Strict checks for `scripts/`                 |
| Prettier     | `config/prettierrc.json`     | Metadata, workflows, and tooling format      |
| Knip         | `config/knip.json`           | Unused JS files, exports, and dependencies   |
| vulture      | `pyproject.toml`             | Unused Python code                           |
| EditorConfig | `.editorconfig`              | Settings by file type                        |
| pre-commit   | `.pre-commit-config.yaml`    | Hook checks                                  |
| esbuild      | `package.json`               | CSS and JS minification during site assembly |

Python declarations and workspace metadata live in `pyproject.toml`. `uv.lock` and `package-lock.json` record the frozen dependency graphs. Change lint, test, and type scope in the owning tool configuration.

## Generated files

Change the inputs or generator for these outputs. Do not edit the outputs by hand:

- `js/data.js` and `js/gallery-config.js`, generated by `scripts/build/generate_index.py`.
- `css/style.css`, generated from `css/src/` by `scripts/build/generate_styles.py`.
- `apps/*/thumbnail.webp`, generated by `scripts/build/generate_thumbnails.py`.
- `_site/`, assembled by `scripts/build/prepare_site.py`.
- Auto-managed marker sections in `README.md`.

## Deployment

Pushes to `main` trigger the GitHub Actions deployment to GitHub Pages. Trusted PRs (same repository, excluding Dependabot) receive previews under `gh-pages/pr-preview/pr-<number>/` and a preview-link comment on each push.

CI manages `gh-pages`. Do not edit it manually. Deployments use GitHub App tokens and verified GraphQL commits. [Architecture](docs/architecture.md) describes the pipeline, token roles, and deployment records.

## App conventions

- Use kebab-case artifact directory names and `index.html` entry points.
- Load `css/style.css` in the gallery. In mature apps, load `../../css/style.css` before `./css/app.css`.
- Reuse `js/app-theme.js`, `js/modules/app-shell.js`, and the shared `formatting.js`, `segmented.js`, `section-nav.js`, and `chart-theme.js` modules.
- Use the tokens in `css/src/01-tokens.css` and the themed colors in `css/src/01-theme-light.css` and `css/src/01-theme-dark.css`, plus the components in `css/src/04-artifact-components.css` before adding app-local CSS. Shared families include `.control-field`, `.stat`, `.chip`, `.segmented`, `.meter`, `.app-callout`, `.section-kicker`, and `.section-nav`.
- Keep app behavior in `apps/<slug>/js/app.js` and app-local modules. Keep app-specific layout in `apps/<slug>/css/app.css`.
- Use the shared bookmark-note palette. Derive app CSS colors from tokens through `var()` or `color-mix()`. Raw color values belong in the shared token definitions. `make lint-app-css-tokens` also checks radius, font-size, and letter-spacing values. [Style guide](docs/style.md) documents allowed values and exceptions.
- Keep Markdown paragraphs on one line. Use sentence case headings and direct instructions. Do not use em dashes or en dashes.

## Documentation ownership

[Workspace documentation](docs/README.md) links to the owning document for each concern: structure, architecture, frontend behavior, operations, maintenance, style, and architecture decisions. Link to those sources instead of repeating their policies.
