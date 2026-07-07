"""Helpers for gallery metadata, generated config, and README output."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, TypedDict, cast

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.build.index_config import IndexConfig
    from scripts.lib.artifact_contract import ArtifactContract


class BadgeConfig(TypedDict):
    """Shields.io badge fields rendered for a tool in the README."""

    label: str
    color: str
    alt: str
    logo: str | None
    logo_color: str | None


MetadataEntry = Mapping[str, str | None]


class GalleryMetadata(TypedDict):
    """Shared tool and tag metadata consumed by generators and the frontend."""

    tools: list[dict[str, str | None]]
    tags: list[dict[str, str | None]]


def read_gallery_metadata(metadata_file: Path) -> GalleryMetadata:
    """Load shared gallery metadata used by generators and the frontend."""
    if not metadata_file.exists():
        raise FileNotFoundError(f"Gallery metadata file not found: {metadata_file}")

    metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    if not isinstance(metadata, dict):
        raise ValueError("Gallery metadata must be a JSON object")

    for group in ("tools", "tags"):
        validate_gallery_metadata_entries(group, metadata.get(group))

    return {
        "tools": cast("list[dict[str, str | None]]", metadata["tools"]),
        "tags": cast("list[dict[str, str | None]]", metadata["tags"]),
    }


def validate_gallery_metadata_entries(group: str, entries: object) -> None:
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


def display_order(entries: Sequence[MetadataEntry]) -> list[str]:
    """Return configured display order for a metadata group."""
    return [str(entry["id"]) for entry in entries]


def badge_config_map(entries: Sequence[MetadataEntry]) -> dict[str, BadgeConfig]:
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


def frontend_config(
    metadata: GalleryMetadata, *, artifact_contract: ArtifactContract
) -> dict[str, object]:
    """Build the browser config object consumed by the gallery UI."""
    return {
        "artifactContract": dict(artifact_contract),
        "toolDisplayOrder": display_order(metadata["tools"]),
        "tagDisplayOrder": display_order(metadata["tags"]),
        "tools": {str(entry["id"]): {"label": str(entry["label"])} for entry in metadata["tools"]},
        "tags": {str(entry["id"]): {"label": str(entry["label"])} for entry in metadata["tags"]},
    }


def write_frontend_config(
    metadata: GalleryMetadata,
    *,
    config: IndexConfig,
) -> None:
    """Write the generated browser config used by the root gallery."""
    config.js_config_output_file.parent.mkdir(exist_ok=True)
    config_content = json.dumps(
        frontend_config(metadata, artifact_contract=config.contract),
        indent=2,
        ensure_ascii=False,
    )
    config.js_config_output_file.write_text(
        f"window.ARTIFACTS_CONFIG = {config_content};\n",
        encoding="utf-8",
    )
    config.logger.info("Successfully generated %s", config.js_config_output_file)


def format_identifier_words(value: str, *, uppercase_identifier_words: set[str]) -> list[str]:
    """Format a kebab-case identifier into display words."""
    words = [word for word in value.split("-") if word]
    return [
        word.upper() if word in uppercase_identifier_words else word.capitalize() for word in words
    ]


def read_note_palette_file(
    palette_file: Path, *, note_color_pattern: re.Pattern[str]
) -> tuple[str, ...]:
    """Read the gallery desk-note palette from the shared CSS file."""
    if not palette_file.exists():
        return ()

    matches = note_color_pattern.findall(palette_file.read_text(encoding="utf-8"))
    ordered = sorted(
        (
            int(index),
            f"{int(red):02X}{int(green):02X}{int(blue):02X}",
        )
        for index, red, green, blue in matches
    )
    return tuple(color for _, color in ordered)


def fallback_badge_color(key: str, *, palette: Sequence[str]) -> str:
    """Choose a stable fallback badge color from the shared note palette."""
    if not palette:
        return "6C757D"

    color_index = hashlib.sha1(key.encode("utf-8")).digest()[0] % len(palette)
    return palette[color_index]


def replace_inline_marker(content: str, marker: str, value: str) -> str:
    """Replace a single inline README auto marker with a value."""
    pattern = re.compile(
        rf"(<!-- AUTO:{re.escape(marker)} -->)(.*?)(<!-- /AUTO:{re.escape(marker)} -->)",
        flags=re.DOTALL,
    )
    matches = pattern.findall(content)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one marker pair for {marker}, found {len(matches)}")
    return pattern.sub(
        lambda match: f"{match.group(1)}{value}{match.group(3)}",
        content,
        count=1,
    )


def replace_block_marker(content: str, marker: str, value: str) -> str:
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


def default_badge(
    identifier: str,
    *,
    uppercase_identifier_words: set[str],
    fallback_color_fn: Callable[[str], str],
) -> BadgeConfig:
    """Build a fallback badge config for unknown tags/tools."""
    words = format_identifier_words(
        identifier,
        uppercase_identifier_words=uppercase_identifier_words,
    )
    return {
        "label": "_".join(words),
        "color": fallback_color_fn(identifier),
        "alt": " ".join(words),
        "logo": None,
        "logo_color": None,
    }


def sort_items(items: set[str], display_order_values: list[str]) -> list[str]:
    """Sort items with known ones first, then unknown alphabetically."""
    known = [item for item in display_order_values if item in items]
    unknown = sorted(item for item in items if item not in display_order_values)
    return known + unknown


def build_badge(
    key: str,
    config: dict[str, BadgeConfig],
    *,
    default_badge_fn: Callable[[str], BadgeConfig],
) -> str:
    """Build one README badge image tag."""
    badge = config.get(key, default_badge_fn(key))
    src = f"https://img.shields.io/badge/{badge['label']}-{badge['color']}?style=flat-square"
    if badge["logo"]:
        src += f"&logo={badge['logo']}"
    if badge["logo_color"]:
        src += f"&logoColor={badge['logo_color']}"
    return f'<img src="{src}" alt="{badge["alt"]}">'


def build_badges_block(
    items: set[str],
    display_order_values: list[str],
    config: dict[str, BadgeConfig],
    *,
    build_badge_fn: Callable[[str, dict[str, BadgeConfig]], str],
) -> str:
    """Build the README badges block from discovered items."""
    sorted_items = sort_items(items, display_order_values)
    if not sorted_items:
        return ""
    return "\n".join(
        f"{build_badge_fn(item, config)}{'&nbsp;' if index < len(sorted_items) - 1 else ''}"
        for index, item in enumerate(sorted_items)
    )


def update_readme(
    *,
    items: Sequence[Mapping[str, object]],
    config: IndexConfig,
    site_url: str,
    gallery_metadata: GalleryMetadata,
) -> None:
    """Update README auto-managed markers."""
    if not config.readme_file.exists():
        raise FileNotFoundError(f"README file not found: {config.readme_file}")

    total_count = len(items)
    all_tags = {tag for item in items for tag in cast("list[str]", item["tags"])}
    all_tools = {tool for item in items for tool in cast("list[str]", item["tools"])}
    readme = config.readme_file.read_text(encoding="utf-8")
    total_badge = (
        f'<img src="https://img.shields.io/badge/Total-{total_count}'
        f'-D97706?style=for-the-badge" alt="Total">'
    )

    readme = replace_inline_marker(readme, "SITE_URL", site_url)
    readme = replace_inline_marker(readme, "TOTAL_BADGE", total_badge)
    readme = replace_inline_marker(readme, "TOTAL_COUNT", str(total_count))
    readme = replace_block_marker(
        readme,
        "TAG_BADGES",
        config.build_badges_block(
            all_tags,
            display_order(gallery_metadata["tags"]),
            badge_config_map(gallery_metadata["tags"]),
        ),
    )
    readme = replace_block_marker(
        readme,
        "TOOL_BADGES",
        config.build_badges_block(
            all_tools,
            display_order(gallery_metadata["tools"]),
            badge_config_map(gallery_metadata["tools"]),
        ),
    )
    config.readme_file.write_text(readme, encoding="utf-8")
    config.logger.info("Successfully updated %s", config.readme_file)
