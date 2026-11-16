# Operations

Failure symptoms and recovery steps are in [Troubleshooting](troubleshooting.md).

## Day-to-day local workflow

Use Make targets for workspace commands. Start with these:

```bash
make help          # list command groups
make help-ci       # list the commands in one group, here CI and GitHub runs
make setup         # install Python and Node dependencies without Chromium
make setup-all     # also install Chromium for browser tests and thumbnails
make install-hooks # install local pre-commit hooks
make pr            # list the PR commands
make issue         # list the issue commands
make git           # list the Git commands
make ci            # run the full non-browser local gate
```

`make issue-list` accepts `state=`, `label=`, `assignee=`, `author=`, `limit=`, and `mine=1`. Set `SEARCH='...'` for a free-text search.

`make issue-summary issue=N` prints the state, labels, assignees, milestone, and recent comments. `make issue-develop issue=N` creates a branch linked to the issue. In REST mode it creates the branch but cannot link it.

Supply issue bodies on stdin. `make issue-edit` takes a new title through `TITLE='...'`. Set `COMMENT='...'` for a short close or reopen comment.

The `make pr-*` and `make issue-*` targets try GraphQL first. When the environment refuses GraphQL, as Claude Code cloud sessions do, they use the REST API for the rest of the run. [ADR 0008](adr/0008-graphql-first-rest-fallback.md) records the design. In REST mode:

- Review threads have no node id. `make pr-review-comments` prints each thread as `thread=<id>`, where the id is the number of the thread's first comment. Pass that number to `make pr-reply`, `make pr-resolve`, or `make pr-address`. Add `pr_num=N` when the PR is not on the current branch.
- `make pr-comments-list` prints numeric comment ids. Pass one to `make pr-comment-delete comment_id=<id>`.
- A `PRRT_` or `PRRC_` node id needs GraphQL. The target fails and names the numeric id to use.
- `make pr-create` does not push. Run `make push` first, or the target stops when the branch on GitHub is missing or behind your local `HEAD`.
- `make pr-merge` and `make pr-close` delete the remote branch and leave the local checkout alone.
- `make pr-merge` refuses a PR that GitHub does not report as mergeable. Run `make pr-merge-admin` only to merge past branch protection on purpose.
- The targets choose the repository from `GH_REPO`, then from the default that `gh repo set-default` stored, then from `origin`. If gh stored a default that these targets cannot read, they stop instead of using `origin`.
- When the selected repository is not `origin`, such as upstream from a fork, the targets read and write the selected repository and push and fetch branches through `origin`. `make pr-create` opens the PR from the fork branch. `make pr-checkout` and `make issue-develop` refuse in this case, and also when `origin` is not a GitHub repository.
- `make issue-list` with `SEARCH` needs the `search/issues` endpoint, which cloud sessions block. The other filters work.

`make pr-watch` observes the Copilot review that starts when a pull request is created, and it waits for the checks to settle. It does not request a second review. After you push a correction that needs a fresh review, run `make pr-watch request=1`. To watch only CI, run `make pr-watch checks_only=1`. `make pr-copilot-review` requests a review on its own.

Python dependency setup uses uv. Put `uv` on PATH before you run the setup, install, lock, or security targets. Leave `PLAYWRIGHT_HOST_PLATFORM_OVERRIDE` unset, because a forced platform key can cache a browser build for the wrong platform. On a Debian or Ubuntu host that lacks the shared libraries the browsers need, use [Browser setup without sudo](#browser-setup-without-sudo).

`make commit` checks the message with `scripts/gh/commit_message.py` and rejects heredoc fragments, shell redirections, and pager pipes that were pasted into it. Fix the flagged line and rerun the target.

To change workspace code:

1. To add an artifact, run `make new name=my-artifact`, or `make new name=my-artifact <<< path/to/page.html` to install an existing HTML file. Both create the metadata, stylesheet, app shell, docs, and a `tests/js/apps/<slug>/app.test.js` stub. The stub passes the gates without edits. An HTML import keeps off-origin references, so vendor or remove each reported reference before the CSP check can pass.
2. Run `make setup`, or `make setup-all` when you also need Chromium. Run `make install-hooks` once to enable the local pre-commit checks.
3. Edit files.
4. Run `make check-local`.
5. Run `make check-web` when you change shared browser behavior or need fresh thumbnails. To test one mature app, run `ARTIFACTS_BROWSER_APP_SLUGS="app-slug" make test-browser-apps`. For the cross-engine smoke pass, run `make setup-playwright-webkit` once, then `make test-browser-webkit-smoke`. On a host without the browsers' shared libraries, follow [Browser setup without sudo](#browser-setup-without-sudo) and append `local_libs=1` to these targets.
6. Run `make check` before you open a PR. It runs the full local release gate.
7. Run `make validate` after you change the directories under `apps/`.
8. Run `make index` when metadata or README markers may have changed.
9. Run `make site` to inspect the Pages output locally, or `make serve` to build it and serve it on `http://localhost:8000/`. Set `PORT=NNNN` to change the port.
10. Run `make lock` after you change Python dependency declarations, and `make lock-node` after you change Node dependencies.

## Browser setup without sudo

`make setup-all` installs Chromium into Playwright's user-level browser cache. It installs no system packages and needs no sudo. Use it when the host already has the shared libraries that the browsers need.

On a Debian or Ubuntu host that lacks those libraries, use the repository-local runtime:

```bash
make setup-playwright-local        # Chromium plus its extracted library closure
make setup-playwright-webkit-local # add WebKit for the cross-engine smoke pass
make playwright-local-status       # report what the cache currently covers
make playwright-local-gate         # launch every prepared engine for real
make playwright-local-clean        # remove only this repository's cache
```

Setup downloads package archives from the APT repositories that the host already uses. It extracts them into the ignored `.playwright/local-libs/` directory. It never installs packages or runs sudo, and it leaves the system package database unchanged. Browsers install into Playwright's shared `~/.cache/ms-playwright`, so every project on the machine reuses one copy.

Chromium and WebKit record into one manifest, so the extracted libraries cover every prepared engine. The runtime rebuilds the manifest when the operating system, architecture, Playwright version, engine set, or resolved package versions change.

Browser targets opt in with `local_libs=1`:

```bash
make test-browser local_libs=1
make test-browser-webkit-smoke local_libs=1
make thumbnails local_libs=1
make visual-baselines local_libs=1
make check-web local_libs=1
```

With `local_libs=1`, the wrapper requires a prepared cache and points `PLAYWRIGHT_BROWSERS_PATH` at the shared browser cache. It keeps the browser's home, cache, configuration, runtime, and temporary files under `.playwright/runtime/`. It prepends only the extracted library and browser-data paths to the child environment. Preparing the runtime also patches the shared WebKit launcher to read the extracted library path. The wrapper never downloads packages during a test run. Runs without `local_libs=1` are unchanged.

`make playwright-local-clean` and `make clean` remove only this repository's `.playwright/` cache. Neither touches the shared browser cache, because other projects use it. Manage shared browsers with Playwright's own tooling.

Use the `--with-deps` setup targets (`make setup-ci`, `make setup-playwright-ci`, `make setup-playwright-webkit-ci`, and `make setup-playwright-engines with_deps=1`) only on CI and other disposable runners. They can install operating-system packages.

## Inspect CI failures

Run `make ci-runs` to find a run, then `make ci-failures run=ID` to read the output of its failed steps. To follow an active run, run `make ci-watch run=ID`.

CI calls the same Make targets as local development. [CI](ci.md#main-pipeline-updateyml) describes job dependencies, shard selection, and build and publish behavior.

## Choose checks

Run `make check-local` for the non-browser gate. When browser behavior or thumbnails changed, also run `make check-web`. `make check` runs both gates plus `make index` and `make site`.

[Quality checks](checks.md) describes each target's behavior, scope, and configuration owner.

## Thumbnail policy

- `thumbnail.webp` in each artifact folder is the generated thumbnail.
- `make thumbnails` skips an artifact whose thumbnail is newer than every file under its `index.html`, `js/`, `css/`, and `assets/`. For apps on the shared runtime, it also compares `css/style.css`, `js/app-theme.js`, and the shared modules. Pass `slug=a,b` to limit the run.
- Local working copies work without checked-in thumbnails.
- In CI, the `plan` job selects the apps to regenerate. A change to an app's own `index.html`, `js/`, `css/`, or `assets/` selects that app. A change to `css/style.css`, `js/app-theme.js`, or `js/modules/app-shell.js` selects every app. A change to another shared module under `js/modules/` selects the apps that import it. Apps with no thumbnail are always selected. Each shard runs `make thumbnails-shard`.
- Edits that touch only an app's `docs/`, `README.md`, or metadata files do not trigger mature-app browser suites or thumbnail generation.
- CI sets `ARTIFACTS_STRICT_THUMBNAILS=1`, so a failed thumbnail attempt fails the workflow instead of logging a warning.
- Thumbnail discovery rejects a symlinked artifact root or descendant before it starts the local server or Playwright. An artifact cannot make the renderer read files outside its own tree.
- Trusted CI runs can save regenerated `thumbnail.webp` files back to the PR branch, or open or update a follow-up PR for `main` pushes. [CI](ci.md#thumbnail-persistence-modes) describes the modes.

## Visual regression baselines

- `make test-visual` compares a hero screenshot of the root gallery and of each mature app, taken at a 1200x800 viewport, with the committed baselines in `tests/browser/baselines/`. The comparison in `scripts/ci/visual_regression.py` is tolerant. A pixel counts as changed only when a channel differs by more than 32 of 255. An image fails when more than 5% of its pixels change, or more than 18% for the root gallery, whose animated 3D book scene stays noisy after animations are frozen.
- Screenshot rendering depends on the host's fonts. The committed baselines are the ones CI's pinned Playwright image renders, and the `root-browser` job compares against them in that image. A local run on another host can fail on font rendering alone.
- After an intentional visual change, push it and let CI fail the comparison. The failing run saves each differing capture under `visual-baselines/` in the `root-browser` failure artifact. Run `make visual-baselines-from-ci` (or add `run=ID`) to adopt those captures, review the PNG diff, and commit it.
- `make visual-baselines` regenerates the baselines from your own host. Use it only for a local before-and-after comparison, and do not commit its output.
- `make test-visual` and `make visual-baselines` need Chromium. Run `make setup-all`, or run `make setup-playwright-local` with `local_libs=1` on a host without the browsers' shared libraries.

## Page-speed budget

- `make test-page-speed` times each page from navigation start until the page's runtime sets `data-runtime-status="ready"`. Each visit uses a fresh browser context, so nothing is cached. The check fails when a page's median over five visits exceeds the 500 ms budget, so one slow visit does not fail it alone.
- The budget leaves room for runner noise and catches large regressions, such as a blocking script, heavy work at startup, or a render loop. It does not measure network transfer, because the site is served locally.
- To investigate, run `make test-page-speed runs=10`, or pass `budget_ms=` to see every page's timings without failing. Raise `DEFAULT_BUDGET_MS` in `tests/browser/test_frontend_page_speed.py` only for a deliberate change that makes a page slower, and say why in the PR.

## Required GitHub settings

[External GitHub settings](ci.md#external-github-settings) lists every required repository setting (Pages, branch protection, app tokens, secrets, rulesets). Run `make ci-audit-repo-settings` to check for drift by hand.

## Vendored runtime dependencies

- No page loads a script, font, or stylesheet from an external CDN. Third-party scripts are vendored in the app.
- Three apps vendor libraries. `config/vendored_assets.json` is the inventory and the only place that records versions:
  - `apps/loan-amortization/js/vendor/`: Chart.js, `chartjs-plugin-annotation`, `chartjs-plugin-datalabels`
  - `apps/bond-price-vs-rate/js/vendor/`: Chart.js
  - `apps/vendor-docs-generator/js/vendor/`: jsPDF, `jspdf-autotable`, html2canvas, JSZip
- Versions are pinned and upgraded by hand. [Vendored dependency update](troubleshooting.md#vendored-dependency-update) lists the steps.
- `make lint-vendored-assets` checks each file against the manifest, and `make audit-vendored` checks each package version against published advisories. See [Formatting and lint](checks.md#formatting-and-lint) and [Dependency audits](checks.md#dependency-audits).
- ESLint skips vendored directories (`**/vendor/**` in `config/eslint.config.js`), and the lint walkers skip them (`vendor` in `SKIP_DIRECTORIES` in `scripts/lint/__init__.py`).
- `apps/loan-amortization/docs/decisions.md` records the rationale.

### Self-hosted fonts

- Gallery display fonts (Caveat, Fredoka One) are self-hosted as WOFF2 Latin subsets in `assets/fonts/`.
- `@font-face` declarations live in `css/src/01-tokens.css` and are bundled into `css/style.css`.
- Only the root gallery renders these display fonts. Artifact pages set `body.artifact-app`, which overrides `--font-body` and `--font-heading` with system fonts, so app pages never fetch the WOFF2 files. Keep the two `<link rel="preload" as="font" ... crossorigin>` hints in the root `index.html` only.
- To add a font, download the WOFF2 subset into `assets/fonts/`, add the `@font-face` rule to `css/src/01-tokens.css`, and run `make styles`. Check that the CSP `font-src 'self'` directive still covers it. Add a `preload` hint to `index.html` only when the root gallery renders the font.

### Adding external assets to a new artifact

Self-host every runtime asset. Do not load scripts, fonts, or stylesheets from an external CDN. For a third-party JS library, download the UMD build into the app's `js/vendor/` directory and add it to `config/vendored_assets.json`. `make lint-artifact-csp` rejects external references, and the browser tests record failed external requests.
