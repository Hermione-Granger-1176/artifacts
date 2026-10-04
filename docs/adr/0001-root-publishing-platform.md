# ADR 0001: Treat the repository root as a strict publishing platform

- Status: Accepted
- Date: 2026-03-23

## Context

This repository has two different responsibilities:

- `apps/` contains the published interactive artifacts.
- The repository root contains the gallery shell, generators, workflows, preview logic, and deployment path that publish those artifacts.

The root-level publish path previously mixed validation, regeneration, deployment, and source-branch mutation in ways that made trust boundaries harder to reason about. The post-deploy check was also weaker than the deployment contract, and the root gallery shell needed clearer accessibility guarantees.

## Decision

The repository root follows these publishing rules:

1. `verify` is the only workflow job that builds the deployable `_site/` output.
2. `publish` deploys only the verified `_site/` artifact produced by `verify`.
3. CI and deployment fail closed. Verification, secret scanning, dependency review, and deploy checks do not auto-heal source branches or silently continue after policy failures.
4. The `publish` job does not commit generated outputs back to contributor branches. Separate, policy-gated writeback flows can persist generated thumbnails or refreshed Dependabot lock files when explicitly allowed.
5. Post-deploy verification must confirm both the cache-busted HTML marker and the `deploy-metadata.json` commit SHA.
6. Root-shell interactions must preserve visible focus, accessible state announcements, and keyboard-safe behavior.

## Amendment (ADR 0005)

ADR 0005 moved site assembly out of `verify`. The `assemble-site` job now builds and uploads the deployable `_site/` artifact after the build gates (`quick-gates`, `heavy-checks`, `root-browser`, and the app-shard jobs) pass. The `verify` job checks dependency results for branch protection. It no longer runs tests or builds files. This amendment supersedes the job assignments in decision points 1 and 2. The build happens once in `assemble-site`, and `publish` deploys that uploaded `_site/` artifact after verification.

## Consequences

- A bad build or failed policy check blocks publish until the underlying issue is fixed.
- Preview and production deploys share the same verified build input instead of rebuilding on the write path.
- Generated-file drift in CI becomes a review signal instead of an automatic branch mutation.
- Deploy debugging now includes both published asset markers and deploy metadata.
- Root-shell changes must keep keyboard behavior, focus, and accessibility covered by tests and documentation.

## Out of scope

- This decision record does not change the individual artifact contract under `apps/`.
- This hardening pass does not introduce `CODEOWNERS` or a changelog process.
