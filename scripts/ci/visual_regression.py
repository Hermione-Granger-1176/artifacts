#!/usr/bin/env python3
"""Tolerant pixel comparison for the visual-regression baseline check.

Screenshot baselines are inherently sensitive to font rendering, so this
comparison is deliberately forgiving: a pixel only counts as changed when at
least one channel differs from the baseline by more than ``channel_tolerance``,
and the overall image only fails when the changed fraction exceeds
``max_diff_fraction``. The Playwright capture in
``tests/browser/test_frontend_visual.py`` drives this module; keeping the math
here makes it unit-testable without a browser.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from PIL import Image, ImageChops

if TYPE_CHECKING:
    from pathlib import Path

# Per-channel absolute difference below which two pixels are treated as equal.
DEFAULT_CHANNEL_TOLERANCE = 32
# Fraction of changed pixels the whole image may contain before it fails.
DEFAULT_MAX_DIFF_FRACTION = 0.05


@dataclass(frozen=True)
class ComparisonResult:
    """Outcome of one baseline-versus-candidate screenshot comparison."""

    passed: bool
    diff_fraction: float
    message: str


def _changed_pixel_count(
    baseline: Image.Image, candidate: Image.Image, *, channel_tolerance: int
) -> int:
    """Return how many pixels differ beyond ``channel_tolerance`` in any channel."""
    difference = ImageChops.difference(baseline, candidate)
    red, green, blue = difference.split()
    max_channel = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    mask = max_channel.point(lambda value: 255 if value > channel_tolerance else 0)
    return mask.histogram()[255]


def compare_images(
    baseline_path: Path,
    candidate_path: Path,
    *,
    channel_tolerance: int = DEFAULT_CHANNEL_TOLERANCE,
    max_diff_fraction: float = DEFAULT_MAX_DIFF_FRACTION,
) -> ComparisonResult:
    """Compare two screenshots and return a tolerant pass/fail result."""
    with Image.open(baseline_path) as baseline_image:
        baseline = baseline_image.convert("RGB")
    with Image.open(candidate_path) as candidate_image:
        candidate = candidate_image.convert("RGB")

    if baseline.size != candidate.size:
        return ComparisonResult(
            passed=False,
            diff_fraction=1.0,
            message=(
                f"size mismatch: baseline {baseline.size} vs candidate {candidate.size}; "
                "regenerate the baselines"
            ),
        )

    changed = _changed_pixel_count(baseline, candidate, channel_tolerance=channel_tolerance)
    # A real screenshot always has a non-zero area, and a size mismatch is
    # handled above, so the divisor is always positive here.
    total = baseline.width * baseline.height
    diff_fraction = changed / total
    passed = diff_fraction <= max_diff_fraction
    if passed:
        message = f"diff fraction {diff_fraction:.4f} within tolerance {max_diff_fraction:.4f}"
    else:
        message = (
            f"diff fraction {diff_fraction:.4f} exceeds tolerance {max_diff_fraction:.4f}; "
            "review the change and, if intended, regenerate the baselines"
        )
    return ComparisonResult(passed=passed, diff_fraction=diff_fraction, message=message)
