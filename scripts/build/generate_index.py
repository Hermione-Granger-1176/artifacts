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

import functools
import json
import logging
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from scripts import REPO_ROOT
from scripts.build import index_outputs, index_sources
from scripts.lib.app_discovery import _artifact_base_path
from scripts.lib.project_config import load_artifacts_setting

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
APPS_DIR = REPO_ROOT / _artifact_base_path()
JS_OUTPUT_FILE = REPO_ROOT / "js" / "data.js"
JS_CONFIG_OUTPUT_FILE = REPO_ROOT / "js" / "gallery-config.js"
README_FILE = REPO_ROOT / "README.md"
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
GALLERY_METADATA_FILE = REPO_ROOT / "config" / "gallery_metadata.json"
ARTIFACT_CONTRACT_FILE = REPO_ROOT / "config" / "artifact_contract.json"
ROOT_GALLERY_FOUNDATION_FILE = REPO_ROOT / "css" / "gallery" / "01-tokens.css"

INDEX_FILE = "index.html"
NAME_FILE = "name.txt"
DESCRIPTION_FILE = "description.txt"
TAGS_FILE = "tags.txt"
TOOLS_FILE = "tools.txt"
NOTE_COLOR_PATTERN = re.compile(
    r"--color-note-(\d+):\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\);"
)
UPPERCASE_IDENTIFIER_WORDS = {
    "ai",
    "api",
    "css",
    "html",
    "js",
    "json",
    "llm",
    "ui",
    "ux",
}
MISSING_REQUIRED_FILE_ISSUES = {
    (False, False): f"missing {INDEX_FILE} and {NAME_FILE}",
    (False, True): f"has {NAME_FILE} but no {INDEX_FILE}",
    (True, False): f"has {INDEX_FILE} but no {NAME_FILE}",
}

ArtifactItem = index_sources.ArtifactItem
ArtifactContract = index_sources.ArtifactContract
BadgeConfig = index_outputs.BadgeConfig
MetadataEntry = index_outputs.MetadataEntry
GalleryMetadata = index_outputs.GalleryMetadata


def _read_file(file_path: Path) -> str:
    """Read and strip a text file, returning empty string if missing."""
    return index_sources.read_file(file_path)


def _parse_lines(file_path: Path) -> list[str]:
    """Parse non-empty lines from a text file."""
    return index_sources.parse_lines(file_path)


@functools.cache
def _read_artifact_contract_file(contract_file: Path) -> ArtifactContract:
    """Load and validate the shared artifact path contract."""
    return cast(
        ArtifactContract,
        index_sources.read_artifact_contract_file(contract_file),
    )


def _artifact_contract() -> ArtifactContract:
    """Return the cached artifact contract used by Python and JS validation."""
    return _read_artifact_contract_file(ARTIFACT_CONTRACT_FILE)


@functools.cache
def _artifact_id_pattern() -> re.Pattern[str]:
    """Return the compiled artifact id pattern from the shared contract."""
    return index_sources.artifact_id_pattern(_artifact_contract())


def _artifact_url(artifact_id: str) -> str:
    """Build the canonical repo-relative URL for one artifact id."""
    return index_sources.artifact_url(_artifact_contract(), artifact_id)


def _artifact_thumbnail_path(artifact_id: str) -> str:
    """Build the canonical thumbnail path for one artifact id."""
    return index_sources.artifact_thumbnail_path(_artifact_contract(), artifact_id)


def _artifact_url_rule() -> str:
    """Return the human-readable artifact URL rule from the shared contract."""
    return index_sources.artifact_url_rule(_artifact_contract())


def _artifact_thumbnail_rule() -> str:
    """Return the human-readable thumbnail rule from the shared contract."""
    return index_sources.artifact_thumbnail_rule(_artifact_contract())


def _matches_artifact_url_shape(value: str) -> bool:
    """Return True when a value matches the shared artifact URL shape."""
    return index_sources.matches_artifact_url_shape(
        value,
        contract=_artifact_contract(),
        compiled_artifact_id_pattern=_artifact_id_pattern(),
    )


def _matches_artifact_thumbnail_shape(value: str) -> bool:
    """Return True when a value matches the shared thumbnail path shape."""
    return index_sources.matches_artifact_thumbnail_shape(
        value,
        contract=_artifact_contract(),
        compiled_artifact_id_pattern=_artifact_id_pattern(),
    )


def is_kebab_case(name: str) -> bool:
    """Return True when a directory name follows kebab-case."""
    return index_sources.is_kebab_case(
        name,
        compiled_artifact_id_pattern=_artifact_id_pattern(),
    )


def _validate_relative_repo_path(value: str, *, field_name: str) -> None:
    """Validate that a value is a safe repo-relative path."""
    index_sources.validate_relative_repo_path(value, field_name=field_name)


def _validate_artifact_item(item: ArtifactItem) -> None:
    """Validate one artifact item against the shared contract."""
    index_sources.validate_artifact_item(
        item,
        contract=_artifact_contract(),
        compiled_artifact_id_pattern=_artifact_id_pattern(),
    )


def _artifact_issues(folder: Path) -> list[str]:
    """Collect validation issues for one top-level artifact directory."""
    return index_sources.artifact_issues(
        folder,
        index_file=INDEX_FILE,
        name_file=NAME_FILE,
        missing_required_file_issues=MISSING_REQUIRED_FILE_ISSUES,
        is_kebab_case_fn=is_kebab_case,
        read_file_fn=_read_file,
    )


def _iter_artifact_dirs() -> list[Path]:
    """Return top-level visible artifact directories under apps/."""
    return index_sources.iter_artifact_dirs(APPS_DIR, logger=logger)


def _extract_artifact(folder: Path) -> ArtifactItem | None:
    """Extract structured data from an artifact folder."""
    return index_sources.extract_artifact(
        folder,
        name_file=NAME_FILE,
        description_file=DESCRIPTION_FILE,
        tags_file=TAGS_FILE,
        tools_file=TOOLS_FILE,
        read_file_fn=_read_file,
        parse_lines_fn=_parse_lines,
        resolve_thumbnail_fn=_resolve_thumbnail,
        artifact_url_fn=_artifact_url,
        validate_artifact_item_fn=_validate_artifact_item,
        logger=logger,
    )


def _resolve_thumbnail(folder: Path) -> str | None:
    """Resolve the preferred thumbnail path when one exists."""
    return index_sources.resolve_thumbnail(
        folder,
        contract=_artifact_contract(),
        artifact_thumbnail_path_fn=_artifact_thumbnail_path,
    )


def _read_gallery_metadata() -> GalleryMetadata:
    """Load shared gallery metadata used by generators and the frontend."""
    return cast(
        GalleryMetadata,
        index_outputs.read_gallery_metadata(GALLERY_METADATA_FILE),
    )


def _validate_gallery_metadata_entries(group: str, entries: object) -> None:
    """Validate one gallery metadata group."""
    index_outputs.validate_gallery_metadata_entries(group, entries)


def _display_order(entries: Sequence[MetadataEntry]) -> list[str]:
    """Return configured display order for a metadata group."""
    return index_outputs.display_order(entries)


def _badge_config_map(entries: Sequence[MetadataEntry]) -> dict[str, BadgeConfig]:
    """Build a badge config lookup from shared metadata entries."""
    return index_outputs.badge_config_map(entries)


def _format_identifier_words(value: str) -> list[str]:
    """Format a kebab-case identifier into display words."""
    return index_outputs.format_identifier_words(
        value,
        uppercase_identifier_words=UPPERCASE_IDENTIFIER_WORDS,
    )


@functools.cache
def _read_note_palette_file(palette_file: Path) -> tuple[str, ...]:
    """Read and cache the gallery desk-note palette from the shared CSS file."""
    return index_outputs.read_note_palette_file(
        palette_file,
        note_color_pattern=NOTE_COLOR_PATTERN,
    )


def _read_note_palette() -> tuple[str, ...]:
    """Read the gallery desk-note palette from the shared CSS variables."""
    return _read_note_palette_file(ROOT_GALLERY_FOUNDATION_FILE)


def _fallback_badge_color(key: str) -> str:
    """Choose a stable fallback badge color from the shared note palette."""
    return index_outputs.fallback_badge_color(key, palette=_read_note_palette())


def _frontend_config(metadata: GalleryMetadata) -> dict[str, object]:
    """Build the browser config object consumed by the gallery UI."""
    return index_outputs.frontend_config(
        metadata,
        artifact_contract=_artifact_contract(),
    )


def _write_frontend_config(metadata: GalleryMetadata) -> None:
    """Write the generated browser config used by the root gallery."""
    index_outputs.write_frontend_config(
        JS_CONFIG_OUTPUT_FILE,
        metadata,
        artifact_contract=_artifact_contract(),
        logger=logger,
    )


def _read_site_url() -> str:
    """Read the canonical live-site URL from pyproject.toml."""
    site_url = load_artifacts_setting(PYPROJECT_FILE, "site_url")
    return site_url.rstrip("/") + "/"


def _scan_artifacts() -> list[ArtifactItem]:
    """Scan the apps/ directory for artifact directories."""
    items: list[ArtifactItem] = []
    for folder in _iter_artifact_dirs():
        issues = _artifact_issues(folder)
        if issues:
            for issue in issues:
                logger.warning("%s: %s", folder.name, issue)
            continue

        item = _extract_artifact(folder)
        if item:
            items.append(item)

    logger.info("Found %d artifact(s)", len(items))
    return items


def _replace_inline_marker(content: str, marker: str, value: str) -> str:
    """Replace a single inline README auto marker with a value."""
    return index_outputs.replace_inline_marker(content, marker, value)


def _replace_block_marker(content: str, marker: str, value: str) -> str:
    """Replace content between AUTO marker start/end comments."""
    return index_outputs.replace_block_marker(content, marker, value)


def _default_badge(identifier: str) -> BadgeConfig:
    """Build a fallback badge config for unknown tags/tools."""
    return index_outputs.default_badge(
        identifier,
        uppercase_identifier_words=UPPERCASE_IDENTIFIER_WORDS,
        fallback_color_fn=_fallback_badge_color,
    )


def _sort_items(items: set[str], display_order: list[str]) -> list[str]:
    """Sort items with known ones first, then unknown alphabetically."""
    return index_outputs.sort_items(items, display_order)


def _build_badge(key: str, config: dict[str, BadgeConfig]) -> str:
    """Build one README badge image tag."""
    return index_outputs.build_badge(
        key,
        config,
        default_badge_fn=_default_badge,
    )


def _build_badges_block(
    items: set[str], display_order: list[str], config: dict[str, BadgeConfig]
) -> str:
    """Build the README badges block from discovered items."""
    return index_outputs.build_badges_block(
        items,
        display_order,
        config,
        build_badge_fn=_build_badge,
    )


def _update_readme(items: list[ArtifactItem]) -> None:
    """Update README auto-managed markers."""
    index_outputs.update_readme(
        README_FILE,
        items=items,
        site_url=_read_site_url(),
        gallery_metadata=_read_gallery_metadata(),
        logger=logger,
        replace_inline_marker_fn=_replace_inline_marker,
        replace_block_marker_fn=_replace_block_marker,
        build_badges_block_fn=_build_badges_block,
        display_order_fn=_display_order,
        badge_config_map_fn=_badge_config_map,
    )


def validate() -> None:
    """Validate artifact directory structure before generation."""
    logger.info("Validating artifact directories")

    issues = [
        f"{folder.name}: {issue}"
        for folder in _iter_artifact_dirs()
        for issue in _artifact_issues(folder)
    ]

    if issues:
        issue_list = "\n- ".join(issues)
        raise ValueError(f"Artifact validation failed:\n- {issue_list}")

    logger.info("Artifact validation passed")


def generate() -> None:
    """Generate gallery data files and update README snapshot markers."""
    logger.info("Starting artifact index generation")

    items = _scan_artifacts()

    if not items:
        logger.warning("No artifacts found")

    seen: set[str] = set()
    for item in items:
        if item["id"] in seen:
            raise ValueError(f"Duplicate artifact ID: '{item['id']}'")
        seen.add(item["id"])

    JS_OUTPUT_FILE.parent.mkdir(exist_ok=True)
    gallery_metadata = _read_gallery_metadata()

    js_content = (
        f"window.ARTIFACTS_DATA = {json.dumps(items, indent=2, ensure_ascii=False)};\n"
    )
    JS_OUTPUT_FILE.write_text(js_content, encoding="utf-8")
    _write_frontend_config(gallery_metadata)
    _update_readme(items)

    logger.info("Successfully generated %s with %d items", JS_OUTPUT_FILE, len(items))


if __name__ == "__main__":  # pragma: no cover
    try:
        generate()
    except (FileNotFoundError, ValueError) as e:
        logger.error("Failed to generate data: %s", e)
        sys.exit(1)
