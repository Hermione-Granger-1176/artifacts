# ADR 0003: Makefile as sole interface, tool configs as single sources of truth

- Status: Accepted
- Date: 2026-03-26

## Context

The workspace had accumulated several inconsistencies:

- Some commands used the Makefile, others invoked `.venv/bin/*` or `npm run` directly.
- File scope for linting and coverage was defined in multiple places (Makefile, package.json, and tool config files) with duplication.
- Python scripts were flat in `scripts/` (17 files mixing build, CI, linting, and library code).
- Tests were flat in `tests/` with no grouping by concern.
- The `make help` output was manually maintained and fell out of sync.

These inconsistencies made it harder to onboard, harder to maintain, and easier to accidentally bypass safety checks.

## Decision

1. **The Makefile is the only interface.** No tool binary (`.venv/bin/*`, `pytest`, `ruff`, `npm run`) is invoked directly; everything goes through `make <target>`. If a target is missing, add one before using the tool.

2. **Each tool's config file owns its scope.** Linting, testing, and coverage scope is defined once in the tool's config or owning script definition, not duplicated across the Makefile and multiple tool configs:
   - ruff: `pyproject.toml` (built-in excludes)
   - pytest/coverage: `pyproject.toml` (`testpaths`, `--cov=scripts/`)
   - ESLint: `eslint.config.js` (files + ignores)
   - stylelint: `stylelint.config.js` (ignoreFiles)
   - yamllint: `.yamllint.yml` (ignore)
   - JS coverage: `package.json` (coverage command, thresholds, and exclude patterns)

3. **Exclude-based, not include-based.** Tools scan the repo root and exclude junk directories (`node_modules/`, `.venv/`, `_site/`). Adding a new source directory requires no config changes.

4. **Scripts organized by concern.** `scripts/` is split into subpackages: `build/`, `ci/`, `lib/`, `lint/`. A centralized `REPO_ROOT` in `scripts/__init__.py` replaces per-file path computation.

5. **Tests mirror scripts.** `tests/` has matching subdirectories: `build/`, `ci/`, `lib/`, `lint/`, plus `browser/` for Playwright and `js/` for Node tests.

6. **Auto-generated two-level help.** `make help` is generated from `## comment` annotations on targets and `# ─── Section ───` headers in the Makefile. Adding a target with `##` makes it appear automatically. `make pr`, `make ci`, and `make git` drill into sub-commands.

7. **Setup is two-level.** `make setup` is the fast default (no Chromium). `make setup-all` includes Chromium for browser tests and thumbnails.

## Consequences

- Adding a new source file or directory requires zero config changes because exclude-based scanning picks it up.
- Adding a new make target with `## description` makes it appear in `make help` automatically.
- Onboarding is: `make setup`, `make help`, start working.
- CI and local workflows use the same make targets, so local results predict CI results.
- The try/except import fallback pattern in scripts is removed. All scripts import via the installed package.

## Out of scope

- This ADR does not change the strict publishing-platform rules from ADR 0001 or the thumbnail persistence model from ADR 0002.
- `js/modules/` and `css/` remain flat because the cost of reorganizing browser ES module paths outweighs the benefit for their current size.
