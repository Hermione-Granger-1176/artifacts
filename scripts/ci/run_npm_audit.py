#!/usr/bin/env python3
"""Run a policy-driven npm dependency security audit.

A bare ``npm audit`` fails the build on any advisory, including unfixable
transitive ones, with no principled override. This module wraps
``npm audit --json`` with the same reviewed-exception policy the Python audit
uses: exceptions expire on a ``review_by`` date, an exception is evicted once a
fix becomes available (when it was granted only while unfixed), and unused
exceptions are reported so the allow-list never rots.

Exceptions live under ``npm_vulnerability_exceptions`` in
``config/security_audit.json`` and share the schema of the Python entries.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date

from scripts.ci.run_security_audit import (
    NPM_EXCEPTIONS_KEY,
    VulnerabilityExceptionEntry,
    _load_security_audit_exceptions,
)

_GHSA_PATTERN = re.compile(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}", re.IGNORECASE)


@dataclass(frozen=True)
class NpmVulnerabilityFinding:
    """One advisory reported by ``npm audit`` for a package."""

    advisory_id: str
    aliases: tuple[str, ...]
    package: str
    severity: str
    fix_available: bool

    @property
    def all_ids(self) -> tuple[str, ...]:
        """Return the primary advisory id plus any aliases."""
        return (self.advisory_id, *self.aliases)


def _advisory_ids(via: dict[str, object]) -> tuple[str, tuple[str, ...]]:
    """Return the primary advisory id and aliases for one ``via`` advisory.

    npm identifies advisories by a numeric ``source`` id and a GitHub advisory
    ``url``. The GHSA id is preferred as the stable primary id; the numeric
    source id is kept as an alias so either form matches a reviewed exception.
    """
    url = str(via.get("url", ""))
    ghsa_match = _GHSA_PATTERN.search(url)
    ghsa = ghsa_match.group(0).upper() if ghsa_match else ""

    source = via.get("source")
    source_id = str(source) if source is not None else ""

    if ghsa:
        aliases = (source_id,) if source_id else ()
        return ghsa, aliases
    return source_id, ()


def _parse_advisory(
    via: object, *, package: str, fix_available: bool
) -> NpmVulnerabilityFinding | None:
    """Parse one ``via`` entry into a finding, or None for a package reference."""
    # ``via`` items are either advisory objects or bare package-name strings
    # that point at another vulnerable dependency; only objects are advisories.
    if not isinstance(via, dict):
        return None

    advisory_id, aliases = _advisory_ids(via)
    if not advisory_id:
        raise ValueError(
            f"npm audit advisory is missing both a GHSA url and a numeric source id: {package}"
        )
    return NpmVulnerabilityFinding(
        advisory_id=advisory_id,
        aliases=aliases,
        package=package,
        severity=str(via.get("severity", "")),
        fix_available=fix_available,
    )


def _parse_npm_audit(payload: dict[str, object]) -> tuple[NpmVulnerabilityFinding, ...]:
    """Parse ``npm audit --json`` output into vulnerability findings."""
    vulnerabilities = payload.get("vulnerabilities", {})
    if not isinstance(vulnerabilities, dict):
        raise ValueError("npm audit 'vulnerabilities' must be an object")

    findings: list[NpmVulnerabilityFinding] = []
    for name, node in vulnerabilities.items():
        if not isinstance(node, dict):
            raise ValueError(f"npm audit vulnerability entries must be objects: {name}")

        via = node.get("via", [])
        if not isinstance(via, list):
            raise ValueError(f"npm audit 'via' must be a list: {name}")

        # ``fixAvailable`` is False, True, or an object describing the fix.
        fix_available = bool(node.get("fixAvailable", False))
        package = str(node.get("name", name))
        for entry in via:
            finding = _parse_advisory(entry, package=package, fix_available=fix_available)
            if finding is not None:
                findings.append(finding)

    return tuple(findings)


def _run_npm_audit(npm_executable: str = "npm") -> tuple[NpmVulnerabilityFinding, ...]:
    """Run ``npm audit --json`` and return parsed vulnerability findings."""
    try:
        result = subprocess.run(
            [npm_executable, "audit", "--json"],
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("npm audit timed out after 120 seconds") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"npm executable not found: {npm_executable}. Install Node.js to run the audit."
        ) from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"npm audit returned invalid JSON: {stderr}") from exc

    if not isinstance(payload, dict):
        raise ValueError("npm audit JSON must be an object")

    error = payload.get("error")
    if error:
        summary = error.get("summary") if isinstance(error, dict) else str(error)
        raise RuntimeError(f"npm audit reported an error: {summary or 'unknown error'}")

    return _parse_npm_audit(payload)


def _matches_exception(
    exception: VulnerabilityExceptionEntry, finding: NpmVulnerabilityFinding
) -> bool:
    """Return whether a reviewed exception matches one npm finding."""
    return (
        exception.package.lower() == finding.package.lower()
        and exception.vulnerability_id in finding.all_ids
    )


def _audit_npm_dependencies(
    *,
    today: date,
    exceptions: tuple[VulnerabilityExceptionEntry, ...],
    findings: tuple[NpmVulnerabilityFinding, ...],
) -> tuple[
    tuple[tuple[NpmVulnerabilityFinding, VulnerabilityExceptionEntry], ...],
    tuple[str, ...],
]:
    """Run policy checks over npm audit findings and reviewed exceptions."""
    ignored: list[tuple[NpmVulnerabilityFinding, VulnerabilityExceptionEntry]] = []
    errors: list[str] = []
    matched_exception_keys: set[tuple[str, str]] = set()

    for finding in findings:
        matching_exceptions = tuple(
            entry for entry in exceptions if _matches_exception(entry, finding)
        )
        if not matching_exceptions:
            errors.append(
                "Unreviewed npm vulnerability: "
                f"{finding.package} {finding.severity} {finding.advisory_id}"
            )
            continue

        matched_exception_keys.update(entry.key for entry in matching_exceptions)
        finding_errors = []
        for matching_exception in matching_exceptions:
            if today > matching_exception.review_by:
                finding_errors.append(
                    "Expired npm vulnerability exception: "
                    f"{matching_exception.package} "
                    f"{matching_exception.vulnerability_id} "
                    f"review_by={matching_exception.review_by.isoformat()}"
                )
            elif matching_exception.ignore_only_without_fix and finding.fix_available:
                finding_errors.append(
                    "npm vulnerability exception must be removed because a fix "
                    "is available: "
                    f"{finding.package} {finding.advisory_id}"
                )

        if finding_errors:
            errors.extend(finding_errors)
            continue

        ignored.append((finding, matching_exceptions[0]))

    for exception in exceptions:
        if exception.key not in matched_exception_keys:
            errors.append(
                "Unused npm vulnerability exception: "
                f"{exception.package} {exception.vulnerability_id}"
            )

    return tuple(ignored), tuple(errors)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Run the npm dependency security audit")
    parser.add_argument(
        "--npm",
        default="npm",
        help="npm executable to invoke (defaults to 'npm')",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the policy-driven npm security audit."""
    args = _parse_args(argv)
    exceptions = _load_security_audit_exceptions(config_key=NPM_EXCEPTIONS_KEY)
    findings = _run_npm_audit(args.npm)
    ignored, errors = _audit_npm_dependencies(
        today=date.today(),
        exceptions=exceptions,
        findings=findings,
    )

    if ignored:
        print("Reviewed npm vulnerability exceptions:")
        for finding, exception in ignored:
            print(
                "- "
                f"{finding.package} {finding.severity} "
                f"{finding.advisory_id} "
                f"(review by {exception.review_by.isoformat()})"
            )
            print(f"  reason: {exception.reason}")

    if errors:
        print("npm dependency audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("npm dependency audit passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
