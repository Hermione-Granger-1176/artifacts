from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ci import run_security_audit


def write_text(path: Path, content: str) -> None:
    """Write text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_resolve_requirements_file_accepts_relative_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test resolve requirements file accepts relative path."""
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    assert (
        run_security_audit._resolve_requirements_file(Path(".artifacts") / "requirements-audit.txt")
        == requirements_file
    )


def test_resolve_requirements_file_accepts_absolute_path(tmp_path: Path) -> None:
    """Test resolve requirements file accepts absolute path."""
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pkg==1.0\n")

    assert run_security_audit._resolve_requirements_file(requirements_file) == (requirements_file)


def test_resolve_requirements_file_rejects_missing_file(tmp_path: Path) -> None:
    """Test resolve requirements file rejects missing file."""
    with pytest.raises(
        FileNotFoundError,
        match="Python security requirements file not found",
    ):
        run_security_audit._resolve_requirements_file(tmp_path / "missing.txt")


def test_resolve_requirements_file_rejects_symlink(tmp_path: Path) -> None:
    """Test resolve requirements file rejects symlinks."""
    target = tmp_path / "target.txt"
    write_text(target, "pkg==1.0\n")
    requirements_file = tmp_path / "requirements.txt"
    requirements_file.symlink_to(target)

    with pytest.raises(ValueError, match="must not be a symlink"):
        run_security_audit._resolve_requirements_file(requirements_file)


def test_relative_path_returns_repo_relative(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test relative path returns repo relative."""
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
    """Test relative path falls back to original outside repo."""
    repo_root = tmp_path / "repo"
    requirements_file = tmp_path / "elsewhere" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    assert run_security_audit._relative_path(requirements_file) == str(requirements_file)


def test_run_pip_audit_parses_valid_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test run pip audit parses valid output."""
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    def _fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        assert args[:4] == [
            "pip-audit",
            "--strict",
            "--requirement",
            str(requirements_file),
        ]
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

    findings, skipped = run_security_audit._run_pip_audit(requirements_file)

    assert skipped == ()
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
    """Test run pip audit rejects subprocess failures."""
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


def test_run_pip_audit_raises_on_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test run pip audit raises on timeout."""
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
    """Test run pip audit rejects invalid json."""
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
            stderr="diagnostic detail",
        ),
    )

    with pytest.raises(ValueError, match=r"invalid JSON.*diagnostic detail"):
        run_security_audit._run_pip_audit(requirements_file)


def test_subprocess_error_detail_normalizes_and_bounds_output() -> None:
    """Subprocess diagnostics stay readable without dumping unbounded output."""
    oversized_detail = "prefix\n" + ("x" * run_security_audit.MAX_SUBPROCESS_ERROR_DETAIL_LENGTH)

    detail = run_security_audit._subprocess_error_detail("", oversized_detail)

    assert "\n" not in detail
    assert detail.startswith("prefix ")
    assert detail.endswith("...")
    assert len(detail) <= run_security_audit.MAX_SUBPROCESS_ERROR_DETAIL_LENGTH + 3
    assert run_security_audit._subprocess_error_detail(None, "  ") == "unknown error"


@pytest.mark.parametrize(
    "payload",
    [
        "[]",
        '{"dependencies": {}}',
        '{"dependencies": [1]}',
        '{"dependencies": [{"name": "", "version": "1.0", "vulns": []}]}',
        '{"dependencies": [{"name": "pkg", "version": "", "vulns": []}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0"}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": {}}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": [1]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", "vulns": [{"id": ""}]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", '
        '"vulns": [{"id": "CVE-1", "aliases": {}}]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", '
        '"vulns": [{"id": "CVE-1", "aliases": [""]}]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", '
        '"vulns": [{"id": "CVE-1", "aliases": [], "fix_versions": {}}]}]}',
        '{"dependencies": [{"name": "pkg", "version": "1.0", '
        '"vulns": [{"id": "CVE-1", "aliases": [], "fix_versions": [""]}]}]}',
        '{"dependencies": [{"name": "pkg", "skip_reason": ""}]}',
        '{"dependencies": [{"name": "", "skip_reason": "not found"}]}',
    ],
)
def test_run_pip_audit_rejects_invalid_dependency_shape(
    payload: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test run pip audit rejects invalid dependency shape."""
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
    """Test audit python dependencies reports unused exception."""
    exceptions = (
        run_security_audit.VulnerabilityExceptionEntry(
            vulnerability_id="CVE-2026-4539",
            package="pygments",
            reason="No patched release yet.",
            review_by=date(2026, 4, 25),
            ignore_only_without_fix=True,
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _, **_kwargs: ((), ()))

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
    """Test audit python dependencies allows reviewed unfixed vulnerability."""
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
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _, **_kwargs: (findings, ()))

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert len(ignored) == 1
    assert errors == ()


def test_audit_python_dependencies_matches_ids_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured advisory ids match case-insensitive pip-audit aliases."""
    exception = run_security_audit.VulnerabilityExceptionEntry(
        vulnerability_id="ghsa-5239-wwwm-4pmq",
        package="PyGments",
        reason="No patched release yet.",
        review_by=date(2026, 4, 25),
        ignore_only_without_fix=True,
    )
    finding = run_security_audit.VulnerabilityFinding(
        vulnerability_id="CVE-2026-4539",
        aliases=("GHSA-5239-WWWM-4PMQ",),
        package="pygments",
        version="2.19.2",
        fix_versions=(),
    )
    monkeypatch.setattr(
        run_security_audit,
        "_run_pip_audit",
        lambda _, **_kwargs: ((finding,), ()),
    )

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=(exception,),
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ((finding, exception),)
    assert errors == ()


def test_audit_python_dependencies_rejects_ambiguous_exceptions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test audit python dependencies rejects multiple matching exceptions."""
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
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _, **_kwargs: (findings, ()))

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == (
        "Multiple Python vulnerability exceptions match one advisory: pygments CVE-2026-4539",
    )


def test_audit_python_dependencies_rejects_exception_when_fix_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test audit python dependencies rejects exception when fix exists."""
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
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _, **_kwargs: (findings, ()))

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
    """Test audit python dependencies rejects expired exception."""
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
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _, **_kwargs: (findings, ()))

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=exceptions,
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == (
        "Expired Python vulnerability exception: pygments CVE-2026-4539 review_by=2026-03-01",
    )


def test_audit_python_dependencies_rejects_unreviewed_vulnerability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test audit python dependencies rejects unreviewed vulnerability."""
    findings = (
        run_security_audit.VulnerabilityFinding(
            vulnerability_id="CVE-2026-4539",
            aliases=(),
            package="pygments",
            version="2.19.2",
            fix_versions=(),
        ),
    )
    monkeypatch.setattr(run_security_audit, "_run_pip_audit", lambda _, **_kwargs: (findings, ()))

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=(),
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == ("Unreviewed Python vulnerability: pygments 2.19.2 CVE-2026-4539",)


def test_run_pip_audit_splits_the_command_override_and_keeps_strict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A launcher override is shlex-split and never drops --strict."""
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)
    recorded: list[list[str]] = []

    def _fake_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        recorded.append(args)
        return SimpleNamespace(returncode=0, stdout='{"dependencies": []}', stderr="")

    monkeypatch.setattr(run_security_audit.subprocess, "run", _fake_run)

    run_security_audit._run_pip_audit(
        requirements_file, pip_audit_command="uv run --with pip-audit pip-audit"
    )

    assert recorded[0][:6] == [
        "uv",
        "run",
        "--with",
        "pip-audit",
        "pip-audit",
        "--strict",
    ]


def test_run_pip_audit_rejects_empty_command(tmp_path: Path) -> None:
    """An empty launcher cannot produce a malformed subprocess command."""
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pkg==1.0\n")

    with pytest.raises(ValueError, match="command must not be empty"):
        run_security_audit._run_pip_audit(requirements_file, pip_audit_command="  ")


def test_run_pip_audit_reports_a_missing_executable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing pip-audit names itself instead of raising a bare OSError."""
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)

    def _missing(*_args: object, **_kwargs: object) -> None:
        error = FileNotFoundError("launcher missing")
        error.filename = "uv"
        raise error

    monkeypatch.setattr(run_security_audit.subprocess, "run", _missing)

    with pytest.raises(RuntimeError, match="pip-audit executable not found: uv"):
        run_security_audit._run_pip_audit(requirements_file)


def test_run_pip_audit_reports_launcher_start_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Other launcher failures are reported as audit errors with context."""
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pkg==1.0\n")

    def _permission_denied(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("permission denied")

    monkeypatch.setattr(run_security_audit.subprocess, "run", _permission_denied)

    with pytest.raises(RuntimeError, match=r"could not start pip-audit.*permission denied"):
        run_security_audit._run_pip_audit(requirements_file)


def test_run_pip_audit_reports_skipped_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A skipped dependency preserves --strict semantics through the JSON report."""
    repo_root = tmp_path / "repo"
    requirements_file = repo_root / ".artifacts" / "requirements-audit.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(run_security_audit, "REPO_ROOT", repo_root)
    monkeypatch.setattr(
        run_security_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=1,
            stdout=(
                '{"dependencies": [{"name": "local-pkg", '
                '"skip_reason": "Dependency not found on PyPI"}]}'
            ),
            stderr="",
        ),
    )

    findings, skipped = run_security_audit._run_pip_audit(requirements_file)

    assert findings == ()
    assert skipped == (
        "pip-audit skipped local-pkg in .artifacts/requirements-audit.txt: "
        "Dependency not found on PyPI",
    )


def test_skipped_dependency_ignores_audited_entries() -> None:
    """Only entries carrying a skip reason produce a strictness error."""
    requirements_file = Path(".artifacts/requirements-audit.txt")

    assert run_security_audit._skipped_dependency({"name": "pkg"}, requirements_file) is None


def test_audit_python_dependencies_surfaces_skipped_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Skip errors fail the audit alongside vulnerability policy errors."""
    monkeypatch.setattr(
        run_security_audit,
        "_run_pip_audit",
        lambda _, **_kwargs: ((), ("pip-audit skipped local-pkg",)),
    )

    ignored, errors = run_security_audit._audit_python_dependencies(
        today=date(2026, 3, 25),
        exceptions=(),
        requirements_file=Path(".artifacts/requirements-audit.txt"),
    )

    assert ignored == ()
    assert errors == ("pip-audit skipped local-pkg",)


def test_main_forwards_the_pip_audit_command_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The --pip-audit option reaches the audit helper unchanged."""
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pkg==1.0\n")
    recorded: dict[str, object] = {}
    monkeypatch.setattr(run_security_audit, "load_security_audit_exceptions", lambda **_: ())

    def _fake_audit(**kwargs: object) -> tuple[tuple[object, ...], tuple[str, ...]]:
        recorded.update(kwargs)
        return (), ()

    monkeypatch.setattr(run_security_audit, "_audit_python_dependencies", _fake_audit)

    exit_code = run_security_audit.main(
        ["--requirements", str(requirements_file), "--pip-audit", "uvx pip-audit"]
    )

    assert exit_code == 0
    assert recorded["pip_audit_command"] == "uvx pip-audit"


def test_main_reports_success_with_reviewed_exceptions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Test main reports success with reviewed exceptions."""
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
        "load_security_audit_exceptions",
        lambda **_: (exception,),
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
    """Test main reports errors."""
    requirements_file = tmp_path / "requirements.txt"
    write_text(requirements_file, "pkg==1.0\n")
    monkeypatch.setattr(
        run_security_audit,
        "load_security_audit_exceptions",
        lambda **_: (),
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


def test_parse_dependency_findings_rejects_a_non_object_entry() -> None:
    """A malformed pip-audit dependency entry fails closed rather than being skipped."""
    with pytest.raises(ValueError, match="dependency entries must be objects"):
        run_security_audit._parse_dependency_findings("not-an-object", Path("requirements.txt"))
