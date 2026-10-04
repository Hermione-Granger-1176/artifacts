# Workspace documentation

This index links to the document that owns each repository concern.

For a first review of the repository, the documents follow this order:

1. [`workspace.md`](workspace.md): reference for repository layout, file ownership, generated outputs, and source-of-truth files
2. [`architecture.md`](architecture.md): reference for runtime, build, and CI/CD design
3. [`frontend.md`](frontend.md): reference for root-gallery modules, shared frontend behavior, and browser-test scope
4. [`operations.md`](operations.md): reference for day-to-day `make` workflows, CI parity, troubleshooting, and recovery
5. [Quality checks](checks.md): reference for check targets, scope, and configuration
6. [`maintenance.md`](maintenance.md): reference for long-term stability contracts and periodic upkeep
7. [`style.md`](style.md): reference for editor configuration and language conventions
8. [`adr/`](adr/): reference for accepted architecture decision records (numbered `0001` through `0006`)

Each concern has one owning document. Other documents link to that source instead of repeating its policy.
