"""Configuration context for artifact index generation.

This module defines :class:`IndexConfig`, a frozen dataclass that captures all
configuration the index generation pipeline needs. Higher-level functions in
:mod:`index_sources` and :mod:`index_outputs` accept a config instance instead
of individual parameters, while the low-level helpers they wrap remain
independently testable with explicit arguments.
"""

from __future__ import annotations

import functools
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from scripts import REPO_ROOT
from scripts.build import index_outputs, index_sources
from scripts.lib.artifact_contract import ArtifactContract, read_artifact_contract_file
from scripts.lib.project_config import load_site_url

if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class IndexConfig:
    """Configuration for artifact index generation."""

    contract: ArtifactContract
    compiled_id_pattern: re.Pattern[str]
    apps_dir: Path
    readme_file: Path
    pyproject_file: Path
    gallery_metadata_file: Path
    js_output_file: Path
    js_config_output_file: Path
    gallery_foundation_file: Path
    index_file: str
    name_file: str
    description_file: str
    tags_file: str
    tools_file: str
    note_color_pattern: re.Pattern[str]
    uppercase_words: frozenset[str]
    missing_file_issues: dict[tuple[bool, bool], str]
    logger: logging.Logger

    # -- convenience methods that delegate to low-level functions -----------

    def artifact_url(self, artifact_id: str) -> str:
        """Build the canonical repo-relative URL for one artifact id."""
        return index_sources.artifact_url(self.contract, artifact_id)

    def artifact_thumbnail_path(self, artifact_id: str) -> str:
        """Build the canonical thumbnail path for one artifact id."""
        return index_sources.artifact_thumbnail_path(self.contract, artifact_id)

    def artifact_url_rule(self) -> str:
        """Return the human-readable artifact URL rule from the shared contract."""
        return index_sources.artifact_url_rule(self.contract)

    def artifact_thumbnail_rule(self) -> str:
        """Return the human-readable thumbnail rule from the shared contract."""
        return index_sources.artifact_thumbnail_rule(self.contract)

    def matches_artifact_url_shape(self, value: str) -> bool:
        """Return True when a value matches the shared artifact URL shape."""
        return index_sources.matches_artifact_url_shape(
            value,
            contract=self.contract,
            compiled_artifact_id_pattern=self.compiled_id_pattern,
        )

    def matches_artifact_thumbnail_shape(self, value: str) -> bool:
        """Return True when a value matches the shared thumbnail path shape."""
        return index_sources.matches_artifact_thumbnail_shape(
            value,
            contract=self.contract,
            compiled_artifact_id_pattern=self.compiled_id_pattern,
        )

    def is_kebab_case(self, name: str) -> bool:
        """Return True when a directory name follows kebab-case."""
        return index_sources.is_kebab_case(
            name,
            compiled_artifact_id_pattern=self.compiled_id_pattern,
        )

    @functools.cached_property
    def note_palette(self) -> tuple[str, ...]:
        """Read and cache the gallery desk-note palette from the CSS file."""
        return index_outputs.read_note_palette_file(
            self.gallery_foundation_file,
            note_color_pattern=self.note_color_pattern,
        )

    def fallback_badge_color(self, key: str) -> str:
        """Choose a stable fallback badge color from the shared note palette."""
        return index_outputs.fallback_badge_color(key, palette=self.note_palette)

    def default_badge(self, identifier: str) -> index_outputs.BadgeConfig:
        """Build a fallback badge config for unknown tags/tools."""
        return index_outputs.default_badge(
            identifier,
            uppercase_identifier_words=set(self.uppercase_words),
            fallback_color_fn=self.fallback_badge_color,
        )

    def build_badge(self, key: str, badge_config: dict[str, index_outputs.BadgeConfig]) -> str:
        """Build one README badge image tag."""
        return index_outputs.build_badge(
            key,
            badge_config,
            default_badge_fn=self.default_badge,
        )

    def build_badges_block(
        self,
        items: set[str],
        display_order_values: list[str],
        badge_config: dict[str, index_outputs.BadgeConfig],
    ) -> str:
        """Build the README badges block from discovered items."""
        return index_outputs.build_badges_block(
            items,
            display_order_values,
            badge_config,
            build_badge_fn=self.build_badge,
        )

    def read_site_url(self) -> str:
        """Read the canonical live-site URL from pyproject.toml."""
        return load_site_url(self.pyproject_file)

    def read_gallery_metadata(self) -> index_outputs.GalleryMetadata:
        """Load shared gallery metadata used by generators and the frontend."""
        return index_outputs.read_gallery_metadata(self.gallery_metadata_file)

    # -- class method to build the production config -----------------------

    @classmethod
    def create_default(cls) -> IndexConfig:
        """Construct the production config from repository-root paths."""
        artifact_contract_file = REPO_ROOT / "config" / "artifact_contract.json"
        contract = read_artifact_contract_file(artifact_contract_file)
        compiled_id_pattern = index_sources.artifact_id_pattern(contract)
        apps_dir = REPO_ROOT / contract["artifactBasePath"]

        index_file = "index.html"
        name_file = "name.txt"

        return cls(
            contract=contract,
            compiled_id_pattern=compiled_id_pattern,
            apps_dir=apps_dir,
            readme_file=REPO_ROOT / "README.md",
            pyproject_file=REPO_ROOT / "pyproject.toml",
            gallery_metadata_file=REPO_ROOT / "config" / "gallery_metadata.json",
            js_output_file=REPO_ROOT / "js" / "data.js",
            js_config_output_file=REPO_ROOT / "js" / "gallery-config.js",
            gallery_foundation_file=REPO_ROOT / "css" / "gallery" / "01-tokens.css",
            index_file=index_file,
            name_file=name_file,
            description_file="description.txt",
            tags_file="tags.txt",
            tools_file="tools.txt",
            note_color_pattern=re.compile(
                r"--color-note-(\d+):\s*rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\);"
            ),
            uppercase_words=frozenset(
                {"ai", "api", "css", "html", "js", "json", "llm", "ui", "ux"}
            ),
            missing_file_issues={
                (False, False): f"missing {index_file} and {name_file}",
                (False, True): f"has {name_file} but no {index_file}",
                (True, False): f"has {index_file} but no {name_file}",
            },
            logger=logging.getLogger("scripts.build.generate_index"),
        )
