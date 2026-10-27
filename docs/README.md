# Workspace documentation

This index links to the document that owns each repository concern. Each concern has one owner, and other documents link to it instead of repeating its policy.

For a first read of the repository, go in this order:

1. [`workspace.md`](workspace.md): repository layout, file ownership, generated outputs, and source-of-truth files
2. [`architecture.md`](architecture.md): the runtime, build, and CI/CD design
3. [`frontend.md`](frontend.md): root-gallery modules, shared frontend behavior, and browser-test scope
4. [`operations.md`](operations.md): day-to-day `make` workflows, CI parity, troubleshooting, and recovery
5. [`checks.md`](checks.md): check targets, their scope, and their configuration
6. [`maintenance.md`](maintenance.md): stability contracts and periodic upkeep
7. [`style.md`](style.md): editor configuration and language conventions
8. [`adr/`](adr/): accepted architecture decision records, numbered `0001` through `0008`

Mature artifacts also keep an `architecture.md`, a `verification.md`, and a `decisions.md` under `apps/<slug>/docs/`.
