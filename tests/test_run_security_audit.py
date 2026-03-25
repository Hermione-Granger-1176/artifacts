from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

import scripts.run_security_audit as run_security_audit


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_security_audit_exceptions_reads_valid_config(tmp_path: Path) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(
        config_file,
        """
{
  "python_lock_files": ["locks/requirements-dev.lock"],
  "python_vulnerability_exceptions": [
    {
      "id": "CVE-2026-4539",
      "package": "pygments",
      "lock_file": "locks/requirements-dev.lock",
      "reason": "No patched release yet.",
      "review_by": "2026-04-25",
      "ignore_only_without_fix": true
    }
  ]
}
""".strip(),
    )

    exceptions = run_security_audit._load_security_audit_exceptions(config_file)

    assert len(exceptions) == 1
    assert exceptions[0].vulnerability_id == "CVE-2026-4539"
    assert exceptions[0].review_by == date(2026, 4, 25)
    assert exceptions[0].ignore_only_without_fix is True


def test_load_security_audit_exceptions_rejects_invalid_review_date(
    tmp_path: Path,
) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(
        config_file,
        """
{
  "python_lock_files": ["locks/requirements-dev.lock"],
  "python_vulnerability_exceptions": [
    {
      "id": "CVE-2026-4539",
      "package": "pygments",
      "lock_file": "locks/requirements-dev.lock",
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


def test_python_lock_files_reads_configured_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    config_file = repo_root / "config" / "security_audit.json"
    lock_a = repo_root / "locks" / "requirements.lock"
    lock_b = repo_root / "locks" / "requirements-dev.lock"
    write_text(
        config_file,
        """
{
  "python_lock_files": ["locks/requirements.lock", "locks/requirements-dev.lock"],
  "python_vulnerability_exceptions": []
}
""".strip(),
    )
    write_text(lock_a, "pkg==1.0\n")
    write_text(lock_b, "pkg==2.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    lock_files = run_security_audit._python_lock_files(config_file)

    assert lock_files == (lock_a, lock_b)


def test_python_lock_files_falls_back_to_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    config_file = repo_root / "config" / "security_audit.json"
    lock_a = repo_root / "locks" / "requirements.lock"
    lock_b = repo_root / "locks" / "requirements-dev.lock"
    write_text(
        config_file,
        '{"python_lock_files": [], "python_vulnerability_exceptions": []}',
    )
    write_text(lock_a, "pkg==1.0\n")
    write_text(lock_b, "pkg==2.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    assert run_security_audit._python_lock_files(config_file) == (lock_a, lock_b)


def test_python_lock_files_rejects_invalid_config_shape(tmp_path: Path) -> None:
    config_file = tmp_path / "security_audit.json"
    write_text(
        config_file,
        '{"python_lock_files": [1], "python_vulnerability_exceptions": []}',
    )

    with pytest.raises(ValueError, match="python_lock_files"):
        run_security_audit._python_lock_files(config_file)


def test_python_lock_files_rejects_missing_configured_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    config_file = repo_root / "config" / "security_audit.json"
    write_text(
        config_file,
        '{"python_lock_files": ["locks/requirements.lock"], "python_vulnerability_exceptions": []}',
    )
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    with pytest.raises(FileNotFoundError, match="Python security lock file not found"):
        run_security_audit._python_lock_files(config_file)


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
      "lock_file": "locks/requirements-dev.lock",
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
    lock_file = repo_root / "locks" / "requirements.lock"
    write_text(lock_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    assert run_security_audit._relative_path(lock_file) == "locks/requirements.lock"


def test_run_pip_audit_parses_valid_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    lock_file = repo_root / "locks" / "requirements-dev.lock"
    write_text(lock_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout='{"dependencies": [{"name": "pygments", "version": "2.19.2", "vulns": [{"id": "CVE-2026-4539", "aliases": ["GHSA-5239-wwwm-4pmq"], "fix_versions": []}]}]}',
            stderr="",
        ),
    )

    findings = run_security_audit._run_pip_audit(lock_file)

    assert findings == (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=("GHSA-5239-wwwm-4pmq",),
            package="pygments",
            version="2.19.2",
            lock_file="locks/requirements-dev.lock",
            fix_versions=(),
        ),
    )


def test_run_pip_audit_rejects_subprocess_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    lock_file = repo_root / "locks" / "requirements-dev.lock"
    write_text(lock_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=2, stdout="", stderr="boom"),
    )

    with pytest.raises(RuntimeError, match="pip-audit failed"):
        run_security_audit._run_pip_audit(lock_file)


def test_run_pip_audit_rejects_invalid_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    lock_file = repo_root / "locks" / "requirements-dev.lock"
    write_text(lock_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="not-json", stderr=""
        ),
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        run_security_audit._run_pip_audit(lock_file)


@pytest.mark.parametrize(
    "payload",
    [
        '{"dependencies": {}}',
        '{"dependencies": [1]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": {}}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": [1]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": [{"id": "CVE-1", "aliases": {}}]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": [{"id": "CVE-1", "aliases": [], "fix_versions": {}}]}]}',
    ],
)
def test_run_pip_audit_rejects_invalid_dependency_shape(
    payload: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = tmp_path / "repo"
    lock_file = repo_root / "locks" / "requirements-dev.lock"
    write_text(lock_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1,
            stdout=payload,
            stderr="",
        ),
    )

    with pytest.raises(ValueError):
        run_security_audit._run_pip_audit(lock_file)


def test_audit_python_dependencies_reports_unused_exception() -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            lock_file="locks/requirements-dev.lock",
            reason="No patched release yet.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
    )

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        lock_files=(),
    )

    assert ignored == ()
    assert errors == (
        "Unused Python vulnerability exception: locks/requirements-dev.lock pygments CVE-2026-4539",
    )


def test_audit_python_dependencies_allows_reviewed_unfixed_vulnerability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            lock_file="locks/requirements-dev.lock",
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
            lock_file="locks/requirements-dev.lock",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        lock_files=(Path("locks/requirements-dev.lock"),),
    )

    assert len(ignored) == 1
    assert errors == ()


def test_audit_python_dependencies_rejects_exception_when_fix_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            lock_file="locks/requirements-dev.lock",
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
            lock_file="locks/requirements-dev.lock",
            fix_versions=("2.19.3",),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        lock_files=(Path("locks/requirements-dev.lock"),),
    )

    assert ignored == ()
    assert errors == (
        "Python vulnerability exception must be removed because fixes are available: locks/requirements-dev.lock pygments CVE-2026-4539 fix_versions=2.19.3",
    )


def test_audit_python_dependencies_rejects_expired_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            lock_file="locks/requirements-dev.lock",
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
            lock_file="locks/requirements-dev.lock",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        lock_files=(Path("locks/requirements-dev.lock"),),
    )

    assert ignored == ()
    assert errors == (
        "Expired Python vulnerability exception: locks/requirements-dev.lock pygments CVE-2026-4539 review_by=2026-03-01",
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
            lock_file="locks/requirements-dev.lock",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _: findings)

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=(),
        lock_files=(Path("locks/requirements-dev.lock"),),
    )

    assert ignored == ()
    assert errors == (
        "Unreviewed Python vulnerability: locks/requirements-dev.lock pygments 2.19.2 CVE-2026-4539",
    )


def test_main_reports_success_with_reviewed_exceptions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    exception = run_security_audit.VulnerabilityExceptionEntry(
        vulnerability_id="CVE-2026-4539",
        package="pygments",
        lock_file="locks/requirements-dev.lock",
        reason="No patched release yet.",
        review_by=date(2026, 4, 25),
        ignore_only_without_fix=True,
    )
    finding = run_security_audit.VulnerabilityFinding(
        vulnerability_id="CVE-2026-4539",
        aliases=(),
        package="pygments",
        version="2.19.2",
        lock_file="locks/requirements-dev.lock",
        fix_versions=(),
    )
    monkeypatch.setattr(
        run_security_audit,
        "_load_security_audit_exceptions",
        lambda: (exception,),
    )
    monkeypatch.setattr(
        run_security_audit,
        "_python_lock_files",
        lambda: (Path("locks/requirements-dev.lock"),),
    )
    monkeypatch.setattr(
        run_security_audit,
        "_audit_python_dependencies",
        lambda **kwargs: (((finding, exception),), ()),
    )

    assert run_security_audit.main() == 0
    output = capsys.readouterr().out
    assert "Reviewed Python vulnerability exceptions:" in output
    assert "Python dependency audit passed." in output


def test_main_reports_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        run_security_audit, "_load_security_audit_exceptions", lambda: ()
    )
    monkeypatch.setattr(run_security_audit, "_python_lock_files", lambda: ())
    monkeypatch.setattr(
        run_security_audit,
        "_audit_python_dependencies",
        lambda **kwargs: ((), ("boom",)),
    )

    assert run_security_audit.main() == 1
    output = capsys.readouterr().out
    assert "Python dependency audit failed:" in output
    assert "- boom" in output
