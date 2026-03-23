#!/usr/bin/env python3
"""Prepare the deployable Pages payload in `_site/`.

Copies the deployable static site into `_site/`, then applies deploy-time
adjustments such as cache-busting query strings, the configured 404 fallback
path, and the `.nojekyll` marker needed for branch-based GitHub Pages.

Usage:
    python scripts/prepare_site.py
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tomllib
from itertools import chain
from pathlib import Path
from urllib.parse import urljoin

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
ROOT_STYLESHEET_IMPORT_PATTERN = re.compile(r'@import url\("(\./[^"?]+\.css)"\);')
DEPLOY_METADATA_FILE = "deploy-metadata.json"
DEPLOY_COMMIT_SHA_ENV_VAR = "ARTIFACTS_DEPLOY_COMMIT_SHA"
DEPLOY_VERSION_ENV_VAR = "ARTIFACTS_DEPLOY_VERSION"
SITE_URL_PLACEHOLDER = "__ARTIFACTS_SITE_URL__"
SHARE_IMAGE_PLACEHOLDER = "__ARTIFACTS_SHARE_IMAGE__"
SHARE_IMAGE_PATH = "assets/social/share-preview.png"


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


def _normalize_site_url(value: str) -> str:
    """Return a normalized canonical site URL with a trailing slash."""
    return value.rstrip("/") + "/"


def _load_site_url() -> str:
    """Load the configured canonical site URL from ``pyproject.toml``."""
    if not PYPROJECT_FILE.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {PYPROJECT_FILE}")

    pyproject = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))

    try:
        site_url = pyproject["tool"]["artifacts"]["site_url"]
    except KeyError as exc:
        raise ValueError("Missing tool.artifacts.site_url in pyproject.toml") from exc

    return _normalize_site_url(site_url)


def _resolve_version() -> str:
    """Return the deploy version from the environment or current Git SHA."""
    env_version = os.environ.get(DEPLOY_VERSION_ENV_VAR)
    if env_version:
        return env_version

    return subprocess.check_output(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=REPO_ROOT,
        text=True,
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    ).strip()


def _resolve_commit_sha() -> str:
    """Return the deploy commit SHA from the environment or current Git HEAD."""
    env_commit_sha = os.environ.get(DEPLOY_COMMIT_SHA_ENV_VAR)
    if env_commit_sha:
        return env_commit_sha

    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
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
        _copy_deploy_item(source, target)


def _copy_deploy_item(source: Path, target: Path) -> None:
    """Copy one deploy input after validating symlink safety."""
    if not source.exists():
        raise FileNotFoundError(f"Required deploy path not found: {source}")

    if source.is_symlink():
        raise ValueError(f"Refusing to copy symlinked deploy path: {source}")

    if not source.is_dir():
        shutil.copy2(source, target)
        return

    _validate_copy_tree(source)
    shutil.copytree(source, target)


def _validate_copy_tree(root_dir: Path) -> None:
    """Reject symlinks anywhere inside a deploy directory tree."""
    for root, dirnames, filenames in os.walk(root_dir, followlinks=False):
        for name in chain(dirnames, filenames):
            nested = Path(root) / name
            if nested.is_symlink():
                raise ValueError(
                    f"Refusing to copy deploy tree containing symlink: {nested}"
                )

        dirnames[:] = [
            name for name in dirnames if not (Path(root) / name).is_symlink()
        ]


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


def _patch_social_metadata(site_url: str, version: str) -> None:
    """Inject canonical URLs and a cache-busted social preview image."""
    index_path = DEPLOY_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    share_image_url = f"{urljoin(site_url, SHARE_IMAGE_PATH)}?v={version}"
    content = _replace_exact(content, SITE_URL_PLACEHOLDER, site_url)
    content = _replace_exact(content, SHARE_IMAGE_PLACEHOLDER, share_image_url)
    index_path.write_text(content, encoding="utf-8")


def _patch_root_stylesheet(version: str) -> None:
    """Apply cache-busting query strings to modular stylesheet imports."""
    stylesheet_path = DEPLOY_DIR / "css" / "style.css"
    if not stylesheet_path.exists():
        return

    content = stylesheet_path.read_text(encoding="utf-8")
    patched = ROOT_STYLESHEET_IMPORT_PATTERN.sub(
        lambda match: f'@import url("{match.group(1)}?v={version}");',
        content,
    )
    stylesheet_path.write_text(patched, encoding="utf-8")


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


def _write_deploy_metadata(*, commit_sha: str, version: str, site_path: str) -> None:
    """Write deploy metadata used by post-deploy verification."""
    metadata_path = DEPLOY_DIR / DEPLOY_METADATA_FILE
    metadata = {
        "commit_sha": commit_sha,
        "site_path": site_path,
        "version": version,
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def prepare_site() -> None:
    """Build the deployable ``_site/`` payload for GitHub Pages."""
    logger.info("Preparing deployable site output")
    site_path = _load_site_path()
    site_url = _load_site_url()
    commit_sha = _resolve_commit_sha()
    version = _resolve_version()
    _copy_deploy_items()
    _patch_index_html(version)
    _patch_social_metadata(site_url, version)
    _patch_root_stylesheet(version)
    _patch_404_html(site_path)
    _patch_manifest(site_path)
    _write_nojekyll()
    _write_deploy_metadata(commit_sha=commit_sha, version=version, site_path=site_path)
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
