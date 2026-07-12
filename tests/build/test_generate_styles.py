from __future__ import annotations

from pathlib import Path

import pytest

import scripts.build.generate_styles as generate_styles


def write_text(path: Path, content: str) -> None:
    """Write text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def configure_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Configure stylesheet generator paths."""
    source_dir = tmp_path / "css" / "src"
    output_file = tmp_path / "css" / "style.css"
    monkeypatch.setattr(generate_styles, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(generate_styles, "OUTPUT_FILE", output_file)
    return source_dir, output_file


def test_source_files_discovers_top_level_partials_in_lexical_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source discovery is top-level and deterministic."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    write_text(source_dir / "20-components.css", "/* components */\n")
    write_text(source_dir / "01-tokens.css", "/* tokens */\n")
    write_text(source_dir / "nested" / "02-ignored.css", "/* nested */\n")
    write_text(source_dir / "notes.txt", "not a stylesheet\n")

    assert generate_styles.source_files() == (
        source_dir / "01-tokens.css",
        source_dir / "20-components.css",
    )


@pytest.mark.parametrize(
    "filename",
    (
        "1-tokens.css",
        "001-tokens.css",
        "01_Tokens.css",
        "01-Tokens.css",
        "tokens.css",
    ),
)
def test_source_files_rejects_invalid_source_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, filename: str
) -> None:
    """Source discovery rejects CSS names outside the ordering convention."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    write_text(source_dir / "01-valid.css", "/* valid */\n")
    write_text(source_dir / filename, "/* invalid */\n")

    with pytest.raises(ValueError, match=r"Invalid stylesheet source filename"):
        generate_styles.source_files()


def test_source_files_rejects_empty_source_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source discovery reports when no partials exist."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    source_dir.mkdir(parents=True)

    with pytest.raises(ValueError, match=r"No stylesheet source partials found"):
        generate_styles.source_files()


def test_build_stylesheet_concatenates_partials_with_one_final_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build content is deterministic and uses the public generated header."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    write_text(source_dir / "20-components.css", "/* 2 */\n.rule-2 {}\n\n")
    write_text(source_dir / "01-tokens.css", "/* 1 */\n.rule-1 {}\n\n")
    sources = generate_styles.source_files()

    assert generate_styles.build_stylesheet() == (
        generate_styles.output_header(sources) + "/* 1 */\n.rule-1 {}\n\n/* 2 */\n.rule-2 {}\n"
    )


def test_output_header_describes_discovered_source_boundaries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The generated header derives its range from discovered source files."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    write_text(source_dir / "20-components.css", "/* components */\n")
    write_text(source_dir / "10-base.css", "/* base */\n")

    assert "Source: css/src/10-base.css through css/src/20-components.css" in (
        generate_styles.output_header()
    )


def test_generate_writes_the_public_stylesheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generate writes the assembled public asset."""
    source_dir, output_file = configure_paths(tmp_path, monkeypatch)
    write_text(source_dir / "01-base.css", "/* base */\n")
    write_text(source_dir / "02-components.css", "/* components */\n")

    generate_styles.generate()

    assert output_file.read_text(encoding="utf-8") == generate_styles.build_stylesheet()


def test_repository_bundle_matches_discovered_sources() -> None:
    """The tracked public bundle remains byte-identical to its source build."""
    assert generate_styles.OUTPUT_FILE.read_bytes() == generate_styles.build_stylesheet().encode()


def test_main_reports_the_generated_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main reports the generated public asset."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(generate_styles, "REPO_ROOT", tmp_path)
    write_text(source_dir / "01-base.css", "/* base */\n")

    assert generate_styles.main([]) == 0
    assert capsys.readouterr().out.strip() == "Generated css/style.css"
