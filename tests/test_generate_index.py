from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

import scripts.generate_index as generate_index


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


def test_read_file_and_parse_lines(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    write_text(sample, " first\n\nsecond \n")

    assert generate_index._read_file(sample) == "first\n\nsecond"
    assert generate_index._read_file(tmp_path / "missing.txt") == ""
    assert generate_index._parse_lines(sample) == ["first", "second"]


def test_is_kebab_case_accepts_expected_directory_names() -> None:
    assert generate_index.is_kebab_case("budget-tracker") is True
    assert generate_index.is_kebab_case("artifact-2026") is True
    assert generate_index.is_kebab_case("BudgetTracker") is False
    assert generate_index.is_kebab_case("budget_tracker") is False


def test_artifact_issues_cover_missing_files_and_empty_name(tmp_path: Path) -> None:
    missing_all = tmp_path / "budget-tracker"
    missing_all.mkdir()
    assert generate_index._artifact_issues(missing_all) == [
        "missing index.html and name.txt"
    ]

    missing_index = tmp_path / "loan-tool"
    missing_index.mkdir()
    write_text(missing_index / "name.txt", "Loan Tool")
    assert generate_index._artifact_issues(missing_index) == [
        "has name.txt but no index.html"
    ]

    missing_name = tmp_path / "chart-tool"
    missing_name.mkdir()
    write_text(missing_name / "index.html", "<html></html>")
    assert generate_index._artifact_issues(missing_name) == [
        "has index.html but no name.txt"
    ]

    empty_name = tmp_path / "empty-name"
    empty_name.mkdir()
    write_text(empty_name / "index.html", "<html></html>")
    write_text(empty_name / "name.txt", "   ")
    assert generate_index._artifact_issues(empty_name) == ["has an empty name.txt"]


def test_artifact_issues_include_non_kebab_case_name(tmp_path: Path) -> None:
    folder = tmp_path / "Bad Artifact"
    folder.mkdir()

    assert generate_index._artifact_issues(folder) == [
        "directory name must use kebab-case",
        "missing index.html and name.txt",
    ]


def test_extract_artifact_builds_expected_structure(tmp_path: Path) -> None:
    artifact_dir = create_artifact(
        tmp_path,
        "loan-tool",
        title="Loan Tool",
        description="Interactive loan helper.",
        tags=["finance", "calculator"],
        tools=["claude", "chatgpt"],
        thumbnail_file=generate_index.PREFERRED_THUMBNAIL_FILE,
    )

    item = generate_index._extract_artifact(artifact_dir)

    assert item == {
        "id": "loan-tool",
        "name": "Loan Tool",
        "description": "Interactive loan helper.",
        "tags": ["finance", "calculator"],
        "tools": ["claude", "chatgpt"],
        "url": "apps/loan-tool/",
        "thumbnail": f"apps/loan-tool/{generate_index.PREFERRED_THUMBNAIL_FILE}",
    }


def test_extract_artifact_falls_back_to_legacy_thumbnail(tmp_path: Path) -> None:
    artifact_dir = create_artifact(
        tmp_path,
        "loan-tool",
        thumbnail_file=generate_index.LEGACY_THUMBNAIL_FILE,
    )

    item = generate_index._extract_artifact(artifact_dir)

    assert item is not None
    assert item["thumbnail"] == f"apps/loan-tool/{generate_index.LEGACY_THUMBNAIL_FILE}"


def test_extract_artifact_rejects_unsafe_thumbnail_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact_dir = create_artifact(tmp_path, "loan-tool")
    monkeypatch.setattr(
        generate_index,
        "_resolve_thumbnail",
        lambda folder: "apps/loan-tool/%2E%2E/thumbnail.webp",
    )

    with pytest.raises(ValueError, match="path traversal"):
        generate_index._extract_artifact(artifact_dir)


def test_extract_artifact_returns_none_for_empty_name(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "broken"
    artifact_dir.mkdir()
    write_text(artifact_dir / "name.txt", "   ")

    assert generate_index._extract_artifact(artifact_dir) is None


def test_scan_artifacts_filters_hidden_and_invalid_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    create_artifact(apps_dir, "z-last", title="Z Last")
    create_artifact(apps_dir, "a-first", title="A First")
    hidden_dir = apps_dir / ".hidden"
    hidden_dir.mkdir()
    create_artifact(apps_dir, "invalid", title="Ignored")
    (apps_dir / "invalid" / "name.txt").unlink()

    monkeypatch.setattr(generate_index, "APPS_DIR", apps_dir)

    items = generate_index._scan_artifacts()

    assert [item["id"] for item in items] == ["a-first", "z-last"]


def test_scan_artifacts_logs_warnings_for_incomplete_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
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

    monkeypatch.setattr(generate_index, "APPS_DIR", apps_dir)

    with caplog.at_level(logging.WARNING):
        items = generate_index._scan_artifacts()

    assert [item["id"] for item in items] == ["valid-artifact"]
    assert "missing-index: has name.txt but no index.html" in caplog.text
    assert "missing-name: has index.html but no name.txt" in caplog.text


def test_scan_artifacts_returns_empty_when_apps_dir_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generate_index, "APPS_DIR", tmp_path / "missing-apps")

    assert generate_index._scan_artifacts() == []


def test_validate_passes_for_valid_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()
    create_artifact(apps_dir, "valid-artifact")

    monkeypatch.setattr(generate_index, "APPS_DIR", apps_dir)

    generate_index.validate()


def test_validate_raises_for_invalid_artifact_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
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

    monkeypatch.setattr(generate_index, "APPS_DIR", apps_dir)

    with pytest.raises(ValueError, match="Artifact validation failed") as exc_info:
        generate_index.validate()

    message = str(exc_info.value)
    assert "missing-index: has name.txt but no index.html" in message
    assert "empty-name: has an empty name.txt" in message
    assert "Bad Artifact: directory name must use kebab-case" in message


def test_replace_inline_marker_requires_exactly_one_pair() -> None:
    content = "<!-- AUTO:TOTAL_COUNT -->1<!-- /AUTO:TOTAL_COUNT -->"

    replaced = generate_index._replace_inline_marker(content, "TOTAL_COUNT", "2")

    assert replaced == "<!-- AUTO:TOTAL_COUNT -->2<!-- /AUTO:TOTAL_COUNT -->"

    with pytest.raises(ValueError, match="Expected exactly one marker pair"):
        generate_index._replace_inline_marker("missing", "TOTAL_COUNT", "2")

    with pytest.raises(ValueError, match="Expected exactly one marker pair"):
        generate_index._replace_inline_marker(
            content + content,
            "TOTAL_COUNT",
            "2",
        )


def test_replace_block_marker_requires_exactly_one_pair() -> None:
    content = "<!-- AUTO:TAG_BADGES_START -->\nold\n<!-- AUTO:TAG_BADGES_END -->"

    replaced = generate_index._replace_block_marker(content, "TAG_BADGES", "new")

    assert (
        replaced == "<!-- AUTO:TAG_BADGES_START -->\nnew\n<!-- AUTO:TAG_BADGES_END -->"
    )

    with pytest.raises(ValueError, match="Expected exactly one block marker pair"):
        generate_index._replace_block_marker("missing", "TAG_BADGES", "new")


def test_build_badges_block_respects_display_order_and_fallback() -> None:
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
    badges = generate_index._build_badges_block(
        {"visualization", "custom-tag", "finance"},
        ["finance", "visualization"],
        tag_badge_config,
    )

    first_line, second_line, third_line = badges.splitlines()
    assert "Finance" in first_line
    assert "Visualization" in second_line
    assert "Custom_Tag" in third_line


def test_build_badge_includes_logo_metadata_for_known_tools() -> None:
    tool_badge_config: dict[str, generate_index.BadgeConfig] = {
        "claude": {
            "label": "Claude",
            "color": "D97706",
            "alt": "Claude",
            "logo": "anthropic",
            "logo_color": "white",
        }
    }
    badge = generate_index._build_badge(
        "claude",
        tool_badge_config,
    )

    assert "logo=anthropic" in badge
    assert "logoColor=white" in badge


def test_build_badges_block_returns_empty_string_for_empty_items() -> None:
    assert (
        generate_index._build_badges_block(
            set(),
            ["finance"],
            {},
        )
        == ""
    )


def test_read_gallery_metadata_loads_shared_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata_file = tmp_path / "gallery_metadata.json"
    write_text(metadata_file, minimal_gallery_metadata())

    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    metadata = generate_index._read_gallery_metadata()

    assert metadata["tools"][0]["id"] == "claude"
    assert metadata["tags"][0]["label"] == "Finance"


def test_read_gallery_metadata_raises_when_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generate_index, "GALLERY_METADATA_FILE", tmp_path / "gallery_metadata.json"
    )

    with pytest.raises(FileNotFoundError, match="Gallery metadata file not found"):
        generate_index._read_gallery_metadata()


def test_read_gallery_metadata_raises_for_invalid_shape(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata_file = tmp_path / "gallery_metadata.json"
    write_text(metadata_file, '{"tools": {}, "tags": []}')

    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    with pytest.raises(ValueError, match="must be a list"):
        generate_index._read_gallery_metadata()


def test_read_gallery_metadata_raises_for_non_object_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata_file = tmp_path / "gallery_metadata.json"
    write_text(metadata_file, "[]")

    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    with pytest.raises(ValueError, match="must be a JSON object"):
        generate_index._read_gallery_metadata()


def test_read_gallery_metadata_raises_for_invalid_entry_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata_file = tmp_path / "gallery_metadata.json"
    write_text(metadata_file, '{"tools": ["claude"], "tags": []}')

    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    with pytest.raises(ValueError, match="entries must be objects"):
        generate_index._read_gallery_metadata()


def test_read_gallery_metadata_raises_for_missing_required_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    metadata_file = tmp_path / "gallery_metadata.json"
    write_text(
        metadata_file,
        '{"tools": [{"id": "claude"}], "tags": [{"id": "finance", "label": "Finance"}]}',
    )

    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    with pytest.raises(ValueError, match="must include label, color, alt"):
        generate_index._read_gallery_metadata()


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

    assert generate_index._display_order(entries) == ["claude", "chatgpt"]
    assert generate_index._badge_config_map(entries)["claude"]["logo"] == "anthropic"


def test_write_frontend_config_writes_browser_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_output = tmp_path / "js" / "gallery-config.js"
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    monkeypatch.setattr(generate_index, "JS_CONFIG_OUTPUT_FILE", config_output)
    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)
    write_text(metadata_file, minimal_gallery_metadata())

    generate_index._write_frontend_config(generate_index._read_gallery_metadata())

    content = config_output.read_text(encoding="utf-8")
    assert content.startswith("window.ARTIFACTS_CONFIG = ")
    assert content.endswith(";\n")


def test_frontend_config_contains_display_labels() -> None:
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

    frontend_config = generate_index._frontend_config(metadata)

    tools = frontend_config["tools"]

    assert isinstance(tools, dict)
    assert tools["claude"]["label"] == "Claude"
    assert frontend_config["tagDisplayOrder"] == ["finance"]


def test_read_site_url_normalizes_trailing_slash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    write_text(pyproject_file, minimal_pyproject())

    monkeypatch.setattr(generate_index, "PYPROJECT_FILE", pyproject_file)

    assert generate_index._read_site_url() == "https://example.com/demo/"


def test_read_site_url_raises_when_config_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject_file = tmp_path / "pyproject.toml"
    write_text(pyproject_file, "[tool.other]\nvalue = true\n")

    monkeypatch.setattr(generate_index, "PYPROJECT_FILE", pyproject_file)

    with pytest.raises(ValueError, match="Missing tool.artifacts.site_url"):
        generate_index._read_site_url()


def test_read_site_url_raises_when_pyproject_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generate_index, "PYPROJECT_FILE", tmp_path / "pyproject.toml")

    with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
        generate_index._read_site_url()


def test_generate_writes_js_output_and_updates_readme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    create_artifact(
        apps_dir,
        "loan-tool",
        title="Loan Tool",
        description="Interactive loan helper.",
        tags=["finance"],
        tools=["claude"],
        thumbnail_file=generate_index.PREFERRED_THUMBNAIL_FILE,
    )

    readme_file = tmp_path / "README.md"
    js_output_file = tmp_path / "js" / "data.js"
    js_config_output_file = tmp_path / "js" / "gallery-config.js"
    pyproject_file = tmp_path / "pyproject.toml"
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(readme_file, minimal_readme())
    write_text(pyproject_file, minimal_pyproject())
    write_text(metadata_file, minimal_gallery_metadata())

    monkeypatch.setattr(generate_index, "APPS_DIR", apps_dir)
    monkeypatch.setattr(generate_index, "README_FILE", readme_file)
    monkeypatch.setattr(generate_index, "JS_OUTPUT_FILE", js_output_file)
    monkeypatch.setattr(generate_index, "JS_CONFIG_OUTPUT_FILE", js_config_output_file)
    monkeypatch.setattr(generate_index, "PYPROJECT_FILE", pyproject_file)
    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    generate_index.generate()

    js_output = js_output_file.read_text(encoding="utf-8")
    assert js_output.startswith("window.ARTIFACTS_DATA = ")
    payload = json.loads(
        js_output.removeprefix("window.ARTIFACTS_DATA = ").removesuffix(";\n")
    )
    assert payload[0]["thumbnail"] == (
        f"apps/loan-tool/{generate_index.PREFERRED_THUMBNAIL_FILE}"
    )

    readme_output = readme_file.read_text(encoding="utf-8")
    assert "https://example.com/demo/" in readme_output
    assert "Total-1" in readme_output
    assert "Claude" in readme_output
    config_output = js_config_output_file.read_text(encoding="utf-8")
    assert "ARTIFACTS_CONFIG" in config_output


def test_update_readme_raises_when_readme_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generate_index, "README_FILE", tmp_path / "README.md")
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(metadata_file, minimal_gallery_metadata())
    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    with pytest.raises(FileNotFoundError, match="README file not found"):
        generate_index._update_readme([])


def test_generate_handles_empty_repo_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme_file = tmp_path / "README.md"
    js_output_file = tmp_path / "js" / "data.js"
    js_config_output_file = tmp_path / "js" / "gallery-config.js"
    pyproject_file = tmp_path / "pyproject.toml"
    metadata_file = tmp_path / "config" / "gallery_metadata.json"
    write_text(readme_file, minimal_readme())
    write_text(pyproject_file, minimal_pyproject())
    write_text(metadata_file, minimal_gallery_metadata())

    monkeypatch.setattr(generate_index, "APPS_DIR", tmp_path / "missing-apps")
    monkeypatch.setattr(generate_index, "README_FILE", readme_file)
    monkeypatch.setattr(generate_index, "JS_OUTPUT_FILE", js_output_file)
    monkeypatch.setattr(generate_index, "JS_CONFIG_OUTPUT_FILE", js_config_output_file)
    monkeypatch.setattr(generate_index, "PYPROJECT_FILE", pyproject_file)
    monkeypatch.setattr(generate_index, "GALLERY_METADATA_FILE", metadata_file)

    generate_index.generate()

    js_output = js_output_file.read_text(encoding="utf-8")
    assert js_output == "window.ARTIFACTS_DATA = [];\n"
    assert js_config_output_file.exists()
    readme_output = readme_file.read_text(encoding="utf-8")
    assert "Total-0" in readme_output


def test_generate_raises_for_duplicate_artifact_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        generate_index,
        "_scan_artifacts",
        lambda: [
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
    monkeypatch.setattr(generate_index, "README_FILE", tmp_path / "README.md")
    monkeypatch.setattr(generate_index, "JS_OUTPUT_FILE", tmp_path / "js" / "data.js")

    with pytest.raises(ValueError, match="Duplicate artifact ID"):
        generate_index.generate()


def test_validate_artifact_item_rejects_external_url() -> None:
    with pytest.raises(ValueError, match="repo-relative path"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "https://example.com/loan-tool/",
                "thumbnail": None,
            }
        )

    with pytest.raises(ValueError, match="javascript URL"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "javascript:alert(1)",
                "thumbnail": None,
            }
        )


def test_validate_artifact_item_rejects_data_url() -> None:
    with pytest.raises(ValueError, match="data URL"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "data:text/html,hello",
                "thumbnail": None,
            }
        )


def test_validate_artifact_item_rejects_non_kebab_case_id() -> None:
    with pytest.raises(ValueError, match="Artifact id must use kebab-case"):
        generate_index._validate_artifact_item(
            {
                "id": "LoanTool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": None,
            }
        )


def test_validate_artifact_item_rejects_bad_url_shape() -> None:
    with pytest.raises(ValueError, match="Artifact url must match"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/index.html",
                "thumbnail": None,
            }
        )


def test_validate_artifact_item_rejects_bad_thumbnail_shape() -> None:
    with pytest.raises(ValueError, match="Artifact thumbnail must match"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": "apps/loan-tool/preview.webp",
            }
        )


def test_validate_artifact_item_rejects_mismatched_url_and_thumbnail() -> None:
    with pytest.raises(ValueError, match="same artifact id"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/other-tool/",
                "thumbnail": None,
            }
        )

    with pytest.raises(ValueError, match="same artifact id"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": "apps/other-tool/thumbnail.webp",
            }
        )


def test_validate_artifact_item_rejects_leading_slash_and_encoded_traversal() -> None:
    with pytest.raises(ValueError, match="must not start with '/'"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "/apps/loan-tool/",
                "thumbnail": None,
            }
        )

    with pytest.raises(ValueError, match="path traversal"):
        generate_index._validate_artifact_item(
            {
                "id": "loan-tool",
                "name": "Loan Tool",
                "description": "",
                "tags": [],
                "tools": [],
                "url": "apps/loan-tool/",
                "thumbnail": "apps/loan-tool/%2E%2E/thumbnail.webp",
            }
        )
