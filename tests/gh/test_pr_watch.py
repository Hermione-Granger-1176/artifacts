from __future__ import annotations

import json

import pytest

from scripts.gh import gh_runner, pr_review, pr_watch
from scripts.gh.gh_runner import GhError
from tests.gh.gh_test_support import FakeGh, completed_process, has

_SINCE = "2026-07-10T12:00:00Z"


def _view_payload(*, rollup: list[object], reviews: list[object]) -> str:
    """Render a PR view payload for one poll."""
    return json.dumps({"statusCheckRollup": rollup, "reviews": reviews})


def _poll_runner(*, rollup: list[object], reviews: list[object]) -> FakeGh:
    """Build a runner that returns one PR poll payload."""
    return FakeGh(
        [(has("pr", "view"), completed_process(0, _view_payload(rollup=rollup, reviews=reviews)))]
    )


def test_default_since_returns_last_commit_date() -> None:
    """default_since reads the last commit rather than the first commit."""
    runner = FakeGh(
        [
            (
                has("pr", "view"),
                completed_process(
                    0,
                    json.dumps(
                        {
                            "commits": [
                                {"committedDate": "2026-07-10T10:00:00Z"},
                                {"committedDate": _SINCE},
                            ]
                        }
                    ),
                ),
            )
        ]
    )

    assert pr_watch.default_since(12, run_fn=runner) == _SINCE
    assert runner.calls[0] == ["gh", "pr", "view", "12", "--json", "commits"]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"commits": []},
        {"commits": ["not a commit"]},
        {"commits": [{}]},
        {"commits": [{"committedDate": 1}]},
        {"commits": [{"committedDate": ""}]},
    ],
)
def test_default_since_rejects_malformed_payload(payload: object) -> None:
    """default_since reports every malformed commits payload as a GhError."""
    runner = FakeGh([(has("pr", "view"), completed_process(0, json.dumps(payload)))])

    with pytest.raises(GhError):
        pr_watch.default_since(12, run_fn=runner)


def test_poll_once_summarizes_mixed_settled_entries_and_fresh_reviews() -> None:
    """Completed check runs and terminal status contexts settle a mixed rollup."""
    runner = _poll_runner(
        rollup=[
            {"status": "COMPLETED", "conclusion": "SUCCESS"},
            {"state": "SUCCESS"},
        ],
        reviews=[
            {
                "author": {"login": "copilot-pull-request-reviewer"},
                "submittedAt": "2026-07-10T12:00:01Z",
            },
            {
                "author": {"login": "copilot-pull-request-reviewer"},
                "submittedAt": _SINCE,
            },
            {"author": {"login": "someone"}, "submittedAt": "2026-07-10T12:00:02Z"},
        ],
    )

    status = pr_watch.poll_once(12, _SINCE, run_fn=runner)

    assert status == pr_watch.PollStatus(True, "2 success", 1)


@pytest.mark.parametrize(
    "rollup",
    [
        [],
        [{"status": "IN_PROGRESS", "conclusion": None}],
        [{"state": "PENDING"}],
        [{"state": "EXPECTED"}],
    ],
)
def test_poll_once_keeps_empty_and_pending_rollups_unsettled(rollup: list[object]) -> None:
    """No checks, running checks, and pending contexts do not settle a PR."""
    status = pr_watch.poll_once(12, _SINCE, run_fn=_poll_runner(rollup=rollup, reviews=[]))

    assert not status.checks_settled


def test_poll_once_checks_only_still_counts_a_fresh_copilot_review() -> None:
    """checks_only keeps the poll report informative while watch skips its requirement."""
    status = pr_watch.poll_once(
        12,
        _SINCE,
        checks_only=True,
        run_fn=_poll_runner(
            rollup=[{"status": "COMPLETED", "conclusion": "SUCCESS"}],
            reviews=[
                {
                    "author": {"login": "copilot-pull-request-reviewer"},
                    "submittedAt": "2026-07-10T12:00:01Z",
                }
            ],
        ),
    )

    assert status.new_review_count == 1


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"statusCheckRollup": {}},
        {"statusCheckRollup": [], "reviews": {}},
    ],
)
def test_poll_once_rejects_malformed_payload(payload: object) -> None:
    """poll_once rejects malformed PR view payload containers."""
    runner = FakeGh([(has("pr", "view"), completed_process(0, json.dumps(payload)))])

    with pytest.raises(GhError):
        pr_watch.poll_once(12, _SINCE, run_fn=runner)


@pytest.mark.parametrize(
    "reviews",
    [
        ["not a review"],
        [{"author": "not an author"}],
    ],
)
def test_poll_once_rejects_malformed_review_entries(reviews: list[object]) -> None:
    """poll_once surfaces malformed review entries rather than guessing."""
    with pytest.raises(GhError):
        pr_watch.poll_once(
            12,
            _SINCE,
            run_fn=_poll_runner(
                rollup=[{"status": "COMPLETED", "conclusion": "SUCCESS"}], reviews=reviews
            ),
        )


def test_poll_once_checks_only_ignores_malformed_review_entries() -> None:
    """checks_only does not let review data block a checks-only wait."""
    status = pr_watch.poll_once(
        12,
        _SINCE,
        checks_only=True,
        run_fn=_poll_runner(
            rollup=[{"status": "COMPLETED", "conclusion": "SUCCESS"}],
            reviews=["not a review"],
        ),
    )

    assert status == pr_watch.PollStatus(True, "1 success", 0)


def test_poll_once_checks_only_tolerates_a_non_list_reviews_field() -> None:
    """checks_only treats a malformed reviews container as no reviews."""
    payload = json.dumps(
        {"statusCheckRollup": [{"status": "COMPLETED", "conclusion": "SUCCESS"}], "reviews": {}}
    )
    runner = FakeGh([(has("pr", "view"), completed_process(0, payload))])

    status = pr_watch.poll_once(12, _SINCE, checks_only=True, run_fn=runner)

    assert status == pr_watch.PollStatus(True, "1 success", 0)


def test_poll_once_compares_timestamps_chronologically_across_timezones() -> None:
    """An offset since timestamp is compared by instant, not by string order."""
    status = pr_watch.poll_once(
        12,
        "2026-07-10T14:00:00+02:00",
        run_fn=_poll_runner(
            rollup=[{"status": "COMPLETED", "conclusion": "SUCCESS"}],
            reviews=[
                {
                    "author": {"login": "copilot-pull-request-reviewer"},
                    "submittedAt": "2026-07-10T12:30:00Z",
                }
            ],
        ),
    )

    assert status.new_review_count == 1


@pytest.mark.parametrize("since", ["not a timestamp", "2026-07-10T12:00:00"])
def test_poll_once_rejects_invalid_and_naive_since_timestamps(since: str) -> None:
    """Unparseable and timezone-naive since values are reported as GhErrors."""
    with pytest.raises(GhError):
        pr_watch.poll_once(
            12,
            since,
            run_fn=_poll_runner(
                rollup=[{"status": "COMPLETED", "conclusion": "SUCCESS"}], reviews=[]
            ),
        )


def test_poll_once_rejects_an_unparseable_copilot_submission_time() -> None:
    """A Copilot review with a garbled submittedAt string is surfaced, not guessed."""
    with pytest.raises(GhError):
        pr_watch.poll_once(
            12,
            _SINCE,
            run_fn=_poll_runner(
                rollup=[{"status": "COMPLETED", "conclusion": "SUCCESS"}],
                reviews=[
                    {
                        "author": {"login": "copilot-pull-request-reviewer"},
                        "submittedAt": "yesterday",
                    }
                ],
            ),
        )


def test_poll_once_ignores_null_author_and_non_string_submission_time() -> None:
    """Incomplete non-Copilot review data does not count as a fresh review."""
    status = pr_watch.poll_once(
        12,
        _SINCE,
        run_fn=_poll_runner(
            rollup=[{"state": "FAILURE"}],
            reviews=[
                {"author": None, "submittedAt": "2026-07-10T12:00:01Z"},
                {"author": {"login": "copilot-pull-request-reviewer"}, "submittedAt": None},
            ],
        ),
    )

    assert status.new_review_count == 0


def _status(*, settled: bool, reviews: int, tally: str = "1 success") -> pr_watch.PollStatus:
    """Build a poll status for watch_pr unit tests."""
    return pr_watch.PollStatus(settled, tally, reviews)


def _watch_stubs(
    monkeypatch: pytest.MonkeyPatch,
    statuses: list[pr_watch.PollStatus],
) -> list[tuple[int, str, bool, object]]:
    """Stub poll_once and thread rendering while recording their input."""
    calls: list[tuple[int, str, bool, object]] = []
    sequence = iter(statuses)

    def poll(
        pr: int,
        since: str,
        *,
        checks_only: bool,
        run_fn: object,
    ) -> pr_watch.PollStatus:
        """Return the next canned poll status."""
        calls.append((pr, since, checks_only, run_fn))
        return next(sequence)

    monkeypatch.setattr(pr_watch, "poll_once", poll)
    monkeypatch.setattr(pr_review, "list_threads", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(pr_review, "format_threads", lambda threads: f"threads={len(threads)}")
    return calls


def test_watch_pr_returns_report_after_immediate_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """watch_pr immediately reports a PR whose checks and review are ready."""
    calls = _watch_stubs(monkeypatch, [_status(settled=True, reviews=1)])
    runner = FakeGh([])

    report = pr_watch.watch_pr(12, _SINCE, run_fn=runner)

    assert report == (
        "PR #12 settled after 1 poll(s)\n"
        "checks: 1 success\n"
        f"new Copilot reviews since {_SINCE}: 1\n\nthreads=0"
    )
    assert calls == [(12, _SINCE, False, runner)]


def test_watch_pr_sleeps_between_polls_and_forwards_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_pr retries incomplete polls and never sleeps after the final success."""
    _watch_stubs(
        monkeypatch,
        [_status(settled=False, reviews=0, tally="1 pending"), _status(settled=True, reviews=1)],
    )
    sleeps: list[float] = []

    report = pr_watch.watch_pr(12, _SINCE, interval=3.5, sleep_fn=sleeps.append)

    assert "after 2 poll(s)" in report
    assert sleeps == [3.5]


def test_watch_pr_checks_only_skips_the_review_requirement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_pr exits for settled checks when checks_only is requested."""
    calls = _watch_stubs(monkeypatch, [_status(settled=True, reviews=0)])

    report = pr_watch.watch_pr(12, _SINCE, checks_only=True)

    assert "after 1 poll(s)" in report
    assert calls[0][2] is True


def test_watch_pr_times_out_with_current_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """watch_pr reports its final tally and review count after the poll limit."""
    _watch_stubs(
        monkeypatch,
        [_status(settled=False, reviews=0, tally="1 pending"), _status(settled=True, reviews=0)],
    )
    sleeps: list[float] = []

    with pytest.raises(
        GhError,
        match=r"checks: 1 success; new Copilot reviews since 2026-07-10T12:00:00Z: 0",
    ):
        pr_watch.watch_pr(12, _SINCE, interval=2.0, max_polls=2, sleep_fn=sleeps.append)

    assert sleeps == [2.0]


def test_watch_pr_defaults_pr_and_since(monkeypatch: pytest.MonkeyPatch) -> None:
    """watch_pr derives both missing values from the current pull request."""
    monkeypatch.setattr(gh_runner, "current_pr_number", lambda **_kwargs: 12)
    monkeypatch.setattr(pr_watch, "default_since", lambda _pr, **_kwargs: _SINCE)
    calls = _watch_stubs(monkeypatch, [_status(settled=True, reviews=1)])

    pr_watch.watch_pr()

    assert calls[0][:3] == (12, _SINCE, False)


def test_watch_pr_rejects_zero_max_polls() -> None:
    """watch_pr rejects a poll limit that cannot produce a current state."""
    with pytest.raises(GhError, match="max_polls must be at least 1"):
        pr_watch.watch_pr(max_polls=0)


def test_watch_pr_uses_time_sleep_when_no_sleeper_is_injected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch_pr defaults to time.sleep when callers do not inject a sleeper."""
    _watch_stubs(
        monkeypatch,
        [_status(settled=False, reviews=0), _status(settled=True, reviews=1)],
    )
    sleeps: list[float] = []
    monkeypatch.setattr(pr_watch.time, "sleep", sleeps.append)

    pr_watch.watch_pr(12, _SINCE, interval=4.0)

    assert sleeps == [4.0]
