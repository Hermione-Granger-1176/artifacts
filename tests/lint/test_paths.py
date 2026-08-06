from __future__ import annotations

from pathlib import Path

from scripts.lint import contains_symlink, iter_lint_paths


def test_iter_lint_paths_sorts_files_and_prunes_ignored_directories(tmp_path: Path) -> None:
    """Traversal is deterministic and never opens generated trees."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "z.md").write_text("z", encoding="utf-8")
    (tmp_path / "docs" / "a.md").write_text("a", encoding="utf-8")
    ignored = tmp_path / "node_modules"
    ignored.mkdir()
    (ignored / "dependency.js").write_text("ignored", encoding="utf-8")

    assert list(iter_lint_paths(tmp_path)) == [
        tmp_path / "docs" / "a.md",
        tmp_path / "docs" / "z.md",
    ]


def test_iter_lint_paths_skips_file_and_directory_symlinks(tmp_path: Path) -> None:
    """Lint traversal does not follow or return symlinked content."""
    real_file = tmp_path / "real.py"
    real_file.write_text("content", encoding="utf-8")
    (tmp_path / "linked.py").symlink_to(real_file)
    external = tmp_path.parent / f"{tmp_path.name}-external-lint"
    external.mkdir()
    (external / "outside.py").write_text("outside", encoding="utf-8")
    (tmp_path / "linked-directory").symlink_to(external, target_is_directory=True)

    assert list(iter_lint_paths(tmp_path)) == [real_file]


def test_contains_symlink_detects_linked_path_components(tmp_path: Path) -> None:
    """Requested paths can be checked without resolving outside the root."""
    real_file = tmp_path / "real.py"
    real_file.write_text("content", encoding="utf-8")
    linked = tmp_path / "linked.py"
    linked.symlink_to(real_file)
    linked_directory = tmp_path / "linked-directory"
    linked_directory.symlink_to(tmp_path, target_is_directory=True)

    assert not contains_symlink(real_file, tmp_path)
    assert contains_symlink(linked, tmp_path)
    assert contains_symlink(linked_directory / "real.py", tmp_path)
