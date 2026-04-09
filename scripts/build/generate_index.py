#!/usr/bin/env python3
"""Generate gallery metadata outputs from the artifact directories.

This module backs `make index` and `make validate`.

It scans top-level artifact directories and generates the JavaScript data files
used by the root gallery page. `js/data.js` contains artifact metadata, while
`js/gallery-config.js` contains shared display configuration consumed by the
browser UI.

It also updates auto-managed sections in `README.md`, including the site URL,
total count, total badge, tool badges, and tag badges, so the README snapshot
stays in sync.

Each artifact directory can contain:
    - index.html: Required. The artifact itself.
    - name.txt: Required. Display title.
    - description.txt: Optional. Short description.
    - tags.txt: Optional. One tag per line.
    - tools.txt: Optional. One AI tool per line.
    - thumbnail.webp: Preferred auto-generated thumbnail written by
      `generate_thumbnails.py`.

Run through the Makefile in normal workflows; direct invocation is mainly for
maintainers working on the build internals.
"""

from __future__ import annotations

import json
import logging
import os
import sys

from scripts import REPO_ROOT
from scripts.build import index_outputs, index_sources
from scripts.build.index_config import IndexConfig
from scripts.lib.app_discovery import _artifact_base_path

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)

# -- Path constants consumed by check_generated_drift.py -----------------------

APPS_DIR = REPO_ROOT / _artifact_base_path()
JS_OUTPUT_FILE = REPO_ROOT / "js" / "data.js"
JS_CONFIG_OUTPUT_FILE = REPO_ROOT / "js" / "gallery-config.js"
README_FILE = REPO_ROOT / "README.md"

# -- Type aliases re-exported for backward compatibility -----------------------

ArtifactItem = index_sources.ArtifactItem
ArtifactContract = index_sources.ArtifactContract
BadgeConfig = index_outputs.BadgeConfig
MetadataEntry = index_outputs.MetadataEntry
GalleryMetadata = index_outputs.GalleryMetadata

# -- Public convenience re-export for scaffold_artifact.py --------------------


def is_kebab_case(name: str) -> bool:
    """Return True when a directory name follows kebab-case.

    Uses the production artifact contract. Kept here for backward
    compatibility with ``scaffold_artifact.py`` and external callers.
    """
    config = IndexConfig.create_default()
    return config.is_kebab_case(name)


# -- Internal helpers ----------------------------------------------------------

def _scan_artifacts(config: IndexConfig) -> list[ArtifactItem]:
    """Scan the apps/ directory for artifact directories."""
    config.logger.debug("Scanning %s for artifacts", config.apps_dir)
    items: list[ArtifactItem] = []
    for folder in index_sources.iter_artifact_dirs(config):
        issues = index_sources.artifact_issues(folder, config=config)
        if issues:
            for issue in issues:
                config.logger.warning("%s: %s", folder.name, issue)
            continue

        item = index_sources.extract_artifact(folder, config=config)
        if item:
            items.append(item)

    config.logger.info("Found %d artifact(s)", len(items))
    return items


# -- Public API ----------------------------------------------------------------

def validate(config: IndexConfig | None = None) -> None:
    """Validate artifact directory structure before generation."""
    if config is None:
        config = IndexConfig.create_default()

    config.logger.info("Validating artifact directories")

    issues = [
        f"{folder.name}: {issue}"
        for folder in index_sources.iter_artifact_dirs(config)
        for issue in index_sources.artifact_issues(folder, config=config)
    ]

    if issues:
        issue_list = "\n- ".join(issues)
        raise ValueError(f"Artifact validation failed:\n- {issue_list}")

    config.logger.info("Artifact validation passed")


def generate(config: IndexConfig | None = None) -> None:
    """Generate gallery data files and update README snapshot markers."""
    if config is None:
        config = IndexConfig.create_default()

    config.logger.info("Starting artifact index generation")
    config.logger.debug(
        "Config: apps_dir=%s, js_output=%s, config_output=%s",
        config.apps_dir,
        config.js_output_file,
        config.js_config_output_file,
    )

    items = _scan_artifacts(config)

    if not items:
        config.logger.warning("No artifacts found")

    seen: set[str] = set()
    for item in items:
        if item["id"] in seen:
            raise ValueError(f"Duplicate artifact ID: '{item['id']}'")
        seen.add(item["id"])

    config.js_output_file.parent.mkdir(exist_ok=True)
    gallery_metadata = config.read_gallery_metadata()

    js_content = (
        f"window.ARTIFACTS_DATA = {json.dumps(items, indent=2, ensure_ascii=False)};\n"
    )
    config.js_output_file.write_text(js_content, encoding="utf-8")
    index_outputs.write_frontend_config(gallery_metadata, config=config)
    index_outputs.update_readme(
        items=items,
        config=config,
        site_url=config.read_site_url(),
        gallery_metadata=gallery_metadata,
    )

    config.logger.info(
        "Successfully generated %s with %d items", config.js_output_file, len(items)
    )


if __name__ == "__main__":  # pragma: no cover
    try:
        generate()
    except (FileNotFoundError, ValueError) as e:
        logger = logging.getLogger(__name__)
        logger.error("Failed to generate data: %s", e)
        sys.exit(1)
