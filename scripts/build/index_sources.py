"""Helpers for artifact contract validation and source discovery."""

from __future__ import annotations

import re
import urllib.parse
from typing import TYPE_CHECKING, TypedDict

from scripts.lib.artifact_contract import ArtifactContract, read_artifact_contract_file

if TYPE_CHECKING:
    from pathlib import Path

    from scripts.build.index_config import IndexConfig

__all__ = ["ArtifactContract", "read_artifact_contract_file"]


class ArtifactItem(TypedDict):
    id: str
    name: str
    description: str
    tags: list[str]
    tools: list[str]
    url: str
    thumbnail: str | None


def read_file(file_path: Path) -> str:
    """Read and strip a text file, returning an empty string when missing."""
    if not file_path.exists():
        return ""
    return file_path.read_text(encoding="utf-8").strip()


def parse_lines(file_path: Path) -> list[str]:
    """Parse non-empty stripped lines from a text file."""
    content = read_file(file_path)
    if not content:
        return []
    return [line.strip() for line in content.splitlines() if line.strip()]


def artifact_id_pattern(contract: ArtifactContract) -> re.Pattern[str]:
    """Compile the artifact id pattern from the shared contract."""
    return re.compile(contract["artifactIdPattern"])


def artifact_url(contract: ArtifactContract, artifact_id: str) -> str:
    """Build the canonical repo-relative URL for one artifact id."""
    return f"{contract['artifactBasePath']}/{artifact_id}/"


def artifact_thumbnail_path(contract: ArtifactContract, artifact_id: str) -> str:
    """Build the canonical thumbnail path for one artifact id."""
    return f"{contract['artifactBasePath']}/{artifact_id}/{contract['thumbnailFile']}"


def artifact_url_rule(contract: ArtifactContract) -> str:
    """Return the human-readable artifact URL rule."""
    return artifact_url(contract, "<artifact-id>")


def artifact_thumbnail_rule(contract: ArtifactContract) -> str:
    """Return the human-readable thumbnail rule."""
    return artifact_thumbnail_path(contract, "<artifact-id>")


def matches_artifact_url_shape(
    value: str,
    *,
    contract: ArtifactContract,
    compiled_artifact_id_pattern: re.Pattern[str],
) -> bool:
    """Return True when a value matches the shared artifact URL shape."""
    parts = value.split("/")
    return (
        len(parts) == 3
        and parts[0] == contract["artifactBasePath"]
        and parts[2] == ""
        and bool(compiled_artifact_id_pattern.fullmatch(parts[1]))
    )


def matches_artifact_thumbnail_shape(
    value: str,
    *,
    contract: ArtifactContract,
    compiled_artifact_id_pattern: re.Pattern[str],
) -> bool:
    """Return True when a value matches the shared thumbnail path shape."""
    parts = value.split("/")
    return (
        len(parts) == 3
        and parts[0] == contract["artifactBasePath"]
        and parts[2] == contract["thumbnailFile"]
        and bool(compiled_artifact_id_pattern.fullmatch(parts[1]))
    )


def is_kebab_case(name: str, *, compiled_artifact_id_pattern: re.Pattern[str]) -> bool:
    """Return True when a directory name follows the shared slug pattern."""
    return bool(compiled_artifact_id_pattern.fullmatch(name))


def validate_relative_repo_path(value: str, *, field_name: str) -> None:
    """Validate a repo-relative path used in generated gallery metadata."""
    decoded = urllib.parse.unquote(value)
    candidates = (value, decoded)
    if any("://" in candidate for candidate in candidates):
        raise ValueError(f"{field_name} must be a repo-relative path")
    if any(candidate.startswith("/") for candidate in candidates):
        raise ValueError(f"{field_name} must not start with '/'")
    if any(candidate.lower().startswith("javascript:") for candidate in candidates):
        raise ValueError(f"{field_name} must not use a javascript URL")
    if any(candidate.lower().startswith("data:") for candidate in candidates):
        raise ValueError(f"{field_name} must not use a data URL")
    if ".." in decoded:
        raise ValueError(f"{field_name} must not contain path traversal segments")


def validate_artifact_item(
    item: ArtifactItem,
    *,
    config: IndexConfig,
) -> None:
    """Validate one generated artifact record against the shared contract."""
    if not is_kebab_case(item["id"], compiled_artifact_id_pattern=config.compiled_id_pattern):
        raise ValueError(f"Artifact id must use kebab-case: {item['id']}")

    validate_relative_repo_path(item["url"], field_name="Artifact url")
    expected_url = artifact_url(config.contract, item["id"])
    if item["url"] != expected_url:
        if matches_artifact_url_shape(
            item["url"],
            contract=config.contract,
            compiled_artifact_id_pattern=config.compiled_id_pattern,
        ):
            raise ValueError(
                f"Artifact url must use the same artifact id as the directory name: {item['url']}"
            )
        raise ValueError(
            f"Artifact url must match {artifact_url_rule(config.contract)}: {item['url']}"
        )

    thumbnail = item.get("thumbnail")
    if thumbnail is None:
        return

    validate_relative_repo_path(thumbnail, field_name="Artifact thumbnail")
    expected_thumbnail = artifact_thumbnail_path(config.contract, item["id"])
    if thumbnail != expected_thumbnail:
        if matches_artifact_thumbnail_shape(
            thumbnail,
            contract=config.contract,
            compiled_artifact_id_pattern=config.compiled_id_pattern,
        ):
            raise ValueError(
                "Artifact thumbnail must use the same artifact id as the directory "
                f"name: {thumbnail}"
            )
        raise ValueError(
            f"Artifact thumbnail must match {artifact_thumbnail_rule(config.contract)}: {thumbnail}"
        )


def artifact_issues(
    folder: Path,
    *,
    config: IndexConfig,
) -> list[str]:
    """Collect validation issues for one top-level artifact directory."""
    issues: list[str] = []
    has_index = (folder / config.index_file).exists()
    has_name = (folder / config.name_file).exists()

    if not config.is_kebab_case(folder.name):
        issues.append("directory name must use kebab-case")

    missing_required_file_issue = config.missing_file_issues.get((has_index, has_name))
    if missing_required_file_issue:
        issues.append(missing_required_file_issue)

    if has_name and not read_file(folder / config.name_file):
        issues.append(f"has an empty {config.name_file}")

    return issues


def iter_artifact_dirs(config: IndexConfig) -> list[Path]:
    """Return top-level visible artifact directories under apps/."""
    if not config.apps_dir.exists():
        config.logger.info("Directory not found: %s (skipping)", config.apps_dir)
        return []

    return sorted(
        (
            folder
            for folder in config.apps_dir.iterdir()
            if folder.is_dir() and not folder.name.startswith(".")
        ),
        key=lambda folder: folder.name,
    )


def resolve_thumbnail(
    folder: Path,
    *,
    config: IndexConfig,
) -> str:
    """Return the canonical thumbnail path for an artifact.

    Every artifact is guaranteed a thumbnail by the build/deploy pipeline (CI
    renders and persists ``thumbnail.webp``), so the path is a stable contract
    value, not a presence flag. Decoupling it from on-disk presence keeps the
    generated-drift check stable no matter when thumbnails are rendered,
    invalidated, or persisted - which is what lets a brand-new app land with a
    correct ``data.js`` before its webp has been generated yet.
    """
    return config.artifact_thumbnail_path(folder.name)


def extract_artifact(
    folder: Path,
    *,
    config: IndexConfig,
) -> ArtifactItem | None:
    """Extract structured data from one artifact folder."""
    name = read_file(folder / config.name_file)
    if not name:
        config.logger.warning("Empty name.txt in %s, skipping", folder)
        return None

    item: ArtifactItem = {
        "id": folder.name,
        "name": name,
        "description": read_file(folder / config.description_file),
        "tags": parse_lines(folder / config.tags_file),
        "tools": parse_lines(folder / config.tools_file),
        "url": config.artifact_url(folder.name),
        "thumbnail": resolve_thumbnail(folder, config=config),
    }
    validate_artifact_item(item, config=config)
    return item
