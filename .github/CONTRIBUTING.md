# Contributing

Thanks for helping improve the Artifacts workspace.

## Start here

- Run `make help` to see the available workspace targets.
- Follow [`docs/operations.md`](../docs/operations.md) for the canonical local workflow, CI mapping, and troubleshooting.
- Use [`docs/workspace.md`](../docs/workspace.md) for repository layout, generated outputs, and source-of-truth ownership.
- Use [`docs/style.md`](../docs/style.md) for editor settings, language conventions, and commit message style.

## Generated files

Do not hand-edit generated outputs unless you are intentionally changing the generator behavior. See [`docs/workspace.md`](../docs/workspace.md#generated-and-derived-files) for the canonical list.

## Pull requests

- Keep changes scoped and describe the user-visible or maintenance impact.
- Trusted PRs publish a live preview; fork and Dependabot PRs skip preview deployment because the GitHub App token is unavailable.
- Trusted preview and production deploys also run `make test-browser-live` against the published URL, so browser-only regressions can still fail the release after deploy verification.
- If CI regenerates thumbnails during trusted same-repo PR or `main` runs, it can persist `apps/*/thumbnail.webp` back to the same PR branch or open a follow-up thumbnail PR from `main`. Other generated files are still summarized rather than auto-committed.

## Dependency updates

- Python dependencies live in `pyproject.toml` and are frozen in `locks/requirements.lock` and `locks/requirements-dev.lock`.
- Node tooling lives in `package.json` and `package-lock.json`.
- Same-repo Dependabot pip PRs auto-refresh the Python lock files through `.github/workflows/refresh-python-locks.yml` and `.github/workflows/commit-python-locks.yml`, but local/manual dependency edits still need `make lock`.
- After changing Python dependency declarations, regenerate the Python lock files with `make lock`.
- After changing Node dependencies, refresh `package-lock.json` before rerunning the relevant `make` setup or check targets.
- `axe-core` is pinned in `package-lock.json` because the Playwright accessibility suite injects it into real browser sessions.
- Workspace-only maintenance changes do not need a standalone changelog entry; app release notes stay app-specific.
