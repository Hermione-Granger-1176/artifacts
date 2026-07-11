from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

import scripts.build.optimize_social_image as optimize_social_image


def _write_noisy_png(path: Path, size: tuple[int, int], mode: str = "RGBA") -> None:
    """Write an incompressible, oversized PNG so re-encoding clearly shrinks it."""
    channels = len(mode)
    data = os.urandom(size[0] * size[1] * channels)
    Image.frombytes(mode, size, data).save(path)


def _write_solid_png(path: Path, size: tuple[int, int]) -> None:
    """Write a small solid-color PNG that is already near its minimal size."""
    Image.new("RGB", size, (12, 34, 56)).save(path)


def test_resize_within_bounds_leaves_small_images_untouched() -> None:
    """Test images already within the Open Graph bounds are returned as-is."""
    image = Image.new("RGB", (100, 100), (0, 0, 0))

    assert optimize_social_image._resize_within_bounds(image) is image


def test_resize_within_bounds_scales_oversized_images() -> None:
    """Test oversized images are scaled to fit within the Open Graph bounds."""
    image = Image.new("RGB", (2400, 1260), (0, 0, 0))

    resized = optimize_social_image._resize_within_bounds(image)

    assert resized is not image
    assert resized.width <= optimize_social_image.MAX_WIDTH
    assert resized.height <= optimize_social_image.MAX_HEIGHT


def test_flatten_to_rgb_passes_through_rgb() -> None:
    """Test an RGB image is returned unchanged by the flattener."""
    image = Image.new("RGB", (4, 4), (1, 2, 3))

    assert optimize_social_image._flatten_to_rgb(image) is image


def test_flatten_to_rgb_composites_transparency() -> None:
    """Test a transparent image is composited onto white and returned as RGB."""
    image = Image.new("RGBA", (4, 4), (0, 0, 0, 0))

    flattened = optimize_social_image._flatten_to_rgb(image)

    assert flattened.mode == "RGB"
    assert flattened.getpixel((0, 0)) == (255, 255, 255)


def test_encode_smallest_returns_png_bytes() -> None:
    """Test the encoder returns valid PNG bytes."""
    image = Image.new("RGB", (16, 16), (10, 20, 30))

    encoded = optimize_social_image._encode_smallest(image)

    assert encoded.startswith(b"\x89PNG\r\n\x1a\n")


def test_optimize_png_writes_when_smaller(tmp_path: Path) -> None:
    """Test optimize_png rewrites the file when the re-encode is smaller."""
    path = tmp_path / "share.png"
    _write_noisy_png(path, (1300, 700))
    before = path.stat().st_size

    result = optimize_social_image.optimize_png(path)

    assert result.written is True
    assert result.before == before
    assert result.after < before
    assert path.stat().st_size == result.after
    with Image.open(path) as reopened:
        assert reopened.width <= optimize_social_image.MAX_WIDTH
        assert reopened.height <= optimize_social_image.MAX_HEIGHT


def test_optimize_png_flattens_before_resizing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test palette sources are converted to RGB before the downscale.

    Pillow forces NEAREST resampling for palette-mode images, so resizing a
    "P" image directly would produce jagged output.
    """
    path = tmp_path / "share.png"
    Image.new("RGB", (2400, 1260), (12, 34, 56)).quantize(colors=8).save(path)
    seen_modes: list[str] = []
    original_resize = optimize_social_image._resize_within_bounds

    def spying_resize(image: Image.Image) -> Image.Image:
        seen_modes.append(image.mode)
        return original_resize(image)

    monkeypatch.setattr(optimize_social_image, "_resize_within_bounds", spying_resize)

    optimize_social_image.optimize_png(path)

    assert seen_modes == ["RGB"]


def test_optimize_png_skips_when_not_smaller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test optimize_png leaves the file untouched when re-encoding does not help."""
    path = tmp_path / "share.png"
    _write_solid_png(path, (20, 20))
    original_bytes = path.read_bytes()

    monkeypatch.setattr(
        optimize_social_image,
        "_encode_smallest",
        lambda _image: b"\x00" * (len(original_bytes) + 100),
    )

    result = optimize_social_image.optimize_png(path)

    assert result.written is False
    assert result.after >= result.before
    assert path.read_bytes() == original_bytes


def test_optimize_png_missing_file_raises(tmp_path: Path) -> None:
    """Test optimize_png raises on a missing source file."""
    with pytest.raises(FileNotFoundError, match="Social image not found"):
        optimize_social_image.optimize_png(tmp_path / "missing.png")


def test_print_report_written(capsys: pytest.CaptureFixture[str]) -> None:
    """Test the report announces the saved bytes when a rewrite happened."""
    result = optimize_social_image.OptimizeResult(before=1000, after=400, written=True)

    optimize_social_image._print_report(Path("share.png"), result)

    captured = capsys.readouterr()
    assert "1000 bytes -> 400 bytes" in captured.out
    assert "saved 600 bytes" in captured.out


def test_print_report_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    """Test the report states when the file was left unchanged."""
    result = optimize_social_image.OptimizeResult(before=400, after=400, written=False)

    optimize_social_image._print_report(Path("share.png"), result)

    captured = capsys.readouterr()
    assert "unchanged" in captured.out


def test_main_optimizes_explicit_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Test main optimizes an explicitly provided path and returns zero."""
    path = tmp_path / "share.png"
    _write_noisy_png(path, (1300, 700))

    result = optimize_social_image.main([str(path)])

    captured = capsys.readouterr()
    assert result == 0
    assert "bytes ->" in captured.out
    assert "saved" in captured.out


def test_main_uses_default_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main falls back to the default target when no path is given."""
    path = tmp_path / "default-share.png"
    _write_noisy_png(path, (1300, 700))
    monkeypatch.setattr(optimize_social_image, "DEFAULT_TARGET", path)

    result = optimize_social_image.main([])

    captured = capsys.readouterr()
    assert result == 0
    assert str(path) in captured.out


def test_main_missing_file_returns_nonzero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main returns a nonzero code and reports a missing file."""
    result = optimize_social_image.main([str(tmp_path / "missing.png")])

    captured = capsys.readouterr()
    assert result == 1
    assert "Social image not found" in captured.err
