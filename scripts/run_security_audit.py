#!/usr/bin/env python3
"""Run policy-driven dependency security audits for locked Python requirements."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SECURITY_AUDIT_CONFIG_FILE = REPO_ROOT / "config" / "security_audit.json"
DEFAULT_PYTHON_SECURITY_LOCK_FILES = (
    "locks/requirements.lock",
    "locks/requirements-dev.lock",
)


@dataclass(frozen=True)
class SecurityAuditException:
    """One reviewed vulnerability exception for a specific lock file and package."""

    vulnerability_id: str
    package: str
    lock_file: str
    reason: str
    review_by: date
    ignore_only_without_fix: bool

    @property
    def key(self) -> tuple[str, str, str]:
        """Return the unique identity for this exception entry."""
        return (self.lock_file, self.package.lower(), self.vulnerability_id)


@dataclass(frozen=True)
class VulnerabilityFinding:
    """One vulnerability reported by pip-audit."""

    vulnerability_id: str
    aliases: tuple[str, ...]
    package: str
    version: str
    lock_file: str
    fix_versions: tuple[str, ...]

    @property
    def all_ids(self) -> tuple[str, ...]:
        """Return the primary vulnerability id plus aliases."""
        return (self.vulnerability_id, *self.aliases)


def _relative_path(path: Path) -> str:
    """Return a repo-relative path string."""
    return str(path.relative_to(REPO_ROOT))


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


def _python_lock_files(
    config_file: Path = SECURITY_AUDIT_CONFIG_FILE,
) -> tuple[Path, ...]:
    """Load the configured Python lock files to audit."""
    payload = _load_security_audit_config(config_file)
    configured = payload.get(
        "python_lock_files", list(DEFAULT_PYTHON_SECURITY_LOCK_FILES)
    )
    if not isinstance(configured, list) or not all(
        isinstance(item, str) for item in configured
    ):
        raise ValueError(
            "Security audit config 'python_lock_files' must be a list of strings"
        )
    if not configured:
        configured = list(DEFAULT_PYTHON_SECURITY_LOCK_FILES)

    lock_files = tuple(REPO_ROOT / entry for entry in configured)
    for lock_file in lock_files:
        if not lock_file.exists():
            raise FileNotFoundError(f"Python security lock file not found: {lock_file}")

    return lock_files


def _load_security_audit_exceptions(
    config_file: Path = SECURITY_AUDIT_CONFIG_FILE,
) -> tuple[SecurityAuditException, ...]:
    """Load reviewed vulnerability exceptions from the JSON config file."""
    payload = _load_security_audit_config(config_file)
    entries = payload.get("python_ignored_vulnerabilities", [])
    if not isinstance(entries, list):
        raise ValueError(
            "Security audit config 'python_ignored_vulnerabilities' must be a list"
        )

    exceptions: list[SecurityAuditException] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(
                "Security audit exceptions must be objects: "
                f"python_ignored_vulnerabilities[{index}]"
            )

        required_fields = ("id", "package", "lock_file", "reason", "review_by")
        missing = [field for field in required_fields if not entry.get(field)]
        if missing:
            raise ValueError(
                "Security audit exceptions must include "
                + ", ".join(missing)
                + f": python_ignored_vulnerabilities[{index}]"
            )

        ignore_only_without_fix = entry.get("ignore_only_without_fix", False)
        if not isinstance(ignore_only_without_fix, bool):
            raise ValueError(
                "Security audit exception 'ignore_only_without_fix' must be a boolean: "
                f"python_ignored_vulnerabilities[{index}]"
            )

        try:
            review_by = date.fromisoformat(str(entry["review_by"]))
        except ValueError as exc:
            raise ValueError(
                "Security audit exception 'review_by' must use YYYY-MM-DD: "
                f"python_ignored_vulnerabilities[{index}]"
            ) from exc

        exceptions.append(
            SecurityAuditException(
                vulnerability_id=str(entry["id"]),
                package=str(entry["package"]),
                lock_file=str(entry["lock_file"]),
                reason=str(entry["reason"]),
                review_by=review_by,
                ignore_only_without_fix=ignore_only_without_fix,
            )
        )

    return tuple(exceptions)


def _run_pip_audit(lock_file: Path) -> tuple[VulnerabilityFinding, ...]:
    """Run pip-audit for one lock file and return all reported vulnerabilities."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "--requirement",
            str(lock_file),
            "--format",
            "json",
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode not in {0, 1}:
        stderr = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(
            f"pip-audit failed for {_relative_path(lock_file)}: {stderr}"
        )

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"pip-audit returned invalid JSON for {_relative_path(lock_file)}"
        ) from exc

    dependencies = payload.get("dependencies")
    if not isinstance(dependencies, list):
        raise ValueError(
            f"pip-audit JSON for {_relative_path(lock_file)} must include a dependencies list"
        )

    findings: list[VulnerabilityFinding] = []
    for dependency in dependencies:
        if not isinstance(dependency, dict):
            raise ValueError(
                f"pip-audit dependency entries must be objects for {_relative_path(lock_file)}"
            )

        vulns = dependency.get("vulns", [])
        if not isinstance(vulns, list):
            raise ValueError(
                f"pip-audit dependency vulns must be a list for {_relative_path(lock_file)}"
            )

        for vulnerability in vulns:
            if not isinstance(vulnerability, dict):
                raise ValueError(
                    f"pip-audit vulnerabilities must be objects for {_relative_path(lock_file)}"
                )

            aliases = vulnerability.get("aliases", [])
            fix_versions = vulnerability.get("fix_versions", [])
            if not isinstance(aliases, list) or not all(
                isinstance(alias, str) for alias in aliases
            ):
                raise ValueError(
                    f"pip-audit aliases must be string lists for {_relative_path(lock_file)}"
                )
            if not isinstance(fix_versions, list) or not all(
                isinstance(version, str) for version in fix_versions
            ):
                raise ValueError(
                    "pip-audit fix_versions must be string lists for "
                    f"{_relative_path(lock_file)}"
                )

            findings.append(
                VulnerabilityFinding(
                    vulnerability_id=str(vulnerability.get("id", "")),
                    aliases=tuple(aliases),
                    package=str(dependency.get("name", "")),
                    version=str(dependency.get("version", "")),
                    lock_file=_relative_path(lock_file),
                    fix_versions=tuple(fix_versions),
                )
            )

    return tuple(findings)


def _matches_exception(
    exception: SecurityAuditException, finding: VulnerabilityFinding
) -> bool:
    """Return whether a reviewed exception matches one vulnerability finding."""
    return (
        exception.lock_file == finding.lock_file
        and exception.package.lower() == finding.package.lower()
        and exception.vulnerability_id in finding.all_ids
    )


def _audit_python_dependencies(
    *,
    today: date,
    exceptions: tuple[SecurityAuditException, ...],
    lock_files: tuple[Path, ...],
) -> tuple[
    tuple[tuple[VulnerabilityFinding, SecurityAuditException], ...], tuple[str, ...]
]:
    """Run policy checks for the configured lock files."""
    ignored: list[tuple[VulnerabilityFinding, SecurityAuditException]] = []
    errors: list[str] = []
    matched_exception_keys: set[tuple[str, str, str]] = set()

    for lock_file in lock_files:
        for finding in _run_pip_audit(lock_file):
            matching_exception = next(
                (entry for entry in exceptions if _matches_exception(entry, finding)),
                None,
            )
            if matching_exception is None:
                errors.append(
                    "Unreviewed Python vulnerability: "
                    f"{finding.lock_file} {finding.package} {finding.version} {finding.vulnerability_id}"
                )
                continue

            matched_exception_keys.add(matching_exception.key)
            if today > matching_exception.review_by:
                errors.append(
                    "Expired Python vulnerability exception: "
                    f"{matching_exception.lock_file} {matching_exception.package} "
                    f"{matching_exception.vulnerability_id} review_by={matching_exception.review_by.isoformat()}"
                )
                continue

            if matching_exception.ignore_only_without_fix and finding.fix_versions:
                errors.append(
                    "Python vulnerability exception must be removed because fixes are available: "
                    f"{finding.lock_file} {finding.package} {finding.vulnerability_id} "
                    f"fix_versions={', '.join(finding.fix_versions)}"
                )
                continue

            ignored.append((finding, matching_exception))

    for exception in exceptions:
        if exception.key not in matched_exception_keys:
            errors.append(
                "Unused Python vulnerability exception: "
                f"{exception.lock_file} {exception.package} {exception.vulnerability_id}"
            )

    return tuple(ignored), tuple(errors)


def main() -> int:
    """Run the policy-driven Python security audit."""
    exceptions = _load_security_audit_exceptions()
    lock_files = _python_lock_files()
    ignored, errors = _audit_python_dependencies(
        today=date.today(), exceptions=exceptions, lock_files=lock_files
    )

    if ignored:
        print("Reviewed Python vulnerability exceptions:")
        for finding, exception in ignored:
            print(
                "- "
                f"{finding.lock_file}: {finding.package} {finding.version} {finding.vulnerability_id} "
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
