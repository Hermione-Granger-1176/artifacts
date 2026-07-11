#!/usr/bin/env python3
"""Verify vendored third-party libraries against a pinned integrity manifest.

Vendored bundles under ``apps/<slug>/js/vendor/*.js`` are excluded from the lint,
type, and dead-code gates, so a silent edit or an upstream swap would otherwise
go unnoticed. This checker reconciles the files on disk with
``config/vendored_assets.json``:

    - every vendored ``*.js`` file must be listed in the manifest;
    - every manifest entry must exist on disk; and
    - every file's SHA-256 must match the recorded hash.

When an upgrade is intentional, update the manifest ``version``, ``upstream``,
and ``sha256`` for the affected entry so the new bundle is pinned explicitly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts import REPO_ROOT

VENDORED_ASSETS_MANIFEST_FILE = REPO_ROOT / "config" / "vendored_assets.json"

# Glob (relative to the workspace root) that matches every vendored bundle.
VENDOR_GLOB = "apps/*/js/vendor/*.js"

_UPDATE_HINT = (
    "If this change is intentional, update config/vendored_assets.json "
    "(version, upstream, sha256) for the affected entry."
)


@dataclass(frozen=True)
class VendoredAsset:
    """One pinned vendored library entry from the manifest."""

    path: str
    package: str
    version: str
    upstream: str
    sha256: str


def _load_manifest(
    manifest_file: Path = VENDORED_ASSETS_MANIFEST_FILE,
) -> tuple[VendoredAsset, ...]:
    """Load and validate the vendored asset manifest."""
    if not manifest_file.exists():
        raise FileNotFoundError(f"Vendored assets manifest not found: {manifest_file}")

    payload = json.loads(manifest_file.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Vendored assets manifest must be a JSON object")

    entries = payload.get("assets", [])
    if not isinstance(entries, list):
        raise ValueError("Vendored assets manifest 'assets' must be a list")

    assets: list[VendoredAsset] = []
    seen_paths: set[str] = set()
    required_fields = ("path", "package", "version", "upstream", "sha256")
    for index, entry in enumerate(entries):
        entry_path = f"assets[{index}]"
        if not isinstance(entry, dict):
            raise ValueError(f"Vendored asset entries must be objects: {entry_path}")

        missing = [field for field in required_fields if not entry.get(field)]
        if missing:
            raise ValueError(
                "Vendored asset entries must include " + ", ".join(missing) + f": {entry_path}"
            )

        asset = VendoredAsset(
            path=str(entry["path"]),
            package=str(entry["package"]),
            version=str(entry["version"]),
            upstream=str(entry["upstream"]),
            sha256=str(entry["sha256"]).lower(),
        )
        if asset.path in seen_paths:
            raise ValueError(f"Vendored asset entries must not duplicate a path: {entry_path}")
        seen_paths.add(asset.path)
        assets.append(asset)

    return tuple(assets)


def _sha256(path: Path) -> str:
    """Return the lower-case SHA-256 hex digest of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_vendor_files(root: Path) -> list[str]:
    """Return repo-relative paths for every vendored bundle on disk."""
    return sorted(match.relative_to(root).as_posix() for match in root.glob(VENDOR_GLOB))


def check_assets(root: Path, assets: tuple[VendoredAsset, ...]) -> list[str]:
    """Return integrity violations between the manifest and the files on disk."""
    violations: list[str] = []
    manifest_paths = {asset.path for asset in assets}

    for disk_path in discover_vendor_files(root):
        if disk_path not in manifest_paths:
            violations.append(
                f"{disk_path}: vendored file is not listed in config/vendored_assets.json. "
                f"{_UPDATE_HINT}"
            )

    for asset in assets:
        file_path = root / asset.path
        if not file_path.is_file():
            violations.append(
                f"{asset.path}: manifest entry has no file on disk "
                f"({asset.package} {asset.version} from {asset.upstream})"
            )
            continue

        actual = _sha256(file_path)
        if actual != asset.sha256:
            violations.append(
                f"{asset.path}: sha256 mismatch for {asset.package} {asset.version} "
                f"(manifest {asset.sha256}, actual {actual}, upstream {asset.upstream}). "
                f"{_UPDATE_HINT}"
            )

    return violations


def run_check(
    root: Path | None = None,
    manifest_file: Path | None = None,
) -> list[str]:
    """Run the vendored asset integrity check and return all violations."""
    workspace_root = root or REPO_ROOT
    assets = _load_manifest(manifest_file or VENDORED_ASSETS_MANIFEST_FILE)
    return check_assets(workspace_root, assets)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the vendored asset checker."""
    parser = argparse.ArgumentParser(
        description="Verify vendored libraries against config/vendored_assets.json."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root (defaults to auto-detected REPO_ROOT)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    args = parse_args(argv)
    workspace_root = Path(args.root) if args.root else REPO_ROOT

    try:
        violations = run_check(workspace_root)
    except (FileNotFoundError, ValueError) as exc:
        print(f"Vendored assets check failed: {exc}")
        return 1

    if not violations:
        print("Vendored assets check passed")
        return 0

    print(f"Vendored assets check failed: {len(violations)} violation(s)")
    for violation in violations:
        print(f"  {violation}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
