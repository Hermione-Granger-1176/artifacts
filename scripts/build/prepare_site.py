#!/usr/bin/env python3
"""Prepare the deployable Pages payload in ``_site/``.

This module backs `make site`.

It copies the deployable static site into ``_site/``, then applies deploy-time
adjustments such as cache-busting query strings, the configured 404 fallback
path, and the ``.nojekyll`` marker needed by GitHub Pages.

Run through the Makefile in normal workflows; direct invocation is mainly for
maintainers working on the build internals.
"""

from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from scripts import REPO_ROOT
from scripts.build.index_sources import artifact_url
from scripts.lib.app_discovery import thumbnail_file
from scripts.lib.artifact_contract import read_artifact_contract_file
from scripts.lib.path_validation import reject_path_symlinks, reject_symlinks
from scripts.lib.project_config import load_artifacts_setting, load_site_url

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.lib.artifact_contract import ArtifactContract

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
DEPLOY_DIR = REPO_ROOT / "_site"
GIT_COMMAND_TIMEOUT_SECONDS = 10
MODULE_SCRIPT_PATTERN = re.compile(r'<script\s+type="module"\s+src="([^"]+)"')
JS_IMPORT_PATTERN = re.compile(
    r"""(?:import|export)\s+.*?\s+from\s+['"]([^'"]+)['"]""",
    re.DOTALL,
)
ESBUILD_BIN = REPO_ROOT / "node_modules" / ".bin" / "esbuild"
ESBUILD_TIMEOUT_SECONDS = 30
MAX_MINIFY_WORKERS = 8
VENDOR_DIR_NAME = "vendor"
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


def _artifact_contract() -> ArtifactContract:
    """Return the validated shared artifact contract."""
    return read_artifact_contract_file(REPO_ROOT / "config" / "artifact_contract.json")


def _artifact_base_path() -> str:
    """Return the top-level artifact directory from the shared contract."""
    return _artifact_contract()["artifactBasePath"]


def _deploy_items() -> tuple[str, ...]:
    """Return root-level deploy inputs excluding separately filtered app files."""
    return ("404.html", "assets", "css", "index.html", "js")


def _reject_symlinked_path(path: Path, *, label: str) -> None:
    """Reject one symlink before a direct filesystem operation."""
    reject_path_symlinks(path, label=label)


def _read_text(path: Path) -> str:
    """Read UTF-8 text only after refusing a symlinked input."""
    _reject_symlinked_path(path, label="Read input")
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    """Write UTF-8 text only after refusing a symlinked output."""
    _reject_symlinked_path(path, label="Write output")
    path.write_text(content, encoding="utf-8")


def _normalize_site_path(value: str) -> str:
    """Return a normalized GitHub Pages site path with surrounding slashes."""
    stripped = value.strip().strip("/")
    if not stripped:
        return "/"
    return f"/{stripped}/"


def _load_site_path() -> str:
    """Load the configured site path from ``pyproject.toml``."""
    return _normalize_site_path(load_artifacts_setting(PYPROJECT_FILE, "site_path"))


def _load_site_url() -> str:
    """Load the configured canonical site URL from ``pyproject.toml``."""
    return load_site_url(PYPROJECT_FILE)


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
    if DEPLOY_DIR.exists() or DEPLOY_DIR.is_symlink():
        _reject_symlinked_path(DEPLOY_DIR, label="Removal target")
        reject_symlinks(DEPLOY_DIR)
        shutil.rmtree(DEPLOY_DIR)

    DEPLOY_DIR.mkdir(parents=True)

    for item in _deploy_items():
        source = REPO_ROOT / item
        target = DEPLOY_DIR / item
        _copy_deploy_item(source, target)
    _copy_runtime_apps()


def _copy_runtime_apps() -> None:
    """Copy only files fetched at runtime from each artifact into the deploy tree."""
    apps_source = REPO_ROOT / _artifact_base_path()
    apps_target = DEPLOY_DIR / _artifact_base_path()
    _reject_symlinked_path(apps_source, label="Copy source")
    if not apps_source.exists():
        raise FileNotFoundError(f"Required deploy path not found: {apps_source}")
    reject_symlinks(apps_source)
    apps_target.mkdir(parents=True)
    runtime_names = ("assets", "css", "js", "index.html", thumbnail_file())
    for app_source in sorted(path for path in apps_source.iterdir() if path.is_dir()):
        app_target = apps_target / app_source.name
        app_target.mkdir()
        for name in runtime_names:
            source = app_source / name
            if source.exists():
                _copy_deploy_item(source, app_target / name)


def _remove_build_only_sources() -> None:
    """Remove stylesheet sources that are compiled into the public bundle."""
    source_dir = DEPLOY_DIR / "css" / "src"
    if source_dir.is_dir():
        _reject_symlinked_path(source_dir, label="Removal target")
        reject_symlinks(source_dir)
        shutil.rmtree(source_dir)


def _copy_deploy_item(source: Path, target: Path) -> None:
    """Copy one deploy input after validating symlink safety."""
    if source.is_symlink():
        raise ValueError(f"Refusing to copy symlinked deploy path: {source}")
    if not source.exists():
        raise FileNotFoundError(f"Required deploy path not found: {source}")

    if not source.is_dir():
        _reject_symlinked_path(target, label="Copy target")
        shutil.copy2(source, target)
        return

    _validate_copy_tree(source)
    _reject_symlinked_path(target, label="Copy target")
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


def _content_hash(path: Path) -> str:
    """Return a short stable content hash for one deployed cache-busted asset."""
    _reject_symlinked_path(path, label="Hash input")
    if not path.is_file():
        raise FileNotFoundError(f"Required deploy asset not found: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _patch_index_html() -> None:
    """Apply cache-busting query strings to root HTML asset references."""
    index_path = DEPLOY_DIR / "index.html"
    content = _read_text(index_path)
    style_hash = _content_hash(DEPLOY_DIR / "css/style.css")
    gallery_config_hash = _content_hash(DEPLOY_DIR / "js/gallery-config.js")
    data_hash = _content_hash(DEPLOY_DIR / "js/data.js")
    app_hash = _content_hash(DEPLOY_DIR / "js/app.js")
    replacements = {
        'href="css/style.css"': f'href="css/style.css?v={style_hash}"',
        'src="js/gallery-config.js"': f'src="js/gallery-config.js?v={gallery_config_hash}"',
        'src="js/data.js"': f'src="js/data.js?v={data_hash}"',
        'src="js/app.js"': f'src="js/app.js?v={app_hash}"',
    }

    content = _replace_exact_many(content, replacements)
    _write_text(index_path, content)


def _patch_app_asset_references() -> None:
    """Apply cache-busting query strings to app asset references."""
    apps_dir = DEPLOY_DIR / _artifact_base_path()
    if not apps_dir.exists():
        return

    for app_dir in apps_dir.iterdir():
        if not app_dir.is_dir():
            continue

        index_path = app_dir / "index.html"
        if not index_path.exists():
            continue

        content = _read_text(index_path)
        asset_paths = {
            'href="../../css/style.css"': DEPLOY_DIR / "css/style.css",
            'href="./css/app.css"': app_dir / "css/app.css",
            'src="../../js/app-theme.js"': DEPLOY_DIR / "js/app-theme.js",
            'src="./js/app.js"': app_dir / "js/app.js",
        }
        applicable = {
            old: f'{old[:-1]}?v={_content_hash(asset_path)}"'
            for old, asset_path in asset_paths.items()
            if old in content
        }
        if not applicable:
            continue

        _write_text(index_path, _replace_exact_many(content, applicable))


def _patch_social_metadata(site_url: str) -> None:
    """Inject canonical URLs and a cache-busted social preview image."""
    index_path = DEPLOY_DIR / "index.html"
    content = _read_text(index_path)
    share_image_url = (
        f"{urljoin(site_url, SHARE_IMAGE_PATH)}?v={_content_hash(DEPLOY_DIR / SHARE_IMAGE_PATH)}"
    )
    content = _replace_exact(content, SITE_URL_PLACEHOLDER, site_url)
    content = _replace_exact(content, SHARE_IMAGE_PLACEHOLDER, share_image_url)
    _write_text(index_path, content)


def _read_optional_text(path: Path, fallback: str = "") -> str:
    """Return stripped file text or ``fallback`` when the file is missing or blank."""
    if not path.exists():
        return fallback
    return _read_text(path).strip() or fallback


def _patch_app_social_metadata(site_url: str) -> None:
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

        content = _read_text(index_path)
        if not any(
            placeholder in content
            for placeholder in (
                APP_URL_PLACEHOLDER,
                APP_TITLE_PLACEHOLDER,
                APP_DESCRIPTION_PLACEHOLDER,
                APP_SHARE_IMAGE_PLACEHOLDER,
            )
        ):
            continue
        source_app_dir = REPO_ROOT / _artifact_base_path() / app_dir.name
        _reject_symlinked_path(source_app_dir, label="Metadata source")
        title = _read_optional_text(
            source_app_dir / "name.txt", app_dir.name.replace("-", " ").title()
        )
        description = _read_optional_text(source_app_dir / "description.txt")

        app_url = urljoin(site_url, artifact_url(_artifact_contract(), app_dir.name))
        thumbnail_url = ""
        if APP_SHARE_IMAGE_PLACEHOLDER in content:
            thumbnail_hash = _content_hash(app_dir / thumbnail_file())
            thumbnail_url = f"{urljoin(app_url, thumbnail_file())}?v={thumbnail_hash}"

        candidates = {
            APP_URL_PLACEHOLDER: app_url,
            APP_TITLE_PLACEHOLDER: html.escape(title, quote=True),
            APP_DESCRIPTION_PLACEHOLDER: html.escape(description, quote=True),
            APP_SHARE_IMAGE_PLACEHOLDER: thumbnail_url,
        }
        replacements = {k: v for k, v in candidates.items() if k in content}
        _write_text(index_path, _replace_exact_many(content, replacements))


def _patch_404_html(site_path: str) -> None:
    """Inject the configured site path into the 404 fallback page."""
    error_path = DEPLOY_DIR / "404.html"
    content = _read_text(error_path)
    content = _replace_exact_many(
        content,
        {
            'data-site-path="/"': f'data-site-path="{site_path}"',
            'href="/"': f'href="{site_path}"',
        },
    )
    _write_text(error_path, content)


def _patch_manifest(site_path: str) -> None:
    """Inject the configured site path into the web app manifest."""
    manifest_path = DEPLOY_DIR / "assets" / "icons" / "manifest.webmanifest"
    if not manifest_path.exists():
        return
    content = _read_text(manifest_path)
    content = _replace_exact_many(
        content,
        {'"start_url": "../../"': f'"start_url": "{site_path}"'},
    )
    _write_text(manifest_path, content)


def _write_nojekyll() -> None:
    """Write the marker file that disables Jekyll processing on Pages."""
    _write_text(DEPLOY_DIR / ".nojekyll", "")


def _write_deploy_metadata(*, commit_sha: str, version: str, site_path: str) -> None:
    """Write deploy metadata used by post-deploy verification."""
    metadata_path = DEPLOY_DIR / DEPLOY_METADATA_FILE
    metadata = {
        "commit_sha": commit_sha,
        "site_path": site_path,
        "version": version,
    }
    _write_text(
        metadata_path,
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
    )


def _resolve_module_tree(entry_file: Path) -> list[Path]:
    """Walk ES module imports starting from *entry_file* and return all dependencies.

    Only static ``import … from "…"`` and ``export … from "…"`` are followed.
    Dynamic ``import()`` is ignored because the browser discovers them at runtime.
    The entry file itself is excluded from the result (it is already referenced by
    the ``<script>`` tag).
    """
    visited: set[Path] = set()
    result: list[Path] = []
    deploy_root = DEPLOY_DIR.resolve()

    def _walk(js_file: Path) -> None:
        visited.add(js_file.resolve())

        if not js_file.exists():
            return

        content = _read_text(js_file)
        for match in JS_IMPORT_PATTERN.finditer(content):
            dep_path = (js_file.parent / match.group(1)).resolve()
            if dep_path in visited or not dep_path.is_relative_to(deploy_root):
                continue
            if dep_path.exists():
                result.append(dep_path)
            _walk(dep_path)

    _walk(entry_file)
    return result


def _relative_href(dep: Path, html_dir: Path) -> str:
    """Return a forward-slash relative href from an HTML directory to a module."""
    return os.path.relpath(dep, html_dir).replace(os.sep, "/")


def _inject_modulepreload_hints() -> None:
    """Inject ``<link rel="modulepreload">`` tags for every ES module dependency.

    For each HTML file in ``_site/`` that contains a ``<script type="module">``,
    the full static import tree is walked and matching ``<link>`` hints are
    inserted before ``</head>`` so the browser can fetch all modules in parallel.
    """
    for html_path in DEPLOY_DIR.rglob("*.html"):
        content = _read_text(html_path)
        script_match = MODULE_SCRIPT_PATTERN.search(content)
        if not script_match:
            continue

        entry_href = script_match.group(1).split("?")[0]
        entry_file = (html_path.parent / entry_href).resolve()
        if not entry_file.is_relative_to(DEPLOY_DIR.resolve()):
            continue
        logger.debug("Walking module tree from %s", entry_file)
        deps = _resolve_module_tree(entry_file)
        if not deps:
            continue

        html_dir = html_path.parent.resolve()
        hints = [
            f'  <link rel="modulepreload" href="{_relative_href(dep, html_dir)}">' for dep in deps
        ]

        insertion = "\n".join(hints) + "\n"
        content = content.replace("</head>", insertion + "</head>")
        _write_text(html_path, content)
        logger.info(
            "Injected %d modulepreload hint(s) in %s",
            len(hints),
            html_path.relative_to(DEPLOY_DIR),
        )


def _is_minifiable_js(path: Path) -> bool:
    """Return True when ``path`` is a JS file eligible for minification."""
    return (
        path.suffix in (".js", ".mjs")
        and ".min." not in path.name
        and VENDOR_DIR_NAME not in path.parts
    )


def _minify_file(file_path: Path) -> int:
    """Minify ``file_path`` in-place using esbuild and return bytes saved."""
    _reject_symlinked_path(file_path, label="Minify target")
    original_size = file_path.stat().st_size
    subprocess.run(
        [
            str(ESBUILD_BIN),
            str(file_path),
            "--minify",
            f"--outfile={file_path}",
            "--allow-overwrite",
        ],
        check=True,
        capture_output=True,
        timeout=ESBUILD_TIMEOUT_SECONDS,
    )
    new_size = file_path.stat().st_size
    return original_size - new_size


def _minify_site_assets() -> None:
    """Minify CSS and JS files in ``_site/`` using esbuild."""
    if not ESBUILD_BIN.exists():
        logger.warning("esbuild not found at %s, skipping minification", ESBUILD_BIN)
        return

    paths: list[Path] = []
    for path in sorted(DEPLOY_DIR.rglob("*")):
        if path.suffix == ".css" or _is_minifiable_js(path):
            paths.append(path)

    if not paths:
        logger.info("Minified site assets (saved 0 bytes total)")
        return

    worker_count = min(MAX_MINIFY_WORKERS, os.cpu_count() or 1, len(paths))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        saved_by_path = list(executor.map(_minify_file, paths))

    total_saved = sum(saved_by_path)
    for path, saved in zip(paths, saved_by_path, strict=True):
        label = "CSS" if path.suffix == ".css" else "JS"
        logger.debug("Minified %s %s (saved %d bytes)", label, path.name, saved)

    logger.info("Minified site assets (saved %d bytes total)", total_saved)


def prepare_site() -> None:
    """Build the deployable ``_site/`` payload for GitHub Pages."""
    logger.info("Preparing deployable site output")
    site_path = _load_site_path()
    site_url = _load_site_url()
    commit_sha = _resolve_commit_sha()
    version = _resolve_version()
    logger.debug(
        "Config: site_path=%s, site_url=%s, version=%s, commit_sha=%s",
        site_path,
        site_url,
        version,
        commit_sha,
    )
    _copy_deploy_items()
    _remove_build_only_sources()
    _inject_modulepreload_hints()
    _minify_site_assets()
    _patch_index_html()
    _patch_app_asset_references()
    _patch_social_metadata(site_url)
    _patch_app_social_metadata(site_url)
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
