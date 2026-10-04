---
name: copilot-review-loop
description: "Use when the user wants a pull request taken through GitHub Copilot review: requesting a Copilot review, fixing or replying to Copilot review comments, resolving its threads, or looping until Copilot approves. Do not use for general code review or for reviews by people."
---

# Copilot review loop

Use the Artifacts repository's Make targets throughout the review loop.

## Inspect the current round

Start with the smallest useful view:

```bash
make pr-summary
make pr-review-comments
```

Do not load all comments or resolved threads by default. Use `make pr-review-comments show=all` only when the summary and open-thread list disagree or when you need to confirm the state of a thread addressed during this loop.

Classify each result before editing:

- **Open thread:** Verify the claim, then fix it or reply with evidence that no change is needed.
- **Suppressed note:** Ignore it unless independent verification finds a material problem in the changed scope.
- **Review summary:** Use it as review state, not as a task list.

## Verify and group

Trace the relevant callers, state changes, contracts, and tests. Do not accept Copilot's explanation after reading only the commented line or local function.

Answer two questions separately:

1. Is the claim correct?
2. Is the change material and in scope?

Before editing, search the changed scope for the same cause. Group related findings into one patch so the next review does not rediscover the same problem elsewhere.

## Address the threads

Make the smallest grouped fix and run the relevant Make checks. Commit and push through Make.

Reply to and resolve every addressed open thread:

```bash
make pr-address thread=PRRT_... < notes.md
```

The reply should state what was verified, what changed or why no change was needed, and the validation result. A pushed fix does not replace the reply and resolution.

Confirm that no addressed thread remains open:

```bash
make pr-review-comments
make pr-summary
```

## Request the next round

Run `make pr-watch request=1` in the background. The `request=1` argument ensures that the watcher waits for a new Copilot review instead of accepting the previous round.

Report progress while the watcher is silent. If the wait is interrupted, inspect the current review state before starting another watcher.

When the watcher finishes, run `make pr-summary` and `make pr-review-comments`. If historical suppressed notes prevent classification, inspect only the latest review or the specific new comment identified by the watcher.

## Stop

Finish when the latest Copilot review recommends approval, no new actionable comments exist, no threads remain open, and the required checks pass. Historical resolved threads and suppressed notes do not block completion.

If another round produces actionable comments, repeat the loop. Stop and report the conflict if the same finding returns after two verified fixes or if resolving it would expand the change's scope.
