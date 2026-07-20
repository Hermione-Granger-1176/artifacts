from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from scripts.ci import schedule_watchdog

_NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fake_api(*, states: dict[str, str], last_runs: dict[str, str | None]):
    """Build a run_gh_api_json_fn stub keyed by workflow file in the endpoint."""

    def _call(endpoint: str, *, description: str, required_permission: str | None = None) -> object:
        assert isinstance(description, str)
        assert required_permission == "actions: read"
        workflow_file = endpoint.split("/actions/workflows/")[1].split("/runs")[0].split("?")[0]
        if endpoint.endswith(workflow_file):
            return {"state": states[workflow_file]}
        run_at = last_runs.get(workflow_file)
        if run_at is None:
            return {"workflow_runs": []}
        return {"workflow_runs": [{"created_at": run_at}]}

    return _call


def test_parse_timestamp_variants() -> None:
    """Timestamps parse from Z-suffixed, offset, naive, and invalid inputs."""
    assert schedule_watchdog._parse_timestamp("2026-07-20T00:00:00Z") == datetime(
        2026, 7, 20, tzinfo=UTC
    )
    assert schedule_watchdog._parse_timestamp("2026-07-20T00:00:00+00:00") == datetime(
        2026, 7, 20, tzinfo=UTC
    )
    naive = schedule_watchdog._parse_timestamp("2026-07-20T00:00:00")
    assert naive is not None and naive.tzinfo is UTC
    assert schedule_watchdog._parse_timestamp("not-a-date") is None
    assert schedule_watchdog._parse_timestamp("") is None
    assert schedule_watchdog._parse_timestamp(123) is None


def test_latest_scheduled_run_at_handles_missing_and_malformed() -> None:
    """The newest run timestamp handles empty, non-list, and malformed payloads."""
    assert schedule_watchdog._latest_scheduled_run_at({"workflow_runs": []}) is None
    assert schedule_watchdog._latest_scheduled_run_at({"workflow_runs": "x"}) is None
    assert schedule_watchdog._latest_scheduled_run_at({"workflow_runs": ["x"]}) is None
    assert schedule_watchdog._latest_scheduled_run_at(
        {"workflow_runs": [{"created_at": "2026-07-20T00:00:00Z"}]}
    ) == datetime(2026, 7, 20, tzinfo=UTC)
    with pytest.raises(RuntimeError):
        schedule_watchdog._latest_scheduled_run_at(["not", "a", "dict"])


def test_fetch_workflow_recency_requires_string_state() -> None:
    """A workflow whose metadata lacks a string state is rejected."""

    def _call(endpoint: str, *, description: str, required_permission: str | None = None) -> object:
        assert isinstance(description, str)
        assert required_permission == "actions: read"
        return {"state": 123} if endpoint.endswith("update.yml") else {"workflow_runs": []}

    with pytest.raises(RuntimeError, match="missing a string state"):
        schedule_watchdog.fetch_workflow_recency("o/r", "update.yml", run_gh_api_json_fn=_call)


def test_evaluate_recency_flags_disabled_state() -> None:
    """A non-active workflow state is reported as a disabled-schedule problem."""
    recency = schedule_watchdog.WorkflowRecency("codeql.yml", "disabled_inactivity", None)
    problem = schedule_watchdog.evaluate_recency(recency, 7 * 86400, now=_NOW)
    assert problem is not None and "disabled_inactivity" in problem


def test_evaluate_recency_allows_recent_and_absent_runs() -> None:
    """A recent run and an active-but-never-run workflow are both healthy."""
    recent = schedule_watchdog.WorkflowRecency(
        "live-site-smoke.yml", "active", _NOW - timedelta(hours=6)
    )
    assert schedule_watchdog.evaluate_recency(recent, 86400, now=_NOW) is None
    never_ran = schedule_watchdog.WorkflowRecency("live-site-smoke.yml", "active", None)
    assert schedule_watchdog.evaluate_recency(never_ran, 86400, now=_NOW) is None


def test_evaluate_recency_flags_stale_run() -> None:
    """A run older than cadence plus grace is reported as stale."""
    stale = schedule_watchdog.WorkflowRecency(
        "live-site-smoke.yml", "active", _NOW - timedelta(days=10)
    )
    problem = schedule_watchdog.evaluate_recency(stale, 86400, now=_NOW)
    assert problem is not None and "days ago" in problem


def test_check_scheduled_workflows_reports_only_problem_workflows() -> None:
    """The aggregate check returns one entry per stale or disabled workflow."""
    cadences = {"live-site-smoke.yml": 86400, "codeql.yml": 7 * 86400}
    api = _fake_api(
        states={"live-site-smoke.yml": "active", "codeql.yml": "disabled_inactivity"},
        last_runs={"live-site-smoke.yml": _iso(_NOW - timedelta(hours=1)), "codeql.yml": None},
    )
    problems = schedule_watchdog.check_scheduled_workflows(
        repo="o/r", now=_NOW, cadences=cadences, run_gh_api_json_fn=api
    )
    assert len(problems) == 1
    assert problems[0].startswith("codeql.yml")


def test_check_scheduled_workflows_defaults_now() -> None:
    """When now is omitted the current UTC time is used."""
    cadences = {"live-site-smoke.yml": 86400}
    api = _fake_api(
        states={"live-site-smoke.yml": "active"},
        last_runs={"live-site-smoke.yml": _iso(datetime.now(UTC))},
    )
    problems = schedule_watchdog.check_scheduled_workflows(
        repo="o/r", cadences=cadences, run_gh_api_json_fn=api
    )
    assert problems == []


def test_main_reports_healthy(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean run prints the healthy message and exits 0."""
    monkeypatch.setattr(schedule_watchdog, "check_scheduled_workflows", lambda **_kwargs: [])
    assert schedule_watchdog.main(["--repo", "o/r"]) == 0
    assert "active and recent" in capsys.readouterr().out


def test_main_reports_problems(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Problems are printed as a bullet list and the CLI exits 1."""
    monkeypatch.setattr(
        schedule_watchdog, "check_scheduled_workflows", lambda **_kwargs: ["codeql.yml: bad"]
    )
    assert schedule_watchdog.main(["--repo", "o/r"]) == 1
    assert "codeql.yml: bad" in capsys.readouterr().out
