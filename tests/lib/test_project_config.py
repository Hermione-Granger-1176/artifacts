from __future__ import annotations

from pathlib import Path

import pytest

import scripts.lib.project_config as project_config


def write_text(path: Path, content: str) -> None:
    """Write text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_load_artifacts_config_returns_empty_dict_when_section_is_missing(
    tmp_path: Path,
) -> None:
    """Test load artifacts config returns empty dict when section is missing."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.other]\nvalue = true\n")

    assert project_config.load_artifacts_config(pyproject) == {}


def test_load_artifacts_config_rejects_non_table_section(tmp_path: Path) -> None:
    """Test load artifacts config rejects non table section."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, 'tool = "invalid"\n')

    assert project_config.load_artifacts_config(pyproject) == {}


def test_load_artifacts_config_rejects_non_mapping_artifacts_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load artifacts config rejects non mapping artifacts table."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com"\n')

    monkeypatch.setattr(
        project_config.tomllib,
        "loads",
        lambda _: {"tool": {"artifacts": "invalid"}},
    )

    with pytest.raises(ValueError, match=r"\[tool\.artifacts\] must be a table"):
        project_config.load_artifacts_config(pyproject)


def test_load_artifacts_setting_errors_for_missing_file(tmp_path: Path) -> None:
    """Test load artifacts setting errors for missing file."""
    missing = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError, match=r"pyproject.toml not found"):
        project_config.load_artifacts_setting(missing, "site_url")


def test_load_artifacts_setting_reads_string_value(tmp_path: Path) -> None:
    """Test load artifacts setting reads string value."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com"\n')

    assert project_config.load_artifacts_setting(pyproject, "site_url") == ("https://example.com")


def test_load_artifacts_setting_errors_for_missing_key(tmp_path: Path) -> None:
    """Test load artifacts setting errors for missing key."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_path = "/artifacts/"\n')

    with pytest.raises(ValueError, match=r"Missing tool.artifacts.site_url"):
        project_config.load_artifacts_setting(pyproject, "site_url")


def test_load_artifacts_setting_rejects_non_string_values(tmp_path: Path) -> None:
    """Test load artifacts setting rejects non string values."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.artifacts]\nsite_url = 1\n")

    with pytest.raises(ValueError, match=r"tool.artifacts.site_url must be a string"):
        project_config.load_artifacts_setting(pyproject, "site_url")


def test_normalize_site_url_adds_trailing_slash() -> None:
    """Test normalize site url adds trailing slash."""
    assert project_config.normalize_site_url("https://example.com/demo") == (
        "https://example.com/demo/"
    )


def test_normalize_site_url_preserves_existing_trailing_slash() -> None:
    """Test normalize site url preserves existing trailing slash."""
    assert project_config.normalize_site_url("https://example.com/demo/") == (
        "https://example.com/demo/"
    )


def test_load_site_url_reads_and_normalizes(tmp_path: Path) -> None:
    """Test load site url reads and normalizes."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com/demo"\n')

    assert project_config.load_site_url(pyproject) == "https://example.com/demo/"
