from __future__ import annotations

import subprocess
from datetime import date
from types import SimpleNamespace

import pytest

import scripts.ci.run_npm_audit as run_npm_audit
from scripts.ci.run_security_audit import VulnerabilityExceptionEntry


def _finding(
    *,
    advisory_id: str = "GHSA-aaaa-bbbb-cccc",
    aliases: tuple[str, ...] = (),
    package: str = "left-pad",
    severity: str = "high",
    fix_available: bool = False,
) -> run_npm_audit.NpmVulnerabilityFinding:
    """Build one npm finding for the audit-policy tests."""
    return run_npm_audit.NpmVulnerabilityFinding(
        advisory_id=advisory_id,
        aliases=aliases,
        package=package,
        severity=severity,
        fix_available=fix_available,
    )


def _exception(
    *,
    vulnerability_id: str = "GHSA-aaaa-bbbb-cccc",
    package: str = "left-pad",
    review_by: date = date(2026, 12, 31),
    ignore_only_without_fix: bool = False,
) -> VulnerabilityExceptionEntry:
    """Build one reviewed exception for the audit-policy tests."""
    return VulnerabilityExceptionEntry(
        vulnerability_id=vulnerability_id,
        package=package,
        reason="Reviewed with maintainers.",
        review_by=review_by,
        ignore_only_without_fix=ignore_only_without_fix,
    )


def test_all_ids_includes_primary_and_aliases() -> None:
    """All ids includes primary and aliases."""
    finding = _finding(advisory_id="GHSA-1", aliases=("1234",))
    assert finding.all_ids == ("GHSA-1", "1234")


def test_advisory_ids_prefers_ghsa_and_keeps_source_alias() -> None:
    """Advisory ids prefers ghsa and keeps source alias."""
    primary, aliases = run_npm_audit._advisory_ids(
        {"url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc", "source": 1088820}
    )
    assert primary == "GHSA-AAAA-BBBB-CCCC"
    assert aliases == ("1088820",)


def test_advisory_ids_ghsa_without_source() -> None:
    """Advisory ids ghsa without source."""
    primary, aliases = run_npm_audit._advisory_ids(
        {"url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc"}
    )
    assert primary == "GHSA-AAAA-BBBB-CCCC"
    assert aliases == ()


def test_advisory_ids_falls_back_to_numeric_source() -> None:
    """Advisory ids falls back to numeric source."""
    primary, aliases = run_npm_audit._advisory_ids({"source": 42})
    assert primary == "42"
    assert aliases == ()


def test_parse_advisory_skips_bare_package_reference() -> None:
    """Parse advisory skips bare package reference."""
    assert run_npm_audit._parse_advisory("upstream-pkg", package="dep", fix_available=False) is None


def test_parse_advisory_rejects_advisory_without_id() -> None:
    """An advisory object with no GHSA url and no source id is an invalid shape."""
    with pytest.raises(ValueError, match="missing both a GHSA url and a numeric source id"):
        run_npm_audit._parse_advisory(
            {"severity": "high"}, package="dep", fix_available=False
        )


def test_parse_advisory_builds_finding() -> None:
    """Parse advisory builds finding."""
    finding = run_npm_audit._parse_advisory(
        {"url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc", "severity": "moderate"},
        package="dep",
        fix_available=True,
    )
    assert finding == _finding(
        advisory_id="GHSA-AAAA-BBBB-CCCC", package="dep", severity="moderate", fix_available=True
    )


def test_parse_npm_audit_collects_findings() -> None:
    """Parse npm audit collects findings."""
    payload = {
        "vulnerabilities": {
            "left-pad": {
                "name": "left-pad",
                "fixAvailable": True,
                "via": [
                    {
                        "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc",
                        "severity": "high",
                        "source": 1,
                    },
                    "another-package",
                ],
            }
        }
    }

    findings = run_npm_audit._parse_npm_audit(payload)

    assert findings == (
        _finding(
            advisory_id="GHSA-AAAA-BBBB-CCCC",
            aliases=("1",),
            package="left-pad",
            severity="high",
            fix_available=True,
        ),
    )


def test_parse_npm_audit_defaults_package_name_to_key() -> None:
    """Parse npm audit defaults package name to key."""
    payload = {
        "vulnerabilities": {
            "lodash": {
                "via": [{"source": 7, "severity": "low"}],
            }
        }
    }

    findings = run_npm_audit._parse_npm_audit(payload)

    assert findings == (
        _finding(advisory_id="7", package="lodash", severity="low", fix_available=False),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"vulnerabilities": []},
        {"vulnerabilities": {"pkg": ["oops"]}},
        {"vulnerabilities": {"pkg": {"via": {}}}},
    ],
)
def test_parse_npm_audit_rejects_invalid_shapes(payload: dict[str, object]) -> None:
    """Parse npm audit rejects invalid shapes."""
    with pytest.raises(ValueError):
        run_npm_audit._parse_npm_audit(payload)


def test_run_npm_audit_parses_clean_report(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run npm audit parses clean report."""
    monkeypatch.setattr(
        run_npm_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0, stdout='{"vulnerabilities": {}}', stderr=""
        ),
    )

    assert run_npm_audit._run_npm_audit("npm") == ()


def test_run_npm_audit_raises_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run npm audit raises on timeout."""

    def _timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(["npm", "audit"], 120)

    monkeypatch.setattr(run_npm_audit.subprocess, "run", _timeout)

    with pytest.raises(RuntimeError, match="npm audit timed out"):
        run_npm_audit._run_npm_audit()


def test_run_npm_audit_raises_when_npm_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run npm audit raises when npm missing."""

    def _missing(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("no npm")

    monkeypatch.setattr(run_npm_audit.subprocess, "run", _missing)

    with pytest.raises(RuntimeError, match="npm executable not found"):
        run_npm_audit._run_npm_audit("npm")


@pytest.mark.parametrize(
    ("stdout", "stderr", "message"),
    [
        ("not-json", "boom", "boom"),
        ("garbage", "", "garbage"),
        ("", "", "unknown error"),
    ],
)
def test_run_npm_audit_rejects_invalid_json(
    stdout: str, stderr: str, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run npm audit rejects invalid json."""
    monkeypatch.setattr(
        run_npm_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=stdout, stderr=stderr),
    )

    with pytest.raises(RuntimeError, match=message):
        run_npm_audit._run_npm_audit()


def test_run_npm_audit_rejects_non_object_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run npm audit rejects non object json."""
    monkeypatch.setattr(
        run_npm_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=0, stdout="[]", stderr=""),
    )

    with pytest.raises(ValueError, match="must be an object"):
        run_npm_audit._run_npm_audit()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ('{"error": {"summary": "no lockfile"}}', "no lockfile"),
        ('{"error": {"code": "EAUDIT"}}', "unknown error"),
        ('{"error": "boom"}', "boom"),
    ],
)
def test_run_npm_audit_reports_audit_errors(
    payload: str, message: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run npm audit reports audit errors."""
    monkeypatch.setattr(
        run_npm_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(returncode=1, stdout=payload, stderr=""),
    )

    with pytest.raises(RuntimeError, match=message):
        run_npm_audit._run_npm_audit()


def test_matches_exception_compares_package_and_ids() -> None:
    """Matches exception compares package and ids."""
    finding = _finding(advisory_id="GHSA-1", aliases=("99",), package="Left-Pad")
    assert run_npm_audit._matches_exception(
        _exception(vulnerability_id="99", package="left-pad"), finding
    )
    assert not run_npm_audit._matches_exception(
        _exception(vulnerability_id="GHSA-2", package="left-pad"), finding
    )


def test_audit_reports_unreviewed_vulnerability() -> None:
    """Audit reports unreviewed vulnerability."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(),
        findings=(_finding(),),
    )

    assert ignored == ()
    assert errors == ("Unreviewed npm vulnerability: left-pad high GHSA-aaaa-bbbb-cccc",)


def test_audit_allows_reviewed_unfixed_vulnerability() -> None:
    """Audit allows reviewed unfixed vulnerability."""
    exception = _exception(ignore_only_without_fix=True)
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(exception,),
        findings=(_finding(fix_available=False),),
    )

    assert len(ignored) == 1
    assert ignored[0][1] is exception
    assert errors == ()


def test_audit_rejects_expired_exception() -> None:
    """Audit rejects expired exception."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 6, 1),
        exceptions=(_exception(review_by=date(2026, 1, 1)),),
        findings=(_finding(),),
    )

    assert ignored == ()
    assert errors == (
        "Expired npm vulnerability exception: left-pad GHSA-aaaa-bbbb-cccc review_by=2026-01-01",
    )


def test_audit_evicts_exception_when_fix_available() -> None:
    """Audit evicts exception when fix available."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(_exception(ignore_only_without_fix=True),),
        findings=(_finding(fix_available=True),),
    )

    assert ignored == ()
    assert errors == (
        "npm vulnerability exception must be removed because a fix is available: "
        "left-pad GHSA-aaaa-bbbb-cccc",
    )


def test_audit_reports_unused_exception() -> None:
    """Audit reports unused exception."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(_exception(),),
        findings=(),
    )

    assert ignored == ()
    assert errors == ("Unused npm vulnerability exception: left-pad GHSA-aaaa-bbbb-cccc",)


def test_main_reports_success_with_reviewed_exceptions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main reports success with reviewed exceptions."""
    exception = _exception(ignore_only_without_fix=True)
    finding = _finding()
    monkeypatch.setattr(
        run_npm_audit, "_load_security_audit_exceptions", lambda **_kwargs: (exception,)
    )
    monkeypatch.setattr(run_npm_audit, "_run_npm_audit", lambda _npm: (finding,))

    assert run_npm_audit.main(["--npm", "npm"]) == 0
    output = capsys.readouterr().out
    assert "Reviewed npm vulnerability exceptions:" in output
    assert "- left-pad high GHSA-aaaa-bbbb-cccc" in output
    assert "npm dependency audit passed." in output


def test_main_reports_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main reports errors."""
    monkeypatch.setattr(run_npm_audit, "_load_security_audit_exceptions", lambda **_kwargs: ())
    monkeypatch.setattr(run_npm_audit, "_run_npm_audit", lambda _npm: (_finding(),))

    assert run_npm_audit.main([]) == 1
    output = capsys.readouterr().out
    assert "npm dependency audit failed:" in output
    assert "- Unreviewed npm vulnerability: left-pad high GHSA-aaaa-bbbb-cccc" in output
