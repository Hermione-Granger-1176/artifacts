from __future__ import annotations

from pathlib import Path

from PIL import Image

from scripts.ci import visual_regression


def _write_image(path: Path, color: tuple[int, int, int], size: tuple[int, int] = (20, 20)) -> Path:
    Image.new("RGB", size, color).save(path)
    return path


def test_identical_images_pass(tmp_path: Path) -> None:
    """Two identical images compare as passing with zero diff."""
    baseline = _write_image(tmp_path / "base.png", (120, 120, 120))
    candidate = _write_image(tmp_path / "cand.png", (120, 120, 120))
    result = visual_regression.compare_images(baseline, candidate)
    assert result.passed
    assert result.diff_fraction == 0.0


def test_small_per_pixel_noise_is_tolerated(tmp_path: Path) -> None:
    """A uniform sub-threshold channel shift across every pixel still passes."""
    baseline = _write_image(tmp_path / "base.png", (120, 120, 120))
    # +16 per channel is below the default channel tolerance of 32.
    candidate = _write_image(tmp_path / "cand.png", (136, 136, 136))
    result = visual_regression.compare_images(baseline, candidate)
    assert result.passed
    assert result.diff_fraction == 0.0


def test_large_area_change_fails(tmp_path: Path) -> None:
    """A big channel change across the whole image exceeds the diff tolerance."""
    baseline = _write_image(tmp_path / "base.png", (0, 0, 0))
    candidate = _write_image(tmp_path / "cand.png", (255, 255, 255))
    result = visual_regression.compare_images(baseline, candidate)
    assert not result.passed
    assert result.diff_fraction == 1.0
    assert "exceeds tolerance" in result.message


def test_small_localized_change_stays_within_fraction(tmp_path: Path) -> None:
    """A few strongly changed pixels stay under the total-fraction tolerance."""
    baseline = _write_image(tmp_path / "base.png", (0, 0, 0), size=(100, 100))
    candidate_image = Image.new("RGB", (100, 100), (0, 0, 0))
    # 100 of 10000 pixels (1%) flipped to white, under the 5% default.
    for x in range(100):
        candidate_image.putpixel((x, 0), (255, 255, 255))
    candidate = tmp_path / "cand.png"
    candidate_image.save(candidate)
    result = visual_regression.compare_images(baseline, candidate)
    assert result.passed
    assert 0 < result.diff_fraction <= 0.05


def test_size_mismatch_fails(tmp_path: Path) -> None:
    """Differently sized images fail immediately with a regenerate hint."""
    baseline = _write_image(tmp_path / "base.png", (10, 10, 10), size=(20, 20))
    candidate = _write_image(tmp_path / "cand.png", (10, 10, 10), size=(30, 30))
    result = visual_regression.compare_images(baseline, candidate)
    assert not result.passed
    assert result.diff_fraction == 1.0
    assert "size mismatch" in result.message


def test_custom_tolerances_change_outcome(tmp_path: Path) -> None:
    """Tightening the channel tolerance turns a tolerated shift into a failure."""
    baseline = _write_image(tmp_path / "base.png", (120, 120, 120))
    candidate = _write_image(tmp_path / "cand.png", (150, 150, 150))
    lenient = visual_regression.compare_images(baseline, candidate)
    assert lenient.passed
    strict = visual_regression.compare_images(
        baseline, candidate, channel_tolerance=10, max_diff_fraction=0.0
    )
    assert not strict.passed
