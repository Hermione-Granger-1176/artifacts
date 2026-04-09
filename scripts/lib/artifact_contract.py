"""Shared artifact contract loading with validation and caching."""

from __future__ import annotations

import functools
import json
import re
from pathlib import Path
from typing import TypedDict, cast

from scripts import REPO_ROOT

CONTRACT_FILE = REPO_ROOT / "config" / "artifact_contract.json"


class ArtifactContract(TypedDict):
    artifactIdPattern: str
    artifactBasePath: str
    thumbnailFile: str


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


@functools.cache
def load_contract(contract_file: Path = CONTRACT_FILE) -> ArtifactContract:
    """Load, validate, and cache the shared artifact contract."""
    return read_artifact_contract_file(contract_file)


def artifact_base_path(contract_file: Path = CONTRACT_FILE) -> str:
    """Return the artifact base path from the shared contract."""
    return load_contract(contract_file)["artifactBasePath"]


def thumbnail_file(contract_file: Path = CONTRACT_FILE) -> str:
    """Return the thumbnail filename from the shared contract."""
    return load_contract(contract_file)["thumbnailFile"]


def artifact_id_pattern(contract_file: Path = CONTRACT_FILE) -> re.Pattern[str]:
    """Return the compiled artifact id regex from the shared contract."""
    return re.compile(load_contract(contract_file)["artifactIdPattern"])
