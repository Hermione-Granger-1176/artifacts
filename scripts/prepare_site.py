#!/usr/bin/env python3
"""
Prepare Site Payload

Copies the deployable static site into `_site/`, then applies deploy-time
adjustments such as cache-busting query strings, the configured 404 fallback
path, and the `.nojekyll` marker needed for branch-based GitHub Pages.

Usage:
    python scripts/prepare_site.py
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
DEPLOY_DIR = REPO_ROOT / "_site"
DEPLOY_ITEMS = ("404.html", "apps", "assets", "css", "index.html", "js")
GIT_COMMAND_TIMEOUT_SECONDS = 10


def _normalize_site_path(value: str) -> str:
    """Return a normalized GitHub Pages site path with surrounding slashes."""
    stripped = value.strip().strip("/")
    if not stripped:
        return "/"
    return f"/{stripped}/"


def _load_site_path() -> str:
    """Load the configured site path from ``pyproject.toml``."""
    if not PYPROJECT_FILE.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {PYPROJECT_FILE}")

    pyproject = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))

    try:
        site_path = pyproject["tool"]["artifacts"]["site_path"]
    except KeyError as exc:
        raise ValueError("Missing tool.artifacts.site_path in pyproject.toml") from exc

    return _normalize_site_path(site_path)


def _resolve_version() -> str:
    """Return the deploy version from the environment or current Git SHA."""
    env_version = os.environ.get("ARTIFACTS_DEPLOY_VERSION")
    if env_version:
        return env_version

    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    ).strip()


def _copy_deploy_items() -> None:
    """Copy the static site inputs into the clean deploy directory."""
    if DEPLOY_DIR.exists():
        shutil.rmtree(DEPLOY_DIR)

    DEPLOY_DIR.mkdir(parents=True)

    for item in DEPLOY_ITEMS:
        source = REPO_ROOT / item
        target = DEPLOY_DIR / item
        if not source.exists():
            raise FileNotFoundError(f"Required deploy path not found: {source}")
        if source.is_symlink():
            raise ValueError(f"Refusing to copy symlinked deploy path: {source}")
        if source.is_dir():
            for nested in source.rglob("*"):
                if nested.is_symlink():
                    raise ValueError(
                        f"Refusing to copy deploy tree containing symlink: {nested}"
                    )
            shutil.copytree(source, target)
            continue
        shutil.copy2(source, target)


def _replace_exact(content: str, old: str, new: str) -> str:
    """Replace one exact string and raise an error if it is missing."""
    if old not in content:
        raise ValueError(f"Expected content not found: {old}")
    return content.replace(old, new)


def _patch_index_html(version: str) -> None:
    """Apply cache-busting query strings to root HTML asset references."""
    index_path = DEPLOY_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    replacements = {
        'href="css/style.css"': f'href="css/style.css?v={version}"',
        'src="js/gallery-config.js"': f'src="js/gallery-config.js?v={version}"',
        'src="js/data.js"': f'src="js/data.js?v={version}"',
        'src="js/app.js"': f'src="js/app.js?v={version}"',
    }

    for old, new in replacements.items():
        content = _replace_exact(content, old, new)

    index_path.write_text(content, encoding="utf-8")


def _patch_404_html(site_path: str) -> None:
    """Inject the configured site path into the 404 fallback page."""
    error_path = DEPLOY_DIR / "404.html"
    content = error_path.read_text(encoding="utf-8")
    content = _replace_exact(
        content, 'data-site-path="/"', f'data-site-path="{site_path}"'
    )
    content = _replace_exact(content, 'href="/"', f'href="{site_path}"')
    error_path.write_text(content, encoding="utf-8")


def _patch_manifest(site_path: str) -> None:
    """Inject the configured site path into the web app manifest."""
    manifest_path = DEPLOY_DIR / "assets" / "icons" / "manifest.webmanifest"
    if not manifest_path.exists():
        return
    content = manifest_path.read_text(encoding="utf-8")
    content = _replace_exact(
        content, '"start_url": "../../"', f'"start_url": "{site_path}"'
    )
    manifest_path.write_text(content, encoding="utf-8")


def _write_nojekyll() -> None:
    """Write the marker file that disables Jekyll processing on Pages."""
    (DEPLOY_DIR / ".nojekyll").write_text("", encoding="utf-8")


def prepare_site() -> None:
    """Build the deployable ``_site/`` payload for GitHub Pages."""
    logger.info("Preparing deployable site output")
    site_path = _load_site_path()
    version = _resolve_version()
    _copy_deploy_items()
    _patch_index_html(version)
    _patch_404_html(site_path)
    _patch_manifest(site_path)
    _write_nojekyll()
    logger.info("Prepared %s", DEPLOY_DIR)


if __name__ == "__main__":  # pragma: no cover
    try:
        prepare_site()
    except (
        FileNotFoundError,
        ValueError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        logger.error("Failed to prepare site: %s", exc)
        sys.exit(1)
