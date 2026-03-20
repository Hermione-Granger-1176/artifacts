# Maintenance Notes

## What to keep stable

These are the main cross-cutting pieces that should stay consistent over time:

- `pyproject.toml` is the source of truth for Python dependencies, test policy, lint policy, and site metadata
- `Makefile` is the common interface for local work and CI
- `.github/actions/verified-commit/action.yml` and `.github/actions/verified-commit/verified-commit.mjs` centralize the verified commit and PR fallback logic used by CI
- `.github/workflows/update.yml` is the main build, validation, and deploy workflow
- `.github/workflows/refresh-action-shas.yml` keeps pinned GitHub Actions references current
- `.github/workflows/refresh-python-locks.yml` keeps Python freeze lock files aligned on same-repo Dependabot pip PRs through an untrusted compute step and a separate trusted commit step
- `.github/dependabot.yml` handles recurring dependency update checks
- `locks/requirements.lock`, `locks/requirements-dev.lock`, and `package-lock.json` keep local and CI installs reproducible
- `gh-pages` is a CI-managed deployment branch protected by a ruleset and should not be edited manually

## When changing CI

If you touch workflow files:

1. prefer extending the existing workflow over cloning logic into another workflow file
2. update the shared verified commit action when commit or PR fallback behavior changes
3. keep action references pinned to full commit SHAs
4. non-fork, non-Dependabot PRs use the app token for preview deploys, while fork and Dependabot PRs are excluded from preview deployment
5. keep local and CI commands aligned through `make`
6. preserve the separation between the source repo and the `_site/` deploy directory
7. keep the PR preview comment recreated on each push so the latest preview link stays easy to find
8. keep read-only verification separate from write-capable publish steps

## When changing URLs or repo metadata

Update `pyproject.toml` under `[tool.artifacts]`.

This is where the repo keeps:

- canonical site URL
- site path
- repository URL

Scripts and docs should read from that shared config instead of embedding one-off copies.

The deployed site path used by the 404 fallback is injected into the deploy output from this shared config.

## When changing generators

If you modify `scripts/generate_index.py`, `scripts/generate_thumbnails.py`, or `scripts/prepare_site.py`:

- update or add tests in `tests/`
- update Node tests in `tests/js/` when shared browser or workflow modules change
- keep `make check` green
- keep `make validate` aligned with the artifact directory contract when required files change
- preserve the 100% coverage gate unless there is an explicit decision to relax it
- regenerate derived files when needed with `make index` or `make generate`

## Thumbnail policy

- CI is allowed to generate thumbnails during pull requests and pushes
- checked-in thumbnails are not required for every local branch state
- if thumbnails are removed locally, the gallery data can temporarily contain `thumbnail: null`
- pushes to `main` will regenerate and persist fresh thumbnails through CI
- PR previews can render regenerated thumbnails without committing them back to the source branch

## Pages preview setup

The preview workflow assumes GitHub Pages serves the repository from the `gh-pages` branch root.

- main site deploys to the root of `gh-pages`
- PR previews deploy under `pr-preview/pr-<number>/`
- main deploys must preserve `pr-preview/`
- do not manually merge or edit `gh-pages`; CI owns it
- `gh-pages` ruleset bypass is intentionally limited to the deploy GitHub App and the single repo admin role for recovery

## Action SHA maintenance

The repo includes a scheduled workflow that refreshes pinned GitHub Action SHAs.

- file: `.github/workflows/refresh-action-shas.yml`
- purpose: keep workflows pinned and reproducible without manual SHA lookup
- expectation: when adding a new external action, pin it immediately and let the refresh workflow keep it current later

## Dependency lock maintenance

- Python declarations live in `pyproject.toml`, but installs should flow through `locks/requirements.lock` and `locks/requirements-dev.lock`
- Node declarations live in `package.json`, but installs should flow through `package-lock.json`
- same-repo Dependabot pip PRs refresh `locks/requirements.lock` and `locks/requirements-dev.lock` automatically through `.github/workflows/refresh-python-locks.yml`
- after Python dependency changes, run `make lock` and `make check`
- after Node dependency changes, refresh `package-lock.json` with npm tooling, then run `npm ci` and `make check`

## Good maintenance habits

- prefer central config over scattered constants
- prefer one well-structured workflow path over several partially duplicated ones
- keep README high level and keep deeper operational detail in `docs/`
- treat generated files as outputs, not primary editing targets
