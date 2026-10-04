#!/usr/bin/env python3
"""Audit vendored third-party bundles against the OSV advisory database.

``npm audit`` and ``pip-audit`` read lock files, so they never see the bundles
under ``apps/<slug>/js/vendor/``. ``config/vendored_assets.json`` pins each
bundle by hash, which proves the file did not change but says nothing about
whether its version has a published advisory.

This script asks OSV (https://osv.dev) about every package and version in that
manifest and applies the same reviewed-exception policy as the npm and Python
audits: an exception stops applying after its ``review_by`` date, is rejected
once a fix exists when it was granted only while unfixed, and is reported when
nothing matches it any more.

Exceptions live under ``vendored_vulnerability_exceptions`` in
``config/security_audit.json`` and share the schema of the npm entries.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from datetime import date
from http.client import HTTPException
from typing import TYPE_CHECKING
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from scripts.ci.security_audit_policy import (
    VENDORED_EXCEPTIONS_KEY,
    VulnerabilityExceptionEntry,
    load_security_audit_exceptions,
)
from scripts.lint.check_vendored_assets import VendoredAsset, _load_manifest

if TYPE_CHECKING:
    from collections.abc import Callable

OSV_QUERY_URL = "https://api.osv.dev/v1/query"
OSV_ECOSYSTEM = "npm"
# OSV starts paginating a query that runs past 20 seconds, so the client waits
# longer than that and follows the page token instead of timing out first.
OSV_TIMEOUT_SECONDS = 45
OSV_MAX_PAGES = 5
# This audit runs in the required PR gate, so one dropped connection must not
# fail a pull request. A transient failure retries. A bad response never does.
OSV_ATTEMPTS = 3
OSV_RETRY_DELAY_SECONDS = 2

# Range types whose events are release versions that can be compared. GIT
# ranges list commit hashes and say nothing about a release. OSV defines no
# other type, so any other value is malformed data.
_COMPARABLE_RANGE_TYPES = frozenset({"SEMVER", "ECOSYSTEM"})
_KNOWN_RANGE_TYPES = _COMPARABLE_RANGE_TYPES | {"GIT"}
_EVENT_KINDS = frozenset({"introduced", "fixed", "last_affected", "limit"})
_SEMVER_PATTERN = re.compile(r"(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?")

# (release numbers, 1 for a release or 0 for a pre-release, pre-release identifiers)
VersionKey = tuple[tuple[int, ...], int, tuple[tuple[int, int, str], ...]]
# One event of an OSV range: its sort key and its kind.
Boundary = tuple[VersionKey, str]

# OSV defines ``introduced: "0"`` as before every version, including pre-releases
# such as ``0.0.0-beta.1`` that sort below the release ``0.0.0``.
_BEFORE_ALL: VersionKey = ((-1,), 0, ())


@dataclass(frozen=True)
class VendoredFinding:
    """One OSV advisory that affects a vendored package version."""

    advisory_id: str
    aliases: tuple[str, ...]
    package: str
    version: str
    fix_available: bool

    @property
    def all_ids(self) -> tuple[str, ...]:
        """Return the primary advisory id plus aliases."""
        return (self.advisory_id, *self.aliases)


def _is_transient(error: Exception) -> bool:
    """Return whether a failed request is worth retrying.

    A timeout, a dropped connection, a truncated body, a 429, and a 5xx can
    clear on their own. Any other 4xx means OSV rejected the request itself.
    """
    if isinstance(error, HTTPError):
        return error.code == 429 or error.code >= 500
    return True


def _post_osv(body: bytes) -> object:
    """POST one query to OSV and return the decoded JSON, retrying transient errors."""
    for attempt in range(1, OSV_ATTEMPTS + 1):
        request = Request(
            OSV_QUERY_URL,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=OSV_TIMEOUT_SECONDS) as response:
                payload: object = json.load(response)
        except (OSError, HTTPException) as error:
            if attempt == OSV_ATTEMPTS or not _is_transient(error):
                raise
            time.sleep(attempt * OSV_RETRY_DELAY_SECONDS)
        else:
            return payload
    raise AssertionError("unreachable")  # pragma: no cover


def query_osv(package: str, version: str) -> object:
    """Return the OSV response for one npm package version, with every page merged.

    A response whose shape is not an object with a ``vulns`` list is returned
    unchanged so ``parse_findings`` can reject it.
    """
    vulnerabilities: list[object] = []
    page_token: str | None = None
    for _ in range(OSV_MAX_PAGES):
        query: dict[str, object] = {
            "package": {"name": package, "ecosystem": OSV_ECOSYSTEM},
            "version": version,
        }
        if page_token is not None:
            query["page_token"] = page_token
        payload = _post_osv(json.dumps(query).encode("utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("vulns", []), list):
            return payload
        vulnerabilities.extend(payload.get("vulns", []))
        token = payload.get("next_page_token")
        if token is None:
            return {"vulns": vulnerabilities}
        if not isinstance(token, str) or not token:
            raise ValueError(f"OSV returned an invalid page token for {package} {version}")
        page_token = token
    raise ValueError(f"OSV returned more than {OSV_MAX_PAGES} pages for {package} {version}")


def _is_queried_package(entry: dict[str, object], package: str) -> bool:
    """Return whether one ``affected`` entry describes the queried npm package."""
    info = entry.get("package")
    return (
        isinstance(info, dict)
        and info.get("ecosystem") == OSV_ECOSYSTEM
        and isinstance(info.get("name"), str)
        and info["name"].casefold() == package.casefold()
    )


def _version_key(value: object, advisory: object) -> VersionKey:
    """Return a sortable key following SemVer 2.0 precedence.

    A release sorts after every pre-release of the same numbers. Numeric
    pre-release identifiers compare as numbers and sort before alphanumeric
    ones, and a shorter identifier list sorts first. Missing release numbers
    count as zero, so OSV's ``0`` and ``3.5`` order against ``4.2.1``. Build
    metadata is ignored. Any other form raises ``ValueError``, so the audit
    fails closed instead of guessing an order.
    """
    match = _SEMVER_PATTERN.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f"OSV version {value!r} is not a semantic version for {advisory}")
    numbers = [int(part) for part in match.group(1).split(".")]
    numbers.extend([0] * (3 - len(numbers)))
    while len(numbers) > 3 and numbers[-1] == 0:
        numbers.pop()
    prerelease = match.group(2)
    if prerelease is None:
        return (tuple(numbers), 1, ())
    identifiers = prerelease.split(".")
    if "" in identifiers:
        raise ValueError(f"OSV version {value!r} is not a semantic version for {advisory}")
    return (
        tuple(numbers),
        0,
        tuple((0, int(i), "") if i.isdecimal() else (1, 0, i) for i in identifiers),
    )


def _boundaries(events: list[dict[str, object]], advisory: object) -> list[Boundary]:
    """Return the sorted-by-kind boundaries of one SEMVER or ECOSYSTEM range.

    Each event holds exactly one of ``introduced``, ``fixed``, ``last_affected``,
    or ``limit``, and a range needs an ``introduced`` event. Anything else is
    malformed and raises, so a misspelled key cannot read as "no fix". A
    ``limit`` of ``*`` bounds nothing and is dropped.
    """
    boundaries: list[Boundary] = []
    for event in events:
        if len(event) != 1:
            raise ValueError(f"OSV event must hold exactly one boundary for {advisory}")
        ((kind, raw),) = event.items()
        if kind not in _EVENT_KINDS:
            raise ValueError(f"OSV event kind {kind!r} is not recognized for {advisory}")
        if kind == "limit" and raw == "*":
            continue
        key = _BEFORE_ALL if kind == "introduced" and raw == "0" else _version_key(raw, advisory)
        boundaries.append((key, kind))
    if not any(kind == "introduced" for _, kind in boundaries):
        raise ValueError(f"OSV range has no introduced event for {advisory}")
    return boundaries


def _range_affects(boundaries: list[Boundary], version: VersionKey) -> bool:
    """Return whether one range contains the version, following the OSV algorithm.

    Boundaries apply in version order. ``introduced`` starts an interval,
    ``fixed`` and ``limit`` end it before their version, and ``last_affected``
    ends it after its version. On a tie ``introduced`` applies last, so a fix
    and a reintroduction at one version leave that version affected.
    """
    affected = False
    ordered = sorted(boundaries, key=lambda boundary: (boundary[0], boundary[1] == "introduced"))
    for key, kind in ordered:
        if kind == "introduced":
            affected = affected or version >= key
        elif kind == "last_affected":
            affected = affected and not version > key
        elif version >= key:
            affected = False
    return affected


def _comparable_ranges(entry: dict[str, object], advisory: object) -> list[list[Boundary]]:
    """Return the boundaries of every SEMVER or ECOSYSTEM range of one entry.

    Every range is validated, so a malformed one raises whatever the others
    hold. GIT ranges list commit hashes and are skipped.
    """
    ranges = entry.get("ranges", [])
    if not isinstance(ranges, list):
        raise ValueError(f"OSV 'ranges' must be a list for {advisory}")

    comparable: list[list[Boundary]] = []
    for version_range in ranges:
        events = version_range.get("events", []) if isinstance(version_range, dict) else None
        if not isinstance(events, list) or not all(isinstance(e, dict) for e in events):
            raise ValueError(f"OSV range 'events' must be a list of objects for {advisory}")
        range_type = version_range.get("type")
        if not isinstance(range_type, str) or range_type not in _KNOWN_RANGE_TYPES:
            raise ValueError(
                f"OSV range type {range_type!r} is not SEMVER, ECOSYSTEM, or GIT for {advisory}"
            )
        if range_type in _COMPARABLE_RANGE_TYPES:
            comparable.append(_boundaries(events, advisory))
    return comparable


def _listed_versions(entry: dict[str, object], advisory: object) -> set[VersionKey]:
    """Return the keys of the versions an entry lists as affected.

    A listed string that is not a semantic version can never equal a fixed
    release being tested, so it is skipped.
    """
    versions = entry.get("versions", [])
    if not isinstance(versions, list):
        raise ValueError(f"OSV 'versions' must be a list for {advisory}")
    keys: set[VersionKey] = set()
    for listed in versions:
        try:
            keys.add(_version_key(listed, advisory))
        except ValueError:
            continue
    return keys


def _has_fix(vulnerability: dict[str, object], package: str, version: str) -> bool:
    """Return whether an OSV record names a release that fixes the queried version.

    One record can cover several packages, so only the ``affected`` entries for
    ``package`` count. The ranges of those entries form a union: a fixed release
    counts only when it is later than ``version`` and lies outside every range
    and every listed version. A fix in one range does not help while another
    range still covers it. A malformed structure, an unknown range type, or a
    record with no entry for the package raises ``ValueError`` so the audit
    fails closed instead of treating unreadable data as "no fix".
    """
    advisory = vulnerability.get("id")
    affected = vulnerability.get("affected", [])
    if not isinstance(affected, list):
        raise ValueError(f"OSV 'affected' must be a list for {advisory}")
    queried = _version_key(version, advisory)

    entries = []
    for entry in affected:
        if not isinstance(entry, dict):
            raise ValueError(f"OSV 'affected' entries must be objects for {advisory}")
        if _is_queried_package(entry, package):
            entries.append(entry)
    if not entries:
        raise ValueError(f"OSV record {advisory} has no affected entry for npm package {package}")

    ranges = [r for entry in entries for r in _comparable_ranges(entry, advisory)]
    listed = set().union(*(_listed_versions(entry, advisory) for entry in entries))
    candidates = {
        key
        for boundaries in ranges
        for key, kind in boundaries
        if kind == "fixed" and key > queried
    }
    return any(
        candidate not in listed and not any(_range_affects(r, candidate) for r in ranges)
        for candidate in candidates
    )


def _aliases(vulnerability: dict[str, object]) -> tuple[str, ...]:
    """Return the string aliases of one OSV record, or none when the field is malformed."""
    aliases = vulnerability.get("aliases", [])
    if not isinstance(aliases, list):
        return ()
    return tuple(alias for alias in aliases if isinstance(alias, str))


def parse_findings(package: str, version: str, payload: object) -> tuple[VendoredFinding, ...]:
    """Parse one OSV response into findings, rejecting an unexpected shape."""
    if not isinstance(payload, dict):
        raise ValueError(f"OSV returned a non-object response for {package} {version}")
    if "next_page_token" in payload:
        raise ValueError(f"OSV paginated the response for {package} {version}")
    vulnerabilities = payload.get("vulns", [])
    if not isinstance(vulnerabilities, list):
        raise ValueError(f"OSV 'vulns' must be a list for {package} {version}")

    findings: list[VendoredFinding] = []
    for vulnerability in vulnerabilities:
        advisory_id = vulnerability.get("id") if isinstance(vulnerability, dict) else None
        if not isinstance(advisory_id, str) or not advisory_id:
            raise ValueError(f"OSV returned an advisory without an id for {package} {version}")
        findings.append(
            VendoredFinding(
                advisory_id=advisory_id,
                aliases=_aliases(vulnerability),
                package=package,
                version=version,
                fix_available=_has_fix(vulnerability, package, version),
            )
        )
    return tuple(findings)


def collect_findings(
    assets: tuple[VendoredAsset, ...],
    query: Callable[[str, str], object] = query_osv,
) -> tuple[VendoredFinding, ...]:
    """Query OSV once per distinct package and version in the manifest."""
    findings: list[VendoredFinding] = []
    seen: set[tuple[str, str]] = set()
    for asset in assets:
        key = (asset.package, asset.version)
        if key in seen:
            continue
        seen.add(key)
        findings.extend(parse_findings(*key, query(*key)))
    return tuple(findings)


def _matches_exception(exception: VulnerabilityExceptionEntry, finding: VendoredFinding) -> bool:
    """Return whether a reviewed exception covers one finding, ignoring id case."""
    finding_ids = {advisory_id.upper() for advisory_id in finding.all_ids}
    return (
        exception.package.casefold() == finding.package.casefold()
        and exception.vulnerability_id.upper() in finding_ids
    )


def audit_findings(
    *,
    today: date,
    exceptions: tuple[VulnerabilityExceptionEntry, ...],
    findings: tuple[VendoredFinding, ...],
) -> tuple[tuple[tuple[VendoredFinding, VulnerabilityExceptionEntry], ...], tuple[str, ...]]:
    """Apply the reviewed-exception policy and return (ignored findings, errors)."""
    ignored: list[tuple[VendoredFinding, VulnerabilityExceptionEntry]] = []
    errors: list[str] = []
    matched_keys: set[tuple[str, str]] = set()

    for finding in findings:
        label = f"{finding.package} {finding.version} {finding.advisory_id}"
        matching = tuple(entry for entry in exceptions if _matches_exception(entry, finding))
        matched_keys.update(entry.key for entry in matching)
        if len(matching) > 1:
            errors.append(f"Multiple vendored vulnerability exceptions match one advisory: {label}")
            continue
        if not matching:
            fix_hint = " (a fixed version exists)" if finding.fix_available else ""
            errors.append(f"Unreviewed vendored vulnerability: {label}{fix_hint}")
            continue

        exception = matching[0]
        if today > exception.review_by:
            errors.append(
                f"Expired vendored vulnerability exception: {label} "
                f"review_by={exception.review_by.isoformat()}"
            )
        elif exception.ignore_only_without_fix and finding.fix_available:
            errors.append(
                f"Vendored vulnerability exception must be removed because a fix is available: "
                f"{label}"
            )
        else:
            ignored.append((finding, exception))

    errors.extend(
        f"Unused vendored vulnerability exception: {exception.package} {exception.vulnerability_id}"
        for exception in exceptions
        if exception.key not in matched_keys
    )
    return tuple(ignored), tuple(errors)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. The audit takes none, so this only serves ``--help``."""
    summary = (__doc__ or "").splitlines()[0]
    return argparse.ArgumentParser(description=summary).parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the vendored-bundle advisory audit."""
    _parse_args(argv)
    exceptions = load_security_audit_exceptions(config_key=VENDORED_EXCEPTIONS_KEY)
    try:
        assets = _load_manifest()
    except (OSError, ValueError) as exc:
        print(f"Vendored dependency audit could not read config/vendored_assets.json: {exc}")
        return 1
    try:
        findings = collect_findings(assets)
    except (OSError, HTTPException) as exc:
        print(f"Vendored dependency audit could not query OSV: {exc}")
        return 1
    except ValueError as exc:
        print(f"Vendored dependency audit could not use the OSV response: {exc}")
        return 1

    ignored, errors = audit_findings(today=date.today(), exceptions=exceptions, findings=findings)

    if ignored:
        print("Reviewed vendored vulnerability exceptions:")
        for finding, exception in ignored:
            label = f"{finding.package} {finding.version} {finding.advisory_id}"
            print(f"- {label} (review by {exception.review_by.isoformat()})")
            print(f"  reason: {exception.reason}")

    if errors:
        print("Vendored dependency audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    checked = len({(asset.package, asset.version) for asset in assets})
    print(f"Vendored dependency audit passed. Package versions checked: {checked}.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
