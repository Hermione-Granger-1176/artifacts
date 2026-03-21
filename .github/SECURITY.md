# Security Policy

## Supported surface

This repository is a static GitHub Pages site plus build and deployment tooling. There is no supported private-data workflow in the repository itself, but supply-chain, deployment, and client-side issues still matter.

## Reporting a vulnerability

Please do not open a public issue for a suspected security problem.

Report vulnerabilities through GitHub private vulnerability reporting if it is enabled for the repository. If that option is unavailable, contact the maintainer directly and include:

- Affected file paths or workflow names.
- Reproduction steps.
- Impact assessment.
- Suggested remediation, if known.

## Expectations

- Do not commit secrets, tokens, or `.env` files.
- Keep workflow actions pinned to full commit SHAs.
- Prefer updating lock files and rerunning `make check` with every dependency change.
