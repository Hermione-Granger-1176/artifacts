#!/usr/bin/env python3
"""Run a policy-driven npm dependency security audit.

A bare ``npm audit --audit-level=high`` fails the build on any high or critical
advisory, including unfixable transitive ones, with no principled override.
This module wraps ``npm audit --json`` with the same reviewed-exception policy
the Python audit uses: exceptions expire on a ``review_by`` date, an exception
is evicted once a fix becomes available (when it was granted only while
unfixed), and unused exceptions are reported so the allow-list never rots.

``npm audit --audit-level`` only changes npm's exit code, and this wrapper
reads the JSON report instead, so the threshold is reapplied here. Every
severity is gated by default, matching the sibling artifacts repository; the
reviewed-exception policy, not a severity floor, is what silences a finding.
``--audit-level`` remains available to narrow an ad-hoc run.

Exceptions live under ``npm_vulnerability_exceptions`` in
``config/security_audit.json`` and share the schema of the Python entries.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from datetime import date

from scripts.ci.security_audit_policy import (
    NPM_EXCEPTIONS_KEY,
    VulnerabilityExceptionEntry,
    load_security_audit_exceptions,
)

_GHSA_PATTERN = re.compile(r"GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}", re.IGNORECASE)

# npm's severity ladder, weakest first. Parsing rejects unknown or absent
# severities, while _is_gated still treats an unexpected value as gated
# defensively.
SEVERITY_ORDER = ("info", "low", "moderate", "high", "critical")
DEFAULT_AUDIT_LEVEL = SEVERITY_ORDER[0]


def _is_gated(severity: str, audit_level: str) -> bool:
    """Return whether one advisory severity is at or above the audit level."""
    if severity not in SEVERITY_ORDER:
        return True
    return SEVERITY_ORDER.index(severity) >= SEVERITY_ORDER.index(audit_level)


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
    url_value = via.get("url", "")
    if not isinstance(url_value, str):
        raise ValueError("npm audit advisory 'url' must be a string")
    url = url_value
    ghsa_match = _GHSA_PATTERN.search(url)
    ghsa = ghsa_match.group(0).upper() if ghsa_match else ""

    source_id = ""
    if "source" in via:
        source = via["source"]
        if not isinstance(source, int) or isinstance(source, bool) or source < 0:
            raise ValueError("npm audit advisory 'source' must be a non-negative integer")
        source_id = str(source)

    if ghsa:
        aliases = (source_id,) if source_id else ()
        return ghsa, aliases
    return source_id, ()


def _parse_advisory(
    via: object, *, package: str, fix_available: bool
) -> NpmVulnerabilityFinding | None:
    """Parse one ``via`` entry into a finding, or None for a package reference."""
    # ``via`` items are either advisory objects or bare package-name strings
    # that point at another vulnerable dependency.
    if isinstance(via, str) and via.strip():
        return None
    if not isinstance(via, dict):
        raise ValueError(
            f"npm audit 'via' entries must be advisory objects or package names: {package}"
        )

    advisory_id, aliases = _advisory_ids(via)
    if not advisory_id:
        raise ValueError(
            f"npm audit advisory is missing both a GHSA url and a numeric source id: {package}"
        )
    severity = via.get("severity")
    if not isinstance(severity, str) or severity not in SEVERITY_ORDER:
        raise ValueError(f"npm audit advisory has an invalid severity for package: {package}")
    return NpmVulnerabilityFinding(
        advisory_id=advisory_id,
        aliases=aliases,
        package=package,
        severity=severity,
        fix_available=fix_available,
    )


def _fix_is_available(value: object, *, package: str) -> bool:
    """Validate npm fix metadata and return whether a fix is available."""
    if isinstance(value, bool):
        return value
    if not isinstance(value, dict):
        raise ValueError(f"npm audit 'fixAvailable' must be a boolean or object: {package}")

    for field in ("name", "version"):
        field_value = value.get(field)
        if not isinstance(field_value, str) or not field_value.strip():
            raise ValueError(
                "npm audit 'fixAvailable' object must include non-empty "
                f"name and version strings: {package}"
            )

    is_major = value.get("isSemVerMajor")
    if is_major is not None and not isinstance(is_major, bool):
        raise ValueError(f"npm audit 'fixAvailable.isSemVerMajor' must be a boolean: {package}")
    return True


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
        fix_value = node.get("fixAvailable", False)
        fix_available = _fix_is_available(fix_value, package=str(name))
        package_value = node.get("name", name)
        if not isinstance(package_value, str) or not package_value.strip():
            raise ValueError(f"npm audit vulnerability has an invalid package name: {name}")
        package = package_value.strip()
        for entry in via:
            finding = _parse_advisory(entry, package=package, fix_available=fix_available)
            if finding is not None:
                findings.append(finding)

    return tuple(findings)


def _run_npm_audit(npm_command: str = "npm") -> tuple[NpmVulnerabilityFinding, ...]:
    """Run ``npm audit --json`` and return parsed vulnerability findings.

    ``npm_command`` is a shell-style command string, so an override may carry
    flags (for example ``npm --silent``). It is split with :func:`shlex.split`
    before the ``audit --json`` arguments are appended.
    """
    npm_parts = shlex.split(npm_command)
    if not npm_parts:
        raise ValueError("npm command must not be empty")
    command = [*npm_parts, "audit", "--json"]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("npm audit timed out after 120 seconds") from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"npm executable not found: {npm_command}. Install Node.js to run the audit."
        ) from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"npm audit returned invalid JSON: {stderr}") from exc

    if not isinstance(payload, dict):
        raise ValueError("npm audit JSON must be an object")

    error = payload.get("error")
    if error is not None:
        summary_value = error.get("summary") if isinstance(error, dict) else error
        summary = (
            summary_value.strip()
            if isinstance(summary_value, str) and summary_value.strip()
            else "unknown error"
        )
        raise RuntimeError(f"npm audit reported an error: {summary}")

    return _parse_npm_audit(payload)


def _matches_exception(
    exception: VulnerabilityExceptionEntry, finding: NpmVulnerabilityFinding
) -> bool:
    """Return whether a reviewed exception matches one npm finding.

    Advisory ids compare case-insensitively: findings normalize GHSA ids to
    upper case, so a lower-case configured exception must still match.
    """
    finding_ids = {advisory_id.upper() for advisory_id in finding.all_ids}
    return (
        exception.package.lower() == finding.package.lower()
        and exception.vulnerability_id.upper() in finding_ids
    )


def _audit_npm_dependencies(
    *,
    today: date,
    exceptions: tuple[VulnerabilityExceptionEntry, ...],
    findings: tuple[NpmVulnerabilityFinding, ...],
    audit_level: str = DEFAULT_AUDIT_LEVEL,
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
        matched_exception_keys.update(entry.key for entry in matching_exceptions)
        if len(matching_exceptions) > 1:
            errors.append(
                "Multiple npm vulnerability exceptions match one advisory: "
                f"{finding.package} {finding.advisory_id}"
            )
            continue

        matching_exception = matching_exceptions[0] if matching_exceptions else None
        if matching_exception is not None:
            if today > matching_exception.review_by:
                errors.append(
                    "Expired npm vulnerability exception: "
                    f"{matching_exception.package} "
                    f"{matching_exception.vulnerability_id} "
                    f"review_by={matching_exception.review_by.isoformat()}"
                )
                continue
            if matching_exception.ignore_only_without_fix and finding.fix_available:
                errors.append(
                    "npm vulnerability exception must be removed because a fix "
                    "is available: "
                    f"{finding.package} {finding.advisory_id}"
                )
                continue

        if not _is_gated(finding.severity, audit_level):
            continue

        if matching_exception is None:
            errors.append(
                "Unreviewed npm vulnerability: "
                f"{finding.package} {finding.severity} {finding.advisory_id}"
            )
            continue

        ignored.append((finding, matching_exception))

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
        help=(
            "npm command to invoke, split with shlex so an override may carry "
            "flags such as 'npm --silent' (defaults to 'npm')"
        ),
    )
    parser.add_argument(
        "--audit-level",
        default=DEFAULT_AUDIT_LEVEL,
        choices=SEVERITY_ORDER,
        help=(
            "Lowest advisory severity that fails the audit, mirroring "
            f"`npm audit --audit-level` (defaults to '{DEFAULT_AUDIT_LEVEL}')"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the policy-driven npm security audit."""
    args = _parse_args(argv)
    exceptions = load_security_audit_exceptions(config_key=NPM_EXCEPTIONS_KEY)
    findings = _run_npm_audit(args.npm)
    ignored, errors = _audit_npm_dependencies(
        today=date.today(),
        exceptions=exceptions,
        findings=findings,
        audit_level=args.audit_level,
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
