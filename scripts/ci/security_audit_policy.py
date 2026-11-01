"""Shared configuration policy for dependency security audits."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from scripts import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sequence
    from pathlib import Path

SECURITY_AUDIT_CONFIG_FILE = REPO_ROOT / "config" / "security_audit.json"

NPM_EXCEPTIONS_KEY = "npm_vulnerability_exceptions"
PYTHON_EXCEPTIONS_KEY = "python_vulnerability_exceptions"
VENDORED_EXCEPTIONS_KEY = "vendored_vulnerability_exceptions"


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
        """Return the case-insensitive identity for this exception entry."""
        return (self.package.casefold(), self.vulnerability_id.casefold())

    def matches(self, package: str, advisory_ids: Iterable[str]) -> bool:
        """Return whether this exception covers ``package`` under any of ``advisory_ids``.

        Package names and advisory ids compare case-insensitively, so a lower-case
        configured id still covers an upper-cased GHSA id.
        """
        advisory_keys = {advisory_id.casefold() for advisory_id in advisory_ids}
        return self.package.casefold() == package.casefold() and (
            self.vulnerability_id.casefold() in advisory_keys
        )


def _load_security_audit_config(
    config_file: Path = SECURITY_AUDIT_CONFIG_FILE,
) -> dict[str, object]:
    """Load the full security audit JSON config."""
    if config_file.is_symlink():
        raise ValueError(f"Security audit config must not be a symlink: {config_file}")
    if not config_file.exists():
        raise FileNotFoundError(f"Security audit config file not found: {config_file}")
    if not config_file.is_file():
        raise ValueError(f"Security audit config must be a regular file: {config_file}")

    try:
        payload = json.loads(
            config_file.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
        )
    except json.JSONDecodeError as exc:
        raise ValueError(f"Security audit config contains invalid JSON: {config_file}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Security audit config must be a JSON object")
    return payload


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build a JSON object while rejecting keys that would be overwritten."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Security audit config contains a duplicate key: {key}")
        result[key] = value
    return result


def _validated_id(value: object, *, entry_path: str) -> str:
    """Return one non-empty string or non-negative numeric advisory id."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return str(value)
    raise ValueError(
        "Security audit exception 'id' must be a non-empty string or "
        f"non-negative integer: {entry_path}"
    )


def _validated_text_field(value: object, *, field: str, entry_path: str) -> str:
    """Return one required non-empty string field."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise ValueError(f"Security audit exception '{field}' must be a non-empty string: {entry_path}")


def _parse_exception_entry(entry: object, entry_path: str) -> VulnerabilityExceptionEntry:
    """Validate one configured exception and return it as an entry."""
    if not isinstance(entry, dict):
        raise ValueError(f"Security audit exceptions must be objects: {entry_path}")

    required_fields = {"id", "package", "reason", "review_by"}
    optional_fields = {"ignore_only_without_fix"}
    missing = sorted(required_fields - entry.keys())
    if missing:
        raise ValueError(
            "Security audit exceptions must include " + ", ".join(missing) + f": {entry_path}"
        )
    unexpected = sorted(entry.keys() - required_fields - optional_fields)
    if unexpected:
        raise ValueError(
            "Security audit exceptions contain unknown fields "
            + ", ".join(unexpected)
            + f": {entry_path}"
        )

    ignore_only_without_fix = entry.get("ignore_only_without_fix", False)
    if not isinstance(ignore_only_without_fix, bool):
        raise ValueError(
            f"Security audit exception 'ignore_only_without_fix' must be a boolean: {entry_path}"
        )

    vulnerability_id = _validated_id(entry["id"], entry_path=entry_path)
    package = _validated_text_field(entry["package"], field="package", entry_path=entry_path)
    reason = _validated_text_field(entry["reason"], field="reason", entry_path=entry_path)
    review_by_value = _validated_text_field(
        entry["review_by"], field="review_by", entry_path=entry_path
    )
    try:
        review_by = date.fromisoformat(review_by_value)
    except ValueError as exc:
        raise ValueError(
            f"Security audit exception 'review_by' must use YYYY-MM-DD: {entry_path}"
        ) from exc

    return VulnerabilityExceptionEntry(
        vulnerability_id=vulnerability_id,
        package=package,
        reason=reason,
        review_by=review_by,
        ignore_only_without_fix=ignore_only_without_fix,
    )


def load_security_audit_exceptions(
    config_file: Path = SECURITY_AUDIT_CONFIG_FILE,
    *,
    config_key: str,
) -> tuple[VulnerabilityExceptionEntry, ...]:
    """Load and validate reviewed exceptions for one package ecosystem."""
    payload = _load_security_audit_config(config_file)
    entries = payload.get(config_key, [])
    if not isinstance(entries, list):
        raise ValueError(f"Security audit config '{config_key}' must be a list")

    exceptions: list[VulnerabilityExceptionEntry] = []
    seen_keys: set[tuple[str, str]] = set()
    for index, entry in enumerate(entries):
        entry_path = f"{config_key}[{index}]"
        exception = _parse_exception_entry(entry, entry_path)
        if exception.key in seen_keys:
            raise ValueError(
                "Security audit exceptions must not duplicate a package and "
                f"vulnerability id pair: {entry_path}"
            )
        seen_keys.add(exception.key)
        exceptions.append(exception)

    return tuple(exceptions)


def unused_exception_errors(
    exceptions: tuple[VulnerabilityExceptionEntry, ...],
    matched_keys: Collection[tuple[str, str]],
    ecosystem: str,
) -> list[str]:
    """Report each reviewed exception that no current finding matched.

    An exception outliving its advisory would silently cover a future one with
    the same id, so every audit fails on it.
    """
    return [
        f"Unused {ecosystem} vulnerability exception: "
        f"{exception.package} {exception.vulnerability_id}"
        for exception in exceptions
        if exception.key not in matched_keys
    ]


def report_audit_outcome(
    *,
    ecosystem: str,
    audit_name: str,
    ignored: Sequence[tuple[str, VulnerabilityExceptionEntry]],
    errors: Sequence[str],
    pass_message: str,
) -> int:
    """Print an audit's reviewed exceptions and verdict, and return its exit code.

    ``ignored`` pairs each silenced finding's one-line label with the exception
    that covered it. A failing audit prints ``"<audit_name> failed:"`` and each
    error and returns 1. A passing audit prints ``pass_message`` and returns 0.
    """
    if ignored:
        print(f"Reviewed {ecosystem} vulnerability exceptions:")
        for label, exception in ignored:
            print(f"- {label} (review by {exception.review_by.isoformat()})")
            print(f"  reason: {exception.reason}")

    if errors:
        print(f"{audit_name} failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(pass_message)
    return 0
