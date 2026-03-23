# ADR 0001: Treat the repository root as a strict publishing platform

- Status: Accepted
- Date: 2026-03-23

## Context

This repository has two different responsibilities:

- `apps/` contains the published interactive artifacts.
- The repository root contains the gallery shell, generators, workflows, preview logic, and deployment path that publish those artifacts.

The root-level publish path previously mixed validation, regeneration, deployment, and source-branch mutation in ways that made trust boundaries harder to reason about. The post-deploy check was also weaker than the deployment contract, and the root gallery shell needed clearer accessibility guarantees.

## Decision

The repository root is treated as a strict publishing platform with these rules:

1. `verify` is the only workflow job that builds the deployable `_site/` output.
2. `publish` deploys only the verified `_site/` artifact produced by `verify`.
3. CI and deployment fail closed. Verification, secret scanning, dependency review, and deploy checks do not auto-heal source branches or silently continue after policy failures.
4. The publish path does not commit generated outputs back to contributor branches. Generated diffs are summarized for humans to inspect.
5. Post-deploy verification must confirm both the cache-busted HTML marker and the `deploy-metadata.json` commit SHA.
6. Root-shell interactions must preserve visible focus, accessible state announcements, and keyboard-safe behavior.

## Consequences

- A bad build or failed policy check blocks publish until the underlying issue is fixed.
- Preview and production deploys share the same verified build input instead of rebuilding on the write path.
- Generated-file drift in CI becomes a review signal instead of an automatic branch mutation.
- Deploy debugging now includes both published asset markers and deploy metadata.
- Root-shell changes must keep keyboard/focus/accessibility behavior covered by tests and documentation.

## Out of scope

- This decision record does not change the individual artifact contract under `apps/`.
- This hardening pass does not introduce `CODEOWNERS` or a changelog process.
