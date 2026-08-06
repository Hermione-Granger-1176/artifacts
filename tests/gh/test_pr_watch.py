from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from scripts.gh import cli, gh_runner, pr_review, pr_watch
from scripts.gh.gh_runner import GhError
from tests.gh.gh_test_support import FakeGh, completed_process, has

_CLEAN_BODY = "Copilot reviewed 8 files and generated no new comments."
_COMMENT_BODY = "Copilot reviewed 8 files and generated 2 comments."
_SUBMITTED_AT = "2026-07-26T12:00:00Z"


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
    ],
)
def test_generated_comment_count_classifies_overviews(body: str, expected: int | None) -> None:
    """Recognize clean and actionable Copilot overview forms."""
    assert pr_watch._generated_comment_count(body) == expected


def test_review_summary_distinguishes_absent_from_unrequested_reviews() -> None:
    """A requested review that never arrived is not reported as unrequested."""
    assert pr_watch._review_summary(None, requested=True) == "no new review yet"
    assert pr_watch._review_summary(None, requested=False) == "not requested"


def test_parse_timestamp_compares_as_instant_and_requires_timezone() -> None:
    """Timestamps compare as instants and cannot be timezone-naive.

    The parser preserves each payload's original offset rather than converting
    to UTC. Aware datetimes already compare and order by instant, which is all
    the watcher needs to pick the latest review.
    """
    parsed = pr_watch._parse_timestamp("2026-07-26T14:00:00+02:00", "review")

    assert parsed == datetime(2026, 7, 26, 12, tzinfo=UTC)
    # GitHub stamps reviews with a trailing Z, which is valid ISO-8601 input
    # for every Python this project supports (requires-python >= 3.12).
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
    """A numeric zero does not replace the required no-comments wording.

    Both the first-review and re-review phrasings count as clean. Copilot drops
    "new" on a first pass, and treating that as unclassifiable stalls the watch
    on exactly the PRs that had nothing wrong with them.
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
    settled, successful, count, _ = pr_watch._check_status(
        [{"state": "SUCCESS"}],
        expected_checks=1,
    )

    assert (settled, successful, count) == (True, True, 1)


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
        pr_watch.watch_pr(12, interval=0, max_polls=1)


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
    settled, successful, _, _ = pr_watch._check_status(
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


def test_check_status_rejects_invalid_expected_count() -> None:
    """The expected check count must enforce at least one check."""
    with pytest.raises(GhError, match="expected_checks must be at least 1"):
        pr_watch._check_status([], expected_checks=0)


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
) -> pr_watch.PollStatus:
    """Build a poll result for watcher control-flow tests."""
    return pr_watch.PollStatus(
        checks_settled=settled,
        checks_successful=successful,
        check_count=15,
        rollup_tally=tally,
        fresh_review=review,
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
    """Stub watcher dependencies and return request and sleep records."""
    sequence = iter(statuses)
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

    report = pr_watch.watch_pr(12, interval=0, max_polls=1)

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
        interval=2.5,
        max_polls=2,
        sleep_fn=sleeps.append,
    )

    assert requested == ["requested"]
    assert sleeps == [2.5]
    assert "settled after 2 poll(s)" in report


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

    report = pr_watch.watch_pr(12, interval=0, max_polls=1)

    assert "generated 2 comment(s)" in report
    assert "thread=PRRT_1" in report
    assert "merge ready: no" in report


def test_watch_pr_waits_for_threads_to_catch_up_with_comment_overview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Thread eventual consistency cannot hide newly generated comments."""
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
        max_polls=2,
        sleep_fn=sleeps.append,
    )

    assert sleeps == [1]
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
        max_polls=2,
        sleep_fn=sleeps.append,
    )

    assert sleeps == [1]
    assert "open review threads: 3" in report


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

    report = pr_watch.watch_pr(12, interval=0, max_polls=1)

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

    report = pr_watch.watch_pr(12, interval=0, max_polls=1)

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
        pr_watch.watch_pr(12, interval=0, max_polls=1)


def test_watch_pr_rejects_unrecognized_fresh_overview(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unknown Copilot wording blocks merge rather than guessing clean state."""
    _watch_stubs(
        monkeypatch,
        [_status(settled=True, review=_parsed_review(count=None))],
    )

    # The remedy must name the review-thread target, since `make pr-comments`
    # shows conversation comments and never surfaces review threads.
    with pytest.raises(GhError, match=r"could not be classified.*make pr-review-comments"):
        pr_watch.watch_pr(12, interval=0, max_polls=1)


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
        max_polls=1,
        checks_only=True,
    )

    assert requested == []
    assert "latest Copilot review: not requested" in report
    assert "merge ready: no" in report


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

    pr_watch.watch_pr(interval=3, max_polls=2)

    assert sleeps == [3]


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
    """The CLI keeps the Make target thin and forwards watcher controls."""
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
        ]
    )

    assert exit_code == 0
    assert captured == {
        "pr": 9,
        "interval": 2.5,
        "max_polls": 3,
        "expected_checks": 17,
        "checks_only": True,
    }
    assert capsys.readouterr().out.strip() == "compact watch report"


def test_watch_cli_uses_conservative_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLI defaults retain the artifacts check-completeness requirement."""
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
    }
