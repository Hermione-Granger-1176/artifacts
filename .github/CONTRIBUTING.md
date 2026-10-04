# Contributing

Use this guide to prepare a contribution to the Artifacts workspace.

## Start here

- Run `make help` to see the available workspace targets.
- Follow [`docs/operations.md`](../docs/operations.md) for the canonical local workflow, CI mapping, and troubleshooting.
- Use [`docs/workspace.md`](../docs/workspace.md) for repository layout, generated outputs, and source-of-truth ownership.
- Use [`docs/style.md`](../docs/style.md) for editor settings, language conventions, and commit message style.

## Add an artifact

1. To create a new app, run `make new name=my-artifact`. To import an HTML file, run `make new name=my-artifact src=path/to/file.html` instead.
2. Build the app and fill in `name.txt`, `description.txt`, `tags.txt`, and `tools.txt`.
3. For an imported page, vendor or remove reported off-origin references before the CSP check.
4. Verify the artifact's behavior or calculations at least once.
5. Run `make validate` and the checks listed in [Operations](../docs/operations.md).

## Generated files

Change the inputs or generator for generated outputs. Do not hand-edit the outputs. See [`docs/workspace.md`](../docs/workspace.md#generated-and-derived-files) for the canonical list.

## Pull requests

- Keep changes scoped and describe the user-visible or maintenance impact.
- For preview eligibility and deployment behavior, see [Architecture](../docs/architecture.md#token-model).
- Trusted preview and production deploys also run `make test-browser-live` against the published URL, so browser-only regressions can still fail the release after deploy verification.
- If CI regenerates thumbnails during trusted same-repo PR or `main` runs, it can persist `apps/*/thumbnail.webp` back to the same PR branch or open a follow-up thumbnail PR from `main`. Other generated files are still summarized rather than auto-committed.

## Dependency updates

- Python dependencies live in `pyproject.toml` and are frozen in `uv.lock`.
- Node tooling lives in `package.json` and `package-lock.json`.
- Same-repo Dependabot uv PRs auto-refresh `uv.lock` through `.github/workflows/refresh-python-locks.yml` and `.github/workflows/commit-python-locks.yml`, but local dependency edits still need `make lock`.
- After changing Python dependency declarations, regenerate `uv.lock` with `make lock`.
- The monthly `.github/workflows/refresh-playwright.yml` workflow runs `make refresh-ci-pins` to update the locked Python Playwright package and matching official CI image digest together.
- After changing Node dependencies, refresh `package-lock.json` before rerunning the relevant `make` setup or check targets.
- `axe-core` is pinned in `package-lock.json` because the Playwright accessibility suite injects it into real browser sessions.
- Workspace-only maintenance changes do not need a standalone changelog entry; app release notes stay app-specific.
