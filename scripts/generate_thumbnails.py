#!/usr/bin/env python3
"""
Generate Thumbnails

Scans artifact directories for index.html files and uses Playwright to
capture screenshots for artifacts with missing or stale thumbnails, saving an
optimized thumbnail.webp in the artifact folder.

Usage:
    python scripts/generate_thumbnails.py
"""

from __future__ import annotations

import logging
import sys
from io import BytesIO
from pathlib import Path
from typing import TypedDict

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
NAVIGATION_TIMEOUT_MS = 30000
POST_LOAD_DELAY_MS = 1000


class ThumbnailStats(TypedDict):
    total: int
    attempted: int
    generated: int
    skipped: int
    failed: int


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


def should_generate_thumbnail(artifact_dir: Path) -> bool:
    """Return True when a thumbnail is missing or stale for one artifact."""
    html_path = artifact_dir / "index.html"
    thumb_path = artifact_dir / SCREENSHOT_FILE
    legacy_thumb_path = artifact_dir / LEGACY_SCREENSHOT_FILE

    if not thumb_path.exists():
        return True
    if legacy_thumb_path.exists():
        return True
    return html_path.stat().st_mtime > thumb_path.stat().st_mtime


def _summarize(stats: ThumbnailStats) -> str:
    """Build a human-readable thumbnail generation summary."""
    return (
        "thumbnail summary: "
        f"total={stats['total']}, attempted={stats['attempted']}, "
        f"generated={stats['generated']}, skipped={stats['skipped']}, "
        f"failed={stats['failed']}"
    )


def generate_thumbnails() -> ThumbnailStats:
    """Generate thumbnail screenshots for all artifacts."""
    artifacts = find_artifacts()
    stats: ThumbnailStats = {
        "total": len(artifacts),
        "attempted": 0,
        "generated": 0,
        "skipped": 0,
        "failed": 0,
    }
    if not artifacts:
        logger.info("No artifacts found")
        return stats

    logger.info("Found %d artifact(s) to screenshot", len(artifacts))

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.error(
            "Playwright is not installed. Run `make setup` to install pinned "
            "dependencies and Chromium."
        )
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

            if not should_generate_thumbnail(artifact_dir):
                stats["skipped"] += 1
                logger.info("Skipping %s (thumbnail is up to date)", artifact_dir.name)
                continue

            logger.info("Screenshotting %s", artifact_dir.name)
            stats["attempted"] += 1
            try:
                page.goto(
                    file_url, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT_MS
                )
                page.wait_for_timeout(POST_LOAD_DELAY_MS)
                screenshot_bytes = page.screenshot(type="png")
                save_thumbnail(screenshot_bytes, thumb_path)
                if legacy_thumb_path.exists():
                    legacy_thumb_path.unlink()
                stats["generated"] += 1
                logger.info("  -> %s", thumb_path.name)
            except Exception as e:
                stats["failed"] += 1
                logger.warning("Failed to screenshot %s: %s", artifact_dir.name, e)

        browser.close()

    logger.info("Done generating thumbnails")
    logger.info(_summarize(stats))

    if stats["attempted"] > 0 and stats["failed"] == stats["attempted"]:
        raise RuntimeError("Thumbnail generation failed for every attempted artifact")

    return stats


if __name__ == "__main__":  # pragma: no cover
    try:
        generate_thumbnails()
    except RuntimeError as exc:
        logger.error("Thumbnail generation failed: %s", exc)
        sys.exit(1)
