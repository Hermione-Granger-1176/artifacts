# Contributing

Thanks for helping improve the Artifacts workspace.

## Development flow

1. Run `make setup-local` to create `.venv` and install pinned Python and Node dependencies, or `make setup` if you also need Chromium for browser smoke tests and thumbnail generation.
2. Make changes.
3. Run `make check-local` while you iterate, `make web` when browser behavior or thumbnails change, and `make check` before opening a pull request.
4. If you changed generated outputs or metadata, run `make generate` and `make site` as needed.

## Generated files

Do not hand-edit generated outputs unless you are intentionally changing the generator behavior.

- `js/data.js`
- `js/gallery-config.js`
- `apps/*/thumbnail.webp`
- `_site/`
- README auto-managed marker sections

## Code conventions

See [`docs/style.md`](../docs/style.md) for editor configuration, language conventions, and commit message style.

## Pull requests

- Keep changes scoped and describe the user-visible or maintenance impact.
- Trusted PRs publish a live preview; fork and Dependabot PRs skip preview deployment because the GitHub App token is unavailable.
- If CI updates generated files on `main`, the workflow writes a verified commit directly or opens a fallback PR when branch protection blocks the direct write.

## Dependency updates

- Python dependencies live in `pyproject.toml` and are frozen in `locks/requirements.lock` and `locks/requirements-dev.lock`.
- Node tooling lives in `package.json` and `package-lock.json`.
- Same-repo Dependabot pip PRs auto-refresh the Python lock files through `.github/workflows/refresh-python-locks.yml` and `.github/workflows/commit-python-locks.yml`, but local/manual dependency edits still need `make lock`.
- After changing Python dependency declarations, regenerate the Python lock files with `make lock`.
- After changing Node dependencies, refresh `package-lock.json` with npm before rerunning `npm ci`, `make check-local`, or `make check`.
- Workspace-only maintenance changes do not need a standalone changelog entry; app release notes stay app-specific.
