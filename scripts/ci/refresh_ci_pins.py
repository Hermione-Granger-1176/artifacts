#!/usr/bin/env python3
"""Keep the Playwright package and its hosted CI image on one exact release."""

from __future__ import annotations

import argparse
import json
import re
import time
import tomllib
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING
from urllib.request import Request, urlopen

from scripts import REPO_ROOT

if TYPE_CHECKING:
    from pathlib import Path

PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
UV_LOCK_PATH = REPO_ROOT / "uv.lock"
PLAYWRIGHT_WORKFLOW_PATHS = (
    REPO_ROOT / ".github" / "workflows" / "update.yml",
    REPO_ROOT / ".github" / "workflows" / "live-site-smoke.yml",
)

PYPI_URL = "https://pypi.org/pypi/playwright/json"
PLAYWRIGHT_IMAGE_PREFIX = "mcr.microsoft.com/playwright/python:"
PLAYWRIGHT_IMAGE_PATTERN = re.compile(
    r"mcr\.microsoft\.com/playwright/python:v[0-9]+\.[0-9]+\.[0-9]+"
    r"-noble@sha256:[0-9a-f]{64}"
)
PLAYWRIGHT_REQUIREMENT_PATTERN = re.compile(r'(?m)^(\s*"playwright==)[^"]+("\s*,?)$')
SEMVER_PATTERN = re.compile(r"v?([0-9]+\.[0-9]+\.[0-9]+)")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")

FetchText = Callable[[], str]


def retry(
    fetch: FetchText, *, attempts: int = 3, sleep: Callable[[float], None] = time.sleep
) -> str:
    """Return a fetched value with bounded backoff for transient registry failures."""
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(1, attempts):
        try:
            return fetch()
        except Exception:
            sleep(attempt * 0.25)
    return fetch()


def pypi_latest_version(*, timeout: float = 15) -> str:
    """Return the latest stable semantic Playwright release on PyPI."""
    request = Request(PYPI_URL, headers={"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    info = payload.get("info") if isinstance(payload, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    match = SEMVER_PATTERN.fullmatch(version) if isinstance(version, str) else None
    if match is None:
        raise ValueError("PyPI returned an invalid latest Playwright version")
    return match.group(1)


def locked_playwright_version(path: Path) -> str:
    """Read the exact installed Playwright version from uv.lock."""
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    packages = payload.get("package")
    versions: list[str] = []
    if isinstance(packages, list):
        for package in packages:
            if not isinstance(package, dict) or package.get("name") != "playwright":
                continue
            version = package.get("version")
            if isinstance(version, str):
                versions.append(version)
    if len(versions) != 1 or SEMVER_PATTERN.fullmatch(versions[0]) is None:
        raise ValueError("uv.lock has no exact Playwright semantic version")
    return versions[0]


def registry_digest(image: str, *, timeout: float = 15) -> str:
    """Resolve an MCR Playwright tag to its immutable OCI manifest digest."""
    if not image.startswith(PLAYWRIGHT_IMAGE_PREFIX) or not image.removeprefix(
        PLAYWRIGHT_IMAGE_PREFIX
    ):
        raise ValueError(f"Unsupported Playwright image reference: {image}")
    tag = image.removeprefix(PLAYWRIGHT_IMAGE_PREFIX)
    request = Request(
        f"https://mcr.microsoft.com/v2/playwright/python/manifests/{tag}",
        method="HEAD",
        headers={
            "Accept": (
                "application/vnd.oci.image.index.v1+json, "
                "application/vnd.docker.distribution.manifest.list.v2+json"
            )
        },
    )
    with urlopen(request, timeout=timeout) as response:
        digest = response.headers.get("Docker-Content-Digest")
    if not isinstance(digest, str) or DIGEST_PATTERN.fullmatch(digest) is None:
        raise ValueError(f"MCR returned an invalid digest for {image}")
    return digest


def replace_one(path: Path, pattern: re.Pattern[str], replacement: str, *, label: str) -> bool:
    """Replace one required pin and report whether the file changed."""
    text = path.read_text(encoding="utf-8")
    new_text, count = pattern.subn(replacement, text)
    if count != 1:
        raise ValueError(f"Expected exactly one {label} in {path}, found {count}")
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def replace_all(path: Path, pattern: re.Pattern[str], replacement: str, *, label: str) -> bool:
    """Replace every owned pin and require at least one match."""
    text = path.read_text(encoding="utf-8")
    new_text, count = pattern.subn(replacement, text)
    if count < 1:
        raise ValueError(f"Expected at least one {label} in {path}, found {count}")
    if new_text == text:
        return False
    path.write_text(new_text, encoding="utf-8")
    return True


def upgrade_project_dependency(path: Path, version: str) -> bool:
    """Update the exact pyproject Playwright requirement without touching the lock."""
    if SEMVER_PATTERN.fullmatch(version) is None:
        raise ValueError(f"Invalid Playwright semantic version: {version}")
    return replace_one(
        path,
        PLAYWRIGHT_REQUIREMENT_PATTERN,
        rf"\g<1>{version}\g<2>",
        label="Playwright project requirement",
    )


def refresh_workflow_images(
    *, version: str, digest: str, paths: Sequence[Path] = PLAYWRIGHT_WORKFLOW_PATHS
) -> list[Path]:
    """Update one pinned Playwright image in every browser workflow."""
    if SEMVER_PATTERN.fullmatch(version) is None:
        raise ValueError(f"Invalid Playwright semantic version: {version}")
    if DIGEST_PATTERN.fullmatch(digest) is None:
        raise ValueError(f"Invalid Playwright image digest: {digest}")
    replacement = f"{PLAYWRIGHT_IMAGE_PREFIX}v{version}-noble@{digest}"
    changed: list[Path] = []
    for path in paths:
        if replace_all(path, PLAYWRIGHT_IMAGE_PATTERN, replacement, label="Playwright image pin"):
            changed.append(path)
    return changed


def refresh_locked_image(
    lock_path: Path, *, paths: Sequence[Path] = PLAYWRIGHT_WORKFLOW_PATHS
) -> list[Path]:
    """Resolve the locked package version and refresh matching workflow images."""
    version = locked_playwright_version(lock_path)
    image = f"{PLAYWRIGHT_IMAGE_PREFIX}v{version}-noble"
    digest = retry(lambda: registry_digest(image))
    return refresh_workflow_images(version=version, digest=digest, paths=paths)


def main(argv: list[str] | None = None) -> int:
    """Run one maintenance action selected by the Make target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action",
        choices=("upgrade-project", "refresh-image"),
        help="upgrade the project requirement or refresh images from uv.lock",
    )
    args = parser.parse_args(argv)

    if args.action == "upgrade-project":
        version = retry(pypi_latest_version)
        changed = [PYPROJECT_PATH] if upgrade_project_dependency(PYPROJECT_PATH, version) else []
    else:
        changed = refresh_locked_image(UV_LOCK_PATH)

    for path in changed:
        print(f"Updated {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
