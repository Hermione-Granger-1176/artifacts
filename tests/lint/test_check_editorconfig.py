from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import scripts.lint.check_editorconfig as check_editorconfig

if TYPE_CHECKING:
    import pytest


def write_bytes(path: Path, content: bytes) -> None:
    """Write bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def write_text(path: Path, content: str) -> None:
    """Write text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_editorconfig_reads_sections_in_order() -> None:
    """Parse editorconfig reads sections in order."""
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
    """Resolve settings applies later unset."""
    sections = [
        check_editorconfig.EditorConfigSection(
            "*",
            {
                "trim_trailing_whitespace": "true",
                "insert_final_newline": "true",
            },
        ),
        check_editorconfig.EditorConfigSection("apps/**", {"trim_trailing_whitespace": "unset"}),
    ]

    settings = check_editorconfig.resolve_settings(sections, "apps/demo/index.html")

    assert settings == {"insert_final_newline": "true"}


def test_resolve_settings_expands_brace_patterns() -> None:
    """Resolve settings supports EditorConfig brace patterns."""
    sections = [
        check_editorconfig.EditorConfigSection(
            "*.{json,yaml,yml}",
            {"indent_style": "space", "indent_size": "2"},
        )
    ]

    assert check_editorconfig.resolve_settings(sections, "config/example.yaml") == {
        "indent_style": "space",
        "indent_size": "2",
    }
    assert check_editorconfig.resolve_settings(sections, "config/example.toml") == {}


def test_resolve_settings_uses_separator_aware_globs() -> None:
    """Single stars stay within a path segment while double stars recurse."""
    sections = [
        check_editorconfig.EditorConfigSection("*.md", {"scope": "basename"}),
        check_editorconfig.EditorConfigSection("docs/*.md", {"depth": "direct"}),
        check_editorconfig.EditorConfigSection("docs/**/guide.md", {"recursive": "true"}),
    ]

    assert check_editorconfig.resolve_settings(sections, "docs/guide.md") == {
        "scope": "basename",
        "depth": "direct",
        "recursive": "true",
    }
    assert check_editorconfig.resolve_settings(sections, "docs/guides/guide.md") == {
        "scope": "basename",
        "recursive": "true",
    }


def test_parse_editorconfig_normalizes_property_names_and_values() -> None:
    """Parse property names and values case-insensitively."""
    sections = check_editorconfig.parse_editorconfig("[*.py]\nIndent_Style = SPACE\n")

    assert sections == [check_editorconfig.EditorConfigSection("*.py", {"indent_style": "space"})]


def test_should_check_file_limits_checks_to_supported_patterns() -> None:
    """Should check file limits checks to supported patterns."""
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
    """Iter workspace files skips dependency and build directories."""
    write_text(tmp_path / "docs" / "guide.md", "hello\n")
    write_text(tmp_path / ".venv" / "ignored.py", "print('x')\n")
    write_text(tmp_path / "node_modules" / "pkg" / "index.js", "export {}\n")
    write_text(tmp_path / "_site" / "index.html", "<html></html>\n")

    files = check_editorconfig.iter_workspace_files(tmp_path)

    assert files == [tmp_path / "docs" / "guide.md"]


def test_iter_workspace_files_never_descends_into_skipped_directories(
    tmp_path: Path, scanned_directories: list[Path]
) -> None:
    """Iter workspace files never opens a skipped directory."""
    write_text(tmp_path / "docs" / "guide.md", "hello\n")
    write_text(tmp_path / ".venv" / "lib" / "ignored.py", "print('x')\n")
    write_text(tmp_path / "node_modules" / "pkg" / "index.js", "export {}\n")
    write_text(tmp_path / "_site" / "assets" / "index.html", "<html></html>\n")

    check_editorconfig.iter_workspace_files(tmp_path)

    assert tmp_path in scanned_directories, "the recording scandir was not installed"
    assert tmp_path / "docs" in scanned_directories
    assert tmp_path / ".venv" not in scanned_directories
    assert tmp_path / "node_modules" not in scanned_directories
    assert tmp_path / "_site" not in scanned_directories


def test_iter_workspace_files_skips_file_and_directory_symlinks(tmp_path: Path) -> None:
    """Workspace scans do not follow or return symlinked files."""
    target = tmp_path / "target.py"
    write_text(target, "print('safe')\n")
    (tmp_path / "linked.py").symlink_to(target)
    external = tmp_path.parent / f"{tmp_path.name}-external-editorconfig-dir"
    write_text(external / "outside.py", "print('outside')\n")
    (tmp_path / "linked-directory").symlink_to(external, target_is_directory=True)

    assert check_editorconfig.iter_workspace_files(tmp_path) == [target]


def test_check_file_reports_expected_text_violations(tmp_path: Path) -> None:
    """Check file reports expected text violations."""
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
    """Check file reports missing final newline."""
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
    """Check file reports unexpected final newline and space indentation."""
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
    """Check file allows binary assets."""
    file_path = tmp_path / "icon.ico"
    write_bytes(file_path, b"\x00\x01binary")

    violations = check_editorconfig.check_file(file_path, "icon.ico", {"end_of_line": "lf"})

    assert violations == []


def test_check_file_reports_non_utf8_text(tmp_path: Path) -> None:
    """Check file reports non utf8 text."""
    file_path = tmp_path / "demo.py"
    write_bytes(file_path, b"\x80bad")

    violations = check_editorconfig.check_file(file_path, "demo.py", {})

    assert violations == ["demo.py: not valid UTF-8 text (invalid start byte)"]


def test_run_check_uses_repo_relative_settings(tmp_path: Path) -> None:
    """Run check uses repo relative settings."""
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
    """Main prints success for clean file."""
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
    monkeypatch.setattr(check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig")

    exit_code = check_editorconfig.main(["demo.md"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "EditorConfig check passed for 1 file(s)"


def test_main_scans_all_files_when_no_paths_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main scans all files when no paths given."""
    write_text(tmp_path / ".editorconfig", "[*.txt]\ninsert_final_newline = true\n")
    write_text(tmp_path / "hello.txt", "ok\n")
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig")

    exit_code = check_editorconfig.main([])

    assert exit_code == 0
    assert "passed" in capsys.readouterr().out


def test_main_rejects_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main rejects missing path."""
    write_text(tmp_path / ".editorconfig", "[*]\nend_of_line = lf\n")
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig")

    exit_code = check_editorconfig.main(["no-such-file.txt"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "path does not exist" in captured


def test_main_rejects_path_outside_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main rejects explicit paths outside the repository."""
    write_text(tmp_path / ".editorconfig", "[*.txt]\ninsert_final_newline = true\n")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    write_text(outside, "outside\n")
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)

    exit_code = check_editorconfig.main([str(outside)])

    assert exit_code == 1
    captured = capsys.readouterr().out
    assert captured.startswith("EditorConfig check failed:\n")
    assert "path must stay within the repository" in captured


def test_main_rejects_symlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main rejects explicit symbolic links."""
    write_text(tmp_path / ".editorconfig", "[*.txt]\ninsert_final_newline = true\n")
    target = tmp_path / "target.txt"
    write_text(target, "safe\n")
    (tmp_path / "linked.txt").symlink_to(target)
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)

    exit_code = check_editorconfig.main(["linked.txt"])

    assert exit_code == 1
    captured = capsys.readouterr().out
    assert captured.startswith("EditorConfig check failed:\n")
    assert "symbolic links are not supported" in captured


def test_main_rejects_path_through_symlinked_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main rejects paths reached through symbolic-link directories."""
    write_text(tmp_path / ".editorconfig", "[*.txt]\ninsert_final_newline = true\n")
    target_directory = tmp_path / "target-directory"
    write_text(target_directory / "target.txt", "safe\n")
    (tmp_path / "linked-directory").symlink_to(target_directory, target_is_directory=True)
    monkeypatch.setattr(check_editorconfig, "REPO_ROOT", tmp_path)

    exit_code = check_editorconfig.main(["linked-directory/target.txt"])

    assert exit_code == 1
    captured = capsys.readouterr().out
    assert captured.startswith("EditorConfig check failed:\n")
    assert "symbolic links are not supported" in captured


def test_main_prints_failures_for_invalid_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main prints failures for invalid file."""
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
    monkeypatch.setattr(check_editorconfig, "EDITORCONFIG_FILE", tmp_path / ".editorconfig")

    exit_code = check_editorconfig.main(["demo.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "EditorConfig check failed:" in captured
    assert "demo.md:1: trailing whitespace" in captured


def test_expand_braces_keeps_an_unclosed_group_literal() -> None:
    """A pattern with no closing brace is matched literally, not expanded."""
    assert check_editorconfig._expand_braces("*.{js") == ["*.{js"]


def test_expand_braces_keeps_a_single_choice_group_literal() -> None:
    """A one-choice group is a literal brace, since EditorConfig needs two or more."""
    assert check_editorconfig._expand_braces("*.{js}") == ["*.{js}"]


def test_resolve_requested_paths_rejects_a_directory(tmp_path: Path) -> None:
    """A directory is refused rather than read as a file."""
    (tmp_path / "docs").mkdir()

    _, errors = check_editorconfig.resolve_requested_paths(["docs"], tmp_path)

    assert errors == ["docs: path does not exist or is not a file"]


def test_resolve_requested_paths_reports_a_missing_path(tmp_path: Path) -> None:
    """A missing explicit path gets a distinct diagnostic."""
    _, errors = check_editorconfig.resolve_requested_paths(["missing.txt"], tmp_path)

    assert errors == ["missing.txt: path does not exist"]


def test_resolve_requested_paths_reports_an_inaccessible_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path that cannot be resolved gets an access diagnostic."""
    original = Path.resolve

    def inaccessible_resolve(self: Path, strict: bool = False) -> Path:
        """Simulate an operating-system access failure for one candidate."""
        if self.name == "blocked.txt":
            raise OSError("permission denied")
        return original(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", inaccessible_resolve)

    _, errors = check_editorconfig.resolve_requested_paths(["blocked.txt"], tmp_path)

    assert errors == ["blocked.txt: path could not be accessed"]


def test_resolve_requested_paths_reports_a_resolved_path_outside_the_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A resolved path outside the root gets a containment diagnostic."""
    candidate = tmp_path / "candidate.txt"
    candidate.write_text("safe\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    original = Path.resolve

    def escaping_resolve(self: Path, strict: bool = False) -> Path:
        """Resolve one regular candidate outside the repository root."""
        if self == candidate:
            return outside
        return original(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", escaping_resolve)

    _, errors = check_editorconfig.resolve_requested_paths(["candidate.txt"], tmp_path)

    assert errors == ["candidate.txt: path resolves outside the repository"]
