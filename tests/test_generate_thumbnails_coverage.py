from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

import scripts.generate_thumbnails as generate_thumbnails


def test_save_thumbnail_converts_non_rgb_images(tmp_path: Path) -> None:
    source = Image.new("L", (640, 360), color=128)
    buffer = BytesIO()
    source.save(buffer, format="PNG")

    thumb_path = tmp_path / "thumbnail.webp"
    generate_thumbnails.save_thumbnail(buffer.getvalue(), thumb_path)

    with Image.open(thumb_path) as thumbnail:
        assert thumbnail.mode == "RGB"
        assert thumbnail.size == (640, 360)


def test_save_thumbnail_converts_alpha_images(tmp_path: Path) -> None:
    source = Image.new("LA", (640, 360), color=(128, 200))
    buffer = BytesIO()
    source.save(buffer, format="PNG")

    thumb_path = tmp_path / "thumbnail.webp"
    generate_thumbnails.save_thumbnail(buffer.getvalue(), thumb_path)

    with Image.open(thumb_path) as thumbnail:
        assert thumbnail.mode == "RGBA"
        assert thumbnail.size == (640, 360)
