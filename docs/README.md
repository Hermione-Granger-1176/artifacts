# Workspace documentation

Each concern has one owning page. Other pages link to it instead of repeating it.

1. [`workspace.md`](workspace.md): repository layout, file ownership, generated outputs, and source-of-truth files
2. [`architecture.md`](architecture.md): the browser runtime and the build scripts
3. [`ci.md`](ci.md): workflows, deployments, PR previews, and GitHub App tokens
4. [`frontend.md`](frontend.md): root-gallery modules, shared frontend behavior, and browser-test scope
5. [`operations.md`](operations.md): day-to-day `make` workflows, browser setup, thumbnails, and vendored dependencies
6. [`troubleshooting.md`](troubleshooting.md): failure symptoms, fixes, and recovery runbooks
7. [`checks.md`](checks.md): check targets, their scope, and their configuration
8. [`maintenance.md`](maintenance.md): stability contracts and periodic upkeep
9. [`style.md`](style.md): editor configuration and language conventions
10. [`adr/`](adr/): architecture decision records, numbered `0001` through `0008`

Pages describe the current system. History and design rationale live only in the ADRs and in each mature artifact's `apps/<slug>/docs/decisions.md`, beside its `architecture.md` and `verification.md`.
