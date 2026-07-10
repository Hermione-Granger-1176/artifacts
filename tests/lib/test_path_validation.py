from __future__ import annotations

from pathlib import Path

import pytest

from scripts.lib.path_validation import reject_symlinks


def test_clean_tree_passes(tmp_path: Path) -> None:
    """Test clean tree passes."""
    sub = tmp_path / "a" / "b"
    sub.mkdir(parents=True)
    (sub / "file.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "top.txt").write_text("ok", encoding="utf-8")

    reject_symlinks(tmp_path)  # should not raise


def test_symlink_file_raises(tmp_path: Path) -> None:
    """Test symlink file raises."""
    real = tmp_path / "real.txt"
    real.write_text("content", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(real)

    with pytest.raises(ValueError, match="symlink"):
        reject_symlinks(tmp_path)


def test_symlink_directory_raises(tmp_path: Path) -> None:
    """Test symlink directory raises."""
    real_dir = tmp_path / "real_dir"
    real_dir.mkdir()
    link_dir = tmp_path / "link_dir"
    link_dir.symlink_to(real_dir)

    with pytest.raises(ValueError, match="symlink"):
        reject_symlinks(tmp_path)


def test_nested_symlink_raises(tmp_path: Path) -> None:
    """Test nested symlink raises."""
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    real = nested / "real.txt"
    real.write_text("content", encoding="utf-8")
    link = nested / "sneaky.txt"
    link.symlink_to(real)

    with pytest.raises(ValueError, match="symlink"):
        reject_symlinks(tmp_path)
