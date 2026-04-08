#!/usr/bin/env python3
"""Prepare the deployable Pages payload in ``_site/``.

This module backs `make site`.

It copies the deployable static site into ``_site/``, then applies deploy-time
adjustments such as cache-busting query strings, the configured 404 fallback
path, and the ``.nojekyll`` marker needed for branch-based GitHub Pages.

Run through the Makefile in normal workflows; direct invocation is mainly for
maintainers working on the build internals.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

from scripts import REPO_ROOT
from scripts.build.index_sources import artifact_url, read_artifact_contract_file
from scripts.lib.app_discovery import thumbnail_file
from scripts.lib.path_validation import reject_symlinks
from scripts.lib.project_config import load_artifacts_setting

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
DEPLOY_DIR = REPO_ROOT / "_site"
GIT_COMMAND_TIMEOUT_SECONDS = 10
ROOT_STYLESHEET_IMPORT_PATTERN = re.compile(r'@import url\("(\./[^"?]+\.css)"\);')
DEPLOY_METADATA_FILE = "deploy-metadata.json"
DEPLOY_COMMIT_SHA_ENV_VAR = "ARTIFACTS_DEPLOY_COMMIT_SHA"
DEPLOY_VERSION_ENV_VAR = "ARTIFACTS_DEPLOY_VERSION"
SITE_URL_PLACEHOLDER = "__ARTIFACTS_SITE_URL__"
SHARE_IMAGE_PLACEHOLDER = "__ARTIFACTS_SHARE_IMAGE__"
APP_URL_PLACEHOLDER = "__APP_URL__"
APP_TITLE_PLACEHOLDER = "__APP_TITLE__"
APP_DESCRIPTION_PLACEHOLDER = "__APP_DESCRIPTION__"
APP_SHARE_IMAGE_PLACEHOLDER = "__APP_THUMBNAIL_URL__"
SHARE_IMAGE_PATH = "assets/social/share-preview.png"
ARTIFACT_CONTRACT_FILE = REPO_ROOT / "config" / "artifact_contract.json"


def _artifact_contract() -> dict[str, str]:
    """Return the validated shared artifact contract."""
    return read_artifact_contract_file(ARTIFACT_CONTRACT_FILE)


def _artifact_base_path() -> str:
    """Return the top-level artifact directory from the shared contract."""
    return _artifact_contract()["artifactBasePath"]


def _deploy_items() -> tuple[str, ...]:
    """Return deploy inputs including the configured artifact root."""
    return ("404.html", _artifact_base_path(), "assets", "css", "index.html", "js")


def _normalize_site_path(value: str) -> str:
    """Return a normalized GitHub Pages site path with surrounding slashes."""
    stripped = value.strip().strip("/")
    if not stripped:
        return "/"
    return f"/{stripped}/"


def _load_site_path() -> str:
    """Load the configured site path from ``pyproject.toml``."""
    return _normalize_site_path(load_artifacts_setting(PYPROJECT_FILE, "site_path"))


def _normalize_site_url(value: str) -> str:
    """Return a normalized canonical site URL with a trailing slash."""
    return value.rstrip("/") + "/"


def _load_site_url() -> str:
    """Load the configured canonical site URL from ``pyproject.toml``."""
    return _normalize_site_url(load_artifacts_setting(PYPROJECT_FILE, "site_url"))


def _read_git_output(*args: str) -> str:
    """Run one git command and return stripped stdout."""
    return subprocess.check_output(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        timeout=GIT_COMMAND_TIMEOUT_SECONDS,
    ).strip()


def _resolve_version() -> str:
    """Return the deploy version from the environment or current Git SHA."""
    env_version = os.environ.get(DEPLOY_VERSION_ENV_VAR)
    if env_version:
        return env_version

    return _read_git_output("rev-parse", "--short", "HEAD")


def _resolve_commit_sha() -> str:
    """Return the deploy commit SHA from the environment or current Git HEAD."""
    env_commit_sha = os.environ.get(DEPLOY_COMMIT_SHA_ENV_VAR)
    if env_commit_sha:
        return env_commit_sha

    return _read_git_output("rev-parse", "HEAD")


def _copy_deploy_items() -> None:
    """Copy the static site inputs into the clean deploy directory."""
    if DEPLOY_DIR.exists():
        shutil.rmtree(DEPLOY_DIR)

    DEPLOY_DIR.mkdir(parents=True)

    for item in _deploy_items():
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
    reject_symlinks(root_dir)


def _replace_exact(content: str, old: str, new: str) -> str:
    """Replace one exact string and raise an error if it is missing."""
    if old not in content:
        raise ValueError(f"Expected content not found: {old}")
    return content.replace(old, new)


def _replace_exact_many(content: str, replacements: dict[str, str]) -> str:
    """Apply a sequence of exact replacements, failing on the first missing one."""
    updated_content = content
    for old, new in replacements.items():
        updated_content = _replace_exact(updated_content, old, new)
    return updated_content


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

    content = _replace_exact_many(content, replacements)
    index_path.write_text(content, encoding="utf-8")


def _patch_social_metadata(site_url: str, version: str) -> None:
    """Inject canonical URLs and a cache-busted social preview image."""
    index_path = DEPLOY_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    share_image_url = f"{urljoin(site_url, SHARE_IMAGE_PATH)}?v={version}"
    content = _replace_exact(content, SITE_URL_PLACEHOLDER, site_url)
    content = _replace_exact(content, SHARE_IMAGE_PLACEHOLDER, share_image_url)
    index_path.write_text(content, encoding="utf-8")


def _patch_app_social_metadata(site_url: str, version: str) -> None:
    """Inject canonical URLs and per-app thumbnail URLs where placeholders exist."""
    apps_dir = DEPLOY_DIR / _artifact_base_path()
    if not apps_dir.exists():
        return

    for app_dir in apps_dir.iterdir():
        if not app_dir.is_dir():
            continue

        index_path = app_dir / "index.html"
        if not index_path.exists():
            continue

        content = index_path.read_text(encoding="utf-8")

        title = app_dir.name.replace("-", " ").title()
        name_path = app_dir / "name.txt"
        if name_path.exists():
            title = name_path.read_text(encoding="utf-8").strip() or title

        description = ""
        description_path = app_dir / "description.txt"
        if description_path.exists():
            description = description_path.read_text(encoding="utf-8").strip()

        app_url = urljoin(site_url, artifact_url(_artifact_contract(), app_dir.name))
        thumbnail_url = f"{urljoin(app_url, thumbnail_file())}?v={version}"

        candidates = {
            APP_URL_PLACEHOLDER: app_url,
            APP_TITLE_PLACEHOLDER: title,
            APP_DESCRIPTION_PLACEHOLDER: description,
            APP_SHARE_IMAGE_PLACEHOLDER: thumbnail_url,
        }
        replacements = {k: v for k, v in candidates.items() if k in content}
        if not replacements:
            continue

        index_path.write_text(
            _replace_exact_many(content, replacements), encoding="utf-8"
        )


def _inline_css_imports(css_file: Path) -> None:
    """Replace ``@import url()`` statements with the contents of imported files.

    This eliminates sequential blocking requests at runtime by concatenating
    CSS partials into a single file at build time.  Source partials remain
    untouched — only the copy in ``_site/`` is modified.
    """
    if not css_file.exists():
        return

    content = css_file.read_text(encoding="utf-8")
    parent_dir = css_file.parent

    def _read_import(match: re.Match[str]) -> str:
        import_path = (parent_dir / match.group(1)).resolve()
        if not import_path.is_relative_to(DEPLOY_DIR.resolve()):
            return match.group(0)
        if not import_path.exists():
            return match.group(0)
        return import_path.read_text(encoding="utf-8")

    inlined = ROOT_STYLESHEET_IMPORT_PATTERN.sub(_read_import, content)
    css_file.write_text(inlined, encoding="utf-8")
    logger.info("Inlined CSS imports in %s", css_file.relative_to(DEPLOY_DIR))


def _inline_all_css_imports() -> None:
    """Inline CSS ``@import`` chains in the deploy directory."""
    for css_entry in (
        DEPLOY_DIR / "css" / "style.css",
        DEPLOY_DIR / "css" / "app-shell.css",
    ):
        _inline_css_imports(css_entry)

    for subdir in ("gallery", "app"):
        partial_dir = DEPLOY_DIR / "css" / subdir
        if partial_dir.is_dir():
            shutil.rmtree(partial_dir)


def _patch_root_stylesheet(version: str) -> None:
    """Apply cache-busting query strings to modular stylesheet imports.

    After ``_inline_all_css_imports`` runs this is normally a no-op because
    there are no remaining ``@import`` statements.  It is kept for safety in
    case inlining is bypassed.
    """
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
    content = _replace_exact_many(
        content,
        {
            'data-site-path="/"': f'data-site-path="{site_path}"',
            'href="/"': f'href="{site_path}"',
        },
    )
    error_path.write_text(content, encoding="utf-8")


def _patch_manifest(site_path: str) -> None:
    """Inject the configured site path into the web app manifest."""
    manifest_path = DEPLOY_DIR / "assets" / "icons" / "manifest.webmanifest"
    if not manifest_path.exists():
        return
    content = manifest_path.read_text(encoding="utf-8")
    content = _replace_exact_many(
        content,
        {'"start_url": "../../"': f'"start_url": "{site_path}"'},
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
    _inline_all_css_imports()
    _patch_index_html(version)
    _patch_social_metadata(site_url, version)
    _patch_app_social_metadata(site_url, version)
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
