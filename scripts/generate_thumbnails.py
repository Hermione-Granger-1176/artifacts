#!/usr/bin/env python3
"""
Generate Thumbnails

Scans artifact directories for index.html files and uses Playwright to
capture a screenshot of each, saving as thumbnail.png in the artifact folder.

Usage:
    python scripts/generate_thumbnails.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = REPO_ROOT / "apps"
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
SCREENSHOT_FILE = "thumbnail.png"


def find_artifacts() -> list[Path]:
    """Find all artifact directories containing an index.html."""
    if not APPS_DIR.exists():
        return []
    artifacts = []
    for item in sorted(APPS_DIR.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        if (item / "index.html").exists():
            artifacts.append(item)
    return artifacts


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
            file_url = html_path.resolve().as_uri()

            logger.info("Screenshotting %s", artifact_dir.name)
            try:
                page.goto(file_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1000)
                page.screenshot(path=str(thumb_path), type="png")
                logger.info("  -> %s", thumb_path.name)
            except Exception as e:
                logger.warning("Failed to screenshot %s: %s", artifact_dir.name, e)

        browser.close()

    logger.info("Done generating thumbnails")


if __name__ == "__main__":
    generate_thumbnails()
