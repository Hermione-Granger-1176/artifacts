# Contributing

Use this guide to prepare a change to the Artifacts workspace.

## Start here

- Run `make help` to list the workspace targets.
- Follow [operations](../docs/operations.md) for the local workflow.
- Use [workspace](../docs/workspace.md) for repository layout, generated outputs, and source-of-truth ownership.
- Use [style](../docs/style.md) for editor settings, language conventions, and commit messages.
- Use [CI and deployment](../docs/ci.md) for CI jobs, tokens, and deploys. Use [troubleshooting](../docs/troubleshooting.md) for failures and recovery.

## Add an artifact

1. Run `make new name=my-artifact` to scaffold an app. To import an HTML file, pass its path on stdin: `make new name=my-artifact <<< path/to/file.html`.
2. Build the app and fill in `name.txt`, `description.txt`, `tags.txt`, and `tools.txt`.
3. For an imported page, vendor or remove the off-origin references that the CSP check reports.
4. Verify the artifact's behavior or calculations at least once.
5. Run `make validate` and the checks in [checks](../docs/checks.md).

## Generated files

Change the inputs or the generator, not the output. Do not edit generated files by hand. The canonical list is in [workspace](../docs/workspace.md#generated-and-derived-files).

## Pull requests

- Keep changes scoped. Describe the user-visible or maintenance impact.
- For preview eligibility and deploy behavior, see [CI and deployment](../docs/ci.md#main-pipeline-updateyml).
- Trusted preview and production deploys run `make test-browser-live` against the published URL. A browser-only regression can fail the release after deploy verification.
- CI can persist regenerated `apps/*/thumbnail.webp` files to a same-repo PR branch, or open a follow-up thumbnail PR from `main`. See [thumbnail persistence modes](../docs/ci.md#thumbnail-persistence-modes).

## Dependency updates

- Python dependencies live in `pyproject.toml` and are frozen in `uv.lock`. After changing them, run `make lock`.
- Node dependencies live in `package.json` and `package-lock.json`. After changing them, run `make lock-node`, then rerun the setup or check targets you need.
- Keep `axe-core` pinned in `package-lock.json`. The accessibility suite injects it into browser sessions.
- Dependabot uv PRs and the monthly Playwright refresh update the locks automatically. See [auxiliary workflows](../docs/ci.md#auxiliary-workflows).
- Workspace-only maintenance changes need no changelog entry. App release notes stay app-specific.
