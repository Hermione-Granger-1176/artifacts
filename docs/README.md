# Workspace Docs

This folder explains how the repository works as a system, not how any single artifact works.

If you are new to the repo, read in this order:

1. [`workspace.md`](workspace.md) for structure, ownership, and source-of-truth files
2. [`architecture.md`](architecture.md) for runtime and build flow
3. [`frontend.md`](frontend.md) for JavaScript module responsibilities and test coverage
4. [`operations.md`](operations.md) for local commands, CI behavior, and troubleshooting
5. [`maintenance.md`](maintenance.md) for ongoing upkeep and workflow hygiene

What these docs cover:

- how the root gallery is assembled
- which files are generated versus hand-maintained
- where URLs and deployment metadata live
- how CI generates data, thumbnails, and the Pages deployment
- how to work locally without breaking generated state
- how to maintain pinned actions, generators, and workspace metadata
- which external GitHub settings the deployment workflow expects
- how to recover from a bad deploy or broken preview workflow
