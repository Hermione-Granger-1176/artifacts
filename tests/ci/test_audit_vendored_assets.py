from __future__ import annotations

import io
import json
from datetime import date
from typing import TYPE_CHECKING

import pytest

from scripts.ci import audit_vendored_assets as audit
from scripts.ci.security_audit_policy import VulnerabilityExceptionEntry
from scripts.lint.check_vendored_assets import VendoredAsset

if TYPE_CHECKING:
    from urllib.request import Request


def _asset(package: str = "jspdf", version: str = "2.5.1", path: str = "a") -> VendoredAsset:
    """Build one manifest entry."""
    return VendoredAsset(
        path=f"apps/demo/js/vendor/{path}.js",
        package=package,
        version=version,
        upstream="https://example.com/lib.js",
        sha256="0" * 64,
    )


def _finding(
    *,
    advisory_id: str = "GHSA-aaaa-bbbb-cccc",
    aliases: tuple[str, ...] = (),
    fix_available: bool = False,
) -> audit.VendoredFinding:
    """Build one finding for the policy tests."""
    return audit.VendoredFinding(
        advisory_id=advisory_id,
        aliases=aliases,
        package="jspdf",
        version="2.5.1",
        fix_available=fix_available,
    )


def _exception(
    *,
    vulnerability_id: str = "GHSA-aaaa-bbbb-cccc",
    package: str = "jspdf",
    review_by: date = date(2999, 12, 31),
    ignore_only_without_fix: bool = False,
) -> VulnerabilityExceptionEntry:
    """Build one reviewed exception."""
    return VulnerabilityExceptionEntry(
        vulnerability_id=vulnerability_id,
        package=package,
        reason="Reviewed.",
        review_by=review_by,
        ignore_only_without_fix=ignore_only_without_fix,
    )


class _Response(io.BytesIO):
    """Minimal urlopen response that works as a context manager."""


def test_query_osv_posts_package_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """The request names the npm ecosystem, package, and exact version."""
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, *, timeout: float) -> _Response:
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data or b"")  # type: ignore[arg-type]
        captured["timeout"] = timeout
        return _Response(b'{"vulns": []}')

    monkeypatch.setattr(audit, "urlopen", fake_urlopen)

    assert audit.query_osv("jspdf", "2.5.1") == {"vulns": []}
    assert captured == {
        "url": audit.OSV_QUERY_URL,
        "body": {"package": {"name": "jspdf", "ecosystem": "npm"}, "version": "2.5.1"},
        "timeout": audit.OSV_TIMEOUT_SECONDS,
    }


def _affected(
    *events: dict[str, str], name: str = "jspdf", ecosystem: str = "npm"
) -> dict[str, object]:
    """Build one OSV ``affected`` entry with a single range of events."""
    return {"package": {"name": name, "ecosystem": ecosystem}, "ranges": [{"events": list(events)}]}


def test_parse_findings_reads_ids_aliases_and_fix_state() -> None:
    """A record with a fixed event is fixable, and aliases are kept."""
    payload = {
        "vulns": [
            {
                "id": "GHSA-1",
                "aliases": ["CVE-1", 7],
                "affected": [_affected({"introduced": "0"}, {"fixed": "4.2.1"})],
            },
            {"id": "GHSA-2", "affected": [_affected({"introduced": "0"})]},
        ]
    }

    first, second = audit.parse_findings("jspdf", "2.5.1", payload)

    assert first.all_ids == ("GHSA-1", "CVE-1")
    assert first.fix_available is True
    assert second.aliases == ()
    assert second.fix_available is False


def test_parse_findings_ignores_non_list_aliases() -> None:
    """A malformed aliases field degrades to no aliases."""
    record = {"id": "A", "aliases": "x", "affected": [_affected()]}
    (finding,) = audit.parse_findings("jspdf", "2.5.1", {"vulns": [record]})
    assert finding.aliases == ()


def test_parse_findings_returns_nothing_without_vulns() -> None:
    """OSV omits ``vulns`` when a version has no advisories."""
    assert audit.parse_findings("chart.js", "4.4.1", {}) == ()


@pytest.mark.parametrize(
    "payload",
    ["text", {"vulns": "x"}, {"vulns": [{}]}, {"vulns": ["x"]}, {"vulns": [{"id": ""}]}],
)
def test_parse_findings_rejects_unexpected_shapes(payload: object) -> None:
    """A response the parser cannot trust fails the audit instead of passing it."""
    with pytest.raises(ValueError, match="OSV"):
        audit.parse_findings("jspdf", "2.5.1", payload)


def test_has_fix_matches_the_package_case_insensitively() -> None:
    """Package names compare without regard to case."""
    record = {"id": "A", "affected": [_affected({"fixed": "2"}, name="JSPDF")]}
    assert audit._has_fix(record, "jspdf") is True


def test_has_fix_ignores_fixed_events_for_other_packages_and_ecosystems() -> None:
    """A fix for another package or ecosystem does not make this package fixable."""
    record = {
        "id": "A",
        "affected": [
            _affected({"fixed": "9"}, name="other"),
            _affected({"fixed": "9"}, ecosystem="PyPI"),
            _affected({"introduced": "0"}),
        ],
    }
    assert audit._has_fix(record, "jspdf") is False


def test_has_fix_accepts_an_entry_without_ranges() -> None:
    """A record that lists only versions has no fixed event."""
    record = {"id": "A", "affected": [{"package": {"name": "jspdf", "ecosystem": "npm"}}]}
    assert audit._has_fix(record, "jspdf") is False


_MALFORMED_RECORDS = [
    {"id": "A", "affected": "x"},
    {"id": "A", "affected": ["x"]},
    {"id": "A"},
    {"id": "A", "affected": []},
    {"id": "A", "affected": [{"package": "jspdf"}]},
    {"id": "A", "affected": [_affected(name="other")]},
    {"id": "A", "affected": [{"package": {"name": "jspdf", "ecosystem": "npm"}, "ranges": "x"}]},
    {"id": "A", "affected": [{"package": {"name": "jspdf", "ecosystem": "npm"}, "ranges": ["x"]}]},
    {
        "id": "A",
        "affected": [
            {"package": {"name": "jspdf", "ecosystem": "npm"}, "ranges": [{"events": "x"}]}
        ],
    },
    {
        "id": "A",
        "affected": [
            {"package": {"name": "jspdf", "ecosystem": "npm"}, "ranges": [{"events": ["x"]}]}
        ],
    },
]


@pytest.mark.parametrize("record", _MALFORMED_RECORDS)
def test_has_fix_fails_closed_on_malformed_or_missing_affected_data(
    record: dict[str, object],
) -> None:
    """Unreadable data raises instead of reading as "no fix"."""
    with pytest.raises(ValueError, match="OSV"):
        audit._has_fix(record, "jspdf")


def test_collect_findings_queries_each_package_version_once() -> None:
    """Two bundles of one package version share a single query."""
    calls: list[tuple[str, str]] = []

    def query(package: str, version: str) -> object:
        calls.append((package, version))
        return {
            "vulns": [
                {
                    "id": f"GHSA-{package}",
                    "affected": [_affected(name=package)],
                }
            ]
        }

    findings = audit.collect_findings(
        (_asset(path="a"), _asset(path="b"), _asset(package="chart.js", version="4.4.1")), query
    )

    assert calls == [("jspdf", "2.5.1"), ("chart.js", "4.4.1")]
    assert [finding.advisory_id for finding in findings] == ["GHSA-jspdf", "GHSA-chart.js"]


def test_audit_reports_unreviewed_finding_with_fix_hint() -> None:
    """A finding with no exception fails, and says when a fix exists."""
    _, errors = audit.audit_findings(
        today=date(2026, 1, 1),
        exceptions=(),
        findings=(_finding(fix_available=True), _finding(advisory_id="GHSA-dddd-eeee-ffff")),
    )

    assert errors == (
        "Unreviewed vendored vulnerability: jspdf 2.5.1 GHSA-aaaa-bbbb-cccc "
        "(a fixed version exists)",
        "Unreviewed vendored vulnerability: jspdf 2.5.1 GHSA-dddd-eeee-ffff",
    )


def test_audit_ignores_a_reviewed_finding_and_matches_alias_case_insensitively() -> None:
    """An alias in a different case still matches its exception."""
    exception = _exception(vulnerability_id="cve-2025-1")
    ignored, errors = audit.audit_findings(
        today=date(2026, 1, 1),
        exceptions=(exception,),
        findings=(_finding(aliases=("CVE-2025-1",)),),
    )

    assert errors == ()
    assert [(finding.advisory_id, entry) for finding, entry in ignored] == [
        ("GHSA-aaaa-bbbb-cccc", exception)
    ]


def test_audit_rejects_expired_exception() -> None:
    """An exception past its review date no longer silences the finding."""
    ignored, errors = audit.audit_findings(
        today=date(2026, 6, 1),
        exceptions=(_exception(review_by=date(2026, 5, 31)),),
        findings=(_finding(),),
    )

    assert ignored == ()
    assert errors == (
        "Expired vendored vulnerability exception: jspdf 2.5.1 GHSA-aaaa-bbbb-cccc "
        "review_by=2026-05-31",
    )


def test_audit_rejects_unfixed_only_exception_once_a_fix_exists() -> None:
    """An exception granted only while unfixed must go when a fix ships."""
    _, errors = audit.audit_findings(
        today=date(2026, 1, 1),
        exceptions=(_exception(ignore_only_without_fix=True),),
        findings=(_finding(fix_available=True),),
    )

    assert errors == (
        "Vendored vulnerability exception must be removed because a fix is available: "
        "jspdf 2.5.1 GHSA-aaaa-bbbb-cccc",
    )


def test_audit_rejects_overlapping_exceptions() -> None:
    """Two exceptions for one advisory are ambiguous, so the audit fails."""
    _, errors = audit.audit_findings(
        today=date(2026, 1, 1),
        exceptions=(_exception(), _exception(vulnerability_id="CVE-1")),
        findings=(_finding(aliases=("CVE-1",)),),
    )

    assert errors == (
        "Multiple vendored vulnerability exceptions match one advisory: "
        "jspdf 2.5.1 GHSA-aaaa-bbbb-cccc",
    )


def test_audit_reports_unused_exception() -> None:
    """An exception with no matching finding is reported so the list cannot rot."""
    _, errors = audit.audit_findings(
        today=date(2026, 1, 1), exceptions=(_exception(),), findings=()
    )

    assert errors == ("Unused vendored vulnerability exception: jspdf GHSA-aaaa-bbbb-cccc",)


def _patch_main(
    monkeypatch: pytest.MonkeyPatch,
    *,
    exceptions: tuple[VulnerabilityExceptionEntry, ...] = (),
    findings: tuple[audit.VendoredFinding, ...] = (),
    error: Exception | None = None,
) -> None:
    """Replace main's config, manifest, and network inputs."""

    def collect(_assets: object) -> tuple[audit.VendoredFinding, ...]:
        if error is not None:
            raise error
        return findings

    monkeypatch.setattr(audit, "load_security_audit_exceptions", lambda **_kwargs: exceptions)
    monkeypatch.setattr(audit, "_load_manifest", lambda: ())
    monkeypatch.setattr(audit, "collect_findings", collect)


def test_main_passes_when_no_findings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean manifest exits 0."""
    _patch_main(monkeypatch)

    assert audit.main([]) == 0
    assert "Vendored dependency audit passed." in capsys.readouterr().out


def test_main_lists_reviewed_exceptions_and_passes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A reviewed finding is printed with its reason and does not fail the run."""
    _patch_main(monkeypatch, exceptions=(_exception(),), findings=(_finding(),))

    assert audit.main([]) == 0
    output = capsys.readouterr().out
    assert "jspdf 2.5.1 GHSA-aaaa-bbbb-cccc (review by 2999-12-31)" in output
    assert "reason: Reviewed." in output


def test_main_fails_on_unreviewed_finding(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unreviewed finding exits 1 and names the advisory."""
    _patch_main(monkeypatch, findings=(_finding(),))

    assert audit.main([]) == 1
    output = capsys.readouterr().out
    assert "Vendored dependency audit failed:" in output
    assert "Unreviewed vendored vulnerability: jspdf 2.5.1 GHSA-aaaa-bbbb-cccc" in output


@pytest.mark.parametrize("error", [OSError("offline"), ValueError("bad response")])
def test_main_fails_when_osv_cannot_be_read(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception
) -> None:
    """A network or parse failure fails the audit instead of passing silently."""
    _patch_main(monkeypatch, error=error)

    assert audit.main([]) == 1
    assert "could not query OSV" in capsys.readouterr().out
