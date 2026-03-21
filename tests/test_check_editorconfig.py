from __future__ import annotations

from pathlib import Path

import pytest

import scripts.check_editorconfig as check_editorconfig


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_editorconfig_reads_sections_in_order() -> None:
    sections = check_editorconfig.parse_editorconfig(
        """
root = true

[*]
end_of_line = lf

[*.py]
indent_style = space

[apps/**]
indent_style = unset
""".strip()
    )

    assert sections == [
        check_editorconfig.EditorConfigSection("*", {"end_of_line": "lf"}),
        check_editorconfig.EditorConfigSection("*.py", {"indent_style": "space"}),
        check_editorconfig.EditorConfigSection("apps/**", {"indent_style": "unset"}),
    ]


def test_resolve_settings_applies_later_unset() -> None:
    sections = [
        check_editorconfig.EditorConfigSection(
            "*",
            {
                "trim_trailing_whitespace": "true",
                "insert_final_newline": "true",
            },
        ),
        check_editorconfig.EditorConfigSection(
            "apps/**", {"trim_trailing_whitespace": "unset"}
        ),
    ]

    settings = check_editorconfig.resolve_settings(sections, "apps/demo/index.html")

    assert settings == {"insert_final_newline": "true"}


def test_should_check_file_limits_checks_to_supported_patterns() -> None:
    sections = [
        check_editorconfig.EditorConfigSection("*", {"end_of_line": "lf"}),
        check_editorconfig.EditorConfigSection("*.py", {"indent_style": "space"}),
    ]

    assert check_editorconfig.should_check_file(sections, ".editorconfig") is True
    assert check_editorconfig.should_check_file(sections, "scripts/demo.py") is True
    assert check_editorconfig.should_check_file(sections, "notes/demo.txt") is False


def test_iter_workspace_files_skips_dependency_and_build_directories(
    tmp_path: Path,
) -> None:
    write_text(tmp_path / "docs" / "guide.md", "hello\n")
    write_text(tmp_path / ".venv" / "ignored.py", "print('x')\n")
    write_text(tmp_path / "node_modules" / "pkg" / "index.js", "export {}\n")
    write_text(tmp_path / "_site" / "index.html", "<html></html>\n")

    files = check_editorconfig.iter_workspace_files(tmp_path)

    assert files == [tmp_path / "docs" / "guide.md"]


def test_check_file_reports_expected_text_violations(tmp_path: Path) -> None:
    file_path = tmp_path / "demo.js"
    write_bytes(file_path, b"\tconst value = 1;  \r\n")

    violations = check_editorconfig.check_file(
        file_path,
        "demo.js",
        {
            "end_of_line": "lf",
            "indent_style": "space",
            "insert_final_newline": "true",
            "trim_trailing_whitespace": "true",
        },
    )

    assert violations == [
        "demo.js: expected LF line endings",
        "demo.js:1: trailing whitespace",
        "demo.js:1: tab used for indentation",
    ]


def test_check_file_reports_missing_final_newline(tmp_path: Path) -> None:
    file_path = tmp_path / "demo.py"
    write_text(file_path, "print('hi')")

    violations = check_editorconfig.check_file(
        file_path,
        "demo.py",
        {"insert_final_newline": "true"},
    )

    assert violations == ["demo.py: missing final newline"]


def test_check_file_reports_unexpected_final_newline_and_space_indentation(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "Makefile"
    write_text(file_path, "  target:\n")

    violations = check_editorconfig.check_file(
        file_path,
        "Makefile",
        {
            "indent_style": "tab",
            "insert_final_newline": "false",
        },
    )

    assert violations == [
        "Makefile: unexpected final newline",
        "Makefile:1: spaces used for indentation",
    ]


def test_check_file_allows_binary_assets(tmp_path: Path) -> None:
    file_path = tmp_path / "icon.ico"
    write_bytes(file_path, b"\x00\x01binary")

    violations = check_editorconfig.check_file(
        file_path, "icon.ico", {"end_of_line": "lf"}
    )

    assert violations == []


def test_check_file_reports_non_utf8_text(tmp_path: Path) -> None:
    file_path = tmp_path / "demo.py"
    write_bytes(file_path, b"\x80bad")

    violations = check_editorconfig.check_file(file_path, "demo.py", {})

    assert violations == ["demo.py: not valid UTF-8 text (invalid start byte)"]


def test_run_check_uses_repo_relative_settings(tmp_path: Path) -> None:
    write_text(
        tmp_path / ".editorconfig",
        """
[*]
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = false

[*.py]
trim_trailing_whitespace = true
""".strip()
        + "\n",
    )
    write_text(tmp_path / "README.md", "line with two spaces  \n")
    write_text(tmp_path / "script.py", "print('hi')  \n")
    write_text(tmp_path / "notes.txt", "not checked  \n")

    violations = check_editorconfig.run_check(root=tmp_path)

    assert violations == ["script.py:1: trailing whitespace"]


def test_main_prints_success_for_clean_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(
        tmp_path / ".editorconfig",
        """
[*]
insert_final_newline = true

[*.md]
trim_trailing_whitespace = false
""".strip()
        + "\n",
    )
    write_text(tmp_path / "demo.md", "ok\n")
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig"
    )

    exit_code = check_editorconfig.main(["demo.md"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "EditorConfig check passed for 1 file(s)"


def test_main_scans_all_files_when_no_paths_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(tmp_path / ".editorconfig", "[*.txt]\ninsert_final_newline = true\n")
    write_text(tmp_path / "hello.txt", "ok\n")
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig"
    )

    exit_code = check_editorconfig.main([])

    assert exit_code == 0
    assert "passed" in capsys.readouterr().out


def test_main_rejects_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(tmp_path / ".editorconfig", "[*]\nend_of_line = lf\n")
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig"
    )

    exit_code = check_editorconfig.main(["no-such-file.txt"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "path does not exist" in captured


def test_main_prints_failures_for_invalid_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    write_text(
        tmp_path / ".editorconfig",
        """
[*]
trim_trailing_whitespace = true

[*.md]
trim_trailing_whitespace = true
""".strip()
        + "\n",
    )
    write_text(tmp_path / "demo.md", "bad  \n")
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig"
    )

    exit_code = check_editorconfig.main(["demo.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "EditorConfig check failed:" in captured
    assert "demo.md:1: trailing whitespace" in captured
