# Security policy

## Repository scope

This repository is a static GitHub Pages site plus build and deployment tooling. The repository does not support private-data workflows. Security reports can cover the dependency supply chain, deployment tooling, and browser code.

## Reporting a vulnerability

Do not open a public issue for a suspected security problem.

If GitHub private vulnerability reporting is enabled, use it to report the vulnerability. Otherwise, contact the maintainer directly. Include the following details:

- Affected file paths or workflow names.
- Reproduction steps.
- Impact assessment.
- Suggested remediation, if known.

## Expectations

- Do not commit secrets, tokens, or `.env` files.
- Keep workflow actions pinned to full commit SHAs.
- Update lockfiles and rerun `make check` for dependency changes.
