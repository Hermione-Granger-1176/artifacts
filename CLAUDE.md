# CLAUDE.md

Collection of interactive HTML artifacts built with AI tools (Claude, ChatGPT, Gemini, etc.). Hosted via GitHub Pages. The canonical site URL is configured in `pyproject.toml` under `[tool.artifacts]`.

## Rules

1. **The Makefile is the only interface.** Never run `.venv/bin/*`, `pytest`, `ruff`, `npm run`, `npx`, `playwright`, or `gh` directly. Always use `make <target>`. If unsure what's available, run `make help` first. The list is auto-generated from the Makefile.
2. **Use the `make pr` / `make git` / `make help-ci` targets for GitHub work.** Prefer `make pr-review-comments`, `make pr-address`, `make pr-reply`, `make pr-resolve`, `make pr-summary`, `make pr-checks`, `make ci-failures`, and `make push` over raw `gh` or `git` commands. `make pr-review-comments` prints `thread=PRRT_...` ids; pass that id straight to `make pr-reply`, `make pr-resolve`, or `make pr-address`.
3. **If a target is missing, add it.** Put `## description` after the target name in the Makefile and it appears in `make help` automatically.
4. **Each tool has one config file.** To change what gets linted/tested/covered, edit the tool's config, nowhere else. See the tool configuration table below.
5. **Configs auto-discover from roots.** Point tools at directory roots, globs, or shared config files so new artifacts, scripts, and tests are covered automatically. Avoid per-file source lists unless the tool requires them.
6. **Read before acting.** Read the Makefile and existing code before proposing changes. Don't reinvent what already exists.
7. **Don't run auto-fix commands** (`make align-tables`, `make fmt`, `make format`, etc.) unless the user asks.
8. **Don't commit, push, or open/merge PRs unless asked.** Make and verify changes in the working tree and stop there until the user asks for GitHub actions.

## Structure

Each artifact lives in its own directory under `apps/` with an `index.html` entry point. The root `index.html` is a gallery page with searchable thumbnails, multi-select filters, theme persistence, and detail overlays.

- `apps/<slug>/`: artifacts, each with `index.html`, `name.txt`, `description.txt`, `tags.txt`, `tools.txt`
- `scripts/{build,ci,gh,lib,lint}/`: Python tooling organized by concern, 100% test coverage enforced
- `tests/{build,ci,gh,lib,lint}/`: mirrors scripts structure; `tests/browser/` for Playwright; `tests/js/{home,common,apps,workflows}/` for Node
- `js/`, `css/`: gallery + shared app modules and styles
- `docs/`: developer documentation
- `config/`: gallery metadata, artifact contract, and security audit policy

## Adding a new artifact

1. `make new name=my-artifact`: scaffolds the directory with placeholder files and the matching `tests/js/apps/<slug>/` folder
2. Place the HTML file as `index.html`, fill in `name.txt`, `description.txt`, `tags.txt`, `tools.txt`
3. `make validate`: fail fast on incomplete directories
4. Push to `main`: CI generates thumbnails, updates gallery data, builds, and deploys
5. PRs get live preview links posted as comments

When adding a user-provided artifact, prefer the minimal path: scaffold, copy HTML, fill metadata. Don't refactor, don't block on thumbnails (CI handles them). Verify artifact code/calculations at least once before committing.

## Local commands

**Run `make help` for command groups, then `make help-<group>` to expand one** (for example `make help-pr`, `make help-quality`, or `make help-build`). `make help-json` emits the same surface for tooling. Groups: setup, lint, format, deadcode, test, build, quality, util, git, pr, ci. Everything is auto-generated from `## comment` annotations and `# ─── Title @slug ───` section headers in the Makefile.

Key entry points:

- `make setup`: fast default (Python + Node deps, no Chromium)
- `make setup-all`: full setup including Chromium for browser tests and thumbnails. Use only when browser work is explicitly needed.
- `make ci`: full non-browser local CI gate
- `make ci-fast`: parallel non-browser local CI gate
- `make check-local`: alias for `make ci`
- `make check-fast`: alias for `make ci-fast`
- `make check-web`: browser tests + thumbnails, requires Chromium
- `make check`: full gate (check-local + browser tests + thumbnails + index + site build)
- `make fmt`: auto-fix lint issues across Python, JS, and CSS
- `make format-check`: check ruff and Prettier formatting without writing files
- `make dead-code`: run vulture and Knip dead-code checks
- `make pr`: show all PR commands (create, list, merge, comments, review, resolve, etc.)
- `make help-ci`: show CI/GitHub run commands (runs, watch, failed logs, repo audit)
- `make git`: show all git commands (branch, commit, push, log, diff)
- `make status`: quick workspace health check

Python dependencies and workspace metadata live in `pyproject.toml`, while frozen installs live in `locks/requirements*.lock` and `package-lock.json`.

## Common commands

High-frequency loops (full surface via `make help`). PR and CI triage targets wrap the tested `scripts/gh/` helper so agents do not need raw GitHub CLI flags.

| Need | Command |
| --- | --- |
| Review threads with resolution state | `make pr-review-comments [pr_num=N]` |
| Reply to a review thread | `make pr-reply thread=PRRT_... body_file=/tmp/reply.md` |
| Reply to and resolve a review thread | `make pr-address thread=PRRT_... body_file=/tmp/reply.md` |
| Resolve a review thread | `make pr-resolve thread=PRRT_...` |
| PR overview with checks and open threads | `make pr-summary [pr_num=N]` |
| List individual review comments | `make pr-comments-list [pr_num=N]` |
| Show PR comments and timeline | `make pr-comments` |
| Watch PR checks | `make pr-checks` |
| Show failed CI logs for this branch | `make ci-failures` |
| New branch off `main` | `make branch name=my-feature` |
| New stacked branch | `make branch name=my-feature base=current-branch` |
| Full local CI gate / parallel | `make ci` / `make ci-fast` |
| Formatting and dead code checks | `make format-check` / `make dead-code` |
| Commit staged work | `make commit message_file=/tmp/commit-message.txt` |
| Push the current branch | `make push` |
| Discover commands | `make help`, then `make help-<group>`, or `make help-json` |

## Tool configuration

Each tool has one config file that owns its scope. The Makefile just calls tools. No file lists repeated anywhere.

| Tool | Config (source of truth) | What it defines |
| --- | --- | --- |
| ruff | `pyproject.toml` | Python lint/format rules; built-in excludes skip `.venv/`, `node_modules/` |
| pytest | `pyproject.toml` | Test paths, coverage target (`scripts/`), 100% threshold |
| ESLint | `eslint.config.js` | JS file patterns, ignores, rules |
| stylelint | `stylelint.config.js` | CSS rules, ignoreFiles |
| yamllint | `.yamllint.yml` | YAML rules, ignore patterns |
| JS coverage | `package.json` | Exclude patterns (`node_modules/`, `tests/`) |
| Prettier | `config/prettierrc.json` | Docs, metadata, workflow, and tooling formatting |
| Knip | `config/knip.json` | JS dead-code, unused exports, and unused dependency detection |
| vulture | `pyproject.toml` | Python dead-code detection |
| editorconfig | `.editorconfig` | Formatting rules per file type |
| esbuild | `package.json` | CSS/JS minification during site assembly (`prepare_site.py`) |

To change what gets linted/tested/covered, edit the tool's config file, nowhere else.

## Auto-generated files

Do not manually edit these outputs unless updating generator logic:

- `js/data.js`, `js/gallery-config.js`: generated by `scripts/build/generate_index.py`
- `apps/*/thumbnail.webp`: generated by `scripts/build/generate_thumbnails.py`
- `_site/`: assembled by `scripts/build/prepare_site.py` for deployment and previews
- Auto-managed marker sections in `README.md`

## Deployment

- GitHub Pages is configured for GitHub Actions publishing
- The `gh-pages` branch remains the CI-managed deploy state for the live site root and PR preview subtrees
- Pushes to `main` update the site root in `gh-pages`, then publish the full branch tree with the official Pages Actions
- Main-site publishes also write a classic deployment record to the `github-pages` environment via the Deployments REST API (workflow `GITHUB_TOKEN`), so the Deployments page and environment badge stay current. PR previews and cleanup do not write these records.
- PRs update previews under `gh-pages/pr-preview/pr-<number>/`, then publish the full branch tree with the official Pages Actions
- All deploys (main, preview, and cleanup) use the escalation app token (Harry1176) and create verified commits via the GraphQL API
- The weekly repository-settings audit and its drift-issue lifecycle use a dedicated read-only app token (Percy1176); it has no deploy or write-to-code capability
- Preview comments are posted by the workflow token, appear as `github-actions[bot]`, and are recreated on each push so the newest preview stays visible
- Same-repo Dependabot pip PRs refresh Python lock files via CI workflows
- `gh-pages` is CI-managed and should not be edited manually

## Docs

Workspace documentation lives in `docs/`:

- [`workspace.md`](docs/workspace.md): repository layout and generated files
- [`architecture.md`](docs/architecture.md): runtime, build, and deploy flow
- [`frontend.md`](docs/frontend.md): root gallery modules, bootstrap flow, and frontend tests
- [`operations.md`](docs/operations.md): local commands, CI behavior, and troubleshooting
- [`maintenance.md`](docs/maintenance.md): long-term upkeep and workflow hygiene
- [`style.md`](docs/style.md): editor configuration and language conventions

## Conventions

- Artifact directories use kebab-case names
- Each artifact keeps `index.html` as the entry point
- All pages should import the single shared stylesheet from `css/style.css`
- Mature apps should reuse `js/app-theme.js` and `js/modules/app-shell.js`
- App-local behavior should live in `apps/<slug>/js/app.js` plus app-local modules/docs
- The bookmark-note palette is the shared color system, and authored app colors should use `rgb()` / `rgba()` values
- Before adding or modifying an artifact, always verify the artifact code or calculations at least once
