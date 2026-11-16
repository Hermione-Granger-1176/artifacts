# Workspace structure

This reference covers the repository layout, the generated files and their inputs, and the source of truth for each area. [Architecture](architecture.md) explains the runtime, build, and deploy design, and [Operations](operations.md) lists the commands. The [documentation index](README.md) names the owner of every other concern.

## What this repo is

- The root site is the gallery.
- Each artifact lives in its own folder under `apps/`.
- Python build tooling generates the shared stylesheet, gallery data, thumbnails, and the deployable site payload.
- GitHub Actions deploys the verified `_site/` artifact and publishes PR previews. The main publish flow never writes to contributor branches.

## Top-level layout

```text
.
|- .github/
|  |- actions/              Shared composite actions for CI and deploys
|  |- codeql/               CodeQL scan scope
|  |- workflows/            GitHub Actions workflows
|- .agents/                 Agent skill definitions
|- .claude/                 Claude Code skill definitions
|- apps/                    One folder per artifact
|- assets/                  Fonts, icons, scrapbook SVGs, and the social preview image
|- config/                  Gallery metadata, artifact contract, tool configuration, type declarations, and audit policy
|- css/
|  |- src/                  Shared stylesheet partials, in filename order
|  |- style.css             Generated bundle of css/src/
|- docs/                    Workspace documentation and ADRs
|- js/                      Gallery entry points, shared modules in modules/ (gallery modules in modules/gallery/), and generated data files
|- mk/                      Make targets, one NN-group.mk file per make help group
|- scripts/
|  |- build/                Index and stylesheet generation, thumbnails, and site assembly
|  |- ci/                   Workflow helpers, deploy verification, security audits, and alerts
|  |- gh/                   PR, issue, and CI helpers behind the make pr-*, issue-*, and ci-* targets
|  |- lib/                  Shared libraries for artifact discovery, the artifact contract, and the GitHub API
|  |- lint/                 Repository lint and consistency checks
|  |- setup/                Local Playwright runtime provisioning
|- tests/
|  |- build/, ci/, gh/, lib/, lint/, setup/   Tests for the matching scripts/ directory
|  |- browser/              Playwright tests
|  |- js/                   Node tests for the gallery, apps, tooling, and workflow actions
|- 404.html, index.html     Error page and root gallery entry point
|- Makefile                 Primary interface for workspace commands
|- pyproject.toml, uv.lock  Python dependencies and the frozen graph
|- package.json, package-lock.json   Node dependencies and the frozen graph
```

Dotfiles at the root hold editor, lint, and secret-scan settings.

## Source of truth by area

- Artifact code: `apps/<slug>/index.html` is the entry point. `apps/<slug>/css/app.css` holds layout for mature apps. Reusable components belong in `css/src/`.
- Artifact metadata: `apps/<slug>/name.txt`, `description.txt`, `tags.txt`, and `tools.txt`.
- Gallery UI: `index.html`, `js/app.js`, `js/boot-guard.js`, and `js/modules/gallery/`. [Frontend](frontend.md) describes each module.
- Shared JavaScript: `js/modules/`, which the gallery and the apps import.
- Themed colors: `css/src/01-theme-light.css` and `css/src/01-theme-dark.css`. Both files declare the same tokens on the same lines ([ADR 0007](adr/0007-line-matched-theme-files.md)).
- Tokens and fonts: `css/src/01-tokens.css` holds the `@font-face` declarations for the self-hosted fonts in `assets/fonts/`, plus the tokens that both themes share.
- Icons and social image: `assets/icons/` and `assets/social/share-preview.png`. Deploy-time metadata references the share image.
- Gallery metadata: `config/gallery_metadata.json` holds tag and tool display metadata. `config/artifact_contract.json` holds the artifact id, URL, and thumbnail path contract.
- Type declarations: `config/types/*.d.ts` declare the vendored libraries and app globals. `make typecheck-web` reads them.
- Vendored libraries: `config/vendored_assets.json` pins each library's version, upstream URL, and SHA-256. `make lint-vendored-assets` checks it, and `make audit-vendored` audits it against OSV.
- Audit policy: `config/security_audit.json` holds the reviewed Python, npm, and vendored exceptions.
- Dependencies: `pyproject.toml` and `package.json` declare dependencies. `uv.lock` and `package-lock.json` freeze the graphs.
- CI and deploy: `.github/workflows/` and `.github/actions/`, owned by [CI and deployment](ci.md).
- Decisions: `docs/adr/*` holds the accepted architecture decision records.

## Tool configuration

Each tool reads one configuration file, and the Makefile calls the tool. Change a tool's scope in its file, not in a target or workflow.

| Config file                     | Owns                                                                                   |
| ------------------------------- | -------------------------------------------------------------------------------------- |
| `pyproject.toml`                | Python deps, ruff, mypy, pytest, coverage, and vulture settings, site URL and metadata |
| `package.json`                  | Node deps, JS test/coverage config, npm script commands                                |
| `config/artifact_contract.json` | Shared artifact id, URL, and thumbnail path validation contract                        |
| `config/eslint.config.js`       | ESLint file patterns, ignores, rules                                                   |
| `config/stylelint.config.js`    | Stylelint rules, ignoreFiles                                                           |
| `config/jsconfig.json`          | TypeScript `checkJs` scope and strictness for authored JS                              |
| `config/knip.json`              | Knip entry points and ignores for unused-code checks                                   |
| `config/prettierrc.json`        | Prettier rules for metadata, config, workflows, and tooling                            |
| `config/prettierignore`         | Paths that Prettier skips                                                              |
| `.yamllint.yml`                 | Yamllint rules, ignore patterns                                                        |
| `.editorconfig`                 | Editor formatting rules per file type                                                  |
| `config/gallery_metadata.json`  | Tag/tool display metadata for gallery config and README badges                         |
| `config/security_audit.json`    | Python, npm, and vendored audit policy, with reviewed exceptions                       |
| `config/vendored_assets.json`   | Pinned version, upstream URL, and SHA-256; input to the OSV audit                      |

## Generated and derived files

Do not edit these outputs by hand. Change the inputs or the generator, then regenerate.

| Output                    | Generator                              | Inputs                                                            | Regenerate with   |
| ------------------------- | -------------------------------------- | ----------------------------------------------------------------- | ----------------- |
| `css/style.css`           | `scripts/build/generate_styles.py`     | `css/src/` partials                                               | `make styles`     |
| `js/data.js`              | `scripts/build/generate_index.py`      | `apps/*/{name,description,tags,tools}.txt` and artifact discovery | `make index`      |
| `js/gallery-config.js`    | `scripts/build/generate_index.py`      | `config/gallery_metadata.json`, `config/artifact_contract.json`   | `make index`      |
| README auto-marked values | `scripts/build/generate_index.py`      | `pyproject.toml`, `config/gallery_metadata.json`, app metadata    | `make index`      |
| `apps/*/thumbnail.webp`   | `scripts/build/generate_thumbnails.py` | Rendered artifact pages                                           | `make thumbnails` |
| `_site/`                  | `scripts/build/prepare_site.py`        | Tracked source files and generated assets                         | `make site`       |

The website is the canonical artifact catalog. `README.md` keeps only a high-level snapshot instead of listing every artifact.

## Artifact folder contract

The artifact contract lists these files. Paths are relative to the artifact directory unless they start with `tests/`. `config/artifact_contract.json` and `make validate` enforce it.

- `index.html`: required entry point.
- `name.txt`: required display name.
- `description.txt`, `tags.txt`, `tools.txt`: optional metadata. `tags.txt` and `tools.txt` hold one value per line.
- `js/app.js`: recommended app-local runtime entry for mature apps.
- `css/app.css`: recommended app-local stylesheet, loaded after the shared `css/style.css`.
- `docs/architecture.md`, `docs/verification.md`, `docs/decisions.md`: recommended internal docs for mature apps.
- `README.md`: recommended app overview and folder map.
- `assets/`, `js/vendor/`: optional app-local runtime assets and vendored libraries. See [Vendored runtime dependencies](operations.md#vendored-runtime-dependencies).
- `tests/js/apps/<slug>/app.test.js`: app-specific Node test. `make new` creates it.
- `thumbnail.webp`: generated thumbnail, used when present.

`make site` deploys only `index.html`, `css/`, `js/`, `assets/`, and `thumbnail.webp` from each artifact folder. Metadata, `README.md`, and `docs/` stay in the repository.

## Editing workflow

[Contributing](../.github/CONTRIBUTING.md) lists the steps to add an artifact. [Operations](operations.md) lists the local checks and generation commands. Follow these ownership rules:

- Change artifacts in `apps/`. Run `make new name=my-artifact` for a starting structure that passes the gates. To import an existing HTML file, run `make new name=my-artifact <<< path/to/file.html`.
- Change the generator in `scripts/` when generated output should change.
- Keep tool scope in its configuration file. See [Tool configuration](#tool-configuration).
- Run `make validate` after you change top-level artifact directories or the artifact folder contract.
- Keep site configuration, dependency declarations, and lockfiles in their owning files.
- When an ownership boundary changes, update this page and link to the owner in other pages instead of copying the rule.
