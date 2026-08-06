from __future__ import annotations

import subprocess
from datetime import date
from types import SimpleNamespace

import pytest

from scripts.ci import run_npm_audit
from scripts.ci.security_audit_policy import VulnerabilityExceptionEntry


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
    # A stable far-future default keeps unexpired-exception tests from rotting
    # as the real calendar advances past any near-term date.
    review_by: date = date(2999, 12, 31),
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


@pytest.mark.parametrize("source", [True, -1, "42", {}, [], None])
def test_advisory_ids_rejects_invalid_numeric_source(source: object) -> None:
    """Malformed npm source ids fail closed instead of becoming bogus aliases."""
    with pytest.raises(ValueError, match="'source' must be a non-negative integer"):
        run_npm_audit._advisory_ids(
            {
                "url": "https://github.com/advisories/GHSA-aaaa-bbbb-cccc",
                "source": source,
            }
        )


def test_advisory_ids_rejects_non_string_url() -> None:
    """Malformed advisory URLs cannot be stringified into trusted input."""
    with pytest.raises(ValueError, match="'url' must be a string"):
        run_npm_audit._advisory_ids({"url": {}, "source": 42})


def test_parse_advisory_skips_bare_package_reference() -> None:
    """Parse advisory skips bare package reference."""
    assert run_npm_audit._parse_advisory("upstream-pkg", package="dep", fix_available=False) is None


@pytest.mark.parametrize("via", [None, 42, [], "", " "])
def test_parse_advisory_rejects_invalid_via_entry(via: object) -> None:
    """Only advisory objects and non-empty package references are accepted."""
    with pytest.raises(ValueError, match="'via' entries must be"):
        run_npm_audit._parse_advisory(via, package="dep", fix_available=False)


def test_parse_advisory_rejects_advisory_without_id() -> None:
    """An advisory object with no GHSA url and no source id is an invalid shape."""
    with pytest.raises(ValueError, match="missing both a GHSA url and a numeric source id"):
        run_npm_audit._parse_advisory({"severity": "high"}, package="dep", fix_available=False)


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


@pytest.mark.parametrize("severity", [None, "", "HIGH", "unknown", 1])
def test_parse_advisory_rejects_invalid_severity(severity: object) -> None:
    """Malformed severities cannot pass through a reviewed exception."""
    with pytest.raises(ValueError, match="invalid severity"):
        run_npm_audit._parse_advisory(
            {"source": 42, "severity": severity},
            package="dep",
            fix_available=False,
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


@pytest.mark.parametrize("name", [None, "", " ", 42])
def test_parse_npm_audit_rejects_invalid_package_name(name: object) -> None:
    """Malformed package names cannot be coerced into exception identities."""
    payload = {
        "vulnerabilities": {
            "left-pad": {
                "name": name,
                "via": [{"source": 7, "severity": "high"}],
            }
        }
    }

    with pytest.raises(ValueError, match="invalid package name"):
        run_npm_audit._parse_npm_audit(payload)


@pytest.mark.parametrize(
    "fix_available",
    [
        "false",
        1,
        [],
        None,
        {},
        {"name": "left-pad"},
        {"version": "2.0.0"},
        {"name": "", "version": "2.0.0"},
        {"name": "left-pad", "version": ""},
        {"name": 42, "version": "2.0.0"},
        {"name": "left-pad", "version": 2},
        {"name": "left-pad", "version": "2.0.0", "isSemVerMajor": "false"},
    ],
)
def test_parse_npm_audit_rejects_invalid_fix_available(fix_available: object) -> None:
    """Unexpected fix metadata fails closed instead of changing policy truthiness."""
    payload = {
        "vulnerabilities": {
            "left-pad": {
                "fixAvailable": fix_available,
                "via": [{"source": 7, "severity": "high"}],
            }
        }
    }

    with pytest.raises(ValueError, match="fixAvailable"):
        run_npm_audit._parse_npm_audit(payload)


def test_parse_npm_audit_accepts_fix_description_object() -> None:
    """An npm fix description object means that a fix is available."""
    payload = {
        "vulnerabilities": {
            "left-pad": {
                "fixAvailable": {
                    "name": "left-pad",
                    "version": "2.0.0",
                    "isSemVerMajor": False,
                },
                "via": [{"source": 7, "severity": "high"}],
            }
        }
    }

    assert run_npm_audit._parse_npm_audit(payload)[0].fix_available is True


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


def test_run_npm_audit_accepts_explicit_null_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A null npm error field still represents a clean audit response."""
    monkeypatch.setattr(
        run_npm_audit.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout='{"error": null, "vulnerabilities": {}}',
            stderr="",
        ),
    )

    assert run_npm_audit._run_npm_audit("npm") == ()


def test_run_npm_audit_splits_command_with_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Run npm audit shlex-splits an npm override that carries flags."""
    captured: dict[str, object] = {}

    def _run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout='{"vulnerabilities": {}}', stderr="")

    monkeypatch.setattr(run_npm_audit.subprocess, "run", _run)

    assert run_npm_audit._run_npm_audit("npm --silent") == ()
    assert captured["command"] == ["npm", "--silent", "audit", "--json"]


def test_run_npm_audit_rejects_empty_command() -> None:
    """An empty override cannot accidentally execute a binary named audit."""
    with pytest.raises(ValueError, match="must not be empty"):
        run_npm_audit._run_npm_audit("  ")


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
        ('{"error": {}}', "unknown error"),
        ('{"error": ""}', "unknown error"),
        ('{"error": false}', "unknown error"),
        ('{"error": []}', "unknown error"),
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


def test_matches_exception_compares_advisory_ids_case_insensitively() -> None:
    """A lower-case configured exception id matches the upper-cased finding id."""
    finding = _finding(advisory_id="GHSA-AAAA-BBBB-CCCC")
    assert run_npm_audit._matches_exception(
        _exception(vulnerability_id="ghsa-aaaa-bbbb-cccc"), finding
    )


def test_audit_allows_lowercase_configured_exception() -> None:
    """A lower-case exception id suppresses the matching finding end to end."""
    exception = _exception(vulnerability_id="ghsa-aaaa-bbbb-cccc")
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(exception,),
        findings=(_finding(advisory_id="GHSA-AAAA-BBBB-CCCC"),),
    )

    assert len(ignored) == 1
    assert ignored[0][1] is exception
    assert errors == ()


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


def test_audit_counts_exception_below_raised_threshold_as_used() -> None:
    """Ad-hoc severity filtering does not make a valid policy look stale."""
    exception = _exception()
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(exception,),
        findings=(_finding(severity="moderate"),),
        audit_level="high",
    )

    assert ignored == ()
    assert errors == ()


def test_audit_rejects_expired_exception_below_threshold() -> None:
    """Severity filtering never bypasses exception expiry."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 6, 1),
        exceptions=(_exception(review_by=date(2026, 1, 1)),),
        findings=(_finding(severity="moderate"),),
        audit_level="high",
    )

    assert ignored == ()
    assert errors == (
        "Expired npm vulnerability exception: left-pad GHSA-aaaa-bbbb-cccc review_by=2026-01-01",
    )


def test_audit_evicts_fixed_exception_below_threshold() -> None:
    """Severity filtering never hides a newly available fix."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(_exception(ignore_only_without_fix=True),),
        findings=(_finding(severity="moderate", fix_available=True),),
        audit_level="high",
    )

    assert ignored == ()
    assert errors == (
        "npm vulnerability exception must be removed because a fix is available: "
        "left-pad GHSA-aaaa-bbbb-cccc",
    )


def test_audit_rejects_ambiguous_exceptions_below_threshold() -> None:
    """Severity filtering never hides ambiguous advisory policies."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(
            _exception(vulnerability_id="GHSA-aaaa-bbbb-cccc"),
            _exception(vulnerability_id="42"),
        ),
        findings=(_finding(aliases=("42",), severity="moderate"),),
        audit_level="high",
    )

    assert ignored == ()
    assert errors == (
        "Multiple npm vulnerability exceptions match one advisory: left-pad GHSA-aaaa-bbbb-cccc",
    )


def test_audit_rejects_multiple_exceptions_matching_one_advisory() -> None:
    """Alias and primary-id policies cannot ambiguously govern one finding."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(
            _exception(vulnerability_id="GHSA-aaaa-bbbb-cccc"),
            _exception(vulnerability_id="42"),
        ),
        findings=(_finding(aliases=("42",)),),
    )

    assert ignored == ()
    assert errors == (
        "Multiple npm vulnerability exceptions match one advisory: left-pad GHSA-aaaa-bbbb-cccc",
    )


def test_main_reports_success_with_reviewed_exceptions(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main reports success with reviewed exceptions."""
    exception = _exception(ignore_only_without_fix=True)
    finding = _finding()
    monkeypatch.setattr(
        run_npm_audit, "load_security_audit_exceptions", lambda **_kwargs: (exception,)
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
    monkeypatch.setattr(run_npm_audit, "load_security_audit_exceptions", lambda **_kwargs: ())
    monkeypatch.setattr(run_npm_audit, "_run_npm_audit", lambda _npm: (_finding(),))

    assert run_npm_audit.main([]) == 1
    output = capsys.readouterr().out
    assert "npm dependency audit failed:" in output
    assert "- Unreviewed npm vulnerability: left-pad high GHSA-aaaa-bbbb-cccc" in output


def test_is_gated_applies_the_npm_severity_ladder() -> None:
    """Severities below the audit level are not gated; unknown ones always are."""
    assert run_npm_audit._is_gated("critical", "high") is True
    assert run_npm_audit._is_gated("high", "high") is True
    assert run_npm_audit._is_gated("moderate", "high") is False
    assert run_npm_audit._is_gated("moderate", "low") is True
    assert run_npm_audit._is_gated("", "high") is True


def test_audit_gates_every_severity_by_default() -> None:
    """The default gate reviews weak advisories too, not just high and critical."""
    for severity in run_npm_audit.SEVERITY_ORDER:
        ignored, errors = run_npm_audit._audit_npm_dependencies(
            today=date(2026, 1, 1),
            exceptions=(),
            findings=(_finding(severity=severity),),
        )

        assert ignored == (), severity
        assert errors == (
            f"Unreviewed npm vulnerability: left-pad {severity} GHSA-aaaa-bbbb-cccc",
        ), severity


def test_audit_skips_findings_below_a_raised_audit_level() -> None:
    """Raising the audit level narrows an ad-hoc run to the stronger advisories."""
    ignored, errors = run_npm_audit._audit_npm_dependencies(
        today=date(2026, 1, 1),
        exceptions=(),
        findings=(_finding(severity="moderate"),),
        audit_level="high",
    )

    assert ignored == ()
    assert errors == ()


def test_main_forwards_the_audit_level(monkeypatch: pytest.MonkeyPatch) -> None:
    """The --audit-level option reaches the policy helper unchanged."""
    recorded: dict[str, object] = {}
    monkeypatch.setattr(run_npm_audit, "load_security_audit_exceptions", lambda **_kwargs: ())
    monkeypatch.setattr(run_npm_audit, "_run_npm_audit", lambda _npm: ())

    def _fake_audit(**kwargs: object) -> tuple[tuple[object, ...], tuple[str, ...]]:
        recorded.update(kwargs)
        return (), ()

    monkeypatch.setattr(run_npm_audit, "_audit_npm_dependencies", _fake_audit)

    assert run_npm_audit.main(["--audit-level", "critical"]) == 0
    assert recorded["audit_level"] == "critical"
