from __future__ import annotations

import io
import json
from datetime import date
from email.message import Message
from http.client import BadStatusLine, IncompleteRead
from typing import TYPE_CHECKING
from urllib.error import HTTPError

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
        upstream=f"https://cdn.jsdelivr.net/npm/{package}@{version}/dist/lib.js",
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


def _affected(
    *events: dict[str, str],
    name: str = "jspdf",
    ecosystem: str = "npm",
    range_type: object = "SEMVER",
) -> dict[str, object]:
    """Build one OSV ``affected`` entry with a single range of events.

    A range needs an ``introduced`` event, so a call with no events gets ``introduced 0``.
    """
    return {
        "package": {"name": name, "ecosystem": ecosystem},
        "ranges": [{"type": range_type, "events": list(events) or [{"introduced": "0"}]}],
    }


def _fixed(*events: dict[str, str], version: str = "2.5.1") -> bool:
    """Return the fix state for one jspdf record holding a single range."""
    return audit._has_fix({"id": "A", "affected": [_affected(*events)]}, "jspdf", version)


class _Response(io.BytesIO):
    """Minimal urlopen response that works as a context manager."""


def _http_error(code: int) -> HTTPError:
    """Build an HTTP error response with a status code."""
    return HTTPError(audit.OSV_QUERY_URL, code, "error", Message(), io.BytesIO(b""))


# ---- query_osv: request shape, retries, pagination ----


def test_query_osv_posts_package_and_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """The request names the npm ecosystem, package, and exact version."""
    captured: dict[str, object] = {}

    def fake_urlopen(request: Request, *, timeout: float) -> _Response:
        captured["url"] = request.full_url
        captured["body"] = json.loads(request.data or b"")
        captured["timeout"] = timeout
        return _Response(b'{"vulns": []}')

    monkeypatch.setattr(audit, "urlopen", fake_urlopen)

    assert audit.query_osv("jspdf", "2.5.1") == {"vulns": []}
    assert captured == {
        "url": audit.OSV_QUERY_URL,
        "body": {"package": {"name": "jspdf", "ecosystem": "npm"}, "version": "2.5.1"},
        "timeout": audit.OSV_TIMEOUT_SECONDS,
    }


def test_the_client_waits_longer_than_osv_takes_to_paginate() -> None:
    """OSV paginates a query after 20 seconds, so a shorter client timeout would cut it off."""
    assert audit.OSV_TIMEOUT_SECONDS > 20


@pytest.mark.parametrize(
    "error",
    [
        OSError("connection reset"),
        _http_error(500),
        _http_error(503),
        _http_error(429),
        IncompleteRead(b"partial"),
        BadStatusLine("garbage"),
    ],
)
def test_query_osv_retries_transient_errors_then_succeeds(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """A transient failure retries with a growing delay."""
    attempts: list[int] = []
    delays: list[float] = []

    def flaky_urlopen(_request: Request, **_kwargs: object) -> _Response:
        attempts.append(1)
        if len(attempts) < audit.OSV_ATTEMPTS:
            raise error
        return _Response(b'{"vulns": []}')

    monkeypatch.setattr(audit, "urlopen", flaky_urlopen)
    monkeypatch.setattr(audit.time, "sleep", delays.append)

    assert audit.query_osv("jspdf", "2.5.1") == {"vulns": []}
    assert delays == [audit.OSV_RETRY_DELAY_SECONDS, 2 * audit.OSV_RETRY_DELAY_SECONDS]
    if isinstance(error, HTTPError):
        error.close()


def test_query_osv_raises_after_the_last_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """A persistent transient error is raised, not swallowed."""
    calls: list[int] = []

    def failing_urlopen(_request: Request, **_kwargs: object) -> _Response:
        calls.append(1)
        raise OSError("offline")

    monkeypatch.setattr(audit, "urlopen", failing_urlopen)
    monkeypatch.setattr(audit.time, "sleep", lambda _seconds: None)

    with pytest.raises(OSError, match="offline"):
        audit.query_osv("jspdf", "2.5.1")
    assert len(calls) == audit.OSV_ATTEMPTS


@pytest.mark.parametrize("code", [400, 404])
def test_query_osv_does_not_retry_a_rejected_request(
    monkeypatch: pytest.MonkeyPatch, code: int
) -> None:
    """A 4xx other than 429 means OSV rejected the query, so a retry cannot help."""
    calls: list[int] = []

    def rejecting_urlopen(_request: Request, **_kwargs: object) -> _Response:
        calls.append(1)
        raise _http_error(code)

    monkeypatch.setattr(audit, "urlopen", rejecting_urlopen)

    with pytest.raises(HTTPError) as caught:
        audit.query_osv("jspdf", "2.5.1")
    caught.value.close()
    assert len(calls) == 1


def test_query_osv_does_not_retry_a_bad_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed body is a data problem, so it fails on the first attempt."""
    calls: list[int] = []

    def bad_urlopen(_request: Request, **_kwargs: object) -> _Response:
        calls.append(1)
        return _Response(b"not json")

    monkeypatch.setattr(audit, "urlopen", bad_urlopen)

    with pytest.raises(ValueError, match="Expecting value"):
        audit.query_osv("jspdf", "2.5.1")
    assert len(calls) == 1


def _stub_pages(monkeypatch: pytest.MonkeyPatch, *payloads: object) -> list[dict[str, object]]:
    """Serve payloads in order from ``_post_osv`` and record each request body."""
    bodies: list[dict[str, object]] = []
    queue = list(payloads)

    def fake_post(body: bytes) -> object:
        bodies.append(json.loads(body))
        return queue.pop(0)

    monkeypatch.setattr(audit, "_post_osv", fake_post)
    return bodies


def test_query_osv_follows_page_tokens_and_merges_every_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A paginated response is read to the end, with the token sent back each time."""
    bodies = _stub_pages(
        monkeypatch,
        {"vulns": [{"id": "A"}], "next_page_token": "t1"},
        {"vulns": [{"id": "B"}], "next_page_token": "t2"},
        {"vulns": [{"id": "C"}]},
    )

    assert audit.query_osv("jspdf", "2.5.1") == {"vulns": [{"id": "A"}, {"id": "B"}, {"id": "C"}]}
    assert ["page_token" in body for body in bodies] == [False, True, True]
    assert [body.get("page_token") for body in bodies] == [None, "t1", "t2"]


def test_query_osv_returns_an_empty_object_as_no_vulnerabilities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OSV answers ``{}`` when a version has no advisories."""
    _stub_pages(monkeypatch, {})
    assert audit.query_osv("chart.js", "4.4.1") == {"vulns": []}


@pytest.mark.parametrize("payload", ["text", {"vulns": "x"}])
def test_query_osv_returns_an_unexpected_shape_for_parse_findings_to_reject(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    """The merge step leaves a malformed response untouched so the parser rejects it."""
    _stub_pages(monkeypatch, payload)
    assert audit.query_osv("jspdf", "2.5.1") == payload


@pytest.mark.parametrize("token", ["", 5])
def test_query_osv_rejects_an_invalid_page_token(
    monkeypatch: pytest.MonkeyPatch, token: object
) -> None:
    """A token the client cannot send back fails closed."""
    _stub_pages(monkeypatch, {"vulns": [], "next_page_token": token})
    with pytest.raises(ValueError, match="invalid page token"):
        audit.query_osv("jspdf", "2.5.1")


def test_query_osv_stops_after_the_page_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """A response that never ends fails closed instead of looping."""
    bodies = _stub_pages(
        monkeypatch, *[{"vulns": [], "next_page_token": "t"} for _ in range(audit.OSV_MAX_PAGES)]
    )
    with pytest.raises(ValueError, match="more than 5 pages"):
        audit.query_osv("jspdf", "2.5.1")
    assert len(bodies) == audit.OSV_MAX_PAGES


# ---- parse_findings ----


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


def test_parse_findings_fails_closed_on_a_paginated_response() -> None:
    """A truncated response would drop advisories, so it raises."""
    with pytest.raises(ValueError, match="paginated"):
        audit.parse_findings("jspdf", "2.5.1", {"vulns": [], "next_page_token": "abc"})


@pytest.mark.parametrize(
    "payload",
    ["text", {"vulns": "x"}, {"vulns": [{}]}, {"vulns": ["x"]}, {"vulns": [{"id": ""}]}],
)
def test_parse_findings_rejects_unexpected_shapes(payload: object) -> None:
    """A response the parser cannot trust fails the audit instead of passing it."""
    with pytest.raises(ValueError, match="OSV"):
        audit.parse_findings("jspdf", "2.5.1", payload)


# ---- version ordering ----

_ASCENDING = [
    "0",
    "1.0.0-alpha",
    "1.0.0-alpha.1",
    "1.0.0-alpha.beta",
    "1.0.0-beta",
    "1.0.0-beta.2",
    "1.0.0-beta.11",
    "1.0.0-rc.1",
    "1.0.0",
    "1.0.1",
    "1.10.0",
    "2",
    "10.0.0",
]


def test_version_key_follows_semver_precedence() -> None:
    """The SemVer 2.0 example order sorts as written, with no two keys equal."""
    keys = [audit._version_key(version, "A") for version in _ASCENDING]
    assert keys == sorted(keys)
    assert len(set(keys)) == len(keys)


def test_version_key_treats_missing_zeros_and_build_metadata_as_equal() -> None:
    """``3.5`` equals ``3.5.0``, and build metadata does not change the order."""
    assert audit._version_key("3.5", "A") == audit._version_key("3.5.0", "A")
    assert audit._version_key("2", "A") == audit._version_key("2.0.0", "A")
    assert audit._version_key("1.0.0+build.7", "A") == audit._version_key("1.0.0", "A")


@pytest.mark.parametrize(
    "value",
    [
        "latest",
        "",
        "v1.0.0",
        "1..2",
        "1.0.0-",
        "1.0.0-a..b",
        "1.0.0-a.",
        "1.2.3.4",
        "2.0.0.0",
        "1.2.3+a..b",
        "1.2.3+",
        "01.0.0",
        "1.00.0",
        "1.0.0-01",
        3,
        None,
    ],
)
def test_version_key_rejects_anything_that_is_not_a_semantic_version(value: object) -> None:
    """An unorderable value raises so the audit fails closed."""
    with pytest.raises(ValueError, match="OSV version"):
        audit._version_key(value, "A")


# ---- fix detection ----


def test_has_fix_matches_the_package_case_insensitively() -> None:
    """Package names compare without regard to case."""
    record = {"id": "A", "affected": [_affected({"introduced": "0"}, {"fixed": "3"}, name="JSPDF")]}
    assert audit._has_fix(record, "jspdf", "2.5.1") is True


def test_has_fix_ignores_fixed_events_for_other_packages_and_ecosystems() -> None:
    """A fix for another package or ecosystem does not make this package fixable."""
    record = {
        "id": "A",
        "affected": [
            _affected({"introduced": "0"}, {"fixed": "9"}, name="other"),
            _affected({"introduced": "0"}, {"fixed": "9"}, ecosystem="PyPI"),
            _affected({"introduced": "0"}),
        ],
    }
    assert audit._has_fix(record, "jspdf", "2.5.1") is False


def test_has_fix_accepts_an_entry_without_ranges() -> None:
    """A record that lists only versions has no fixed event."""
    record = {"id": "A", "affected": [{"package": {"name": "jspdf", "ecosystem": "npm"}}]}
    assert audit._has_fix(record, "jspdf", "2.5.1") is False


_REINTRODUCED = ({"introduced": "0"}, {"fixed": "2"}, {"introduced": "3"})


def test_has_fix_uses_the_interval_that_holds_the_queried_version() -> None:
    """A fix in an earlier interval does not cover a later, reintroduced one."""
    assert _fixed(*_REINTRODUCED, version="1") is True
    assert _fixed(*_REINTRODUCED, version="3.5") is False
    assert _fixed(*_REINTRODUCED, {"fixed": "4"}, version="3.5") is True


def test_has_fix_is_false_when_the_boundary_is_not_a_fix() -> None:
    """A last_affected boundary names no fixed release."""
    assert _fixed({"introduced": "0"}, {"last_affected": "3"}) is False


def test_has_fix_prefers_the_non_fix_boundary_on_a_tie() -> None:
    """A fix and a reintroduction at one version leave no fixed release."""
    assert _fixed({"introduced": "0"}, {"fixed": "3"}, {"introduced": "3"}) is False


def test_has_fix_compares_versions_numerically_and_ignores_trailing_zeros() -> None:
    """Versions order by number, so 10 is after 9, and 3.5 equals 3.5.0."""
    assert _fixed({"introduced": "0"}, {"fixed": "10.0.0"}, version="9.9.9") is True
    assert _fixed({"introduced": "0"}, {"fixed": "3.5"}, version="3.5.0") is False


def test_has_fix_orders_pre_release_boundaries_in_unrelated_intervals() -> None:
    """A beta boundary elsewhere in the timeline does not abort the audit.

    Real npm records carry boundaries such as ``introduced 16.0.0-beta.0``.
    """
    events = (
        {"introduced": "0"},
        {"fixed": "4.3.0"},
        {"introduced": "5.0.0-beta.1"},
        {"fixed": "5.0.0"},
    )
    assert _fixed(*events, version="4.2.1") is True
    assert _fixed(*events, version="5.0.0-beta.2") is True
    assert _fixed(*events, version="5.0.0") is False


def test_has_fix_orders_a_pre_release_fix_boundary_before_its_release() -> None:
    """A fix at ``3.0.0-beta.4`` leaves ``3.0.0`` unaffected and ``3.0.0-beta.2`` fixable."""
    events = ({"introduced": "0"}, {"fixed": "3.0.0-beta.4"})
    assert _fixed(*events, version="3.0.0-beta.2") is True
    assert _fixed(*events, version="3.0.0") is False


def test_has_fix_counts_a_fix_in_any_alternative_range() -> None:
    """Several ranges in one entry are alternatives, as in the real jszip record."""
    entry = {
        "package": {"name": "jspdf", "ecosystem": "npm"},
        "ranges": [
            {"type": "SEMVER", "events": [{"introduced": "3.0.0"}, {"fixed": "3.7.0"}]},
            {"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "2.7.0"}]},
        ],
    }
    record = {"id": "A", "affected": [entry]}
    assert audit._has_fix(record, "jspdf", "3.2.0") is True
    assert audit._has_fix(record, "jspdf", "2.0.0") is True
    assert audit._has_fix(record, "jspdf", "3.7.0") is False


def test_has_fix_reads_every_range_even_after_an_earlier_fix() -> None:
    """A malformed later range raises whether or not an earlier range names a fix."""
    entry = {
        "package": {"name": "jspdf", "ecosystem": "npm"},
        "ranges": [
            {"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "3"}]},
            {"type": "SEMVER", "events": [{"introduced": "0"}, {"fixed": "latest"}]},
        ],
    }
    with pytest.raises(ValueError, match="OSV version"):
        audit._has_fix({"id": "A", "affected": [entry]}, "jspdf", "2.5.1")


def _record(*ranges: list[dict[str, str]], **entry_fields: object) -> dict[str, object]:
    """Build one record whose single entry holds several SEMVER ranges."""
    entry: dict[str, object] = {
        "package": {"name": "jspdf", "ecosystem": "npm"},
        "ranges": [{"type": "SEMVER", "events": list(events)} for events in ranges],
        **entry_fields,
    }
    return {"id": "A", "affected": [entry]}


def test_has_fix_needs_a_release_outside_every_overlapping_range() -> None:
    """A fix in one range does not help while another range still covers the release."""
    unfixed_overlap = _record(
        [{"introduced": "0"}, {"fixed": "4.0.0"}],
        [{"introduced": "0"}],
    )
    assert audit._has_fix(unfixed_overlap, "jspdf", "3.0.0") is False

    covered_until_later = _record(
        [{"introduced": "0"}, {"fixed": "4.0.0"}],
        [{"introduced": "0"}, {"fixed": "5.0.0"}],
    )
    assert audit._has_fix(covered_until_later, "jspdf", "3.0.0") is True


def test_has_fix_treats_introduced_zero_as_before_every_version() -> None:
    """OSV's ``0`` sorts below pre-releases of ``0.0.0``, which are still affected."""
    events = ({"introduced": "0"}, {"fixed": "1.0.0"})
    assert _fixed(*events, version="0.0.0-beta.1") is True
    boundaries = audit._boundaries(list(events), "A")
    assert audit._range_affects(boundaries, audit._version_key("0.0.0-a", "A")) is True


@pytest.mark.parametrize(
    "event",
    [{"fixd": "4.0.0"}, {"Fixed": "4.0.0"}, {"commit": "abc"}],
)
def test_has_fix_rejects_an_event_kind_it_does_not_know(event: dict[str, str]) -> None:
    """A misspelled key must not read as "no fix"."""
    with pytest.raises(ValueError, match="event kind"):
        _fixed({"introduced": "0"}, event)


@pytest.mark.parametrize("event", [{}, {"fixed": "4.0.0", "last_affected": "5.0.0"}])
def test_has_fix_rejects_an_event_that_is_not_exactly_one_boundary(event: dict[str, str]) -> None:
    """An empty event or one with two kinds is malformed."""
    with pytest.raises(ValueError, match="exactly one boundary"):
        _fixed({"introduced": "0"}, event)


def test_has_fix_rejects_a_range_with_no_introduced_event() -> None:
    """A range must say where it starts."""
    with pytest.raises(ValueError, match="no introduced event"):
        _fixed({"fixed": "4.0.0"})


def test_range_affects_follows_last_affected_and_limit() -> None:
    """``last_affected`` ends the interval after its version and ``limit`` before it."""
    last = audit._boundaries([{"introduced": "0"}, {"last_affected": "3"}], "A")
    assert audit._range_affects(last, audit._version_key("3", "A")) is True
    assert audit._range_affects(last, audit._version_key("3.0.1", "A")) is False

    limit = audit._boundaries([{"introduced": "0"}, {"limit": "5"}], "A")
    assert audit._range_affects(limit, audit._version_key("4.9.9", "A")) is True
    assert audit._range_affects(limit, audit._version_key("5", "A")) is False


def test_has_fix_finds_a_fix_after_a_last_affected_boundary() -> None:
    """A fixed release past a ``last_affected`` boundary is a usable fix."""
    assert _fixed({"introduced": "0"}, {"last_affected": "3"}, {"fixed": "5"}, version="3") is True


def test_has_fix_is_false_when_the_fixed_release_is_listed_as_affected() -> None:
    """An explicit ``versions`` list keeps a release affected whatever the ranges say."""
    listed = _record([{"introduced": "0"}, {"fixed": "4.0.0"}], versions=["3.0.0", "4.0.0"])
    assert audit._has_fix(listed, "jspdf", "3.0.0") is False


@pytest.mark.parametrize("listed", ["latest", "v4.0.0", 5, "1.0.0-a..b"])
def test_has_fix_rejects_a_listed_version_it_cannot_order(listed: object) -> None:
    """A listed ``v4.0.0`` could be the fixed ``4.0.0``, so an unreadable value is not skipped."""
    record = _record([{"introduced": "0"}, {"fixed": "4.0.0"}], versions=["3.0.0", listed])
    with pytest.raises(ValueError, match="OSV version"):
        audit._has_fix(record, "jspdf", "3.0.0")


def test_has_fix_rejects_a_versions_field_that_is_not_a_list() -> None:
    """Unreadable version data fails closed."""
    record = _record([{"introduced": "0"}, {"fixed": "4.0.0"}], versions="3.0.0")
    with pytest.raises(ValueError, match="'versions' must be a list"):
        audit._has_fix(record, "jspdf", "3.0.0")


def test_has_fix_reads_ecosystem_ranges_and_skips_git_ranges() -> None:
    """An ECOSYSTEM range compares like SEMVER, and a GIT range carries no release version."""
    ecosystem = {
        "id": "A",
        "affected": [_affected({"introduced": "0"}, {"fixed": "3"}, range_type="ECOSYSTEM")],
    }
    assert audit._has_fix(ecosystem, "jspdf", "2.5.1") is True

    git = {
        "id": "A",
        "affected": [_affected({"introduced": "0"}, {"fixed": "abc123"}, range_type="GIT")],
    }
    assert audit._has_fix(git, "jspdf", "2.5.1") is False


def test_has_fix_ignores_unknown_event_kinds() -> None:
    """A limit event is not a release boundary."""
    assert _fixed({"introduced": "0"}, {"limit": "*"}) is False


@pytest.mark.parametrize(
    ("events", "version"),
    [
        (({"introduced": "0"}, {"fixed": "latest"}), "2.5.1"),
        (({"introduced": "0"}, {"fixed": 3}), "2.5.1"),
        (({"introduced": "0"}, {"fixed": "1.0.0-a..b"}), "2.5.1"),
        (({"introduced": "0"}, {"fixed": "3"}), "not-a-version"),
    ],
)
def test_has_fix_fails_closed_on_versions_it_cannot_order(
    events: tuple[dict[str, object], ...], version: str
) -> None:
    """A value that is not a semantic version raises instead of guessing an order."""
    record = {"id": "A", "affected": [_affected(*events)]}
    with pytest.raises(ValueError, match="OSV version"):
        audit._has_fix(record, "jspdf", version)


_PACKAGE = {"name": "jspdf", "ecosystem": "npm"}
_EVENTS = [{"introduced": "0"}, {"fixed": "5"}]

_MALFORMED_RECORDS = [
    {"id": "A", "affected": "x"},
    {"id": "A", "affected": ["x"]},
    {"id": "A"},
    {"id": "A", "affected": []},
    {"id": "A", "affected": [{"package": "jspdf"}]},
    {"id": "A", "affected": [_affected(name="other")]},
    {"id": "A", "affected": [{"package": _PACKAGE, "ranges": "x"}]},
    {"id": "A", "affected": [{"package": _PACKAGE, "ranges": ["x"]}]},
    {"id": "A", "affected": [{"package": _PACKAGE, "ranges": [{"events": "x"}]}]},
    {"id": "A", "affected": [{"package": _PACKAGE, "ranges": [{"events": ["x"]}]}]},
    # A range with no type or an unknown type could hide a fix, so it is rejected.
    {"id": "A", "affected": [{"package": _PACKAGE, "ranges": [{"events": _EVENTS}]}]},
    {"id": "A", "affected": [_affected(*_EVENTS, range_type="SEMVR")]},
    # A type that is not a string must raise ValueError, not crash on a set lookup.
    {"id": "A", "affected": [_affected(*_EVENTS, range_type=["SEMVER"])]},
    {"id": "A", "affected": [_affected(*_EVENTS, range_type=5)]},
]


@pytest.mark.parametrize("record", _MALFORMED_RECORDS)
def test_has_fix_fails_closed_on_malformed_or_missing_affected_data(
    record: dict[str, object],
) -> None:
    """Unreadable data raises instead of reading as "no fix"."""
    with pytest.raises(ValueError, match="OSV"):
        audit._has_fix(record, "jspdf", "2.5.1")


# ---- collect_findings and the exception policy ----


def test_collect_findings_queries_each_package_version_once() -> None:
    """Two bundles of one package version share a single query."""
    calls: list[tuple[str, str]] = []

    def query(package: str, version: str) -> object:
        calls.append((package, version))
        return {"vulns": [{"id": f"GHSA-{package}", "affected": [_affected(name=package)]}]}

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


def test_audit_applies_an_exception_through_its_review_by_date() -> None:
    """An exception still applies on its review_by date and stops the day after."""
    on_the_day, errors = audit.audit_findings(
        today=date(2026, 5, 31),
        exceptions=(_exception(review_by=date(2026, 5, 31)),),
        findings=(_finding(),),
    )
    assert errors == ()
    assert len(on_the_day) == 1


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


# ---- main ----


def _patch_main(
    monkeypatch: pytest.MonkeyPatch,
    *,
    exceptions: tuple[VulnerabilityExceptionEntry, ...] = (),
    assets: tuple[VendoredAsset, ...] = (),
    findings: tuple[audit.VendoredFinding, ...] = (),
    error: Exception | None = None,
    manifest_error: Exception | None = None,
) -> None:
    """Replace main's config, manifest, and findings so only main's own logic runs."""

    def load_manifest() -> tuple[VendoredAsset, ...]:
        if manifest_error is not None:
            raise manifest_error
        return assets

    def collect(_assets: object) -> tuple[audit.VendoredFinding, ...]:
        if error is not None:
            raise error
        return findings

    monkeypatch.setattr(audit, "load_security_audit_exceptions", lambda **_kwargs: exceptions)
    monkeypatch.setattr(audit, "_load_manifest", load_manifest)
    monkeypatch.setattr(audit, "collect_findings", collect)


def test_main_passes_and_says_how_many_package_versions_it_checked(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A clean manifest exits 0 and the count shows the audit looked at something."""
    _patch_main(monkeypatch, assets=(_asset(path="a"), _asset(path="b"), _asset("jszip", "3.10.1")))

    assert audit.main([]) == 0
    assert (
        "Vendored dependency audit passed. Package versions checked: 2." in capsys.readouterr().out
    )


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


@pytest.mark.parametrize("error", [OSError("offline"), BadStatusLine("garbage")])
def test_main_fails_when_osv_cannot_be_reached(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception
) -> None:
    """A network failure fails the audit instead of passing silently."""
    _patch_main(monkeypatch, error=error)

    assert audit.main([]) == 1
    assert "could not query OSV" in capsys.readouterr().out


def test_main_fails_when_the_osv_response_is_unusable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A parse failure blames the response, not the network."""
    _patch_main(monkeypatch, error=ValueError("OSV 'affected' must be a list for A"))

    assert audit.main([]) == 1
    output = capsys.readouterr().out
    assert "could not use the OSV response" in output
    assert "could not query OSV" not in output


@pytest.mark.parametrize("error", [FileNotFoundError("missing"), ValueError("bad manifest")])
def test_main_reports_manifest_errors_separately_from_osv_errors(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], error: Exception
) -> None:
    """A manifest failure never reaches OSV and does not blame it."""
    _patch_main(monkeypatch, manifest_error=error)

    assert audit.main([]) == 1
    output = capsys.readouterr().out
    assert "could not read config/vendored_assets.json" in output
    assert "OSV" not in output


def _stub_osv_server(monkeypatch: pytest.MonkeyPatch, record: dict[str, object]) -> None:
    """Make ``urlopen`` answer every OSV query with one advisory record."""
    body = json.dumps({"vulns": [record]}).encode()
    monkeypatch.setattr(audit, "urlopen", lambda _request, **_kwargs: _Response(body))


def test_main_runs_end_to_end_through_the_real_parser(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Only the network and the manifest are stubbed, so query, parse, and policy all run."""
    record = {
        "id": "GHSA-1",
        "aliases": ["CVE-1"],
        "affected": [_affected({"introduced": "0"}, {"fixed": "4.2.1"})],
    }
    _stub_osv_server(monkeypatch, record)
    monkeypatch.setattr(audit, "_load_manifest", lambda: (_asset(),))
    monkeypatch.setattr(audit, "load_security_audit_exceptions", lambda **_kwargs: ())

    assert audit.main([]) == 1
    assert (
        "Unreviewed vendored vulnerability: jspdf 2.5.1 GHSA-1 (a fixed version exists)"
        in capsys.readouterr().out
    )

    monkeypatch.setattr(
        audit,
        "load_security_audit_exceptions",
        lambda **_kwargs: (_exception(vulnerability_id="CVE-1"),),
    )

    assert audit.main([]) == 0
    assert "Package versions checked: 1." in capsys.readouterr().out
