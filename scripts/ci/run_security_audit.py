#!/usr/bin/env python3
"""Run policy-driven dependency security audits for exported requirements."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from scripts import REPO_ROOT

SECURITY_AUDIT_CONFIG_FILE = REPO_ROOT / "config" / "security_audit.json"


@dataclass(frozen=True)
class VulnerabilityExceptionEntry:
    """One reviewed vulnerability exception entry for a package."""

    vulnerability_id: str
    package: str
    reason: str
    review_by: date
    ignore_only_without_fix: bool

    @property
    def key(self) -> tuple[str, str]:
        """Return the unique identity for this exception entry."""
        return (self.package.lower(), self.vulnerability_id)


@dataclass(frozen=True)
class VulnerabilityFinding:
    """One vulnerability reported by pip-audit."""

    vulnerability_id: str
    aliases: tuple[str, ...]
    package: str
    version: str
    fix_versions: tuple[str, ...]

    @property
    def all_ids(self) -> tuple[str, ...]:
        """Return the primary vulnerability id plus aliases."""
        return (self.vulnerability_id, *self.aliases)


def _relative_path(path: Path) -> str:
    """Return a repo-relative path string, or the original path."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_security_audit_config(
    config_file: Path = SECURITY_AUDIT_CONFIG_FILE,
) -> dict[str, object]:
    """Load the full security audit JSON config."""
    if not config_file.exists():
        raise FileNotFoundError(f"Security audit config file not found: {config_file}")

    payload = json.loads(config_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Security audit config must be a JSON object")
    return payload


def _load_security_audit_exceptions(
    config_file: Path = SECURITY_AUDIT_CONFIG_FILE,
) -> tuple[VulnerabilityExceptionEntry, ...]:
    """Load reviewed vulnerability exceptions from the JSON config file."""
    payload = _load_security_audit_config(config_file)
    entries = payload.get("python_vulnerability_exceptions", [])
    if not isinstance(entries, list):
        raise ValueError(
            "Security audit config 'python_vulnerability_exceptions' must be a list"
        )

    exceptions: list[VulnerabilityExceptionEntry] = []
    for index, entry in enumerate(entries):
        entry_path = f"python_vulnerability_exceptions[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"Security audit exceptions must be objects: {entry_path}")

        required_fields = ("id", "package", "reason", "review_by")
        missing = [field for field in required_fields if not entry.get(field)]
        if missing:
            raise ValueError(
                "Security audit exceptions must include "
                + ", ".join(missing)
                + f": {entry_path}"
            )

        ignore_only_without_fix = entry.get("ignore_only_without_fix", False)
        if not isinstance(ignore_only_without_fix, bool):
            raise ValueError(
                "Security audit exception 'ignore_only_without_fix' must be a "
                f"boolean: {entry_path}"
            )

        try:
            review_by = date.fromisoformat(str(entry["review_by"]))
        except ValueError as exc:
            raise ValueError(
                "Security audit exception 'review_by' must use YYYY-MM-DD: "
                f"{entry_path}"
            ) from exc

        exceptions.append(
            VulnerabilityExceptionEntry(
                vulnerability_id=str(entry["id"]),
                package=str(entry["package"]),
                reason=str(entry["reason"]),
                review_by=review_by,
                ignore_only_without_fix=ignore_only_without_fix,
            )
        )

    return tuple(exceptions)


def _parse_vulnerability(
    vulnerability: object,
    *,
    package: str,
    version: str,
    requirements_file: Path,
) -> VulnerabilityFinding:
    """Parse one pip-audit vulnerability entry into a finding."""
    relative_requirements_file = _relative_path(requirements_file)
    if not isinstance(vulnerability, dict):
        raise ValueError(
            f"pip-audit vulnerabilities must be objects for {relative_requirements_file}"
        )

    aliases = vulnerability.get("aliases", [])
    if not isinstance(aliases, list) or not all(
        isinstance(alias, str) for alias in aliases
    ):
        raise ValueError(
            f"pip-audit aliases must be string lists for {relative_requirements_file}"
        )

    fix_versions = vulnerability.get("fix_versions", [])
    if not isinstance(fix_versions, list) or not all(
        isinstance(fix_version, str) for fix_version in fix_versions
    ):
        raise ValueError(
            "pip-audit fix_versions must be string lists for "
            f"{relative_requirements_file}"
        )

    return VulnerabilityFinding(
        vulnerability_id=str(vulnerability.get("id", "")),
        aliases=tuple(aliases),
        package=package,
        version=version,
        fix_versions=tuple(fix_versions),
    )


def _parse_dependency_findings(
    dependency: object, requirements_file: Path
) -> tuple[VulnerabilityFinding, ...]:
    """Parse all pip-audit findings for one dependency entry."""
    relative_requirements_file = _relative_path(requirements_file)
    if not isinstance(dependency, dict):
        raise ValueError(
            f"pip-audit dependency entries must be objects for {relative_requirements_file}"
        )

    vulns = dependency.get("vulns", [])
    if not isinstance(vulns, list):
        raise ValueError(
            f"pip-audit dependency vulns must be a list for {relative_requirements_file}"
        )

    package = str(dependency.get("name", ""))
    version = str(dependency.get("version", ""))
    return tuple(
        _parse_vulnerability(
            vulnerability,
            package=package,
            version=version,
            requirements_file=requirements_file,
        )
        for vulnerability in vulns
    )


def _run_pip_audit(requirements_file: Path) -> tuple[VulnerabilityFinding, ...]:
    """Run pip-audit for one requirements file and return vulnerabilities."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "--requirement",
                str(requirements_file),
                "--format",
                "json",
                "--progress-spinner",
                "off",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            "pip-audit timed out after 120 seconds for "
            f"{_relative_path(requirements_file)}"
        ) from exc
    if result.returncode not in {0, 1}:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(
            f"pip-audit failed for {_relative_path(requirements_file)}: {stderr}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"pip-audit returned invalid JSON for {_relative_path(requirements_file)}"
        ) from exc

    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError(
            f"pip-audit JSON for {_relative_path(requirements_file)} "
            "must include a dependencies list"
        )

    return tuple(
        finding
        for dependency in dependencies
        for finding in _parse_dependency_findings(dependency, requirements_file)
    )


def _matches_exception(
    exception: VulnerabilityExceptionEntry, finding: VulnerabilityFinding
) -> bool:
    """Return whether a reviewed exception matches one vulnerability finding."""
    return (
        exception.package.lower() == finding.package.lower()
        and exception.vulnerability_id in finding.all_ids
    )


def _audit_python_dependencies(
    *,
    today: date,
    exceptions: tuple[VulnerabilityExceptionEntry, ...],
    requirements_file: Path,
) -> tuple[
    tuple[tuple[VulnerabilityFinding, VulnerabilityExceptionEntry], ...],
    tuple[str, ...],
]:
    """Run policy checks for the exported requirements file."""
    ignored: list[tuple[VulnerabilityFinding, VulnerabilityExceptionEntry]] = []
    errors: list[str] = []
    matched_exception_keys: set[tuple[str, str]] = set()

    for finding in _run_pip_audit(requirements_file):
        matching_exceptions = tuple(
            entry for entry in exceptions if _matches_exception(entry, finding)
        )
        if not matching_exceptions:
            errors.append(
                "Unreviewed Python vulnerability: "
                f"{finding.package} {finding.version} {finding.vulnerability_id}"
            )
            continue

        matched_exception_keys.update(entry.key for entry in matching_exceptions)
        finding_errors = []
        for matching_exception in matching_exceptions:
            if today > matching_exception.review_by:
                finding_errors.append(
                    "Expired Python vulnerability exception: "
                    f"{matching_exception.package} "
                    f"{matching_exception.vulnerability_id} "
                    f"review_by={matching_exception.review_by.isoformat()}"
                )
            elif matching_exception.ignore_only_without_fix and finding.fix_versions:
                finding_errors.append(
                    "Python vulnerability exception must be removed because fixes "
                    "are available: "
                    f"{finding.package} {finding.vulnerability_id} "
                    f"fix_versions={', '.join(finding.fix_versions)}"
                )

        if finding_errors:
            errors.extend(finding_errors)
            continue

        ignored.append((finding, matching_exceptions[0]))

    for exception in exceptions:
        if exception.key not in matched_exception_keys:
            errors.append(
                "Unused Python vulnerability exception: "
                f"{exception.package} {exception.vulnerability_id}"
            )

    return tuple(ignored), tuple(errors)


def _resolve_requirements_file(requirements_file: Path) -> Path:
    """Resolve and validate the exported requirements file path."""
    resolved = (
        requirements_file
        if requirements_file.is_absolute()
        else REPO_ROOT / requirements_file
    )
    if not resolved.is_file():
        raise FileNotFoundError(
            f"Python security requirements file not found: {resolved}"
        )
    return resolved


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Run the Python dependency security audit"
    )
    parser.add_argument(
        "--requirements",
        required=True,
        type=Path,
        help="Exported requirements.txt file to audit",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the policy-driven Python security audit."""
    args = _parse_args(argv)
    exceptions = _load_security_audit_exceptions()
    requirements_file = _resolve_requirements_file(args.requirements)
    ignored, errors = _audit_python_dependencies(
        today=date.today(),
        exceptions=exceptions,
        requirements_file=requirements_file,
    )

    if ignored:
        print("Reviewed Python vulnerability exceptions:")
        for finding, exception in ignored:
            print(
                "- "
                f"{finding.package} {finding.version} "
                f"{finding.vulnerability_id} "
                f"(review by {exception.review_by.isoformat()})"
            )
            print(f"  reason: {exception.reason}")

    if errors:
        print("Python dependency audit failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Python dependency audit passed.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
