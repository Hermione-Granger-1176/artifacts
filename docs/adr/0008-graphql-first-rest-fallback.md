# ADR 0008: Try GraphQL first and fall back to REST for local GitHub tooling

- Status: Accepted
- Date: 2026-10-18

## Context

The local GitHub targets depend on GraphQL. The review-thread helpers in `scripts/gh/pr_review.py` call it directly, and `gh pr` and `gh issue` call it internally. Claude Code cloud sessions refuse every GraphQL request with an HTTP 403 that names the REST routes to use instead. In those sessions `make pr-summary`, `make pr-address`, and most other PR and issue targets failed, while `gh api repos/...` REST calls worked.

## Decision

1. GraphQL, or the existing `gh` subcommand, stays the primary path. On a machine that allows GraphQL, every target runs the same `gh` arguments and returns the same exit codes as before.
2. `scripts/lib/gh_policy.py` classifies the refusal as the `graphql_unavailable` failure kind, and `scripts/gh/gh_runner.py` raises `GhGraphqlUnavailableError` for it. The runner never retries that error. No other 403 produces it, so a missing token scope or a rate limit still fails.
3. `gh_runner.py` remembers the first refusal for the rest of the process. Later calls skip GraphQL, so one run sends at most one refused request.
4. Each caller passes a REST equivalent to `with_rest_fallback` for data, or to `gh_or_rest` for commands that print to the terminal. Every fallback uses the `rest`, `rest_text`, and `rest_pages` helpers in `gh_runner.py`. `scripts/gh/pr_rest.py` rebuilds the `gh pr view --json` fields, so the summary, watch, and checks code parses one format.
5. Every `make pr-*` and `make issue-*` target that called `gh` inline now calls a `scripts/gh/cli.py` subcommand. The fallback is tested Python, not shell.
6. REST has no review-thread node id. In fallback mode, a thread uses the numeric id of its first comment, and listings print it as `thread=<id>`. `reply`, `resolve`, `address`, and `delete-comment` accept that number, and they still accept `PRRT_` and `PRRC_` node ids. A node id fails with a pointer to the numeric id when GraphQL is unavailable.
7. Only GraphQL can link a branch to an issue. The `make issue-develop` fallback creates and checks out the branch, then says that the branch is not linked.

## Rejected alternatives

- Use REST everywhere. It would need one code path instead of two, but it would change the output of every target on machines where GraphQL works, and REST cannot resolve a thread by node id or link a branch to an issue.
- Run the review targets only from a local machine. That leaves cloud sessions unable to finish a Copilot review loop.

## Consequences

- Review loops, PR creation and merging, and issue triage work in cloud sessions with the same `make` commands.
- Each operation has two code paths. The tests cover both, plus the failures that must not switch to REST.
- In fallback mode, list, view, and checks output is tab-separated and close to the `gh` output, not identical.
- The REST thread route (`/ccr/review_threads`), the Copilot reviewer request, and issue search depend on endpoints that some environments do not expose. Cloud sessions block `search/issues`, so `make issue-list` with `SEARCH` fails there.

## Out of scope

- GitHub Actions workflows and the Node actions under `.github/actions/`. They run on GitHub-hosted runners, where GraphQL works.
