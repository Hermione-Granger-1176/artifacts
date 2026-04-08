"""Helpers for artifact contract validation and source discovery."""

from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, cast


class ArtifactItem(TypedDict):
    id: str
    name: str
    description: str
    tags: list[str]
    tools: list[str]
    url: str
    thumbnail: str | None


class ArtifactContract(TypedDict):
    artifactIdPattern: str
    artifactBasePath: str
    thumbnailFile: str


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


def read_artifact_contract_file(contract_file: Path) -> ArtifactContract:
    """Load and validate the shared artifact path contract."""
    if not contract_file.exists():
        raise FileNotFoundError(f"Artifact contract file not found: {contract_file}")

    contract = json.loads(contract_file.read_text(encoding="utf-8"))
    if not isinstance(contract, dict):
        raise ValueError("Artifact contract must be a JSON object")

    required_fields = ("artifactIdPattern", "artifactBasePath", "thumbnailFile")
    missing = [field for field in required_fields if not contract.get(field)]
    if missing:
        raise ValueError("Artifact contract must include " + ", ".join(sorted(missing)))

    artifact_id_pattern = contract["artifactIdPattern"]
    artifact_base_path = contract["artifactBasePath"]
    thumbnail_file = contract["thumbnailFile"]
    if not all(
        isinstance(value, str)
        for value in (artifact_id_pattern, artifact_base_path, thumbnail_file)
    ):
        raise ValueError("Artifact contract values must be strings")

    try:
        re.compile(artifact_id_pattern)
    except re.error as exc:
        raise ValueError("Artifact contract artifactIdPattern must be valid") from exc
    if "/" in artifact_base_path or artifact_base_path.startswith("."):
        raise ValueError(
            "Artifact contract artifactBasePath must be one safe path segment"
        )
    if "/" in thumbnail_file or thumbnail_file.startswith("."):
        raise ValueError("Artifact contract thumbnailFile must be one safe file name")

    return cast(ArtifactContract, contract)


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


def validate_artifact_item(
    item: ArtifactItem,
    *,
    contract: ArtifactContract,
    compiled_artifact_id_pattern: re.Pattern[str],
) -> None:
    """Validate one generated artifact record against the shared contract."""
    if not is_kebab_case(
        item["id"], compiled_artifact_id_pattern=compiled_artifact_id_pattern
    ):
        raise ValueError(f"Artifact id must use kebab-case: {item['id']}")

    validate_relative_repo_path(item["url"], field_name="Artifact url")
    expected_url = artifact_url(contract, item["id"])
    if item["url"] != expected_url:
        if matches_artifact_url_shape(
            item["url"],
            contract=contract,
            compiled_artifact_id_pattern=compiled_artifact_id_pattern,
        ):
            raise ValueError(
                "Artifact url must use the same artifact id as the directory name: "
                f"{item['url']}"
            )
        raise ValueError(
            f"Artifact url must match {artifact_url_rule(contract)}: {item['url']}"
        )

    thumbnail = item.get("thumbnail")
    if thumbnail is None:
        return

    validate_relative_repo_path(thumbnail, field_name="Artifact thumbnail")
    expected_thumbnail = artifact_thumbnail_path(contract, item["id"])
    if thumbnail != expected_thumbnail:
        if matches_artifact_thumbnail_shape(
            thumbnail,
            contract=contract,
            compiled_artifact_id_pattern=compiled_artifact_id_pattern,
        ):
            raise ValueError(
                "Artifact thumbnail must use the same artifact id as the directory "
                f"name: {thumbnail}"
            )
        raise ValueError(
            "Artifact thumbnail must match "
            f"{artifact_thumbnail_rule(contract)}: {thumbnail}"
        )


def artifact_issues(
    folder: Path,
    *,
    index_file: str,
    name_file: str,
    missing_required_file_issues: dict[tuple[bool, bool], str],
    is_kebab_case_fn: Callable[[str], bool],
    read_file_fn: Callable[[Path], str],
) -> list[str]:
    """Collect validation issues for one top-level artifact directory."""
    issues: list[str] = []
    has_index = (folder / index_file).exists()
    has_name = (folder / name_file).exists()

    if not is_kebab_case_fn(folder.name):
        issues.append("directory name must use kebab-case")

    missing_required_file_issue = missing_required_file_issues.get(
        (has_index, has_name)
    )
    if missing_required_file_issue:
        issues.append(missing_required_file_issue)

    if has_name and not read_file_fn(folder / name_file):
        issues.append(f"has an empty {name_file}")

    return issues


def iter_artifact_dirs(apps_dir: Path, *, logger: object) -> list[Path]:
    """Return top-level visible artifact directories under apps/."""
    if not apps_dir.exists():
        logger.info("Directory not found: %s (skipping)", apps_dir)
        return []

    return sorted(
        (
            folder
            for folder in apps_dir.iterdir()
            if folder.is_dir() and not folder.name.startswith(".")
        ),
        key=lambda folder: folder.name,
    )


def resolve_thumbnail(
    folder: Path,
    *,
    contract: ArtifactContract,
    artifact_thumbnail_path_fn: Callable[[str], str],
) -> str | None:
    """Resolve the preferred thumbnail path when one exists."""
    if not (folder / contract["thumbnailFile"]).exists():
        return None
    return artifact_thumbnail_path_fn(folder.name)


def extract_artifact(
    folder: Path,
    *,
    name_file: str,
    description_file: str,
    tags_file: str,
    tools_file: str,
    read_file_fn: Callable[[Path], str],
    parse_lines_fn: Callable[[Path], list[str]],
    resolve_thumbnail_fn: Callable[[Path], str | None],
    artifact_url_fn: Callable[[str], str],
    validate_artifact_item_fn: Callable[[ArtifactItem], None],
    logger: object,
) -> ArtifactItem | None:
    """Extract structured data from one artifact folder."""
    name = read_file_fn(folder / name_file)
    if not name:
        logger.warning("Empty name.txt in %s, skipping", folder)
        return None

    item: ArtifactItem = {
        "id": folder.name,
        "name": name,
        "description": read_file_fn(folder / description_file),
        "tags": parse_lines_fn(folder / tags_file),
        "tools": parse_lines_fn(folder / tools_file),
        "url": artifact_url_fn(folder.name),
        "thumbnail": resolve_thumbnail_fn(folder),
    }
    validate_artifact_item_fn(item)
    return item
