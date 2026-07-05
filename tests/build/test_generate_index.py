from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import pytest

import scripts.build.generate_index as generate_index
from scripts.build import index_outputs, index_sources
from scripts.build.index_config import IndexConfig
from scripts.lib.artifact_contract import read_artifact_contract_file


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_artifact(
    base_dir: Path,
    name: str,
    *,
    title: str = "Artifact Title",
    description: str = "Artifact description.",
    tags: list[str] | None = None,
    tools: list[str] | None = None,
    thumbnail_file: str | None = None,
) -> Path:
    artifact_dir = base_dir / name
    artifact_dir.mkdir(parents=True)
    write_text(artifact_dir / "index.html", "<html></html>")
    write_text(artifact_dir / "name.txt", title)
    if description is not None:
        write_text(artifact_dir / "description.txt", description)
    if tags is not None:
        write_text(artifact_dir / "tags.txt", "\n".join(tags) + "\n")
    if tools is not None:
        write_text(artifact_dir / "tools.txt", "\n".join(tools) + "\n")
    if thumbnail_file is not None:
        (artifact_dir / thumbnail_file).write_bytes(b"thumb")
    return artifact_dir


def minimal_readme() -> str:
    return "".join(
        [
            "# Artifacts\n\n",
            "**Live site:** <!-- AUTO:SITE_URL -->old<!-- /AUTO:SITE_URL -->\n\n",
            "<!-- AUTO:TOTAL_BADGE -->old<!-- /AUTO:TOTAL_BADGE -->\n",
            "<!-- AUTO:TAG_BADGES_START -->\nold\n<!-- AUTO:TAG_BADGES_END -->\n",
            "<!-- AUTO:TOOL_BADGES_START -->\nold\n<!-- AUTO:TOOL_BADGES_END -->\n",
            "## Snapshot\n\n",
            "- <!-- AUTO:TOTAL_COUNT -->0<!-- /AUTO:TOTAL_COUNT --> artifacts published\n",
        ]
    )


def minimal_pyproject() -> str:
    return "".join(
        [
            "[tool.artifacts]\n",
            'site_url = "https://example.com/demo"\n',
        ]
    )


def minimal_gallery_metadata() -> str:
    return json.dumps(
        {
            "tools": [
                {
                    "id": "claude",
                    "label": "Claude",
                    "color": "D97706",
                    "alt": "Claude",
                    "logo": "anthropic",
                    "logo_color": "white",
                }
            ],
            "tags": [
                {
                    "id": "finance",
                    "label": "Finance",
                    "color": "27AE60",
                    "alt": "Finance",
                    "logo": None,
                    "logo_color": None,
                }
            ],
        }
    )


# -- Default test contract used by most tests ---------------------------------

DEFAULT_CONTRACT = {
    "artifactIdPattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$",
    "artifactBasePath": "apps",
    "thumbnailFile": "thumbnail.webp",
}


def make_config(
    tmp_path: Path,
    *,
    contract: dict[str, str] | None = None,
    apps_dir: Path | None = None,
    gallery_foundation_file: Path | None = None,
) -> IndexConfig:
    """Build an IndexConfig pointing at *tmp_path* for test isolation."""
    if contract is None:
        contract = dict(DEFAULT_CONTRACT)
    compiled = re.compile(contract["artifactIdPattern"])
    index_file = "index.html"
    name_file = "name.txt"
    return IndexConfig(
        contract=contract,  # type: ignore[arg-type]
        compiled_id_pattern=compiled,
        apps_dir=apps_dir if apps_dir is not None else tmp_path / "apps",
        readme_file=tmp_path / "README.md",
        pyproject_file=tmp_path / "pyproject.toml",
        gallery_metadata_file=tmp_path / "config" / "gallery_metadata.json",
        js_output_file=tmp_path / "js" / "data.js",
        js_config_output_file=tmp_path / "js" / "gallery-config.js",
        gallery_foundation_file=(
            gallery_foundation_file
            if gallery_foundation_file is not None
            else tmp_path / "css" / "style.css"
        ),
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


# -- Contract loading tests (call read_artifact_contract_file directly) --------


def test_read_artifact_contract_loads_shared_validation_rules(
    tmp_path: Path,
) -> None:
    contract_file = tmp_path / "config" / "artifact_contract.json"
    write_text(
        contract_file,
        json.dumps(
            {
                "artifactIdPattern": "^[a-z]+$",
                "artifactBasePath": "apps",
                "thumbnailFile": "thumbnail.webp",
            }
        ),
    )

    contract = read_artifact_contract_file(contract_file)

    assert contract["artifactBasePath"] == "apps"
    assert contract["thumbnailFile"] == "thumbnail.webp"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        (None, "Artifact contract must be a JSON object"),
        (
            {"artifactIdPattern": "^[a-z]+$", "artifactBasePath": "apps"},
            "Artifact contract must include thumbnailFile",
        ),
        (
            {
                "artifactIdPattern": 42,
                "artifactBasePath": "apps",
                "thumbnailFile": "thumbnail.webp",
            },
            "Artifact contract values must be strings",
        ),
        (
            {
                "artifactIdPattern": "[",
                "artifactBasePath": "apps",
                "thumbnailFile": "thumbnail.webp",
            },
            "Artifact contract artifactIdPattern must be valid",
        ),
        (
            {
                "artifactIdPattern": "^[a-z]+$",
                "artifactBasePath": "apps/nested",
                "thumbnailFile": "thumbnail.webp",
            },
            "artifactBasePath must be one safe path segment",
        ),
        (
            {
                "artifactIdPattern": "^[a-z]+$",
                "artifactBasePath": "apps",
                "thumbnailFile": "thumbs/preview.webp",
            },
            "thumbnailFile must be one safe file name",
        ),
    ],
)
def test_read_artifact_contract_rejects_invalid_contract_shapes(
    tmp_path: Path,
    payload: object,
    message: str,
) -> None:
    contract_file = tmp_path / "config" / "artifact_contract.json"
    write_text(contract_file, json.dumps(payload))

    with pytest.raises(ValueError, match=message):
        read_artifact_contract_file(contract_file)


def test_read_artifact_contract_requires_existing_file(
    tmp_path: Path,
) -> None:
    with pytest.raises(FileNotFoundError, match="Artifact contract file not found"):
        read_artifact_contract_file(tmp_path / "config" / "artifact_contract.json")


# -- Palette and badge color tests --------------------------------------------


def test_fallback_badge_color_uses_shared_note_palette(
    tmp_path: Path,
) -> None:
    tokens_file = tmp_path / "css" / "style.css"
    write_text(
        tokens_file,
        """
:root {
  --color-note-1: rgb(1, 2, 3);
  --color-note-2: rgb(4, 5, 6);
}
""".strip(),
    )
    config = make_config(tmp_path, gallery_foundation_file=tokens_file)

    assert config.fallback_badge_color("ai") in {"010203", "040506"}


def test_fallback_badge_color_uses_default_when_palette_file_is_missing(
    tmp_path: Path,
) -> None:
    config = make_config(
        tmp_path,
        gallery_foundation_file=tmp_path / "css" / "missing-style.css",
    )

    assert config.note_palette == ()
    assert config.fallback_badge_color("ai") == "6C757D"


# -- Low-level source helpers --------------------------------------------------


def test_read_file_and_parse_lines(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    write_text(sample, " first\n\nsecond \n")

    assert index_sources.read_file(sample) == "first\n\nsecond"
    assert index_sources.read_file(tmp_path / "missing.txt") == ""
    assert index_sources.parse_lines(sample) == ["first", "second"]


def test_is_kebab_case_accepts_expected_directory_names(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    assert config.is_kebab_case("budget-tracker") is True
    assert config.is_kebab_case("artifact-2026") is True
    assert config.is_kebab_case("BudgetTracker") is False
    assert config.is_kebab_case("budget_tracker") is False


# -- artifact_issues tests ----------------------------------------------------


def test_artifact_issues_cover_missing_files_and_empty_name(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)

    missing_all = tmp_path / "budget-tracker"
    missing_all.mkdir()
    assert index_sources.artifact_issues(missing_all, config=config) == [
        "missing index.html and name.txt"
    ]

    missing_index = tmp_path / "loan-tool"
    missing_index.mkdir()
    write_text(missing_index / "name.txt", "Loan Tool")
    assert index_sources.artifact_issues(missing_index, config=config) == [
        "has name.txt but no index.html"
    ]

    missing_name = tmp_path / "chart-tool"
    missing_name.mkdir()
    write_text(missing_name / "index.html", "<html></html>")
    assert index_sources.artifact_issues(missing_name, config=config) == [
        "has index.html but no name.txt"
    ]

    empty_name = tmp_path / "empty-name"
    empty_name.mkdir()
    write_text(empty_name / "index.html", "<html></html>")
    write_text(empty_name / "name.txt", "   ")
    assert index_sources.artifact_issues(empty_name, config=config) == [
        "has an empty name.txt"
    ]


def test_artifact_issues_include_non_kebab_case_name(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)

    folder = tmp_path / "Bad Artifact"
    folder.mkdir()

    assert index_sources.artifact_issues(folder, config=config) == [
        "directory name must use kebab-case",
        "missing index.html and name.txt",
    ]


# -- extract_artifact tests ---------------------------------------------------


def test_extract_artifact_builds_expected_structure(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    artifact_dir = create_artifact(
        tmp_path,
        "loan-tool",
        title="Loan Tool",
        description="Interactive loan helper.",
        tags=["finance", "calculator"],
        tools=["claude", "chatgpt"],
        thumbnail_file=config.contract["thumbnailFile"],
    )

    item = index_sources.extract_artifact(artifact_dir, config=config)

    assert item == {
        "id": "loan-tool",
        "name": "Loan Tool",
        "description": "Interactive loan helper.",
        "tags": ["finance", "calculator"],
        "tools": ["claude", "chatgpt"],
        "url": "apps/loan-tool/",
        "thumbnail": config.artifact_thumbnail_path("loan-tool"),
    }


def test_extract_artifact_rejects_unsafe_thumbnail_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = make_config(tmp_path)
    artifact_dir = create_artifact(tmp_path, "loan-tool")
    monkeypatch.setattr(
        index_sources,
        "resolve_thumbnail",
        lambda folder, *, config: "apps/loan-tool/%2E%2E/thumbnail.webp",
    )

    with pytest.raises(ValueError, match="path traversal"):
        index_sources.extract_artifact(artifact_dir, config=config)


def test_extract_artifact_returns_none_for_empty_name(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    artifact_dir = tmp_path / "broken"
    artifact_dir.mkdir()
    write_text(artifact_dir / "name.txt", "   ")

    assert index_sources.extract_artifact(artifact_dir, config=config) is None


# -- scan / iter tests ---------------------------------------------------------


def test_scan_artifacts_filters_hidden_and_invalid_dirs(
    tmp_path: Path,
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    create_artifact(apps_dir, "z-last", title="Z Last")
    create_artifact(apps_dir, "a-first", title="A First")
    hidden_dir = apps_dir / ".hidden"
    hidden_dir.mkdir()
    create_artifact(apps_dir, "invalid", title="Ignored")
    (apps_dir / "invalid" / "name.txt").unlink()

    config = make_config(tmp_path, apps_dir=apps_dir)

    items = generate_index._scan_artifacts(config)

    assert [item["id"] for item in items] == ["a-first", "z-last"]


def test_scan_artifacts_logs_warnings_for_incomplete_directories(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    create_artifact(apps_dir, "valid-artifact")
    missing_index = apps_dir / "missing-index"
    missing_index.mkdir()
    write_text(missing_index / "name.txt", "Missing Index")
    missing_name = apps_dir / "missing-name"
    missing_name.mkdir()
    write_text(missing_name / "index.html", "<html></html>")

    config = make_config(tmp_path, apps_dir=apps_dir)

    with caplog.at_level(logging.WARNING):
        items = generate_index._scan_artifacts(config)

    assert [item["id"] for item in items] == ["valid-artifact"]
    assert "missing-index: has name.txt but no index.html" in caplog.text
    assert "missing-name: has index.html but no name.txt" in caplog.text


def test_scan_artifacts_emits_debug_log_for_apps_dir(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    config = make_config(tmp_path, apps_dir=apps_dir)

    with caplog.at_level(logging.DEBUG):
        generate_index._scan_artifacts(config)

    assert f"Scanning {apps_dir} for artifacts" in caplog.text


def test_scan_artifacts_returns_empty_when_apps_dir_is_missing(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path, apps_dir=tmp_path / "missing-apps")

    assert generate_index._scan_artifacts(config) == []


# -- validate tests ------------------------------------------------------------


def test_validate_passes_for_valid_artifacts(
    tmp_path: Path,
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    create_artifact(apps_dir, "valid-artifact")

    config = make_config(tmp_path, apps_dir=apps_dir)

    generate_index.validate(config)


def test_validate_raises_for_invalid_artifact_directories(
    tmp_path: Path,
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    missing_index = apps_dir / "missing-index"
    missing_index.mkdir()
    write_text(missing_index / "name.txt", "Missing Index")
    empty_name = apps_dir / "empty-name"
    empty_name.mkdir()
    write_text(empty_name / "index.html", "<html></html>")
    write_text(empty_name / "name.txt", "   ")
    bad_name = apps_dir / "Bad Artifact"
    bad_name.mkdir()
    write_text(bad_name / "index.html", "<html></html>")
    write_text(bad_name / "name.txt", "Bad Artifact")

    config = make_config(tmp_path, apps_dir=apps_dir)

    with pytest.raises(ValueError, match="Artifact validation failed") as exc_info:
        generate_index.validate(config)

    message = str(exc_info.value)
    assert "missing-index: has name.txt but no index.html" in message
    assert "empty-name: has an empty name.txt" in message
    assert "Bad Artifact: directory name must use kebab-case" in message


# -- README marker tests -------------------------------------------------------


def test_replace_inline_marker_requires_exactly_one_pair() -> None:
    content = "<!-- AUTO:TOTAL_COUNT -->1<!-- /AUTO:TOTAL_COUNT -->"

    replaced = index_outputs.replace_inline_marker(content, "TOTAL_COUNT", "2")

    assert replaced == "<!-- AUTO:TOTAL_COUNT -->2<!-- /AUTO:TOTAL_COUNT -->"

    with pytest.raises(ValueError, match="Expected exactly one marker pair"):
        index_outputs.replace_inline_marker("missing", "TOTAL_COUNT", "2")

    with pytest.raises(ValueError, match="Expected exactly one marker pair"):
        index_outputs.replace_inline_marker(
            content + content,
            "TOTAL_COUNT",
            "2",
        )


def test_replace_block_marker_requires_exactly_one_pair() -> None:
    content = "<!-- AUTO:TAG_BADGES_START -->\nold\n<!-- AUTO:TAG_BADGES_END -->"

    replaced = index_outputs.replace_block_marker(content, "TAG_BADGES", "new")

    assert (
        replaced == "<!-- AUTO:TAG_BADGES_START -->\nnew\n<!-- AUTO:TAG_BADGES_END -->"
    )

    with pytest.raises(ValueError, match="Expected exactly one block marker pair"):
        index_outputs.replace_block_marker("missing", "TAG_BADGES", "new")


# -- Badge tests ---------------------------------------------------------------


def test_build_badges_block_respects_display_order_and_fallback(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    tag_badge_config: dict[str, generate_index.BadgeConfig] = {
        "finance": {
            "label": "Finance",
            "color": "27AE60",
            "alt": "Finance",
            "logo": None,
            "logo_color": None,
        },
        "visualization": {
            "label": "Visualization",
            "color": "E67E22",
            "alt": "Visualization",
            "logo": None,
            "logo_color": None,
        },
    }
    badges = config.build_badges_block(
        {"visualization", "custom-tag", "finance"},
        ["finance", "visualization"],
        tag_badge_config,
    )

    first_line, second_line, third_line = badges.splitlines()
    assert "Finance" in first_line
    assert "Visualization" in second_line
    assert "Custom_Tag" in third_line


def test_build_badge_includes_logo_metadata_for_known_tools(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    tool_badge_config: dict[str, generate_index.BadgeConfig] = {
        "claude": {
            "label": "Claude",
            "color": "D97706",
            "alt": "Claude",
            "logo": "anthropic",
            "logo_color": "white",
        }
    }
    badge = config.build_badge(
        "claude",
        tool_badge_config,
    )

    assert "logo=anthropic" in badge
    assert "logoColor=white" in badge


def test_build_badges_block_returns_empty_string_for_empty_items(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    assert (
        config.build_badges_block(
            set(),
            ["finance"],
            {},
        )
        == ""
    )


# -- Gallery metadata tests ---------------------------------------------------


def test_read_gallery_metadata_loads_shared_config(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(metadata_file, minimal_gallery_metadata())

    config = make_config(tmp_path)
    metadata = config.read_gallery_metadata()

    assert metadata["tools"][0]["id"] == "claude"
    assert metadata["tags"][0]["label"] == "Finance"


def test_read_gallery_metadata_raises_when_file_is_missing(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)

    with pytest.raises(FileNotFoundError, match="Gallery metadata file not found"):
        config.read_gallery_metadata()


def test_read_gallery_metadata_raises_for_invalid_shape(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(metadata_file, '{"tools": {}, "tags": []}')

    config = make_config(tmp_path)

    with pytest.raises(ValueError, match="must be a list"):
        config.read_gallery_metadata()


def test_read_gallery_metadata_raises_for_non_object_root(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(metadata_file, "[]")

    config = make_config(tmp_path)

    with pytest.raises(ValueError, match="must be a JSON object"):
        config.read_gallery_metadata()


def test_read_gallery_metadata_raises_for_invalid_entry_object(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(metadata_file, '{"tools": ["claude"], "tags": []}')

    config = make_config(tmp_path)

    with pytest.raises(ValueError, match="entries must be objects"):
        config.read_gallery_metadata()


def test_read_gallery_metadata_raises_for_missing_required_fields(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(
        metadata_file,
        '{"tools": [{"id": "claude"}], "tags": [{"id": "finance", "label": "Finance"}]}',
    )

    config = make_config(tmp_path)

    with pytest.raises(ValueError, match="must include label, color, alt"):
        config.read_gallery_metadata()


def test_badge_config_map_and_display_order_use_shared_metadata() -> None:
    entries: list[dict[str, str | None]] = [
        {
            "id": "claude",
            "label": "Claude",
            "color": "D97706",
            "alt": "Claude",
            "logo": "anthropic",
            "logo_color": "white",
        },
        {
            "id": "chatgpt",
            "label": "ChatGPT",
            "color": "10A37F",
            "alt": "ChatGPT",
            "logo": "openai",
            "logo_color": "white",
        },
    ]

    assert index_outputs.display_order(entries) == ["claude", "chatgpt"]
    assert index_outputs.badge_config_map(entries)["claude"]["logo"] == "anthropic"


# -- Frontend config tests -----------------------------------------------------


def test_write_frontend_config_writes_browser_metadata(
    tmp_path: Path,
) -> None:
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(metadata_file, minimal_gallery_metadata())

    config = make_config(tmp_path)
    metadata = config.read_gallery_metadata()
    index_outputs.write_frontend_config(metadata, config=config)

    content = config.js_config_output_file.read_text(encoding="utf-8")
    assert content.startswith("window.ARTIFACTS_CONFIG = ")
    assert content.endswith(";\n")


def test_frontend_config_contains_display_labels(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    metadata: generate_index.GalleryMetadata = {
        "tools": [
            {
                "id": "claude",
                "label": "Claude",
                "color": "D97706",
                "alt": "Claude",
                "logo": "anthropic",
                "logo_color": "white",
            }
        ],
        "tags": [
            {
                "id": "finance",
                "label": "Finance",
                "color": "27AE60",
                "alt": "Finance",
                "logo": None,
                "logo_color": None,
            }
        ],
    }

    fc = index_outputs.frontend_config(metadata, artifact_contract=config.contract)

    tools = fc["tools"]

    assert isinstance(tools, dict)
    assert fc["artifactContract"] == dict(config.contract)
    assert tools["claude"]["label"] == "Claude"
    assert fc["tagDisplayOrder"] == ["finance"]


# -- Site URL tests ------------------------------------------------------------


def test_read_site_url_normalizes_trailing_slash(
    tmp_path: Path,
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    write_text(pyproject_file, minimal_pyproject())

    config = make_config(tmp_path)

    assert config.read_site_url() == "https://example.com/demo/"


def test_read_site_url_raises_when_config_is_missing(
    tmp_path: Path,
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    write_text(pyproject_file, "[tool.other]\nvalue = true\n")

    config = make_config(tmp_path)

    with pytest.raises(ValueError, match="Missing tool.artifacts.site_url"):
        config.read_site_url()


def test_read_site_url_raises_when_pyproject_is_missing(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)

    with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
        config.read_site_url()


# -- Full generate tests -------------------------------------------------------


def test_generate_writes_js_output_and_updates_readme(
    tmp_path: Path,
) -> None:
    apps_dir = tmp_path / "apps"
    config = make_config(tmp_path, apps_dir=apps_dir)
    create_artifact(
        apps_dir,
        "loan-tool",
        title="Loan Tool",
        description="Interactive loan helper.",
        tags=["finance"],
        tools=["claude"],
        thumbnail_file=config.contract["thumbnailFile"],
    )

    write_text(config.readme_file, minimal_readme())
    write_text(config.pyproject_file, minimal_pyproject())
    write_text(config.gallery_metadata_file, minimal_gallery_metadata())

    generate_index.generate(config)

    js_output = config.js_output_file.read_text(encoding="utf-8")
    assert js_output.startswith("window.ARTIFACTS_DATA = ")
    payload = json.loads(
        js_output.removeprefix("window.ARTIFACTS_DATA = ").removesuffix(";\n")
    )
    assert payload[0]["thumbnail"] == config.artifact_thumbnail_path("loan-tool")

    readme_output = config.readme_file.read_text(encoding="utf-8")
    assert "https://example.com/demo/" in readme_output
    assert "Total-1" in readme_output
    assert "Claude" in readme_output
    config_output = config.js_config_output_file.read_text(encoding="utf-8")
    assert "ARTIFACTS_CONFIG" in config_output


def test_update_readme_raises_when_readme_file_is_missing(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(metadata_file, minimal_gallery_metadata())

    with pytest.raises(FileNotFoundError, match="README file not found"):
        index_outputs.update_readme(
            items=[],
            config=config,
            site_url="https://example.com/",
            gallery_metadata=config.read_gallery_metadata(),
        )


def test_generate_emits_debug_log_with_config_paths(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    apps_dir = tmp_path / "apps"
    config = make_config(tmp_path, apps_dir=apps_dir)
    create_artifact(apps_dir, "demo-app")
    write_text(config.readme_file, minimal_readme())
    write_text(config.pyproject_file, minimal_pyproject())
    write_text(config.gallery_metadata_file, minimal_gallery_metadata())

    with caplog.at_level(logging.DEBUG):
        generate_index.generate(config)

    assert "Config: apps_dir=" in caplog.text
    assert str(config.apps_dir) in caplog.text


def test_generate_handles_empty_repo_state(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path, apps_dir=tmp_path / "missing-apps")
    write_text(config.readme_file, minimal_readme())
    write_text(config.pyproject_file, minimal_pyproject())
    write_text(config.gallery_metadata_file, minimal_gallery_metadata())

    generate_index.generate(config)

    js_output = config.js_output_file.read_text(encoding="utf-8")
    assert js_output == "window.ARTIFACTS_DATA = [];\n"
    assert config.js_config_output_file.exists()
    readme_output = config.readme_file.read_text(encoding="utf-8")
    assert "Total-0" in readme_output


def test_generate_raises_for_duplicate_artifact_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = make_config(tmp_path)
    monkeypatch.setattr(
        generate_index,
        "_scan_artifacts",
        lambda _cfg: [
            {
                "id": "duplicate",
                "name": "One",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/duplicate/",
                "thumbnail": None,
            },
            {
                "id": "duplicate",
                "name": "Two",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/duplicate/",
                "thumbnail": None,
            },
        ],
    )

    with pytest.raises(ValueError, match="Duplicate artifact ID"):
        generate_index.generate(config)


# -- validate_artifact_item tests ----------------------------------------------


def test_validate_artifact_item_rejects_external_url(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    with pytest.raises(ValueError, match="repo-relative path"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "https://example.com/loan-tool/",
                "thumbnail": None,
            },
            config=config,
        )

    with pytest.raises(ValueError, match="javascript URL"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "javascript:alert(1)",
                "thumbnail": None,
            },
            config=config,
        )


def test_validate_artifact_item_rejects_data_url(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    with pytest.raises(ValueError, match="data URL"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "data:text/html,hello",
                "thumbnail": None,
            },
            config=config,
        )


def test_validate_artifact_item_rejects_non_kebab_case_id(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    with pytest.raises(ValueError, match="Artifact id must use kebab-case"):
        index_sources.validate_artifact_item(
            {
                "id": "LoanTool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": None,
            },
            config=config,
        )


def test_validate_artifact_item_rejects_bad_url_shape(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    with pytest.raises(ValueError, match="Artifact url must match"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/index.html",
                "thumbnail": None,
            },
            config=config,
        )


def test_validate_artifact_item_accepts_null_thumbnail(tmp_path: Path) -> None:
    # Generation now always emits the contract thumbnail path, but a null
    # thumbnail remains a valid legacy/external value and must pass untouched.
    config = make_config(tmp_path)
    assert (
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": None,
            },
            config=config,
        )
        is None
    )


def test_validate_artifact_item_rejects_bad_thumbnail_shape(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    with pytest.raises(ValueError, match="Artifact thumbnail must match"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": "apps/loan-tool/preview.webp",
            },
            config=config,
        )


def test_validate_artifact_item_rejects_mismatched_url_and_thumbnail(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    with pytest.raises(ValueError, match="same artifact id"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/other-tool/",
                "thumbnail": None,
            },
            config=config,
        )

    with pytest.raises(ValueError, match="same artifact id"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": "apps/other-tool/thumbnail.webp",
            },
            config=config,
        )


def test_validate_artifact_item_rejects_leading_slash_and_encoded_traversal(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    with pytest.raises(ValueError, match="must not start with '/'"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "/apps/loan-tool/",
                "thumbnail": None,
            },
            config=config,
        )

    with pytest.raises(ValueError, match="path traversal"):
        index_sources.validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": "apps/loan-tool/%2E%2E/thumbnail.webp",
            },
            config=config,
        )


# -- Helper wrapper / convenience method tests --------------------------------


def test_helper_wrappers_delegate_expected_contract_and_metadata_logic(
    tmp_path: Path,
) -> None:
    config = make_config(tmp_path)
    assert config.artifact_url_rule() == "apps/<artifact-id>/"
    assert config.artifact_thumbnail_rule() == "apps/<artifact-id>/thumbnail.webp"
    assert config.matches_artifact_url_shape("apps/loan-tool/") is True
    assert (
        config.matches_artifact_thumbnail_shape("apps/loan-tool/thumbnail.webp") is True
    )
    index_sources.validate_relative_repo_path(
        "apps/loan-tool/thumbnail.webp",
        field_name="Artifact thumbnail",
    )
    index_outputs.validate_gallery_metadata_entries(
        "tags",
        [
            {
                "id": "finance",
                "label": "Finance",
                "color": "27AE60",
                "alt": "Finance",
            }
        ],
    )
    assert index_outputs.format_identifier_words(
        "ai-ui", uppercase_identifier_words={"ai", "ui"}
    ) == ["AI", "UI"]
    assert index_outputs.sort_items({"beta", "alpha"}, ["beta"]) == ["beta", "alpha"]


# -- IndexConfig.create_default and backward-compat re-exports ----------------


def test_create_default_builds_production_config() -> None:
    config = IndexConfig.create_default()

    assert config.contract["artifactBasePath"] == "apps"
    assert config.contract["thumbnailFile"] == "thumbnail.webp"
    assert config.index_file == "index.html"
    assert config.name_file == "name.txt"
    assert config.is_kebab_case("loan-tool")
    assert not config.is_kebab_case("Bad Name")


def test_generate_index_is_kebab_case_re_export() -> None:
    assert generate_index.is_kebab_case("budget-tracker") is True
    assert generate_index.is_kebab_case("BudgetTracker") is False


def test_artifact_id_pattern_compiles_from_contract() -> None:
    contract = dict(DEFAULT_CONTRACT)
    pattern = index_sources.artifact_id_pattern(contract)  # type: ignore[arg-type]
    assert pattern.fullmatch("loan-tool")
    assert not pattern.fullmatch("Bad Name")


def test_validate_defaults_to_production_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    create_artifact(apps_dir, "valid-artifact")

    config = make_config(tmp_path, apps_dir=apps_dir)
    monkeypatch.setattr(IndexConfig, "create_default", staticmethod(lambda: config))

    generate_index.validate()


def test_generate_defaults_to_production_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    create_artifact(apps_dir, "valid-artifact")

    config = make_config(tmp_path, apps_dir=apps_dir)
    write_text(config.readme_file, minimal_readme())
    write_text(config.pyproject_file, minimal_pyproject())
    write_text(config.gallery_metadata_file, minimal_gallery_metadata())
    monkeypatch.setattr(IndexConfig, "create_default", staticmethod(lambda: config))

    generate_index.generate()
