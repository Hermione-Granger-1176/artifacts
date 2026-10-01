"""Cover workflow discovery, enabled-state verdicts, and alert routing."""

from __future__ import annotations

import subprocess

import pytest

from scripts.ci import schedule_watchdog


def test_discover_only_scheduled_yaml_files(tmp_path):
    """New cron workflows are monitored without maintaining a filename table."""
    for name in ("b.yml", "a.yaml"):
        (tmp_path / name).write_text("on:\n  schedule:\n    - cron: '0 7 * * *'\n")
    (tmp_path / "manual.yml").write_text("on:\n  workflow_dispatch:\n")
    (tmp_path / "comment.yml").write_text("# - cron: '0 7 * * *'\n")
    (tmp_path / "readme.md").write_text("  - cron: '0 7 * * *'\n")
    (tmp_path / "directory.yml").mkdir()
    assert schedule_watchdog.scheduled_workflow_files(tmp_path) == ("a.yaml", "b.yml")


@pytest.mark.parametrize("payload", [None, [], {}, {"state": None}, {"state": ""}, {"state": 1}])
def test_unreadable_metadata_is_check_failure(payload):
    """Unreadable metadata cannot produce a healthy verdict."""
    with pytest.raises(RuntimeError, match="metadata"):
        schedule_watchdog.fetch_workflow_state(
            "owner/name", "smoke.yml", run_gh_api_json_fn=lambda *_args, **_kwargs: payload
        )


@pytest.mark.parametrize(
    "state", ["active", "disabled_inactivity", "disabled_manually", "disabled_fork"]
)
def test_only_enabled_state_matters(state):
    """The check never requests run history, even when timestamps look old."""
    calls = []

    def respond(endpoint, *, description, required_permission):
        assert description
        assert required_permission == "actions: read"
        calls.append(endpoint)
        return {"state": state, "created_at": "2000-01-01T00:00:00Z"}

    problems = schedule_watchdog.check_scheduled_workflows(
        repo="owner/name", workflows=("smoke.yml",), run_gh_api_json_fn=respond
    )
    assert calls == ["repos/owner/name/actions/workflows/smoke.yml"]
    if state == "active":
        assert problems == []
    else:
        assert len(problems) == 1
        assert "smoke.yml" in problems[0]
        assert state in problems[0]


def test_default_discovery_and_sorted_checks(monkeypatch):
    """Discover schedules by default and check each in stable order."""
    monkeypatch.setattr(schedule_watchdog, "scheduled_workflow_files", lambda: ("b.yml", "a.yml"))
    calls = []

    def respond(endpoint, **_kwargs):
        calls.append(endpoint)
        return {"state": "active"}

    assert (
        schedule_watchdog.check_scheduled_workflows(repo="owner/name", run_gh_api_json_fn=respond)
        == []
    )
    assert calls == [
        "repos/owner/name/actions/workflows/a.yml",
        "repos/owner/name/actions/workflows/b.yml",
    ]
    assert schedule_watchdog.check_scheduled_workflows(repo="owner/name", workflows=()) == []


@pytest.mark.parametrize("env", [{}, {"GITHUB_OUTPUT": ""}])
def test_checked_output_optional(env):
    """Local runs do not require an Actions output file."""
    schedule_watchdog.report_checked(True, env=env)


def test_checked_output_appends(tmp_path, monkeypatch):
    """Preserve other step outputs while recording the verdict."""
    output = tmp_path / "output"
    output.write_text("previous=value\n")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    schedule_watchdog.report_checked(True)
    schedule_watchdog.report_checked(False)
    assert output.read_text() == "previous=value\nchecked=true\nchecked=false\n"


@pytest.mark.parametrize("problems, expected", [([], 0), (["smoke.yml: disabled_manually"], 1)])
def test_cli_verdict(monkeypatch, tmp_path, capsys, problems, expected):
    """Healthy and disabled states both report a completed check."""
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def check(*, repo):
        assert repo == "owner/name"
        return problems

    monkeypatch.setattr(schedule_watchdog, "check_scheduled_workflows", check)
    assert schedule_watchdog.main(["--repo", "owner/name"]) == expected
    assert output.read_text() == "checked=true\n"
    stdout = capsys.readouterr().out
    assert ("All scheduled workflows are active" if not problems else problems[0]) in stdout


@pytest.mark.parametrize(
    "error", [RuntimeError("API unavailable"), ValueError("bad JSON"), OSError("unreadable YAML")]
)
def test_cli_failure_does_not_report_disabled_workflow(monkeypatch, tmp_path, capsys, error):
    """API and filesystem failures route to setup alerts."""
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))

    def check(**_kwargs):
        raise error

    monkeypatch.setattr(schedule_watchdog, "check_scheduled_workflows", check)
    assert schedule_watchdog.main(["--repo", "owner/name"]) == 2
    assert output.read_text() == "checked=false\n"
    assert str(error) in capsys.readouterr().err


@pytest.mark.parametrize("exit_code, checked", [(1, "true"), (2, "false")])
def test_make_preserves_checked_when_it_collapses_exit_codes(tmp_path, exit_code, checked):
    """Alert routing uses checked because Make returns 2 for both failures."""
    output = tmp_path / "output"
    makefile = tmp_path / "Makefile"
    makefile.write_text(f"check:\n\t@echo checked={checked} >> {output}\n\t@exit {exit_code}\n")
    result = subprocess.run(
        ["make", "-f", str(makefile), "check"], capture_output=True, check=False
    )
    assert result.returncode == 2
    assert output.read_text() == f"checked={checked}\n"
