"""Tests for the widened __main__ error handling in the build entry points.

The ``if __name__ == "__main__"`` blocks are excluded from coverage, so these
tests execute the scripts as ``__main__`` through :func:`runpy.run_path` to prove
the widened ``except`` tuples turn the newly caught error types into a clean
exit(1) instead of a raw traceback.
"""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

import scripts.build.generate_index as generate_index
import scripts.build.generate_thumbnails as generate_thumbnails
import scripts.build.index_config as index_config


def _run_as_main(module_file: str) -> None:
    """Execute a module file under the ``__main__`` name via runpy."""
    runpy.run_path(module_file, run_name="__main__")


def test_thumbnails_main_exits_on_manifest_value_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Thumbnails main exits on manifest value error."""
    # An unknown slug makes find_artifacts return no work, so the run reaches the
    # manifest write; a path outside the repo makes _write_manifest raise ValueError.
    monkeypatch.setenv("ARTIFACTS_THUMBNAIL_SLUGS", "no-such-slug-xyz")
    monkeypatch.setenv("ARTIFACTS_THUMBNAIL_MANIFEST", str(tmp_path / "manifest.json"))

    with pytest.raises(SystemExit) as exc_info:
        _run_as_main(generate_thumbnails.__file__)

    assert exc_info.value.code == 1


def test_thumbnails_main_exits_on_manifest_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Thumbnails main exits on manifest os error."""
    # A manifest path whose parent is an existing file makes mkdir raise OSError
    # (NotADirectoryError) while staying inside the repository root.
    manifest_path = generate_thumbnails.REPO_ROOT / "README.md" / "nested" / "manifest.json"
    monkeypatch.setenv("ARTIFACTS_THUMBNAIL_SLUGS", "no-such-slug-xyz")
    monkeypatch.setenv("ARTIFACTS_THUMBNAIL_MANIFEST", str(manifest_path))

    with pytest.raises(SystemExit) as exc_info:
        _run_as_main(generate_thumbnails.__file__)

    assert exc_info.value.code == 1


@pytest.mark.parametrize("error", [ValueError("bad data"), OSError("disk gone")])
def test_index_main_exits_on_generate_error(
    error: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Index main exits on generate error."""

    class _RaisingConfig:
        @staticmethod
        def create_default() -> object:
            raise error

    monkeypatch.setattr(index_config, "IndexConfig", _RaisingConfig)

    with pytest.raises(SystemExit) as exc_info:
        _run_as_main(generate_index.__file__)

    assert exc_info.value.code == 1
