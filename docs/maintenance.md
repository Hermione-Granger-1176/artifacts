# Maintenance Notes

## What to keep stable

These are the main cross-cutting pieces that should stay consistent over time:

- `pyproject.toml` is the source of truth for Python dependencies, test policy, lint policy, and site metadata.
- `Makefile` is the common interface for local work and CI.
- `.github/actions/verified-commit/action.yml` and `.github/actions/verified-commit/verified-commit.mjs` centralize the verified commit and PR fallback logic used by CI.
- `.github/actions/deploy-site/action.yml` and `.github/actions/deploy-site/deploy-verified.mjs` handle verified deploys to `gh-pages` via the GraphQL API, preserving PR preview directories.
- `scripts/workflow_helpers.py` centralizes workflow trust, artifact-validation, thumbnail invalidation, and fallback PR detection helpers so the YAML stays policy-focused and the procedural logic stays testable.
- `.github/workflows/update.yml` is the main build, validation, and deploy workflow.
- `.github/workflows/refresh-action-shas.yml` keeps pinned GitHub Actions references current.
- `.github/workflows/refresh-python-locks.yml` computes Python lock refresh artifacts for same-repo Dependabot pip PRs.
- `.github/workflows/commit-python-locks.yml` validates and commits those refreshed Python lock artifacts in a separate trusted workflow.
- `.github/dependabot.yml` handles recurring dependency update checks.
- `locks/requirements.lock`, `locks/requirements-dev.lock`, and `package-lock.json` keep local and CI installs reproducible.
- `gh-pages` is a CI-managed deployment branch protected by a ruleset and should not be edited manually.

## When changing CI

If you touch workflow files:

1. Prefer extending the existing workflow over cloning logic into another workflow file.
2. Update the shared verified commit action when commit or PR fallback behavior changes.
3. Keep action references pinned to full commit SHAs.
4. Non-fork, non-Dependabot PRs use the escalation app token (Harry1176) for all deploys (main, preview, and cleanup), while fork and Dependabot PRs are excluded from deployment.
5. Keep local and CI commands aligned through `make`.
6. Preserve the separation between the source repo and the `_site/` deploy directory.
7. Keep the PR preview comment recreated on each push so the latest preview link stays easy to find.
8. Keep read-only verification separate from write-capable publish steps.
9. Pull repeated workflow constants into top-level or job-level `env` entries before copy-pasting them across steps.

## When changing URLs or repo metadata

Update `pyproject.toml` under `[tool.artifacts]`.

This is where the repo keeps:

- Canonical site URL.
- Site path.
- Repository URL.

Scripts and docs should read from that shared config instead of embedding one-off copies.

The deployed site path used by the 404 fallback is injected into the deploy output from this shared config.

## When changing generators

If you modify `scripts/generate_index.py`, `scripts/generate_thumbnails.py`, or `scripts/prepare_site.py`:

- Update or add tests in `tests/`.
- Update Node tests in `tests/js/` when shared browser or workflow modules change.
- Keep `make check-local` green while iterating, and keep `make check` green before shipping.
- Keep `make validate` aligned with the artifact directory contract when required files change.
- Preserve the 100% Python coverage gate and the current JavaScript coverage baseline unless there is an explicit decision to relax them.
- Regenerate derived files when needed with `make index` or `make generate`.

## Thumbnail policy

- CI is allowed to generate thumbnails during pull requests and pushes.
- Checked-in thumbnails are not required for every local branch state.
- If thumbnails are removed locally, the gallery data can temporarily contain `thumbnail: null`.
- Pushes to `main` will regenerate and persist fresh thumbnails through CI.
- PR previews can render regenerated thumbnails without committing them back to the source branch.

## Pages preview setup

The preview workflow assumes GitHub Pages serves the repository from the `gh-pages` branch root.

- Main site deploys to the root of `gh-pages`.
- PR previews deploy under `pr-preview/pr-<number>/`.
- Main deploys must preserve `pr-preview/`.
- Do not manually merge or edit `gh-pages`; CI owns it.
- `gh-pages` ruleset bypass is intentionally limited to the deploy GitHub App and the single repo admin role for recovery.

## Action SHA maintenance

The repo includes a scheduled workflow that refreshes pinned GitHub Action SHAs.

- File: `.github/workflows/refresh-action-shas.yml`.
- Purpose: keep workflows pinned and reproducible without manual SHA lookup.
- Expectation: when adding a new external action, pin it immediately and let the refresh workflow keep it current later.

## Dependency lock maintenance

- Python declarations live in `pyproject.toml`, but installs should flow through `locks/requirements.lock` and `locks/requirements-dev.lock`.
- Node declarations live in `package.json`, but installs should flow through `package-lock.json`.
- Same-repo Dependabot pip PRs refresh `locks/requirements.lock` and `locks/requirements-dev.lock` automatically through `.github/workflows/refresh-python-locks.yml`.
- After Python dependency changes, run `make lock`, `make check-local`, and `make check` when browser or deploy behavior is affected.
- After Node dependency changes, refresh `package-lock.json` with npm tooling, then run `npm ci`, `make check-local`, and `make check`.

## Good maintenance habits

- Prefer central config over scattered constants.
- Prefer one well-structured workflow path over several partially duplicated ones.
- Keep README high level and keep deeper operational detail in `docs/`.
- Treat generated files as outputs, not primary editing targets.
