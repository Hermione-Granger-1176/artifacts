from __future__ import annotations

from pathlib import Path

import pytest

from scripts.setup import clean_venv


def test_remove_venv_deletes_a_direct_repository_child(tmp_path: Path) -> None:
    """Remove the configured environment without touching its siblings."""
    environment = tmp_path / ".venv"
    environment.mkdir()
    (environment / "marker").write_text("remove", encoding="utf-8")
    sibling = tmp_path / "keep"
    sibling.mkdir()

    assert clean_venv.remove_venv(tmp_path, ".venv")
    assert not environment.exists()
    assert sibling.is_dir()


def test_remove_venv_is_idempotent(tmp_path: Path) -> None:
    """A missing, otherwise safe environment is already clean."""
    assert not clean_venv.remove_venv(tmp_path, ".venv")


@pytest.mark.parametrize(
    "value",
    (
        "",
        ".",
        "..",
        "../outside",
        "nested/.venv",
        "/tmp/external-venv",
    ),
)
def test_validated_venv_path_rejects_escaping_or_ambiguous_values(
    tmp_path: Path,
    value: str,
) -> None:
    """Only one repository-root child can be selected for deletion."""
    with pytest.raises(clean_venv.CleanVenvError, match="directly below"):
        clean_venv.validated_venv_path(tmp_path, value)


def test_validated_venv_path_rejects_a_symlink(tmp_path: Path) -> None:
    """Never follow a virtual-environment symlink to another location."""
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    environment = tmp_path / ".venv"
    environment.symlink_to(outside, target_is_directory=True)

    with pytest.raises(clean_venv.CleanVenvError, match="must not be a symlink"):
        clean_venv.validated_venv_path(tmp_path, ".venv")


def test_validated_venv_path_rejects_a_symlink_loop(tmp_path: Path) -> None:
    """A self-referential environment link fails closed."""
    environment = tmp_path / ".venv"
    environment.symlink_to(environment, target_is_directory=True)

    with pytest.raises(clean_venv.CleanVenvError, match="must not be a symlink"):
        clean_venv.validated_venv_path(tmp_path, ".venv")


def test_validated_venv_path_rejects_a_regular_file(tmp_path: Path) -> None:
    """Do not delete a file that happens to use the configured directory name."""
    (tmp_path / ".venv").write_text("keep", encoding="utf-8")

    with pytest.raises(clean_venv.CleanVenvError, match="must be a directory"):
        clean_venv.validated_venv_path(tmp_path, ".venv")


def test_validated_venv_path_reports_an_unresolvable_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolution errors fail closed before any deletion is attempted."""
    original_resolve = Path.resolve

    def fail_for_root(path: Path, *, strict: bool = False) -> Path:
        if path == tmp_path:
            raise OSError("permission denied")
        return original_resolve(path, strict=strict)

    monkeypatch.setattr(Path, "resolve", fail_for_root)

    with pytest.raises(clean_venv.CleanVenvError, match="permission denied"):
        clean_venv.validated_venv_path(tmp_path, ".venv")


def test_validated_venv_path_rejects_a_non_directory_root(tmp_path: Path) -> None:
    """The safety boundary itself must be a directory."""
    root_file = tmp_path / "repo-file"
    root_file.write_text("not a directory", encoding="utf-8")

    with pytest.raises(clean_venv.CleanVenvError, match="root is not a directory"):
        clean_venv.validated_venv_path(root_file, ".venv")


def test_validated_venv_path_reports_inspection_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An inaccessible environment fails closed."""
    environment = tmp_path / ".venv"
    original_lstat = Path.lstat

    def fail_for_environment(path: Path) -> object:
        if path == environment:
            raise OSError("permission denied")
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fail_for_environment)

    with pytest.raises(clean_venv.CleanVenvError, match="permission denied"):
        clean_venv.validated_venv_path(tmp_path, ".venv")


def test_remove_venv_reports_a_post_validation_inspection_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A path that becomes inaccessible after validation is not removed."""
    environment = tmp_path / ".venv"
    environment.mkdir()

    def fail_inspection(_path: Path) -> object:
        raise OSError("blocked")

    monkeypatch.setattr(clean_venv, "validated_venv_path", lambda *_args: environment)
    monkeypatch.setattr(Path, "lstat", fail_inspection)

    with pytest.raises(clean_venv.CleanVenvError, match="blocked"):
        clean_venv.remove_venv(tmp_path, ".venv")


@pytest.mark.parametrize("replacement", ("file", "symlink"))
def test_remove_venv_revalidates_the_path_before_deletion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    replacement: str,
) -> None:
    """A path swapped after initial validation fails closed."""
    environment = tmp_path / ".venv"
    if replacement == "file":
        environment.write_text("keep", encoding="utf-8")
        expected = "must be a directory"
    else:
        outside = tmp_path / "outside"
        outside.mkdir()
        environment.symlink_to(outside, target_is_directory=True)
        expected = "must not be a symlink"

    monkeypatch.setattr(clean_venv, "validated_venv_path", lambda *_args: environment)

    with pytest.raises(clean_venv.CleanVenvError, match=expected):
        clean_venv.remove_venv(tmp_path, ".venv")


def test_remove_venv_reports_deletion_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Recursive-removal failures retain their operating-system reason."""
    environment = tmp_path / ".venv"
    environment.mkdir()

    def fail_removal(_path: Path) -> None:
        raise OSError("busy")

    monkeypatch.setattr(clean_venv.shutil, "rmtree", fail_removal)

    with pytest.raises(clean_venv.CleanVenvError, match="busy"):
        clean_venv.remove_venv(tmp_path, ".venv")


def test_main_reports_unsafe_values(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The Make-facing command returns a concise refusal."""
    assert clean_venv.main(["--repo-root", str(tmp_path), "--venv", "../outside"]) == 1
    assert "ERROR: refusing to clean:" in capsys.readouterr().err


def test_main_accepts_an_already_clean_environment(tmp_path: Path) -> None:
    """The Make-facing command succeeds when there is nothing to remove."""
    assert clean_venv.main(["--repo-root", str(tmp_path), "--venv", ".venv"]) == 0


def test_main_reads_make_values_from_the_environment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Make can pass paths without interpolating them into a shell command."""
    monkeypatch.setenv("CLEAN_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("CLEAN_VENV", ".venv")

    assert clean_venv.main([]) == 0
    assert clean_venv.parse_args([]).repo_root == tmp_path


def test_parse_args_treats_empty_environment_values_as_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty inherited values cannot silently select the current directory."""
    monkeypatch.setenv("CLEAN_REPO_ROOT", "")
    monkeypatch.setenv("CLEAN_VENV", "")

    with pytest.raises(SystemExit):
        clean_venv.parse_args([])
