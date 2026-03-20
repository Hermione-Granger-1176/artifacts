#!/usr/bin/env python3
"""
Generate Thumbnails

Scans artifact directories for index.html files and uses Playwright to
capture screenshots for artifacts with missing or stale thumbnails, saving an
optimized thumbnail.webp in the artifact folder.

Artifacts are processed concurrently using async Playwright with a bounded
semaphore to limit parallel browser pages.

Usage:
    python scripts/generate_thumbnails.py
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

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
SCREENSHOT_RETRY_ATTEMPTS = 3
SCREENSHOT_RETRY_BACKOFF_BASE_SECONDS = 0.5
SCREENSHOT_RETRY_BACKOFF_MAX_SECONDS = 2.0
MAX_CONCURRENT_PAGES = 4
STRICT_THUMBNAILS_ENV_VAR = "ARTIFACTS_STRICT_THUMBNAILS"
ThumbnailStatus = Literal["generated", "skipped", "failed"]


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


def _retry_delay_seconds(attempt: int) -> float:
    """Return a bounded exponential backoff for retry attempt numbers."""

    return min(
        SCREENSHOT_RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempt - 1)),
        SCREENSHOT_RETRY_BACKOFF_MAX_SECONDS,
    )


def strict_thumbnail_failures_enabled() -> bool:
    """Return True when any attempted thumbnail failure should fail the run."""

    return os.environ.get(STRICT_THUMBNAILS_ENV_VAR) == "1"


async def _capture_screenshot(page: Any, file_url: str, artifact_name: str) -> bytes:
    """Capture one artifact screenshot with bounded retries for transient failures."""

    last_error: Exception | None = None

    for attempt in range(1, SCREENSHOT_RETRY_ATTEMPTS + 1):
        try:
            await page.goto(
                file_url, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT_MS
            )
            await page.wait_for_timeout(POST_LOAD_DELAY_MS)
            return await page.screenshot(type="png")
        except Exception as exc:
            last_error = exc
            if attempt >= SCREENSHOT_RETRY_ATTEMPTS:
                break
            delay_seconds = _retry_delay_seconds(attempt)
            logger.warning(
                "Retrying %s after screenshot attempt %d/%d failed: %s",
                artifact_name,
                attempt,
                SCREENSHOT_RETRY_ATTEMPTS,
                exc,
            )
            await asyncio.sleep(delay_seconds)

    assert last_error is not None
    raise last_error


async def _process_artifact(
    browser: Any,
    artifact_dir: Path,
    semaphore: asyncio.Semaphore,
) -> str:
    """Process one artifact and return its status string."""
    if not should_generate_thumbnail(artifact_dir):
        logger.info("Skipping %s (thumbnail is up to date)", artifact_dir.name)
        return "skipped"

    logger.info("Screenshotting %s", artifact_dir.name)
    page = None
    async with semaphore:
        try:
            page = await browser.new_page(
                viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
                device_scale_factor=2,
            )
            html_path = artifact_dir / "index.html"
            thumb_path = artifact_dir / SCREENSHOT_FILE
            legacy_thumb_path = artifact_dir / LEGACY_SCREENSHOT_FILE
            file_url = html_path.resolve().as_uri()

            screenshot_bytes = await _capture_screenshot(
                page, file_url, artifact_dir.name
            )
            save_thumbnail(screenshot_bytes, thumb_path)
            if legacy_thumb_path.exists():
                legacy_thumb_path.unlink()
            logger.info("  -> %s", thumb_path.name)
            return "generated"
        except Exception as exc:
            logger.warning("Failed to screenshot %s: %s", artifact_dir.name, exc)
            return "failed"
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass


async def _run_generation(
    artifacts: list[Path], async_playwright_cm: Any
) -> ThumbnailStats:
    """Run concurrent thumbnail generation and return aggregated stats."""
    stats: ThumbnailStats = {
        "total": len(artifacts),
        "attempted": 0,
        "generated": 0,
        "skipped": 0,
        "failed": 0,
    }

    async with async_playwright_cm() as p:
        browser = await p.chromium.launch()
        try:
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_PAGES)

            results = await asyncio.gather(
                *[_process_artifact(browser, d, semaphore) for d in artifacts],
                return_exceptions=True,
            )

            for result in results:
                status: ThumbnailStatus = (
                    "failed"
                    if isinstance(result, Exception)
                    else cast(ThumbnailStatus, result)
                )
                stats[status] += 1
                if status != "skipped":
                    stats["attempted"] += 1
        finally:
            await browser.close()

    logger.info("Done generating thumbnails")
    logger.info(_summarize(stats))

    if stats["attempted"] > 0 and stats["failed"] == stats["attempted"]:
        raise RuntimeError("Thumbnail generation failed for every attempted artifact")

    if stats["failed"] > 0 and strict_thumbnail_failures_enabled():
        raise RuntimeError(
            "Thumbnail generation failed for one or more attempted artifacts"
        )

    return stats


def generate_thumbnails() -> ThumbnailStats:
    """Generate thumbnail screenshots for all artifacts."""
    artifacts = find_artifacts()
    if not artifacts:
        logger.info("No artifacts found")
        return {
            "total": 0,
            "attempted": 0,
            "generated": 0,
            "skipped": 0,
            "failed": 0,
        }

    logger.info("Found %d artifact(s) to screenshot", len(artifacts))

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "Playwright is not installed. Run `make setup` to install pinned "
            "dependencies and Chromium."
        )
        sys.exit(1)

    return asyncio.run(_run_generation(artifacts, async_playwright))


if __name__ == "__main__":  # pragma: no cover
    try:
        generate_thumbnails()
    except RuntimeError as exc:
        logger.error("Thumbnail generation failed: %s", exc)
        sys.exit(1)
