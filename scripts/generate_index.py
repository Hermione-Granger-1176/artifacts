#!/usr/bin/env python3
"""Generate gallery metadata outputs from the artifact directories.

Scans top-level artifact directories and generates the JavaScript data files
used by the root gallery page. `js/data.js` contains artifact metadata, while
`js/gallery-config.js` contains shared display configuration consumed by the
browser UI.

The script also updates auto-managed sections in README.md, including the site
URL, total count, total badge, tool badges, and tag badges, so the README
snapshot stays in sync.

Each artifact directory can contain:
    - index.html: Required. The artifact itself.
    - name.txt: Required. Display title.
    - description.txt: Optional. Short description.
    - tags.txt: Optional. One tag per line.
    - tools.txt: Optional. One AI tool per line.
    - thumbnail.webp: Preferred auto-generated thumbnail written by generate_thumbnails.py.
    - thumbnail.png: Legacy fallback thumbnail still accepted for compatibility.

Usage:
    python scripts/generate_index.py
"""

from __future__ import annotations

import json
import logging
import re
import sys
import tomllib
import urllib.parse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict, cast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "apps"
JS_OUTPUT_FILE = REPO_ROOT / "js" / "data.js"
JS_CONFIG_OUTPUT_FILE = REPO_ROOT / "js" / "gallery-config.js"
README_FILE = REPO_ROOT / "README.md"
PYPROJECT_FILE = REPO_ROOT / "pyproject.toml"
GALLERY_METADATA_FILE = REPO_ROOT / "config" / "gallery_metadata.json"

INDEX_FILE = "index.html"
NAME_FILE = "name.txt"
DESCRIPTION_FILE = "description.txt"
TAGS_FILE = "tags.txt"
TOOLS_FILE = "tools.txt"
PREFERRED_THUMBNAIL_FILE = "thumbnail.webp"
LEGACY_THUMBNAIL_FILE = "thumbnail.png"
THUMBNAIL_FILES = (PREFERRED_THUMBNAIL_FILE, LEGACY_THUMBNAIL_FILE)
KEBAB_CASE_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ARTIFACT_URL_PATTERN = re.compile(r"^apps/([a-z0-9]+(?:-[a-z0-9]+)*)/$")
THUMBNAIL_PATH_PATTERN = re.compile(
    r"^apps/([a-z0-9]+(?:-[a-z0-9]+)*)/(thumbnail\.(?:webp|png))$"
)
MISSING_REQUIRED_FILE_ISSUES = {
    (False, False): f"missing {INDEX_FILE} and {NAME_FILE}",
    (False, True): f"has {NAME_FILE} but no {INDEX_FILE}",
    (True, False): f"has {INDEX_FILE} but no {NAME_FILE}",
}


class ArtifactItem(TypedDict):
    id: str
    name: str
    description: str
    tags: list[str]
    tools: list[str]
    url: str
    thumbnail: str | None


class BadgeConfig(TypedDict):
    label: str
    color: str
    alt: str
    logo: str | None
    logo_color: str | None


MetadataEntry = Mapping[str, str | None]


class GalleryMetadata(TypedDict):
    tools: list[dict[str, str | None]]
    tags: list[dict[str, str | None]]


def _read_file(file_path: Path) -> str:
    """Read and strip a text file, returning empty string if missing."""
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8").strip()


def _parse_lines(file_path: Path) -> list[str]:
    """Parse non-empty lines from a text file."""
    content = _read_file(file_path)
    if not content:
        return []
    return [line.strip() for line in content.splitlines() if line.strip()]


def is_kebab_case(name: str) -> bool:
    """Return True when a directory name follows kebab-case."""
    return bool(KEBAB_CASE_PATTERN.fullmatch(name))


def _validate_relative_repo_path(value: str, *, field_name: str) -> None:
    decoded = urllib.parse.unquote(value)
    if "://" in value or "://" in decoded:
        raise ValueError(f"{field_name} must be a repo-relative path")
    if value.startswith("/") or decoded.startswith("/"):
        raise ValueError(f"{field_name} must not start with '/'")
    if value.lower().startswith("javascript:") or decoded.lower().startswith(
        "javascript:"
    ):
        raise ValueError(f"{field_name} must not use a javascript URL")
    if value.lower().startswith("data:") or decoded.lower().startswith("data:"):
        raise ValueError(f"{field_name} must not use a data URL")
    if ".." in decoded:
        raise ValueError(f"{field_name} must not contain path traversal segments")


def _validate_artifact_item(item: ArtifactItem) -> None:
    if not is_kebab_case(item["id"]):
        raise ValueError(f"Artifact id must use kebab-case: {item['id']}")

    _validate_relative_repo_path(item["url"], field_name="Artifact url")
    url_match = ARTIFACT_URL_PATTERN.fullmatch(item["url"])
    if not url_match:
        raise ValueError(f"Artifact url must match apps/<artifact-id>/: {item['url']}")
    if url_match.group(1) != item["id"]:
        raise ValueError(
            "Artifact url must use the same artifact id as the directory name: "
            f"{item['url']}"
        )

    thumbnail = item.get("thumbnail")
    if thumbnail is None:
        return

    _validate_relative_repo_path(thumbnail, field_name="Artifact thumbnail")
    thumbnail_match = THUMBNAIL_PATH_PATTERN.fullmatch(thumbnail)
    if not thumbnail_match:
        raise ValueError(
            "Artifact thumbnail must match apps/<artifact-id>/thumbnail.(webp|png): "
            f"{thumbnail}"
        )
    if thumbnail_match.group(1) != item["id"]:
        raise ValueError(
            "Artifact thumbnail must use the same artifact id as the directory name: "
            f"{thumbnail}"
        )


def _artifact_issues(folder: Path) -> list[str]:
    """Collect validation issues for one top-level artifact directory."""
    issues: list[str] = []
    has_index = (folder / INDEX_FILE).exists()
    has_name = (folder / NAME_FILE).exists()

    if not is_kebab_case(folder.name):
        issues.append("directory name must use kebab-case")

    missing_required_file_issue = MISSING_REQUIRED_FILE_ISSUES.get(
        (has_index, has_name)
    )
    if missing_required_file_issue:
        issues.append(missing_required_file_issue)

    if has_name and not _read_file(folder / NAME_FILE):
        issues.append(f"has an empty {NAME_FILE}")

    return issues


def _iter_artifact_dirs() -> list[Path]:
    """Return top-level visible artifact directories under apps/."""
    if not APPS_DIR.exists():
        logger.info("Directory not found: %s (skipping)", APPS_DIR)
        return []

    return sorted(
        (
            folder
            for folder in APPS_DIR.iterdir()
            if folder.is_dir() and not folder.name.startswith(".")
        ),
        key=lambda folder: folder.name,
    )


def _extract_artifact(folder: Path) -> ArtifactItem | None:
    """Extract structured data from an artifact folder."""
    name = _read_file(folder / NAME_FILE)
    if not name:
        logger.warning("Empty name.txt in %s, skipping", folder)
        return None

    description = _read_file(folder / DESCRIPTION_FILE)
    tags = _parse_lines(folder / TAGS_FILE)
    tools = _parse_lines(folder / TOOLS_FILE)

    thumbnail = _resolve_thumbnail(folder)

    item: ArtifactItem = {
        "id": folder.name,
        "name": name,
        "description": description,
        "tags": tags,
        "tools": tools,
        "url": f"apps/{folder.name}/",
        "thumbnail": thumbnail,
    }
    _validate_artifact_item(item)
    return item


def _resolve_thumbnail(folder: Path) -> str | None:
    """Resolve the preferred thumbnail path, with legacy fallback support."""
    thumbnail_file = next(
        (candidate for candidate in THUMBNAIL_FILES if (folder / candidate).exists()),
        None,
    )
    if thumbnail_file is None:
        return None
    return f"apps/{folder.name}/{thumbnail_file}"


def _read_gallery_metadata() -> GalleryMetadata:
    """Load shared gallery metadata used by generators and the frontend."""
    if not GALLERY_METADATA_FILE.exists():
        raise FileNotFoundError(
            f"Gallery metadata file not found: {GALLERY_METADATA_FILE}"
        )

    metadata = json.loads(GALLERY_METADATA_FILE.read_text(encoding="utf-8"))

    if not isinstance(metadata, dict):
        raise ValueError("Gallery metadata must be a JSON object")

    for group in ("tools", "tags"):
        _validate_gallery_metadata_entries(group, metadata.get(group))

    return {
        "tools": cast(list[dict[str, str | None]], metadata["tools"]),
        "tags": cast(list[dict[str, str | None]], metadata["tags"]),
    }


def _validate_gallery_metadata_entries(group: str, entries: object) -> None:
    """Validate one gallery metadata group."""

    if not isinstance(entries, list):
        raise ValueError(f"Gallery metadata '{group}' must be a list")

    required_fields = ("id", "label", "color", "alt")
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"Gallery metadata '{group}' entries must be objects")
        missing = [field for field in required_fields if not entry.get(field)]
        if missing:
            raise ValueError(
                f"Gallery metadata '{group}' entries must include " + ", ".join(missing)
            )


def _display_order(entries: Sequence[MetadataEntry]) -> list[str]:
    """Return configured display order for a metadata group."""
    return [str(entry["id"]) for entry in entries]


def _badge_config_map(entries: Sequence[MetadataEntry]) -> dict[str, BadgeConfig]:
    """Build a badge config lookup from shared metadata entries."""
    return {
        str(entry["id"]): {
            "label": str(entry["label"]),
            "color": str(entry["color"]),
            "alt": str(entry["alt"]),
            "logo": entry.get("logo"),
            "logo_color": entry.get("logo_color"),
        }
        for entry in entries
    }


def _frontend_config(metadata: GalleryMetadata) -> dict[str, object]:
    """Build the browser config object consumed by the gallery UI."""
    return {
        "toolDisplayOrder": _display_order(metadata["tools"]),
        "tagDisplayOrder": _display_order(metadata["tags"]),
        "tools": {
            str(entry["id"]): {"label": str(entry["label"])}
            for entry in metadata["tools"]
        },
        "tags": {
            str(entry["id"]): {"label": str(entry["label"])}
            for entry in metadata["tags"]
        },
    }


def _write_frontend_config(metadata: GalleryMetadata) -> None:
    """Write the generated browser config used by the root gallery."""
    JS_CONFIG_OUTPUT_FILE.parent.mkdir(exist_ok=True)
    config_content = json.dumps(
        _frontend_config(metadata), indent=2, ensure_ascii=False
    )
    JS_CONFIG_OUTPUT_FILE.write_text(
        f"window.ARTIFACTS_CONFIG = {config_content};\n",
        encoding="utf-8",
    )
    logger.info("Successfully generated %s", JS_CONFIG_OUTPUT_FILE)


def _read_site_url() -> str:
    """Read the canonical live-site URL from pyproject.toml."""
    if not PYPROJECT_FILE.exists():
        raise FileNotFoundError(f"pyproject.toml not found: {PYPROJECT_FILE}")

    pyproject = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf-8"))

    try:
        site_url = pyproject["tool"]["artifacts"]["site_url"]
    except KeyError as exc:
        raise ValueError("Missing tool.artifacts.site_url in pyproject.toml") from exc

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
    pattern = re.compile(
        rf"(<!-- AUTO:{re.escape(marker)} -->)(.*?)(<!-- /AUTO:{re.escape(marker)} -->)",
        flags=re.DOTALL,
    )
    matches = pattern.findall(content)
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one marker pair for {marker}, found {len(matches)}"
        )
    return pattern.sub(
        lambda match: f"{match.group(1)}{value}{match.group(3)}",
        content,
        count=1,
    )


def _replace_block_marker(content: str, marker: str, value: str) -> str:
    """Replace content between AUTO marker start/end comments."""
    pattern = re.compile(
        rf"(<!-- AUTO:{re.escape(marker)}_START -->)(.*?)(<!-- AUTO:{re.escape(marker)}_END -->)",
        flags=re.DOTALL,
    )
    matches = pattern.findall(content)
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly one block marker pair for {marker}, found {len(matches)}"
        )
    return pattern.sub(
        lambda match: f"{match.group(1)}\n{value}\n{match.group(3)}",
        content,
        count=1,
    )


def _default_badge(tag: str) -> BadgeConfig:
    """Build a fallback badge config for unknown tags/tools."""
    words = tag.split("-")
    return {
        "label": "_".join(word.capitalize() for word in words),
        "color": "6C757D",
        "alt": " ".join(word.capitalize() for word in words),
        "logo": None,
        "logo_color": None,
    }


def _sort_items(items: set[str], display_order: list[str]) -> list[str]:
    """Sort items with known ones first, then unknown alphabetically."""
    known = [item for item in display_order if item in items]
    unknown = sorted(item for item in items if item not in display_order)
    return known + unknown


def _build_badge(key: str, config: dict[str, BadgeConfig]) -> str:
    """Build one README badge image tag."""
    badge = config.get(key, _default_badge(key))
    src = (
        f"https://img.shields.io/badge/{badge['label']}-{badge['color']}"
        "?style=flat-square"
    )
    if badge["logo"]:
        src += f"&logo={badge['logo']}"
    if badge["logo_color"]:
        src += f"&logoColor={badge['logo_color']}"
    return f'<img src="{src}" alt="{badge["alt"]}">'


def _build_badges_block(
    items: set[str], display_order: list[str], config: dict[str, BadgeConfig]
) -> str:
    """Build the README badges block from discovered items."""
    sorted_items = _sort_items(items, display_order)
    if not sorted_items:
        return ""
    return "\n".join(
        f"{_build_badge(item, config)}{'&nbsp;' if index < len(sorted_items) - 1 else ''}"
        for index, item in enumerate(sorted_items)
    )


def _update_readme(items: list[ArtifactItem]) -> None:
    """Update README auto-managed markers."""
    if not README_FILE.exists():
        raise FileNotFoundError(f"README file not found: {README_FILE}")

    site_url = _read_site_url()
    gallery_metadata = _read_gallery_metadata()
    total_count = len(items)
    all_tags = {tag for item in items for tag in item["tags"]}
    all_tools = {tool for item in items for tool in item["tools"]}

    readme = README_FILE.read_text(encoding="utf-8")

    total_badge = (
        f'<img src="https://img.shields.io/badge/Total-{total_count}'
        f'-D97706?style=for-the-badge" alt="Total">'
    )

    readme = _replace_inline_marker(readme, "SITE_URL", site_url)
    readme = _replace_inline_marker(readme, "TOTAL_BADGE", total_badge)
    readme = _replace_inline_marker(readme, "TOTAL_COUNT", str(total_count))
    readme = _replace_block_marker(
        readme,
        "TAG_BADGES",
        _build_badges_block(
            all_tags,
            _display_order(gallery_metadata["tags"]),
            _badge_config_map(gallery_metadata["tags"]),
        ),
    )
    readme = _replace_block_marker(
        readme,
        "TOOL_BADGES",
        _build_badges_block(
            all_tools,
            _display_order(gallery_metadata["tools"]),
            _badge_config_map(gallery_metadata["tools"]),
        ),
    )
    README_FILE.write_text(readme, encoding="utf-8")
    logger.info("Successfully updated %s", README_FILE)


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
