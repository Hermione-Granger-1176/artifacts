from __future__ import annotations

from pathlib import Path

import pytest

import scripts.align_tables as align_tables


def test_is_table_line_detects_pipe_rows() -> None:
    assert align_tables.is_table_line("| a | b |") is True
    assert align_tables.is_table_line("| --- | --- |") is True
    assert align_tables.is_table_line("  | x | y |  ") is True
    assert align_tables.is_table_line("no pipes here") is False
    assert align_tables.is_table_line("partial | pipe") is False
    assert align_tables.is_table_line("| only left") is False


def test_split_cells_strips_outer_pipes() -> None:
    assert align_tables.split_cells("| a | b | c |") == ["a", "b", "c"]
    assert align_tables.split_cells("|  x  |  y  |") == ["x", "y"]


def test_is_separator_row() -> None:
    assert align_tables.is_separator_row(["---", "---"]) is True
    assert align_tables.is_separator_row([":---:", "---:"]) is True
    assert align_tables.is_separator_row(["text", "---"]) is False


def test_build_separator_preserves_alignment_markers() -> None:
    result = align_tables.build_separator([10, 10], [":---", "---:"])
    assert result.startswith("| :---")
    assert "---:" in result


def test_build_separator_uses_minimum_width() -> None:
    result = align_tables.build_separator([3, 3], ["---", "---"])
    assert result == "| --- | --- |"


def test_align_table_pads_cells() -> None:
    lines = [
        "| A | Long |",
        "| --- | --- |",
        "| x | y |",
    ]
    aligned = align_tables.align_table(lines)
    assert aligned[0] == "| A   | Long |"
    assert aligned[2] == "| x   | y    |"


def test_align_table_handles_uneven_columns() -> None:
    lines = [
        "| A | B |",
        "| --- | --- |",
        "| x |",
    ]
    aligned = align_tables.align_table(lines)
    assert len(aligned) == 3
    assert aligned[2].count("|") == 3


def test_process_file_aligns_tables(tmp_path: Path) -> None:
    md = tmp_path / "test.md"
    md.write_text(
        "# Title\n\n"
        "| Short | Very Long Column |\n"
        "| --- | --- |\n"
        "| a | b |\n",
        encoding="utf-8",
    )

    changed = align_tables.process_file(md)
    assert changed is True

    content = md.read_text(encoding="utf-8")
    lines = content.split("\n")
    header = [line for line in lines if line.startswith("| Short")]
    assert len(header) == 1
    # Pipes should be aligned: "Short" padded to match "Very Long Column"
    assert "| Short " in header[0]
    assert "| Very Long Column |" in header[0]


def test_process_file_skips_code_fences(tmp_path: Path) -> None:
    md = tmp_path / "test.md"
    md.write_text(
        "```\n"
        "| A | B |\n"
        "| --- | --- |\n"
        "```\n",
        encoding="utf-8",
    )

    changed = align_tables.process_file(md)
    assert changed is False


def test_process_file_returns_false_when_already_aligned(tmp_path: Path) -> None:
    md = tmp_path / "test.md"
    md.write_text(
        "| A   | B   |\n"
        "| --- | --- |\n"
        "| x   | y   |\n",
        encoding="utf-8",
    )

    changed = align_tables.process_file(md)
    assert changed is False


def test_process_file_handles_table_at_end_of_file(tmp_path: Path) -> None:
    md = tmp_path / "test.md"
    md.write_text(
        "| A | B |\n"
        "| --- | --- |\n"
        "| x | y |",
        encoding="utf-8",
    )

    changed = align_tables.process_file(md)
    assert changed is True


def test_find_markdown_files_excludes_node_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(align_tables, "REPO_ROOT", tmp_path)

    (tmp_path / "README.md").write_text("# Hi", encoding="utf-8")
    nm = tmp_path / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "README.md").write_text("# Pkg", encoding="utf-8")
    venv = tmp_path / ".venv" / "lib"
    venv.mkdir(parents=True)
    (venv / "README.md").write_text("# Venv", encoding="utf-8")

    files = align_tables.find_markdown_files()
    names = [f.name for f in files]
    assert "README.md" in names
    assert len(files) == 1


def test_main_with_no_args_processes_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(align_tables, "REPO_ROOT", tmp_path)
    monkeypatch.setattr("sys.argv", ["align_tables.py"])

    (tmp_path / "doc.md").write_text(
        "| A | B |\n| --- | --- |\n| x | y |\n",
        encoding="utf-8",
    )

    align_tables.main()
    captured = capsys.readouterr()
    assert "Aligned tables in 1 file(s)" in captured.out


def test_main_with_explicit_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    md = tmp_path / "test.md"
    md.write_text("No tables here.\n", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["align_tables.py", str(md)])

    align_tables.main()
    captured = capsys.readouterr()
    assert "No tables needed alignment" in captured.out


def test_main_skips_missing_files(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.argv", ["align_tables.py", "/nonexistent/file.md"])

    align_tables.main()
    captured = capsys.readouterr()
    assert "Skipping" in captured.out
