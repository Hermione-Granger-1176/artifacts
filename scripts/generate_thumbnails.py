#!/usr/bin/env python3
"""
Generate Thumbnails

Scans artifact directories for index.html files and uses Playwright to
capture a screenshot of each, saving an optimized thumbnail.webp in the
artifact folder.

Usage:
    python scripts/generate_thumbnails.py
"""

from __future__ import annotations

import logging
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "apps"
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
SCREENSHOT_FILE = "thumbnail.webp"
LEGACY_SCREENSHOT_FILE = "thumbnail.png"
THUMBNAIL_WIDTH = 960
THUMBNAIL_QUALITY = 85


def find_artifacts() -> list[Path]:
    """Find all artifact directories containing an index.html."""
    if not APPS_DIR.exists():
        return []
    return [
        item
        for item in sorted(APPS_DIR.iterdir())
        if item.is_dir()
        and not item.name.startswith(".")
        and (item / "index.html").exists()
    ]


def save_thumbnail(image_bytes: bytes, thumb_path: Path) -> None:
    """Resize a screenshot and save it as an optimized WebP thumbnail."""
    with Image.open(BytesIO(image_bytes)) as image:
        width = min(THUMBNAIL_WIDTH, image.width)
        height = round(image.height * width / image.width)
        if (width, height) != image.size:
            image = image.resize((width, height), Image.Resampling.LANCZOS)
        if image.mode not in {"RGB", "RGBA"}:
            image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
        image.save(thumb_path, format="WEBP", quality=THUMBNAIL_QUALITY, method=6)


def generate_thumbnails() -> None:
    """Generate thumbnail screenshots for all artifacts."""
    artifacts = find_artifacts()
    if not artifacts:
        logger.info("No artifacts found")
        return

    logger.info("Found %d artifact(s) to screenshot", len(artifacts))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error("Playwright is not installed. Run: pip install playwright")
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
            device_scale_factor=2,
        )

        for artifact_dir in artifacts:
            html_path = artifact_dir / "index.html"
            thumb_path = artifact_dir / SCREENSHOT_FILE
            legacy_thumb_path = artifact_dir / LEGACY_SCREENSHOT_FILE
            file_url = html_path.resolve().as_uri()

            logger.info("Screenshotting %s", artifact_dir.name)
            try:
                page.goto(file_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1000)
                screenshot_bytes = page.screenshot(type="png")
                save_thumbnail(screenshot_bytes, thumb_path)
                if legacy_thumb_path.exists():
                    legacy_thumb_path.unlink()
                logger.info("  -> %s", thumb_path.name)
            except Exception as e:
                logger.warning("Failed to screenshot %s: %s", artifact_dir.name, e)

        browser.close()

    logger.info("Done generating thumbnails")


if __name__ == "__main__":  # pragma: no cover
    generate_thumbnails()
