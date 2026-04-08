# Workspace Docs

This folder documents repository-level behavior. It should route readers to the right canonical doc instead of restating the same policy in multiple places.

Read in this order when you are new to the repo:

1. [`workspace.md`](workspace.md): canonical for repository layout, file ownership, generated outputs, and source-of-truth files
2. [`architecture.md`](architecture.md): canonical for runtime, build, and CI/CD design
3. [`frontend.md`](frontend.md): canonical for root-gallery modules, shared frontend behavior, and browser-test scope
4. [`operations.md`](operations.md): canonical for day-to-day `make` workflows, CI parity, troubleshooting, and recovery
5. [`maintenance.md`](maintenance.md): canonical for long-term stability contracts and periodic upkeep
6. [`style.md`](style.md): canonical for editor configuration and language conventions

If two docs seem to overlap, prefer the one that owns the concern above and link to it instead of copying the policy again.
