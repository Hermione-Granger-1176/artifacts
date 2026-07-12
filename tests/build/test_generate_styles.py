from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import scripts.build.generate_styles as generate_styles

if TYPE_CHECKING:
    import pytest


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


def test_source_files_follow_the_documented_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Source files follow the documented numeric order."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)

    assert generate_styles.source_files() == tuple(
        source_dir / filename for filename in generate_styles.SOURCE_FILES
    )


def test_build_stylesheet_concatenates_partials_with_one_final_newline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build content is deterministic and uses the public generated header."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    for index, filename in enumerate(generate_styles.SOURCE_FILES, start=1):
        write_text(source_dir / filename, f"/* {index} */\n.rule-{index} {{}}\n\n")

    assert generate_styles.build_stylesheet() == (
        generate_styles.OUTPUT_HEADER
        + "\n\n".join(
            f"/* {index} */\n.rule-{index} {{}}"
            for index in range(1, len(generate_styles.SOURCE_FILES) + 1)
        )
        + "\n"
    )


def test_generate_writes_the_public_stylesheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generate writes the assembled public asset."""
    source_dir, output_file = configure_paths(tmp_path, monkeypatch)
    for filename in generate_styles.SOURCE_FILES:
        write_text(source_dir / filename, f"/* {filename} */\n")

    generate_styles.generate()

    assert output_file.read_text(encoding="utf-8") == generate_styles.build_stylesheet()


def test_main_reports_the_generated_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main reports the generated public asset."""
    source_dir, _ = configure_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(generate_styles, "REPO_ROOT", tmp_path)
    for filename in generate_styles.SOURCE_FILES:
        write_text(source_dir / filename, f"/* {filename} */\n")

    assert generate_styles.main([]) == 0
    assert capsys.readouterr().out.strip() == "Generated css/style.css"
