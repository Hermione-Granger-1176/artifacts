#!/usr/bin/env python3
"""Recompress an oversized social share image in place.

This module backs `make optimize-social-image`.

The Open Graph share card (`assets/social/share-preview.png`) is served on every
link unfurl, so it should stay small. A 1200x630 card is comfortable at roughly
100-150 KB, yet exported PNGs routinely ship several times that. This helper
re-encodes the PNG (and downscales it to fit within 1200x630 when it is larger),
writing back only when the result is actually smaller so a repeat run is a no-op.

The optimization is lossy. Any transparency is flattened onto a white background,
and one of the candidate encodings quantizes the image to a 256-color palette, so
fine gradients and alpha edges can shift. The smaller of the palette candidate and
a plain optimized truecolor candidate wins, which keeps flat graphic cards tiny
while protecting gradient-heavy art.

Run through the Makefile in normal workflows; direct invocation is mainly for
maintainers working on the build internals.
"""

from __future__ import annotations

import argparse
import sys
from io import BytesIO
from pathlib import Path
from typing import NamedTuple

from PIL import Image

from scripts import REPO_ROOT

# Canonical Open Graph card. Overridable on the command line.
DEFAULT_TARGET = REPO_ROOT / "assets" / "social" / "share-preview.png"

# Open Graph recommends a 1200x630 card; never emit anything larger.
MAX_WIDTH = 1200
MAX_HEIGHT = 630

# Palette ceiling for the quantized candidate encoding.
MAX_PALETTE_COLORS = 256


class OptimizeResult(NamedTuple):
    """Outcome of one optimization pass."""

    before: int
    after: int
    written: bool


def _resize_within_bounds(image: Image.Image) -> Image.Image:
    """Return a copy scaled to fit within the Open Graph bounds, if oversized."""
    if image.width <= MAX_WIDTH and image.height <= MAX_HEIGHT:
        return image
    resized = image.copy()
    resized.thumbnail((MAX_WIDTH, MAX_HEIGHT))
    return resized


def _flatten_to_rgb(image: Image.Image) -> Image.Image:
    """Return an RGB image, compositing any transparency onto white."""
    if image.mode == "RGB":
        return image
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def _encode_smallest(image: Image.Image) -> bytes:
    """Encode the image as PNG twice and return the smaller candidate.

    Candidate one is a plain optimized truecolor PNG; candidate two quantizes to
    a 256-color palette. The palette encoding usually wins for flat, graphic
    cards while the truecolor encoding protects gradient-heavy art.
    """
    rgb = _flatten_to_rgb(image)

    truecolor = BytesIO()
    rgb.save(truecolor, format="PNG", optimize=True)

    palette = BytesIO()
    rgb.quantize(colors=MAX_PALETTE_COLORS).save(palette, format="PNG", optimize=True)

    return min(truecolor.getvalue(), palette.getvalue(), key=len)


def optimize_png(path: Path) -> OptimizeResult:
    """Recompress a PNG in place, writing only when it shrinks."""
    if not path.is_file():
        raise FileNotFoundError(f"Social image not found: {path}")

    before = path.stat().st_size
    with Image.open(path) as opened:
        opened.load()
        # Flatten before resizing: Pillow forces NEAREST resampling for
        # palette ("P") and bilevel ("1") images, so downscaling those modes
        # directly would produce jagged output.
        image = _resize_within_bounds(_flatten_to_rgb(opened))
        encoded = _encode_smallest(image)

    after = len(encoded)
    written = after < before
    if written:
        path.write_bytes(encoded)
    return OptimizeResult(before=before, after=after, written=written)


def _print_report(path: Path, result: OptimizeResult) -> None:
    """Print a before/after summary for one optimization pass."""
    print(f"{path}: {result.before} bytes -> {result.after} bytes")
    if result.written:
        saved = result.before - result.after
        print(f"Rewrote {path.name}, saved {saved} bytes")
    else:
        print(f"Left {path.name} unchanged (re-encode was not smaller)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the social image optimizer."""
    parser = argparse.ArgumentParser(
        description="Recompress an oversized social share PNG in place."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help=f"PNG to optimize (defaults to {DEFAULT_TARGET})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    args = parse_args(argv)
    path = Path(args.path) if args.path else DEFAULT_TARGET

    try:
        result = optimize_png(path)
    except (OSError, ValueError) as exc:
        # OSError covers a missing file and Pillow's UnidentifiedImageError /
        # truncated-file errors; ValueError covers malformed PNG chunk data.
        print(f"Social image optimization failed: {exc}", file=sys.stderr)
        return 1

    _print_report(path, result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
