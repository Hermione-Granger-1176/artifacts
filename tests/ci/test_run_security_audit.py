from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.ci.run_security_audit as run_security_audit


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_security_audit_exceptions_reads_valid_config(tmp_path: Path) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(
        config_file,
        """
{
  "python_vulnerability_exceptions": [
    {
      "id": "CVE-2026-4539",
      "package": "pygments",
      "reason": "No patched release yet.",
      "review_by": "2026-04-25",
      "ignore_only_without_fix": true
    },
    {
      "id": "GHSA-5239-wwwm-4pmq",
      "package": "pygments",
      "reason": "Alias reviewed with the primary CVE.",
      "review_by": "2026-04-25"
    }
  ]
}
""".strip(),
    )

    exceptions = run_security_audit._load_security_audit_exceptions(config_file)

    assert len(exceptions) == 2
    assert exceptions[0].vulnerability_id == "CVE-2026-4539"
    assert exceptions[0].review_by == date(2026, 4, 25)
    assert exceptions[0].ignore_only_without_fix is True
    assert exceptions[0].key == ("pygments", "CVE-2026-4539")
    assert exceptions[1].ignore_only_without_fix is False


def test_load_security_audit_exceptions_rejects_duplicate_entries(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(
        config_file,
        """
{
  "python_vulnerability_exceptions": [
    {
      "id": "CVE-2026-4539",
      "package": "pygments",
      "reason": "No patched release yet.",
      "review_by": "2026-04-25"
    },
    {
      "id": "CVE-2026-4539",
      "package": "Pygments",
      "reason": "Duplicate entry added by mistake.",
      "review_by": "2026-05-25"
    }
  ]
}
""".strip(),
    )

    with pytest.raises(
        ValueError,
        match=r"must not duplicate.*python_vulnerability_exceptions\[1\]",
    ):
        run_security_audit._load_security_audit_exceptions(config_file)


def test_load_security_audit_exceptions_rejects_invalid_review_date(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(
        config_file,
        """
{
  "python_vulnerability_exceptions": [
    {
      "id": "CVE-2026-4539",
      "package": "pygments",
      "reason": "No patched release yet.",
      "review_by": "04-25-2026"
    }
  ]
}
""".strip(),
    )

    with pytest.raises(ValueError, match="review_by"):
        run_security_audit._load_security_audit_exceptions(config_file)


def test_load_security_audit_config_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Security audit config file not found"):
        run_security_audit._load_security_audit_config(tmp_path / "missing.json")


def test_load_security_audit_config_rejects_non_object_root(tmp_path: Path) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(config_file, "[]")

    with pytest.raises(ValueError, match="must be a JSON object"):
        run_security_audit._load_security_audit_config(config_file)


def test_resolve_requirements_file_accepts_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    assert (
        run_security_audit._resolve_requirements_file(
            Path(".artifacts") / "requirements-audit.txt"
        )
        == requirements_file
    )


def test_resolve_requirements_file_accepts_absolute_path(tmp_path: Path) -> None:
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pkg==1.0\n")

    assert run_security_audit._resolve_requirements_file(requirements_file) == (
        requirements_file
    )


def test_resolve_requirements_file_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(
        FileNotFoundError,
        match="Python security requirements file not found",
    ):
        run_security_audit._resolve_requirements_file(tmp_path / "missing.txt")


def test_load_security_audit_exceptions_rejects_invalid_entries_list(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(config_file, '{"python_vulnerability_exceptions": {}}')

    with pytest.raises(ValueError, match="must be a list"):
        run_security_audit._load_security_audit_exceptions(config_file)


def test_load_security_audit_exceptions_rejects_non_object_entry(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(config_file, '{"python_vulnerability_exceptions": ["bad"]}')

    with pytest.raises(ValueError, match="must be objects"):
        run_security_audit._load_security_audit_exceptions(config_file)


def test_load_security_audit_exceptions_rejects_missing_required_fields(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(config_file, '{"python_vulnerability_exceptions": [{"id": "CVE-1"}]}')

    with pytest.raises(ValueError, match="must include"):
        run_security_audit._load_security_audit_exceptions(config_file)


def test_load_security_audit_exceptions_rejects_invalid_ignore_flag(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(
        config_file,
        """
{
  "python_vulnerability_exceptions": [
    {
      "id": "CVE-2026-4539",
      "package": "pygments",
      "reason": "No patched release yet.",
      "review_by": "2026-04-25",
      "ignore_only_without_fix": "yes"
    }
  ]
}
""".strip(),
    )

    with pytest.raises(ValueError, match="must be a boolean"):
        run_security_audit._load_security_audit_exceptions(config_file)


def test_relative_path_returns_repo_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    assert run_security_audit._relative_path(requirements_file) == (
        ".artifacts/requirements-audit.txt"
    )


def test_relative_path_falls_back_to_original_outside_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = tmp_path / "elsewhere" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    assert run_security_audit._relative_path(requirements_file) == str(
        requirements_file
    )


def test_run_pip_audit_parses_valid_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    def _fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        assert args[3:5] == ["--requirement", str(requirements_file)]
        return SimpleNamespace(
            returncode=1,
            stdout=(
                '{"dependencies": [{"name": "pygments", "version": "2.19.2", '
                '"vulns": [{"id": "CVE-2026-4539", '
                '"aliases": ["GHSA-5239-wwwm-4pmq"], '
                '"fix_versions": []}]}]}'
            ),
            stderr="",
        )

    monkeypatch.setattr(run_security_audit.subprocess, "run", _fake_run)

    findings = run_security_audit._run_pip_audit(requirements_file)

    assert findings == (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=("GHSA-5239-wwwm-4pmq",),
            package="pygments",
            version="2.19.2",
            fix_versions=(),
        ),
    )


@pytest.mark.parametrize(
    ("stdout", "stderr", "message"),
    [
        ("", "boom", "boom"),
        ("stdout boom", "", "stdout boom"),
        ("", "", "unknown error"),
    ],
)
def test_run_pip_audit_rejects_subprocess_failures(
    stdout: str,
    stderr: str,
    message: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=2,
            stdout=stdout,
            stderr=stderr,
        ),
    )

    with pytest.raises(RuntimeError, match=message):
        run_security_audit._run_pip_audit(requirements_file)


def test_run_pip_audit_raises_on_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    def _timeout_run(*_args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired(["pip-audit"], kwargs.get("timeout", 120))

    monkeypatch.setattr(run_security_audit.subprocess, "run", _timeout_run)

    with pytest.raises(RuntimeError, match="pip-audit timed out"):
        run_security_audit._run_pip_audit(requirements_file)


def test_run_pip_audit_rejects_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout="not-json",
            stderr="",
        ),
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        run_security_audit._run_pip_audit(requirements_file)


@pytest.mark.parametrize(
    "payload",
    [
        '{"dependencies": {}}',
        '{"dependencies": [1]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": {}}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": [1]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", '
        '"vulns": [{"id": "CVE-1", "aliases": {}}]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", '
        '"vulns": [{"id": "CVE-1", "aliases": [], "fix_versions": {}}]}]}',
    ],
)
def test_run_pip_audit_rejects_invalid_dependency_shape(
    payload: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout=payload,
            stderr="",
        ),
    )

    with pytest.raises(ValueError):
        run_security_audit._run_pip_audit(requirements_file)


def test_audit_python_dependencies_reports_unused_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            reason="No patched release yet.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: ())

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == ("Unused Python vulnerability exception: pygments CVE-2026-4539",)


def test_audit_python_dependencies_allows_reviewed_unfixed_vulnerability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="GHSA-5239-wwwm-4pmq",
            package="PyGments",
            reason="No patched release yet.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
    )
    findings = (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=("GHSA-5239-wwwm-4pmq",),
            package="pygments",
            version="2.19.2",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert len(ignored) == 1
    assert errors == ()


def test_audit_python_dependencies_marks_all_matching_exceptions_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            reason="No patched release yet.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="GHSA-5239-wwwm-4pmq",
            package="pygments",
            reason="Alias entry for the same advisory.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
    )
    findings = (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=("GHSA-5239-wwwm-4pmq",),
            package="pygments",
            version="2.19.2",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert len(ignored) == 1
    assert ignored[0][1] is exceptions[0]
    assert errors == ()


def test_audit_python_dependencies_validates_every_matching_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            reason="No patched release yet.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="GHSA-5239-wwwm-4pmq",
            package="pygments",
            reason="Alias entry for the same advisory.",
            review_by=date(2026, 2, 25),
            ignore_only_without_fix=True,
        ),
    )
    findings = (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=("GHSA-5239-wwwm-4pmq",),
            package="pygments",
            version="2.19.2",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == (
        "Expired Python vulnerability exception: "
        "pygments GHSA-5239-wwwm-4pmq review_by=2026-02-25",
    )


def test_audit_python_dependencies_rejects_exception_when_fix_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            reason="No patched release yet.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
    )
    findings = (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=(),
            package="pygments",
            version="2.19.2",
            fix_versions=("2.19.3",),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == (
        "Python vulnerability exception must be removed because fixes are "
        "available: pygments CVE-2026-4539 fix_versions=2.19.3",
    )


def test_audit_python_dependencies_rejects_expired_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            reason="No patched release yet.",
            review_by=date(2026, 3, 1),
            ignore_only_without_fix=True,
        ),
    )
    findings = (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=(),
            package="pygments",
            version="2.19.2",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == (
        "Expired Python vulnerability exception: pygments CVE-2026-4539 "
        "review_by=2026-03-01",
    )


def test_audit_python_dependencies_rejects_unreviewed_vulnerability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    findings = (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=(),
            package="pygments",
            version="2.19.2",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=(),
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == ("Unreviewed Python vulnerability: pygments 2.19.2 CVE-2026-4539",)


def test_main_reports_success_with_reviewed_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pygments==2.19.2\n")
    exception = run_security_audit.VulnerabilityExceptionEntry(
        vulnerability_id="CVE-2026-4539",
        package="pygments",
        reason="No patched release yet.",
        review_by=date(2026, 4, 25),
        ignore_only_without_fix=True,
    )
    finding = run_security_audit.VulnerabilityFinding(
        vulnerability_id="CVE-2026-4539",
        aliases=(),
        package="pygments",
        version="2.19.2",
        fix_versions=(),
    )
    monkeypatch.setattr(
        run_security_audit,
        "_load_security_audit_exceptions",
        lambda: (exception,),
    )
    monkeypatch.setattr(
        run_security_audit,
        "_audit_python_dependencies",
        lambda *_args, **_kwargs: (((finding, exception),), ()),
    )

    assert run_security_audit.main(["--requirements", str(requirements_file)]) == 0
    output = capsys.readouterr().out
    assert "Reviewed Python vulnerability exceptions:" in output
    assert "- pygments 2.19.2 CVE-2026-4539" in output
    assert "Python dependency audit passed." in output


def test_main_reports_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(
        run_security_audit,
        "_load_security_audit_exceptions",
        lambda: (),
    )
    monkeypatch.setattr(
        run_security_audit,
        "_audit_python_dependencies",
        lambda *_args, **_kwargs: ((), ("boom",)),
    )

    assert run_security_audit.main(["--requirements", str(requirements_file)]) == 1
    output = capsys.readouterr().out
    assert "Python dependency audit failed:" in output
    assert "- boom" in output
