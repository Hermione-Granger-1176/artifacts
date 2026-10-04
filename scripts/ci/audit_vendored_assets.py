#!/usr/bin/env python3
"""Audit vendored third-party bundles against the OSV advisory database.

``npm audit`` and ``pip-audit`` read lock files, so they never see the bundles
under ``apps/<slug>/js/vendor/``. ``config/vendored_assets.json`` pins each
bundle by hash, which proves the file did not change but says nothing about
whether its version has a published advisory.

This script asks OSV (https://osv.dev) about every package and version in that
manifest and applies the same reviewed-exception policy as the npm and Python
audits: an exception expires on its ``review_by`` date, is rejected once a fix
exists when it was granted only while unfixed, and is reported when nothing
matches it any more.

Exceptions live under ``vendored_vulnerability_exceptions`` in
``config/security_audit.json`` and share the schema of the npm entries.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING
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
OSV_TIMEOUT_SECONDS = 20


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


def query_osv(package: str, version: str) -> object:
    """Return the OSV JSON response for one npm package version."""
    body = json.dumps(
        {"package": {"name": package, "ecosystem": OSV_ECOSYSTEM}, "version": version}
    ).encode("utf-8")
    request = Request(
        OSV_QUERY_URL,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urlopen(request, timeout=OSV_TIMEOUT_SECONDS) as response:
        payload: object = json.load(response)
    return payload


def _is_queried_package(entry: dict[str, object], package: str) -> bool:
    """Return whether one ``affected`` entry describes the queried npm package."""
    info = entry.get("package")
    return (
        isinstance(info, dict)
        and info.get("ecosystem") == OSV_ECOSYSTEM
        and isinstance(info.get("name"), str)
        and info["name"].casefold() == package.casefold()
    )


def _has_fix(vulnerability: dict[str, object], package: str) -> bool:
    """Return whether an OSV record names a fixed version for the queried package.

    One record can cover several packages, so only the ``affected`` entry for
    ``package`` counts. A malformed structure, or a record with no entry for the
    package, raises ``ValueError`` so the audit fails closed instead of treating
    unreadable data as "no fix".
    """
    advisory = vulnerability.get("id")
    affected = vulnerability.get("affected", [])
    if not isinstance(affected, list):
        raise ValueError(f"OSV 'affected' must be a list for {advisory}")

    matched = False
    fixed = False
    for entry in affected:
        if not isinstance(entry, dict):
            raise ValueError(f"OSV 'affected' entries must be objects for {advisory}")
        if not _is_queried_package(entry, package):
            continue
        matched = True
        ranges = entry.get("ranges", [])
        if not isinstance(ranges, list):
            raise ValueError(f"OSV 'ranges' must be a list for {advisory}")
        for version_range in ranges:
            events = version_range.get("events", []) if isinstance(version_range, dict) else None
            if not isinstance(events, list) or not all(isinstance(e, dict) for e in events):
                raise ValueError(f"OSV range 'events' must be a list of objects for {advisory}")
            fixed = fixed or any("fixed" in event for event in events)

    if not matched:
        raise ValueError(f"OSV record {advisory} has no affected entry for npm package {package}")
    return fixed


def parse_findings(package: str, version: str, payload: object) -> tuple[VendoredFinding, ...]:
    """Parse one OSV response into findings, rejecting an unexpected shape."""
    if not isinstance(payload, dict):
        raise ValueError(f"OSV returned a non-object response for {package} {version}")
    vulnerabilities = payload.get("vulns", [])
    if not isinstance(vulnerabilities, list):
        raise ValueError(f"OSV 'vulns' must be a list for {package} {version}")

    findings: list[VendoredFinding] = []
    for vulnerability in vulnerabilities:
        advisory_id = vulnerability.get("id") if isinstance(vulnerability, dict) else None
        if not isinstance(advisory_id, str) or not advisory_id:
            raise ValueError(f"OSV returned an advisory without an id for {package} {version}")
        aliases = vulnerability.get("aliases", [])
        findings.append(
            VendoredFinding(
                advisory_id=advisory_id,
                aliases=tuple(alias for alias in aliases if isinstance(alias, str))
                if isinstance(aliases, list)
                else (),
                package=package,
                version=version,
                fix_available=_has_fix(vulnerability, package),
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


def main(argv: list[str] | None = None) -> int:
    """Run the vendored-bundle advisory audit."""
    argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None).parse_args(
        argv
    )
    exceptions = load_security_audit_exceptions(config_key=VENDORED_EXCEPTIONS_KEY)
    try:
        findings = collect_findings(_load_manifest())
    except (OSError, ValueError) as exc:
        print(f"Vendored dependency audit could not query OSV: {exc}")
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

    print("Vendored dependency audit passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
