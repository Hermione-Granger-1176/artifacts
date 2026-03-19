from __future__ import annotations

import json
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


def test_read_file_and_parse_lines(tmp_path: Path) -> None:
    sample = tmp_path / "sample.txt"
    write_text(sample, " first\n\nsecond \n")

    assert generate_index._read_file(sample) == "first\n\nsecond"
    assert generate_index._read_file(tmp_path / "missing.txt") == ""
    assert generate_index._parse_lines(sample) == ["first", "second"]


def test_is_valid_artifact_requires_index_and_name(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "valid-artifact"
    artifact_dir.mkdir()
    assert not generate_index._is_valid_artifact(artifact_dir)

    write_text(artifact_dir / "index.html", "<html></html>")
    assert not generate_index._is_valid_artifact(artifact_dir)

    write_text(artifact_dir / "name.txt", "Valid")
    assert generate_index._is_valid_artifact(artifact_dir)
    assert not generate_index._is_valid_artifact(artifact_dir / "index.html")


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


def test_scan_artifacts_returns_empty_when_apps_dir_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generate_index, "APPS_DIR", tmp_path / "missing-apps")

    assert generate_index._scan_artifacts() == []


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
    badges = generate_index._build_badges_block(
        {"visualization", "custom-tag", "finance"},
        generate_index.TAG_DISPLAY_ORDER,
        generate_index.TAG_BADGE_CONFIG,
    )

    first_line, second_line, third_line = badges.splitlines()
    assert "Finance" in first_line
    assert "Visualization" in second_line
    assert "Custom_Tag" in third_line


def test_build_badge_includes_logo_metadata_for_known_tools() -> None:
    badge = generate_index._build_badge("claude", generate_index.TOOL_BADGE_CONFIG)

    assert "logo=anthropic" in badge
    assert "logoColor=white" in badge


def test_build_badges_block_returns_empty_string_for_empty_items() -> None:
    assert (
        generate_index._build_badges_block(
            set(),
            generate_index.TAG_DISPLAY_ORDER,
            generate_index.TAG_BADGE_CONFIG,
        )
        == ""
    )


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
    pyproject_file = tmp_path / "pyproject.toml"
    write_text(readme_file, minimal_readme())
    write_text(pyproject_file, minimal_pyproject())

    monkeypatch.setattr(generate_index, "APPS_DIR", apps_dir)
    monkeypatch.setattr(generate_index, "README_FILE", readme_file)
    monkeypatch.setattr(generate_index, "JS_OUTPUT_FILE", js_output_file)
    monkeypatch.setattr(generate_index, "PYPROJECT_FILE", pyproject_file)

    generate_index.generate()

    js_output = js_output_file.read_text(encoding="utf-8")
    assert js_output.startswith("window.ARTIFACTS_DATA = ")
    payload = json.loads(
        js_output.removeprefix("window.ARTIFACTS_DATA = ").removesuffix(";")
    )
    assert payload[0]["thumbnail"] == (
        f"apps/loan-tool/{generate_index.PREFERRED_THUMBNAIL_FILE}"
    )

    readme_output = readme_file.read_text(encoding="utf-8")
    assert "https://example.com/demo/" in readme_output
    assert "Total-1" in readme_output
    assert "Claude" in readme_output


def test_update_readme_raises_when_readme_file_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generate_index, "README_FILE", tmp_path / "README.md")

    with pytest.raises(FileNotFoundError, match="README file not found"):
        generate_index._update_readme([])


def test_generate_handles_empty_repo_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    readme_file = tmp_path / "README.md"
    js_output_file = tmp_path / "js" / "data.js"
    pyproject_file = tmp_path / "pyproject.toml"
    write_text(readme_file, minimal_readme())
    write_text(pyproject_file, minimal_pyproject())

    monkeypatch.setattr(generate_index, "APPS_DIR", tmp_path / "missing-apps")
    monkeypatch.setattr(generate_index, "README_FILE", readme_file)
    monkeypatch.setattr(generate_index, "JS_OUTPUT_FILE", js_output_file)
    monkeypatch.setattr(generate_index, "PYPROJECT_FILE", pyproject_file)

    generate_index.generate()

    js_output = js_output_file.read_text(encoding="utf-8")
    assert js_output == "window.ARTIFACTS_DATA = [];"
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
