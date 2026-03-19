# Maintenance Notes

## What to keep stable

These are the main cross-cutting pieces that should stay consistent over time:

- `pyproject.toml` is the source of truth for Python dependencies, test policy, lint policy, and site metadata
- `Makefile` is the common interface for local work and CI
- `.github/workflows/update.yml` is the main build, validation, and deploy workflow
- `.github/workflows/refresh-action-shas.yml` keeps pinned GitHub Actions references current

## When changing CI

If you touch workflow files:

1. prefer extending the existing workflow over cloning logic into another workflow file
2. keep action references pinned to full commit SHAs
3. update conditions carefully so pull requests do not require deploy secrets or write access
4. keep local and CI commands aligned through `make`

## When changing URLs or repo metadata

Update `pyproject.toml` under `[tool.artifacts]`.

This is where the repo keeps:

- canonical site URL
- site path
- repository URL

Scripts and docs should read from that shared config instead of embedding one-off copies.

## When changing generators

If you modify `scripts/generate_index.py` or `scripts/generate_thumbnails.py`:

- update or add tests in `tests/`
- keep `make check` green
- preserve the 100% coverage gate unless there is an explicit decision to relax it
- regenerate derived files when needed with `make index` or `make generate`

## Thumbnail policy

- CI is allowed to generate thumbnails during pull requests and pushes
- checked-in thumbnails are not required for every local branch state
- if thumbnails are removed locally, the gallery data can temporarily contain `thumbnail: null`
- pushes to `main` will regenerate and persist fresh thumbnails through CI

## Action SHA maintenance

The repo includes a scheduled workflow that refreshes pinned GitHub Action SHAs.

- file: `.github/workflows/refresh-action-shas.yml`
- purpose: keep workflows pinned and reproducible without manual SHA lookup
- expectation: when adding a new external action, pin it immediately and let the refresh workflow keep it current later

## Good maintenance habits

- prefer central config over scattered constants
- prefer one well-structured workflow path over several partially duplicated ones
- keep README high level and keep deeper operational detail in `docs/`
- treat generated files as outputs, not primary editing targets
