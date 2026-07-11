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

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING
from urllib.parse import urljoin

from scripts import REPO_ROOT
from scripts.build.index_sources import artifact_url
from scripts.lib.app_discovery import thumbnail_file
from scripts.lib.artifact_contract import read_artifact_contract_file
from scripts.lib.path_validation import reject_symlinks
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
ROOT_STYLESHEET_IMPORT_PATTERN = re.compile(r'@import url\("(\./[^"?]+\.css)"\);')
MODULE_SCRIPT_PATTERN = re.compile(r'<script\s+type="module"\s+src="([^"]+)"')
JS_IMPORT_PATTERN = re.compile(
    r"""(?:import|export)\s+.*?\s+from\s+['"]([^'"]+)['"]""",
    re.DOTALL,
)
ESBUILD_BIN = REPO_ROOT / "node_modules" / ".bin" / "esbuild"
ESBUILD_TIMEOUT_SECONDS = 30
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


def _patch_app_asset_references(version: str) -> None:
    """Apply cache-busting query strings to app asset references."""
    apps_dir = DEPLOY_DIR / _artifact_base_path()
    if not apps_dir.exists():
        return

    replacements = {
        'href="../../css/style.css"': f'href="../../css/style.css?v={version}"',
        'href="./css/app.css"': f'href="./css/app.css?v={version}"',
        'src="../../js/app-theme.js"': f'src="../../js/app-theme.js?v={version}"',
        'src="./js/app.js"': f'src="./js/app.js?v={version}"',
    }

    for app_dir in apps_dir.iterdir():
        if not app_dir.is_dir():
            continue

        index_path = app_dir / "index.html"
        if not index_path.exists():
            continue

        content = index_path.read_text(encoding="utf-8")
        applicable = {old: new for old, new in replacements.items() if old in content}
        if not applicable:
            continue

        index_path.write_text(_replace_exact_many(content, applicable), encoding="utf-8")


def _patch_social_metadata(site_url: str, version: str) -> None:
    """Inject canonical URLs and a cache-busted social preview image."""
    index_path = DEPLOY_DIR / "index.html"
    content = index_path.read_text(encoding="utf-8")
    share_image_url = f"{urljoin(site_url, SHARE_IMAGE_PATH)}?v={version}"
    content = _replace_exact(content, SITE_URL_PLACEHOLDER, site_url)
    content = _replace_exact(content, SHARE_IMAGE_PLACEHOLDER, share_image_url)
    index_path.write_text(content, encoding="utf-8")


def _read_optional_text(path: Path, fallback: str = "") -> str:
    """Return stripped file text or ``fallback`` when the file is missing or blank."""
    if not path.exists():
        return fallback
    return path.read_text(encoding="utf-8").strip() or fallback


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
        title = _read_optional_text(app_dir / "name.txt", app_dir.name.replace("-", " ").title())
        description = _read_optional_text(app_dir / "description.txt")

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

        index_path.write_text(_replace_exact_many(content, replacements), encoding="utf-8")


def _inline_css_imports(css_file: Path) -> None:
    """Replace ``@import url()`` statements with the contents of imported files.

    This eliminates sequential blocking requests at runtime by concatenating
    CSS partials into a single file at build time.  Source partials remain
    untouched; only the copy in ``_site/`` is modified.
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
    """Inline CSS ``@import`` chains in the deploy stylesheet."""
    _inline_css_imports(DEPLOY_DIR / "css" / "style.css")

    for subdir in ("gallery", "app"):
        partial_dir = DEPLOY_DIR / "css" / subdir
        if not partial_dir.is_dir():
            continue
        referencing = [
            css_file
            for css_file in (DEPLOY_DIR / "css").iterdir()
            if css_file.suffix == ".css" and f"./{subdir}/" in css_file.read_text(encoding="utf-8")
        ]
        if referencing:
            logger.warning(
                "Keeping %s, still referenced by: %s",
                partial_dir.relative_to(DEPLOY_DIR),
                ", ".join(f.name for f in referencing),
            )
            continue
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

        content = js_file.read_text(encoding="utf-8")
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
        content = html_path.read_text(encoding="utf-8")
        script_match = MODULE_SCRIPT_PATTERN.search(content)
        if not script_match:
            continue

        entry_href = script_match.group(1).split("?")[0]
        entry_file = (html_path.parent / entry_href).resolve()
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
        html_path.write_text(content, encoding="utf-8")
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

    total_saved = 0

    for path in sorted(DEPLOY_DIR.rglob("*")):
        if path.suffix == ".css":
            label = "CSS"
        elif _is_minifiable_js(path):
            label = "JS"
        else:
            continue
        saved = _minify_file(path)
        total_saved += saved
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
    _inline_all_css_imports()
    _patch_index_html(version)
    _patch_app_asset_references(version)
    _patch_social_metadata(site_url, version)
    _patch_app_social_metadata(site_url, version)
    _patch_root_stylesheet(version)
    _patch_404_html(site_path)
    _patch_manifest(site_path)
    _inject_modulepreload_hints()
    _minify_site_assets()
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
