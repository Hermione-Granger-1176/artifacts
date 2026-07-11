"""Tests for the vendored asset integrity lint check."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.lint.check_vendored_assets import (
    VendoredAsset,
    _load_manifest,
    check_assets,
    discover_vendor_files,
    main,
    run_check,
)


def _write_vendor_file(root: Path, rel_path: str, content: bytes) -> str:
    """Write a vendored bundle under the root and return its sha256."""
    path = root / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _write_manifest(path: Path, entries: list[dict[str, str]]) -> None:
    """Write a vendored asset manifest file."""
    path.write_text(json.dumps({"assets": entries}), encoding="utf-8")


def _entry(path: str, sha256: str, *, package: str = "chart.js") -> dict[str, str]:
    """Build one manifest entry."""
    return {
        "path": path,
        "package": package,
        "version": "1.0.0",
        "upstream": "https://cdn.jsdelivr.net/npm/pkg/dist/pkg.js",
        "sha256": sha256,
    }


_REL = "apps/demo/js/vendor/lib.min.js"
_SHA_A = "a" * 64
_SHA_B = "b" * 64


def test_check_assets_passes_when_hashes_match(tmp_path: Path) -> None:
    """Check assets passes when hashes match."""
    digest = _write_vendor_file(tmp_path, _REL, b"console.log(1);")
    assets = (VendoredAsset(_REL, "chart.js", "1.0.0", "https://example/x.js", digest),)
    assert check_assets(tmp_path, assets) == []


def test_check_assets_flags_hash_mismatch(tmp_path: Path) -> None:
    """Check assets flags hash mismatch."""
    _write_vendor_file(tmp_path, _REL, b"tampered();")
    assets = (VendoredAsset(_REL, "chart.js", "1.0.0", "https://example/x.js", "deadbeef"),)
    violations = check_assets(tmp_path, assets)
    assert len(violations) == 1
    assert "sha256 mismatch" in violations[0]
    assert "config/vendored_assets.json" in violations[0]


def test_check_assets_flags_file_missing_on_disk(tmp_path: Path) -> None:
    """Check assets flags file missing on disk."""
    assets = (VendoredAsset(_REL, "chart.js", "1.0.0", "https://example/x.js", "abc123"),)
    violations = check_assets(tmp_path, assets)
    assert violations == [
        f"{_REL}: manifest entry has no file on disk (chart.js 1.0.0 from https://example/x.js)",
    ]


def test_check_assets_flags_file_missing_from_manifest(tmp_path: Path) -> None:
    """Check assets flags file missing from manifest."""
    _write_vendor_file(tmp_path, _REL, b"console.log(1);")
    violations = check_assets(tmp_path, ())
    assert len(violations) == 1
    assert violations[0].startswith(f"{_REL}: vendored file is not listed")


def test_check_assets_flags_symlinked_file(tmp_path: Path) -> None:
    """Check assets flags a symlinked vendored file instead of hashing its target."""
    root = tmp_path / "repo"
    outside = tmp_path / "outside.js"
    outside.write_bytes(b"console.log(1);")
    digest = hashlib.sha256(b"console.log(1);").hexdigest()
    vendor_dir = root / "apps" / "demo" / "js" / "vendor"
    vendor_dir.mkdir(parents=True)
    (vendor_dir / "lib.min.js").symlink_to(outside)
    assets = (VendoredAsset(_REL, "chart.js", "1.0.0", "https://example/x.js", digest),)

    violations = check_assets(root, assets)

    assert len(violations) == 1
    assert violations[0].startswith(f"{_REL}: path must resolve to a regular file")
    assert "no symlinked components" in violations[0]


def test_check_assets_flags_symlinked_parent_directory(tmp_path: Path) -> None:
    """Check assets flags a symlinked parent directory even when the hash matches."""
    root = tmp_path / "repo"
    outside_dir = tmp_path / "outside-vendor"
    outside_dir.mkdir()
    (outside_dir / "lib.min.js").write_bytes(b"console.log(1);")
    digest = hashlib.sha256(b"console.log(1);").hexdigest()
    js_dir = root / "apps" / "demo" / "js"
    js_dir.mkdir(parents=True)
    (js_dir / "vendor").symlink_to(outside_dir, target_is_directory=True)
    assets = (VendoredAsset(_REL, "chart.js", "1.0.0", "https://example/x.js", digest),)

    violations = check_assets(root, assets)

    assert len(violations) == 1
    assert violations[0].startswith(f"{_REL}: path must resolve to a regular file")
    assert "no symlinked components" in violations[0]


def test_discover_vendor_files_returns_sorted_relative_paths(tmp_path: Path) -> None:
    """Discover vendor files returns sorted relative paths."""
    _write_vendor_file(tmp_path, "apps/b/js/vendor/two.js", b"2")
    _write_vendor_file(tmp_path, "apps/a/js/vendor/one.js", b"1")
    # A non-vendor JS file must be ignored by the glob.
    _write_vendor_file(tmp_path, "apps/a/js/app.js", b"0")
    assert discover_vendor_files(tmp_path) == [
        "apps/a/js/vendor/one.js",
        "apps/b/js/vendor/two.js",
    ]


def test_load_manifest_reads_valid_entries(tmp_path: Path) -> None:
    """Load manifest reads valid entries."""
    manifest = tmp_path / "vendored_assets.json"
    _write_manifest(manifest, [_entry(_REL, _SHA_A.upper())])
    assets = _load_manifest(manifest)
    assert len(assets) == 1
    assert assets[0].path == _REL
    # Recorded hashes are normalized to lower case for comparison.
    assert assets[0].sha256 == _SHA_A


def test_load_manifest_rejects_missing_file(tmp_path: Path) -> None:
    """Load manifest rejects missing file."""
    with pytest.raises(FileNotFoundError, match="Vendored assets manifest not found"):
        _load_manifest(tmp_path / "missing.json")


def test_load_manifest_rejects_non_object_root(tmp_path: Path) -> None:
    """Load manifest rejects non object root."""
    manifest = tmp_path / "vendored_assets.json"
    manifest.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a JSON object"):
        _load_manifest(manifest)


def test_load_manifest_rejects_non_list_assets(tmp_path: Path) -> None:
    """Load manifest rejects non list assets."""
    manifest = tmp_path / "vendored_assets.json"
    manifest.write_text('{"assets": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="'assets' must be a list"):
        _load_manifest(manifest)


def test_load_manifest_rejects_non_object_entry(tmp_path: Path) -> None:
    """Load manifest rejects non object entry."""
    manifest = tmp_path / "vendored_assets.json"
    manifest.write_text('{"assets": ["bad"]}', encoding="utf-8")
    with pytest.raises(ValueError, match="must be objects"):
        _load_manifest(manifest)


def test_load_manifest_rejects_missing_fields(tmp_path: Path) -> None:
    """Load manifest rejects missing fields."""
    manifest = tmp_path / "vendored_assets.json"
    manifest.write_text('{"assets": [{"path": "x"}]}', encoding="utf-8")
    with pytest.raises(ValueError, match="must include"):
        _load_manifest(manifest)


def test_load_manifest_rejects_duplicate_paths(tmp_path: Path) -> None:
    """Load manifest rejects duplicate paths."""
    manifest = tmp_path / "vendored_assets.json"
    _write_manifest(manifest, [_entry(_REL, _SHA_A), _entry(_REL, _SHA_B)])
    with pytest.raises(ValueError, match="must not duplicate a path"):
        _load_manifest(manifest)


@pytest.mark.parametrize(
    "bad_path",
    [
        "apps/demo/js/vendor/../../../etc/passwd.js",
        "/etc/passwd.js",
        "config/secrets.js",
        "apps/demo/js/app.js",
        "apps/demo/js/vendor/nested/lib.js",
    ],
)
def test_load_manifest_rejects_unsafe_paths(tmp_path: Path, bad_path: str) -> None:
    """Load manifest rejects traversal, absolute, and non-vendor paths."""
    manifest = tmp_path / "vendored_assets.json"
    _write_manifest(manifest, [_entry(bad_path, _SHA_A)])
    with pytest.raises(ValueError, match="must be a repo-relative"):
        _load_manifest(manifest)


def test_load_manifest_rejects_malformed_sha256(tmp_path: Path) -> None:
    """Load manifest rejects a sha256 that is not a 64-hex digest."""
    manifest = tmp_path / "vendored_assets.json"
    _write_manifest(manifest, [_entry(_REL, "deadbeef")])
    with pytest.raises(ValueError, match="must be a 64-character hex digest"):
        _load_manifest(manifest)


def test_run_check_uses_manifest_and_disk(tmp_path: Path) -> None:
    """Run check uses manifest and disk."""
    digest = _write_vendor_file(tmp_path, _REL, b"console.log(1);")
    manifest = tmp_path / "vendored_assets.json"
    _write_manifest(manifest, [_entry(_REL, digest)])
    assert run_check(tmp_path, manifest) == []


def test_main_returns_zero_when_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Main returns zero when clean."""
    digest = _write_vendor_file(tmp_path, _REL, b"console.log(1);")
    manifest = tmp_path / "vendored_assets.json"
    _write_manifest(manifest, [_entry(_REL, digest)])
    monkeypatch.setattr(
        "scripts.lint.check_vendored_assets.VENDORED_ASSETS_MANIFEST_FILE", manifest
    )
    assert main(["--root", str(tmp_path)]) == 0


def test_main_returns_one_when_violations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Main returns one when violations."""
    _write_vendor_file(tmp_path, _REL, b"tampered();")
    manifest = tmp_path / "vendored_assets.json"
    _write_manifest(manifest, [_entry(_REL, _SHA_A)])
    monkeypatch.setattr(
        "scripts.lint.check_vendored_assets.VENDORED_ASSETS_MANIFEST_FILE", manifest
    )
    assert main(["--root", str(tmp_path)]) == 1


def test_main_returns_one_on_manifest_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main returns one on manifest error."""
    monkeypatch.setattr(
        "scripts.lint.check_vendored_assets.VENDORED_ASSETS_MANIFEST_FILE",
        tmp_path / "missing.json",
    )
    assert main(["--root", str(tmp_path)]) == 1
    assert "Vendored assets check failed" in capsys.readouterr().out
