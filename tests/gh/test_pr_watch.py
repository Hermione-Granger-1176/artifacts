from __future__ import annotations

import json
from datetime import UTC, datetime
from itertools import chain, repeat

import pytest

from scripts.gh import cli, gh_runner, pr_review, pr_watch
from scripts.gh.gh_runner import GhError
from tests.gh.gh_test_support import (
    FakeGh,
    completed_process,
    has,
    json_response,
    rest,
    sandbox_routes,
)

_CLEAN_BODY = "Copilot reviewed 8 files and generated no new comments."
_COMMENT_BODY = "Copilot reviewed 8 files and generated 2 comments."
_SUBMITTED_AT = "2026-07-26T12:00:00Z"
# Trimmed v2 overview: approval recommended with no findings.
_V2_CLEAN_BODY = """<!-- ccr-overview-v2 -->

## Copilot review overview

### 🟢 Approval recommended

The theme architecture is consistent and complete.

**Review effort:** Balanced \x20
**Findings:** None

<details>
<summary><strong>Resolved since last review (1)</strong></summary>

</details>
"""
_V2_COMMENT_BODY = """<!-- ccr-overview-v2 -->

## Copilot review overview

### 🟡 Changes recommended

The new parity invariant lacks automated enforcement.

**Review effort:** Balanced \x20

<details open>
<summary><strong>Open (2)</strong></summary>

- [Enforce token parity](#discussion_r101) · New
- [Update the ADR](#discussion_r102)
</details>

<details>
<summary><strong>Resolved since last review (1)</strong></summary>

- [Earlier finding](#discussion_r99)
</details>
"""
# Trimmed v2 overview: no findings, with a previously missed finding that has no thread.
_V2_CLOSER_LOOK_BODY = """<!-- ccr-overview-v2 -->

## Copilot review overview

### 🔵 Needs a closer look

Unclassifiable v2 reviews can exhaust the polling budget.

**Review effort:** Balanced \x20
**Findings:** None

<details>
<summary><strong>Previously missed (1)</strong></summary>

<details>
<summary>Avoid waiting on unclassified overview</summary>

`scripts/gh/pr_watch.py:446`
</details>
</details>
"""
_PICTURE = '<picture><img alt="High severity"></picture>'
_PR_URL = "https://github.com/o/r/pull/7"
# Trimmed v2 overview with counted section headings. The verdict follows the marker,
# sections are headed "N <label>", and open findings link full thread URLs.
_V2_COUNTED_COMMENT_BODY = f"""<!-- ccr-overview-v2 -->

### 🟡 Changes recommended

Repository identity handling can redirect destructive commands.

<details open>
<summary><strong>2 open issues</strong></summary>

- {_PICTURE} [PR number cache reused]({_PR_URL}#discussion_r101) · New
- {_PICTURE} [Comparisons are case-sensitive]({_PR_URL}#discussion_r102) · New
</details>

<details>
<summary><strong>1 previously missed issue</strong></summary>

In code that hasn't changed since last review

<details>
<summary>{_PICTURE} Branch lookup errors are misreported</summary>

`scripts/gh/pr_commands.py:179`
</details>
</details>

<details>
<summary><strong>1 resolved since last review</strong></summary>

- {_PICTURE} [Earlier finding]({_PR_URL}#discussion_r99)
</details>

<sub>Review effort: Balanced</sub>
"""
# The same layout with approval and only the resolved list.
_V2_COUNTED_CLEAN_BODY = f"""<!-- ccr-overview-v2 -->

### 🟢 Approval recommended

The fallback is complete.

<details>
<summary><strong>1 resolved since last review</strong></summary>

- {_PICTURE} [Earlier finding]({_PR_URL}#discussion_r99)
</details>
"""
# No open section, but a previously missed finding without a thread.
_V2_COUNTED_MISSED_BODY = (
    _V2_COUNTED_COMMENT_BODY.split("<details open>")[0]
    + "<details>"
    + _V2_COUNTED_COMMENT_BODY.split("</details>\n\n<details>", 1)[1]
)
# "**Findings:** None" followed by an "Open (2)" section that never closes.
_V2_UNCLOSED_OPEN_BODY = (
    _V2_CLEAN_BODY + _V2_COMMENT_BODY.split("<details open>")[1].split("</details>")[0]
)
# An unclosed "Open (2)" section followed by a closed "Previously missed" block.
_V2_OPEN_THEN_NESTED_BODY = (
    _V2_COMMENT_BODY.split("</details>")[0]
    + "<details>"
    + _V2_CLOSER_LOOK_BODY.split("<details>", 1)[1]
)


def _review(
    review_id: str,
    *,
    body: object = _CLEAN_BODY,
    submitted_at: object = _SUBMITTED_AT,
    login: object = "copilot-pull-request-reviewer",
    state: object = "COMMENTED",
) -> dict[str, object]:
    """Build one review payload."""
    return {
        "id": review_id,
        "author": {"login": login},
        "body": body,
        "submittedAt": submitted_at,
        "state": state,
    }


def _check(
    *,
    status: object = "COMPLETED",
    conclusion: object = "SUCCESS",
) -> dict[str, object]:
    """Build one check-run payload."""
    return {"status": status, "conclusion": conclusion}


def _payload(
    *,
    reviews: object,
    rollup: object,
) -> str:
    """Serialize one PR view response."""
    return json.dumps({"reviews": reviews, "statusCheckRollup": rollup})


def _poll_runner(*, reviews: object, rollup: object) -> FakeGh:
    """Return a fake runner for one PR view poll."""
    return FakeGh(
        [
            (
                has("pr", "view"),
                completed_process(0, _payload(reviews=reviews, rollup=rollup)),
            )
        ]
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        (_CLEAN_BODY, 0),
        ("Copilot reviewed 15 out of 15 changed files and generated no comments.", 0),
        (_COMMENT_BODY, 2),
        ("generated 1 comment", 1),
        ("unrecognized overview", None),
        (_V2_CLEAN_BODY, 0),
        (_V2_COMMENT_BODY, 2),
        (_V2_CLEAN_BODY.replace("**Findings:** None", "**Findings:** Some"), None),
        (_V2_COMMENT_BODY.replace("- [Update the ADR](#discussion_r102)\n", ""), None),
        (_V2_CLOSER_LOOK_BODY, 0),
        (_V2_OPEN_THEN_NESTED_BODY, None),
        (_V2_UNCLOSED_OPEN_BODY, None),
        (_V2_COUNTED_COMMENT_BODY, 2),
        (_V2_COUNTED_CLEAN_BODY, 0),
        (_V2_COUNTED_MISSED_BODY, 0),
        (_V2_COUNTED_COMMENT_BODY.replace("2 open issues", "1 open issue"), None),
        (_V2_COUNTED_CLEAN_BODY.replace("### 🟢 Approval recommended", ""), None),
    ],
)
def test_generated_comment_count_classifies_overviews(body: str, expected: int | None) -> None:
    """Recognize clean and actionable Copilot overview forms."""
    assert pr_watch._generated_comment_count(body) == expected


@pytest.mark.parametrize(
    ("body", "summary"),
    [
        (
            _V2_COUNTED_COMMENT_BODY,
            "generated 2 comment(s) and 1 without a thread; "
            "read the overview with `make pr-comments`",
        ),
        (_V2_COMMENT_BODY, "generated 2 comment(s)"),
    ],
)
def test_review_summary_counts_v2_findings_without_threads(body: str, summary: str) -> None:
    """Previously missed findings have no thread, so the summary points at the overview."""
    review = pr_watch.CopilotReview(
        "v2",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        body,
        pr_watch._generated_comment_count(body),
    )

    assert pr_watch._review_summary(review, requested=True) == summary


def test_review_summary_distinguishes_absent_from_unrequested_reviews() -> None:
    """A requested review that never arrived is not reported as unrequested."""
    assert pr_watch._review_summary(None, requested=True) == "no new review yet"
    assert pr_watch._review_summary(None, requested=False) == "not requested"


def test_parse_timestamp_compares_as_instant_and_requires_timezone() -> None:
    """Timestamps compare as instants and cannot be timezone-naive.

    The parser keeps each payload's original offset. Aware datetimes compare by instant.
    """
    parsed = pr_watch._parse_timestamp("2026-07-26T14:00:00+02:00", "review")

    assert parsed == datetime(2026, 7, 26, 12, tzinfo=UTC)
    # GitHub's trailing Z form parses as UTC.
    assert pr_watch._parse_timestamp(_SUBMITTED_AT, "review") == datetime(
        2026, 7, 26, 12, tzinfo=UTC
    )
    with pytest.raises(GhError, match="must include timezone"):
        pr_watch._parse_timestamp("2026-07-26T12:00:00", "review")
    with pytest.raises(GhError, match="not a valid ISO-8601"):
        pr_watch._parse_timestamp("not-a-date", "review")


def test_copilot_reviews_ignores_other_authors_and_parses_copilot() -> None:
    """Only validated Copilot reviews participate in the baseline."""
    reviews = pr_watch._copilot_reviews(
        [
            _review("other", login="octocat"),
            _review("copilot", body=_COMMENT_BODY),
        ]
    )

    assert reviews == (
        pr_watch.CopilotReview(
            review_id="copilot",
            submitted_at=datetime(2026, 7, 26, 12, tzinfo=UTC),
            body=_COMMENT_BODY,
            generated_comment_count=2,
            state="COMMENTED",
        ),
    )


def test_copilot_review_requires_exact_clean_wording() -> None:
    """A numeric zero is not the clean wording.

    Both the first-review and re-review phrasings count as clean. The first-review
    phrasing has no "new".
    """
    first_pass = pr_watch.CopilotReview(
        "first-pass",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        "generated no comments",
        0,
    )
    re_review = pr_watch.CopilotReview(
        "re-review",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        "generated no new comments",
        0,
    )
    numeric = pr_watch.CopilotReview(
        "numeric",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        "generated 0 comments",
        0,
    )

    assert first_pass.is_explicitly_clean
    assert re_review.is_explicitly_clean
    assert not numeric.is_explicitly_clean


@pytest.mark.parametrize(
    ("body", "verdict"),
    [
        (_V2_CLEAN_BODY, "Approval recommended"),
        (_V2_COMMENT_BODY, "Changes recommended"),
        (_V2_CLOSER_LOOK_BODY, "Needs a closer look"),
        (_V2_COUNTED_COMMENT_BODY, "Changes recommended"),
        (_V2_COUNTED_CLEAN_BODY, "Approval recommended"),
        ("<!-- ccr-overview-v2 -->\n**Findings:** None\n", ""),
        ("<!-- ccr-overview-v2 -->\n**Findings:** None\n\n### Approval recommended\n", ""),
    ],
)
def test_v2_overview_verdict_drops_the_emoji(body: str, verdict: str) -> None:
    """The verdict is the heading under the overview title, without its emoji."""
    review = pr_watch.CopilotReview("v2", datetime(2026, 7, 26, 12, tzinfo=UTC), body, 0)

    assert review.verdict == verdict


@pytest.mark.parametrize(
    ("body", "summary"),
    [
        (_V2_CLOSER_LOOK_BODY, "needs a closer look with no open threads"),
        (_V2_COUNTED_MISSED_BODY, "changes recommended with no open threads"),
        ("<!-- ccr-overview-v2 -->\n**Findings:** None\n", "no verdict with no open threads"),
    ],
)
def test_review_summary_points_a_v2_review_without_approval_at_the_overview(
    body: str, summary: str
) -> None:
    """A v2 review with no threads but no approval names its verdict instead of passing."""
    review = pr_watch.CopilotReview(
        "v2",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        body,
        pr_watch._generated_comment_count(body),
    )

    assert pr_watch._review_summary(review, requested=True) == (
        f"{summary}; read the overview with `make pr-comments`"
    )


@pytest.mark.parametrize(
    ("body", "clean"),
    [
        (_V2_CLEAN_BODY, True),
        (_V2_COMMENT_BODY, False),
        (_V2_COMMENT_BODY + "**Findings:** None\n", False),
        (_V2_CLOSER_LOOK_BODY, False),
        (_V2_CLEAN_BODY + _V2_CLOSER_LOOK_BODY.split("**Findings:** None")[1], False),
        (_V2_CLEAN_BODY.replace("Resolved since last review", "Needs a decision"), False),
        (_V2_UNCLOSED_OPEN_BODY, False),
        ("<!-- ccr-overview-v2 -->\ngenerated no comments", False),
        (_V2_COUNTED_CLEAN_BODY, True),
        (_V2_COUNTED_COMMENT_BODY, False),
        (_V2_COUNTED_MISSED_BODY, False),
    ],
)
def test_v2_overview_is_clean_only_with_no_findings_and_no_open_section(
    body: str, clean: bool
) -> None:
    """A v2 overview needs "**Findings:** None" and no "Open (N)" section to count as clean."""
    review = pr_watch.CopilotReview(
        "v2",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        body,
        pr_watch._generated_comment_count(body),
    )

    assert review.is_v2_overview
    assert review.is_explicitly_clean is clean


@pytest.mark.parametrize(
    "reviews",
    [
        {},
        ["not-an-object"],
        [{"author": "invalid"}],
        [_review("", body=_CLEAN_BODY)],
        [_review("review", submitted_at=None)],
        [_review("review", body=None)],
        [_review("review", state=None)],
        [{key: value for key, value in _review("review").items() if key != "state"}],
    ],
)
def test_copilot_reviews_rejects_malformed_payloads(reviews: object) -> None:
    """Malformed review data fails closed instead of satisfying a watch."""
    with pytest.raises(GhError):
        pr_watch._copilot_reviews(reviews)


def test_watch_baseline_returns_existing_review_and_thread_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The baseline captures reviews and every thread before a new request."""
    runner = _poll_runner(
        reviews=[_review("old"), _review("other", login="octocat")],
        rollup=[],
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        pr_review,
        "list_threads",
        lambda *_args, **kwargs: (
            calls.append(kwargs)
            or [
                pr_review.ReviewThread("PRRT_open", "open", "f", 1, "copilot", "body", "url"),
                pr_review.ReviewThread(
                    "PRRT_resolved",
                    "resolved",
                    "f",
                    2,
                    "copilot",
                    "body",
                    "url",
                ),
            ]
        ),
    )

    assert pr_watch.watch_baseline(12, run_fn=runner) == pr_watch.WatchBaseline(
        frozenset({"old"}),
        frozenset({"PRRT_open", "PRRT_resolved"}),
    )
    assert calls == [{"include_resolved": True, "run_fn": runner}]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"reviews": []},
        {"reviews": [], "statusCheckRollup": {}},
    ],
)
def test_poll_once_rejects_malformed_containers(payload: object) -> None:
    """PR view response containers must match the expected schema."""
    runner = FakeGh([(has("pr", "view"), completed_process(0, json.dumps(payload)))])

    with pytest.raises(GhError):
        pr_watch.poll_once(12, frozenset(), expected_checks=1, run_fn=runner)


def test_check_status_waits_for_expected_count_and_pending_checks() -> None:
    """A partial or running rollup cannot satisfy the watcher."""
    partial = pr_watch._check_status([_check()], expected_checks=2)
    pending = pr_watch._check_status(
        [_check(status="IN_PROGRESS", conclusion=None)],
        expected_checks=1,
    )

    assert partial[:3] == (False, False, 1)
    assert pending[:3] == (False, False, 1)


def test_check_status_accepts_a_successful_status_context() -> None:
    """A legacy status context reporting SUCCESS settles like a completed check run."""
    settled, successful, count, _, identities = pr_watch._check_status(
        [{"state": "SUCCESS"}],
        expected_checks=1,
    )

    assert (settled, successful, count) == (True, True, 1)
    assert identities == frozenset({"index:0"})


def test_check_identity_prefers_names_then_contexts_then_position() -> None:
    """Each rollup entry gets an identity from its name, then its context, then its position."""
    assert pr_watch._check_identity({"name": "verify"}, 0) == "name:verify"
    assert pr_watch._check_identity({"context": "vercel"}, 0) == "context:vercel"
    assert pr_watch._check_identity({"name": ""}, 3) == "index:3"


def test_check_status_identities_track_growth_past_duplicate_names() -> None:
    """A duplicate name does not make a grown rollup produce the same identities.

    An unnamed entry's ordinal is its index in the rollup.
    """
    ok = {"status": "COMPLETED", "conclusion": "SUCCESS"}
    before = [{"name": "x", **ok}, dict(ok)]
    after = [{"name": "x", **ok}, {"name": "x", **ok}, dict(ok)]

    identities_before = pr_watch._check_status(before, expected_checks=1)[4]
    identities_after = pr_watch._check_status(after, expected_checks=1)[4]

    assert identities_before == frozenset({"name:x", "index:1"})
    # The trailing entry keeps its index in the rollup, so it is index:2.
    assert identities_after == frozenset({"name:x", "index:2"})
    assert identities_before != identities_after


def test_check_status_settles_on_a_rollup_smaller_than_a_full_ci_run() -> None:
    """A scoped PR settles on the checks it has, not on a fixed total."""
    rollup = [
        {"name": "verify", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "app-shard", "status": "COMPLETED", "conclusion": "SKIPPED"},
    ]

    settled, successful, count, _, identities = pr_watch._check_status(
        rollup,
        expected_checks=pr_watch.DEFAULT_EXPECTED_CHECKS,
    )

    assert (settled, successful, count) == (True, True, 2)
    assert identities == frozenset({"name:verify", "name:app-shard"})


def test_watch_pr_ignores_stability_observed_while_checks_were_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unchanged check set seen while checks run does not settle the first terminal poll.

    Only consecutive settled polls with the same check set count as stable.
    """
    early = frozenset({"name:plan", "name:secret-scan"})
    running = _status(settled=False, review=_parsed_review(), check_ids=early)
    terminal = _status(settled=True, review=_parsed_review(), check_ids=early)
    complete = _status(
        settled=True,
        review=_parsed_review(),
        check_ids=early | {"name:verify"},
    )
    _, sleeps = _watch_stubs(monkeypatch, [running, terminal, complete])

    report = pr_watch.watch_pr(
        12,
        interval=7,
        max_polls=5,
        request_copilot=True,
        sleep_fn=sleeps.append,
    )

    # Poll 2 does not settle even though its ids match poll 1, so the watch polls
    # again and sees the check that had not registered yet.
    assert len(sleeps) == 3
    assert sleeps[0] == 7
    assert "merge ready: yes" in report


def test_watch_pr_settles_once_the_check_set_repeats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rollup that grows between polls is not treated as finished."""
    growing = _status(settled=True, review=_parsed_review(), check_ids=frozenset({"name:plan"}))
    complete = _status(
        settled=True,
        review=_parsed_review(),
        check_ids=frozenset({"name:plan", "name:verify"}),
    )
    _, sleeps = _watch_stubs(monkeypatch, [growing, complete])

    report = pr_watch.watch_pr(
        12,
        interval=9,
        max_polls=4,
        request_copilot=True,
        sleep_fn=sleeps.append,
    )

    # Two short confirmations: one after the rollup grew, one before settling.
    assert sleeps == [pr_watch.CONFIRM_DELAY_SECONDS, pr_watch.CONFIRM_DELAY_SECONDS]
    assert "merge ready: yes" in report


def test_review_summary_flags_an_unrecognized_overview() -> None:
    """Wording the classifier cannot read is reported rather than assumed clean."""
    review = pr_watch.CopilotReview(
        review_id="R_1",
        submitted_at=datetime(2026, 7, 26, 12, tzinfo=UTC),
        body="Copilot had thoughts",
        generated_comment_count=None,
    )

    assert pr_watch._review_summary(review, requested=True) == "unrecognized Copilot overview"


def test_an_approval_state_does_not_bypass_unrecognized_wording() -> None:
    """A review state without clean wording must not be treated as clean."""
    review = _parsed_review(count=None, state="APPROVED")

    assert not review.is_explicitly_clean
    assert pr_watch._review_summary(review, requested=True) == "unrecognized Copilot overview"


def test_a_non_approving_review_still_needs_recognizable_wording() -> None:
    """A commented or dismissed review must not inherit the approval shortcut."""
    review = _parsed_review(count=None, state="COMMENTED")

    assert not review.is_explicitly_clean
    assert pr_watch._review_summary(review, requested=True) == "unrecognized Copilot overview"


def test_watch_pr_rejects_an_approval_state_without_clean_wording(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An approval state without recognizable wording blocks the watch."""
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_parsed_review(count=None, state="APPROVED"))],
    )

    with pytest.raises(GhError, match="could not be classified"):
        pr_watch.watch_pr(12, interval=0, max_polls=2)


@pytest.mark.parametrize("conclusion", ["SUCCESS", "NEUTRAL", "SKIPPED"])
def test_check_status_accepts_successful_terminal_outcomes(conclusion: str) -> None:
    """Successful, neutral, and skipped completed checks are acceptable."""
    status = pr_watch._check_status(
        [_check(conclusion=conclusion)],
        expected_checks=1,
    )

    assert status[:3] == (True, True, 1)


@pytest.mark.parametrize(
    "rollup",
    [
        [_check(conclusion="FAILURE")],
        [{"state": "FAILURE"}],
        [{"state": "PENDING"}],
    ],
)
def test_check_status_rejects_or_waits_for_unsuccessful_contexts(
    rollup: list[dict[str, object]],
) -> None:
    """Failed contexts are unsuccessful and pending contexts remain unsettled."""
    settled, successful, _, _, _ = pr_watch._check_status(
        rollup,
        expected_checks=1,
    )

    assert not successful
    assert settled is (rollup[0].get("state") != "PENDING")


@pytest.mark.parametrize(
    "rollup",
    [
        ["invalid"],
        [{"status": None}],
        [{"status": "COMPLETED", "conclusion": None}],
        [{"state": None}],
    ],
)
def test_check_status_rejects_malformed_entries(rollup: object) -> None:
    """Malformed check data cannot be mistaken for a passing rollup."""
    with pytest.raises(GhError):
        pr_watch._check_status(rollup, expected_checks=1)


def test_poll_once_uses_only_reviews_newer_than_the_id_baseline() -> None:
    """A review from an earlier cycle cannot satisfy a new watch."""
    runner = _poll_runner(
        reviews=[
            _review("old", submitted_at="2026-07-26T12:00:05Z"),
            _review("new", submitted_at="2026-07-26T12:00:01Z"),
        ],
        rollup=[_check()],
    )

    status = pr_watch.poll_once(
        12,
        frozenset({"old"}),
        expected_checks=1,
        run_fn=runner,
    )

    assert status.checks_settled
    assert status.checks_successful
    assert status.fresh_review is not None
    assert status.fresh_review.review_id == "new"


def test_poll_once_selects_latest_fresh_review_chronologically() -> None:
    """Multiple new reviews are ordered by timestamp rather than payload order."""
    runner = _poll_runner(
        reviews=[
            _review("latest", submitted_at="2026-07-26T14:30:00+02:00"),
            _review("earlier", submitted_at="2026-07-26T12:15:00Z"),
        ],
        rollup=[_check()],
    )

    status = pr_watch.poll_once(
        12,
        frozenset(),
        expected_checks=1,
        run_fn=runner,
    )

    assert status.fresh_review is not None
    assert status.fresh_review.review_id == "latest"


def test_poll_once_uses_payload_order_to_break_timestamp_ties() -> None:
    """The later review wins when GitHub timestamps share one-second precision."""
    runner = _poll_runner(
        reviews=[
            _review("first", body=_COMMENT_BODY),
            _review("second", body=_CLEAN_BODY),
        ],
        rollup=[_check()],
    )

    status = pr_watch.poll_once(
        12,
        frozenset(),
        expected_checks=1,
        run_fn=runner,
    )

    assert status.fresh_review is not None
    assert status.fresh_review.review_id == "second"


def test_poll_once_checks_only_ignores_fresh_review() -> None:
    """Checks-only mode never treats review data as a completion requirement."""
    status = pr_watch.poll_once(
        12,
        frozenset(),
        expected_checks=1,
        checks_only=True,
        run_fn=_poll_runner(reviews=[_review("new")], rollup=[_check()]),
    )

    assert status.fresh_review is None


def _status(
    *,
    settled: bool,
    successful: bool = True,
    review: pr_watch.CopilotReview | None = None,
    tally: str = "15 success",
    check_ids: frozenset[str] = frozenset({"name:verify"}),
) -> pr_watch.PollStatus:
    """Build a poll result for watcher control-flow tests."""
    return pr_watch.PollStatus(
        checks_settled=settled,
        checks_successful=successful,
        check_count=15,
        rollup_tally=tally,
        fresh_review=review,
        check_ids=check_ids,
    )


def _parsed_review(
    review_id: str = "new",
    *,
    count: int | None = 0,
    state: str = "",
) -> pr_watch.CopilotReview:
    """Build one parsed fresh review."""
    body = _CLEAN_BODY if count == 0 else _COMMENT_BODY if count == 2 else "unrecognized"
    return pr_watch.CopilotReview(
        review_id=review_id,
        submitted_at=datetime(2026, 7, 26, 12, tzinfo=UTC),
        body=body,
        generated_comment_count=count,
        state=state,
    )


def _watch_stubs(
    monkeypatch: pytest.MonkeyPatch,
    statuses: list[pr_watch.PollStatus],
    *,
    thread_batches: list[list[pr_review.ReviewThread]] | None = None,
) -> tuple[list[str], list[float]]:
    """Stub watcher dependencies and return request and sleep records.

    The final status repeats forever. A settled check set must be seen on two
    consecutive polls, so a single steady-state status is followed by the same
    status on the next poll.
    """
    sequence = chain(statuses, repeat(statuses[-1]))
    threads = iter(thread_batches or [[]])
    requested: list[str] = []
    sleeps: list[float] = []
    monkeypatch.setattr(
        pr_watch,
        "watch_baseline",
        lambda *_args, **_kwargs: pr_watch.WatchBaseline(
            frozenset({"old"}),
            frozenset(),
        ),
    )
    monkeypatch.setattr(
        pr_review,
        "request_copilot_review",
        lambda *_args, **_kwargs: requested.append("requested"),
    )
    monkeypatch.setattr(
        pr_watch,
        "poll_once",
        lambda *_args, **_kwargs: next(sequence),
    )
    monkeypatch.setattr(
        pr_review,
        "list_threads",
        lambda *_args, **_kwargs: next(threads),
    )
    return requested, sleeps


def test_watch_pr_captures_baseline_before_request_and_reports_clean_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The combined baseline and request flow cannot accept an older review."""
    order: list[str] = []
    monkeypatch.setattr(
        pr_watch,
        "watch_baseline",
        lambda *_args, **_kwargs: (
            order.append("baseline") or pr_watch.WatchBaseline(frozenset({"old"}), frozenset())
        ),
    )
    monkeypatch.setattr(
        pr_review,
        "request_copilot_review",
        lambda *_args, **_kwargs: order.append("request"),
    )
    monkeypatch.setattr(
        pr_watch,
        "poll_once",
        lambda *_args, **_kwargs: _status(
            settled=True,
            review=_parsed_review(),
        ),
    )
    monkeypatch.setattr(pr_review, "list_threads", lambda *_args, **_kwargs: [])

    report = pr_watch.watch_pr(12, interval=0, max_polls=2, request_copilot=True)

    assert order == ["baseline", "request"]
    assert "latest Copilot review: generated no comments" in report
    assert "open review threads: 0" in report
    assert "merge ready: yes" in report


def test_watch_pr_sleeps_until_checks_and_review_are_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The watcher waits without printing every intermediate poll."""
    requested, sleeps = _watch_stubs(
        monkeypatch,
        [
            _status(settled=False, review=None, tally="4 pending, 11 success"),
            _status(settled=True, review=_parsed_review()),
        ],
    )

    report = pr_watch.watch_pr(
        12,
        interval=3,
        max_polls=3,
        request_copilot=True,
        sleep_fn=sleeps.append,
    )

    # A full interval while checks run, then the short stability confirmation.
    assert requested == ["requested"]
    assert sleeps == [3, 3]
    assert "settled after 3 poll(s)" in report


def test_watch_pr_reports_actionable_threads_after_commented_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A new review with comments returns only its current open threads."""
    thread = pr_review.ReviewThread(
        "PRRT_1",
        "open",
        "file.py",
        12,
        "copilot-pull-request-reviewer",
        "Fix this issue.",
        "https://example.test/thread",
    )
    second_thread = pr_review.ReviewThread(
        "PRRT_2",
        "open",
        "other.py",
        20,
        "copilot-pull-request-reviewer",
        "Fix the related issue.",
        "https://example.test/thread-2",
    )
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_parsed_review(count=2))],
        thread_batches=[[thread, second_thread]],
    )

    report = pr_watch.watch_pr(12, interval=0, max_polls=2)

    assert "generated 2 comment(s)" in report
    assert "thread=PRRT_1" in report
    assert "merge ready: no" in report


def test_watch_pr_waits_for_threads_to_catch_up_with_comment_overview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Newly generated comments are reported even when the thread list lags behind."""
    thread = pr_review.ReviewThread(
        "PRRT_1",
        "open",
        "file.py",
        12,
        "copilot-pull-request-reviewer",
        "Fix this issue.",
        "url",
    )
    _, sleeps = _watch_stubs(
        monkeypatch,
        [
            _status(settled=True, review=_parsed_review(count=1)),
            _status(settled=True, review=_parsed_review(count=1)),
        ],
        thread_batches=[[], [thread]],
    )

    report = pr_watch.watch_pr(
        12,
        interval=1,
        max_polls=3,
        request_copilot=True,
        sleep_fn=sleeps.append,
    )

    # First sleep is the short stability confirmation, second waits for threads.
    assert sleeps == [1, 1]
    assert "thread=PRRT_1" in report


def test_watch_pr_counts_only_threads_newer_than_the_request_baseline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Older open threads cannot satisfy a fresh review's comment count."""
    old_thread = pr_review.ReviewThread("PRRT_old", "open", "old.py", 1, "copilot", "old", "url")
    new_thread = pr_review.ReviewThread("PRRT_new", "open", "new.py", 2, "copilot", "new", "url")
    second_new_thread = pr_review.ReviewThread(
        "PRRT_new_2", "open", "newer.py", 3, "copilot", "newer", "url"
    )
    sequence = iter(
        [
            _status(settled=True, review=_parsed_review(count=2)),
            _status(settled=True, review=_parsed_review(count=2)),
            _status(settled=True, review=_parsed_review(count=2)),
        ]
    )
    thread_batches = iter(
        [
            [old_thread, new_thread],
            [old_thread, new_thread, second_new_thread],
        ]
    )
    sleeps: list[float] = []
    monkeypatch.setattr(
        pr_watch,
        "watch_baseline",
        lambda *_args, **_kwargs: pr_watch.WatchBaseline(
            frozenset({"old-review"}),
            frozenset({"PRRT_old"}),
        ),
    )
    monkeypatch.setattr(
        pr_review,
        "request_copilot_review",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        pr_watch,
        "poll_once",
        lambda *_args, **_kwargs: next(sequence),
    )
    monkeypatch.setattr(
        pr_review,
        "list_threads",
        lambda *_args, **_kwargs: next(thread_batches),
    )

    report = pr_watch.watch_pr(
        12,
        interval=1,
        max_polls=3,
        request_copilot=True,
        sleep_fn=sleeps.append,
    )

    # First sleep confirms rollup stability, second waits for the later thread.
    assert sleeps == [1, 1]
    assert "open review threads: 3" in report


def _thread(
    thread_id: str, anchor: str, *, state: str = "open", author: str = ""
) -> pr_review.ReviewThread:
    """Build one review thread whose URL ends in the given discussion anchor."""
    return pr_review.ReviewThread(
        thread_id,
        state,
        "file.py",
        1,
        author or "copilot-pull-request-reviewer",
        "body",
        f"https://github.com/o/r/pull/12#{anchor}",
    )


def _v2_review() -> pr_watch.CopilotReview:
    """Build a fresh v2 review that links discussion_r101 and discussion_r102."""
    return pr_watch.CopilotReview(
        "new",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        _V2_COMMENT_BODY,
        pr_watch._generated_comment_count(_V2_COMMENT_BODY),
    )


def test_v2_overview_lists_only_its_open_discussions() -> None:
    """Links in the resolved section are not threads the review waits for."""
    assert _v2_review().open_discussions == {"discussion_r101", "discussion_r102"}


def test_watch_pr_waits_for_every_thread_a_v2_overview_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unrelated human thread cannot stand in for a linked Copilot thread."""
    human = _thread("PRRT_human", "discussion_r50", author="a-reviewer")
    carried_over = _thread("PRRT_old", "discussion_r102")
    new = _thread("PRRT_new", "discussion_r101")
    _, sleeps = _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_v2_review())],
        thread_batches=[[human, carried_over], [human, carried_over, new]],
    )

    report = pr_watch.watch_pr(
        12, interval=1, max_polls=3, request_copilot=True, sleep_fn=sleeps.append
    )

    # First sleep confirms rollup stability, second waits for discussion_r101.
    assert sleeps == [1, 1]
    assert "generated 2 comment(s)" in report
    assert "open review threads: 3" in report


def test_watch_pr_accepts_a_linked_thread_resolved_before_the_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A linked thread still matches after it is resolved, whatever the baseline holds."""
    resolved = _thread("PRRT_old", "discussion_r102", state="resolved")
    new = _thread("PRRT_new", "discussion_r101")
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_v2_review())],
        thread_batches=[[resolved, new]],
    )
    monkeypatch.setattr(
        pr_watch,
        "watch_baseline",
        lambda *_args, **_kwargs: pr_watch.WatchBaseline(
            frozenset({"old-review"}), frozenset({"PRRT_old"})
        ),
    )

    report = pr_watch.watch_pr(12, interval=0, max_polls=2, request_copilot=True)

    assert "settled after 2 poll(s)" in report
    assert "open review threads: 1" in report


def test_watch_pr_v2_review_without_approval_is_not_merge_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A "Needs a closer look" review with no threads still blocks merge."""
    review = pr_watch.CopilotReview(
        "new",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        _V2_CLOSER_LOOK_BODY,
        pr_watch._generated_comment_count(_V2_CLOSER_LOOK_BODY),
    )
    _watch_stubs(monkeypatch, [_status(settled=True, review=review)])

    report = pr_watch.watch_pr(12, interval=0, max_polls=2)

    assert "latest Copilot review: needs a closer look with no open threads" in report
    assert "merge ready: no" in report


def test_watch_pr_rejects_an_unclassified_v2_review_without_waiting_for_its_links(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A link that never gets a thread cannot turn a classification error into a timeout."""
    body = _V2_COMMENT_BODY.replace("- [Update the ADR](#discussion_r102)\n", "")
    review = pr_watch.CopilotReview(
        "new",
        datetime(2026, 7, 26, 12, tzinfo=UTC),
        body,
        pr_watch._generated_comment_count(body),
    )
    _watch_stubs(monkeypatch, [_status(settled=True, review=review)])

    with pytest.raises(GhError, match="could not be classified"):
        pr_watch.watch_pr(12, interval=0, max_polls=3)


def test_watch_pr_clean_review_with_older_open_thread_is_not_merge_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean latest overview does not override an unresolved older thread."""
    thread = pr_review.ReviewThread("PRRT_1", "open", "f", 1, "copilot", "body", "url")
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_parsed_review())],
        thread_batches=[[thread]],
    )

    report = pr_watch.watch_pr(12, interval=0, max_polls=2)

    assert "latest Copilot review: generated no comments" in report
    assert "open review threads: 1" in report
    assert "merge ready: no" in report


def test_watch_pr_counts_resolved_fresh_threads_but_reports_only_open_threads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A quickly resolved fresh comment cannot leave the watcher polling."""
    resolved = pr_review.ReviewThread(
        "PRRT_new",
        "resolved",
        "f",
        1,
        "copilot",
        "body",
        "url",
    )
    calls: list[dict[str, object]] = []
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_parsed_review(count=1))],
        thread_batches=[[resolved]],
    )
    original = pr_review.list_threads
    monkeypatch.setattr(
        pr_review,
        "list_threads",
        lambda *_args, **kwargs: calls.append(kwargs) or original(),
    )

    report = pr_watch.watch_pr(12, interval=0, max_polls=2)

    assert calls == [{"include_resolved": True, "run_fn": None}]
    assert "open review threads: 0" in report
    assert "thread=PRRT_new" not in report
    assert "merge ready: no" in report


def test_watch_pr_fails_immediately_for_settled_failed_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A terminal check failure cannot be reported as a settled success."""
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, successful=False, tally="1 failure, 14 success")],
    )

    with pytest.raises(GhError, match="checks settled unsuccessfully"):
        pr_watch.watch_pr(12, interval=0, max_polls=2)


def test_watch_pr_rejects_unrecognized_fresh_overview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown Copilot wording blocks merge rather than guessing clean state."""
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_parsed_review(count=None))],
    )

    # The message names both targets: pr-comments lists conversation comments,
    # and pr-review-comments lists review threads.
    with pytest.raises(
        GhError, match=r"could not be classified.*make pr-comments.*make pr-review-comments"
    ):
        pr_watch.watch_pr(12, interval=0, max_polls=2)


def test_watch_pr_checks_only_skips_review_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Checks-only mode waits for checks without mutating reviewer state."""
    requested, _ = _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=None)],
    )
    monkeypatch.setattr(
        pr_watch,
        "watch_baseline",
        lambda *_args, **_kwargs: pytest.fail("checks-only should skip the review baseline"),
    )

    report = pr_watch.watch_pr(
        12,
        interval=0,
        max_polls=2,
        checks_only=True,
        request_copilot=True,
    )

    assert requested == []
    assert "latest Copilot review: not requested" in report
    assert "merge ready: no" in report


def test_watch_pr_waits_for_auto_requested_review_without_mutating_reviewers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default watcher observes an automatic review without requesting another."""
    requested, _ = _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_parsed_review())],
    )
    monkeypatch.setattr(
        pr_watch,
        "watch_baseline",
        lambda *_args, **_kwargs: pytest.fail(
            "observation mode should not capture a request baseline"
        ),
    )

    report = pr_watch.watch_pr(12, interval=0, max_polls=2)

    assert requested == []
    assert "latest Copilot review: generated no comments" in report


def test_watch_pr_defaults_current_pr_and_sleep(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Omitted collaborators use current PR detection and time.sleep."""
    monkeypatch.setattr(gh_runner, "current_pr_number", lambda **_kwargs: 12)
    _watch_stubs(
        monkeypatch,
        [
            _status(settled=False),
            _status(settled=True, review=_parsed_review()),
        ],
    )
    sleeps: list[float] = []
    monkeypatch.setattr(pr_watch.time, "sleep", sleeps.append)

    pr_watch.watch_pr(interval=3, max_polls=3)

    assert sleeps == [3, 3]


def test_watch_pr_uses_the_conservative_default_check_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct watcher callers use the same check floor as the CLI."""
    captured: list[int] = []
    monkeypatch.setattr(
        pr_watch,
        "watch_baseline",
        lambda *_args, **_kwargs: pr_watch.WatchBaseline(frozenset(), frozenset()),
    )
    monkeypatch.setattr(pr_review, "request_copilot_review", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        pr_watch,
        "poll_once",
        lambda *_args, **kwargs: (
            captured.append(kwargs["expected_checks"])
            or _status(settled=True, review=_parsed_review())
        ),
    )
    monkeypatch.setattr(pr_review, "list_threads", lambda *_args, **_kwargs: [])

    pr_watch.watch_pr(12, interval=0, max_polls=2)

    assert captured == [pr_watch.DEFAULT_EXPECTED_CHECKS] * 2


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"interval": -1}, "interval must not be negative"),
        ({"max_polls": 0}, "max_polls must be at least 1"),
        ({"expected_checks": 0}, "expected_checks must be at least 1"),
    ],
)
def test_watch_pr_rejects_invalid_limits(
    kwargs: dict[str, object],
    message: str,
) -> None:
    """Invalid polling limits fail before any GitHub calls."""
    with pytest.raises(GhError, match=message):
        pr_watch.watch_pr(12, **kwargs)


def test_watch_pr_timeout_reports_bounded_current_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeouts summarize the final state without dumping full API payloads."""
    _, sleeps = _watch_stubs(
        monkeypatch,
        [
            _status(settled=False, tally="2 pending, 13 success"),
            _status(settled=True, review=None),
        ],
    )

    with pytest.raises(
        GhError,
        match=r"15 total.*latest Copilot review: no new review yet",
    ):
        pr_watch.watch_pr(
            12,
            interval=1,
            max_polls=2,
            sleep_fn=sleeps.append,
        )

    assert sleeps == [1]


def test_watch_cli_forwards_every_option_and_prints_report(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The CLI forwards every watcher control to watch_pr."""
    captured: dict[str, object] = {}

    def _watch(pr: int | None, **kwargs: object) -> str:
        captured["pr"] = pr
        captured.update(kwargs)
        return "compact watch report"

    monkeypatch.setattr(pr_watch, "watch_pr", _watch)

    exit_code = cli.main(
        [
            "watch",
            "--pr",
            "9",
            "--interval",
            "2.5",
            "--max-polls",
            "3",
            "--expected-checks",
            "17",
            "--checks-only",
            "--request-copilot",
        ]
    )

    assert exit_code == 0
    assert captured == {
        "pr": 9,
        "interval": 2.5,
        "max_polls": 3,
        "expected_checks": 17,
        "checks_only": True,
        "request_copilot": True,
    }
    assert capsys.readouterr().out.strip() == "compact watch report"


def test_watch_cli_uses_conservative_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI defaults match the watcher's expected-check count and polling limits."""
    captured: dict[str, object] = {}

    def _watch(pr: int | None, **kwargs: object) -> str:
        captured["pr"] = pr
        captured.update(kwargs)
        return "report"

    monkeypatch.setattr(pr_watch, "watch_pr", _watch)

    assert cli.main(["watch"]) == 0
    assert captured == {
        "pr": None,
        "interval": 45.0,
        "max_polls": 40,
        "expected_checks": pr_watch.DEFAULT_EXPECTED_CHECKS,
        "checks_only": False,
        "request_copilot": False,
    }


def test_review_payload_falls_back_to_rest_with_the_same_shape() -> None:
    """A blocked ``gh pr view`` is rebuilt from REST checks and reviews."""
    runner = FakeGh(
        [
            *sandbox_routes(),
            (rest("GET", "repos/o/r/pulls/7"), json_response({"head": {"sha": "abc"}})),
            (
                rest("GET", "repos/o/r/commits/abc/check-runs"),
                json_response(
                    {
                        "check_runs": [
                            {"name": "lint", "status": "completed", "conclusion": "success"}
                        ]
                    }
                ),
            ),
            (rest("GET", "repos/o/r/commits/abc/status"), json_response({"statuses": []})),
            (
                rest("GET", "repos/o/r/pulls/7/reviews"),
                json_response(
                    [
                        {
                            "node_id": "PRR_1",
                            "user": {"login": "copilot-pull-request-reviewer[bot]"},
                            "submitted_at": "2026-01-01T00:00:00Z",
                            "body": _CLEAN_BODY,
                            "state": "COMMENTED",
                        }
                    ]
                ),
            ),
        ]
    )

    status = pr_watch.poll_once(7, frozenset(), run_fn=runner)

    assert status.checks_settled
    assert status.checks_successful
    assert status.fresh_review is not None
    assert status.fresh_review.review_id == "PRR_1"
    assert status.fresh_review.is_explicitly_clean
