#!/usr/bin/env python3
"""Generate artifact thumbnails with Playwright and Pillow.

This module backs `make thumbnails`.

It scans artifact directories for `index.html` files and uses Playwright to
capture screenshots for artifacts with missing or stale thumbnails, saving an
optimized `thumbnail.webp` in each artifact folder.

Artifacts are processed concurrently using async Playwright with a bounded
semaphore to limit parallel browser pages.

Run through the Makefile in normal workflows; direct invocation is mainly for
maintainers working on the build internals.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

from PIL import Image

from scripts import REPO_ROOT
from scripts.lib.app_discovery import (
    APP_RUNTIME_TOP_LEVELS,
    _artifact_base_path,
    artifact_uses_shared_app_runtime,
    shared_app_runtime_paths,
    thumbnail_file,
)

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
APPS_DIR = REPO_ROOT / _artifact_base_path()
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 800
SCREENSHOT_FILE = thumbnail_file()
SHARED_APP_RUNTIME_FILES = shared_app_runtime_paths(REPO_ROOT)
THUMBNAIL_WIDTH = 960
THUMBNAIL_QUALITY = 85
NAVIGATION_TIMEOUT_MS = 30000
POST_LOAD_DELAY_MS = 1000
READY_SIGNAL_TIMEOUT_MS = 12000
SCREENSHOT_RETRY_ATTEMPTS = 3
SCREENSHOT_RETRY_BACKOFF_BASE_SECONDS = 0.5
SCREENSHOT_RETRY_BACKOFF_MAX_SECONDS = 2.0
MAX_CONCURRENT_PAGES = 4
STRICT_THUMBNAILS_ENV_VAR = "ARTIFACTS_STRICT_THUMBNAILS"
THUMBNAIL_SLUGS_ENV_VAR = "ARTIFACTS_THUMBNAIL_SLUGS"
THUMBNAIL_MANIFEST_ENV_VAR = "ARTIFACTS_THUMBNAIL_MANIFEST"
ThumbnailStatus = Literal["generated", "skipped", "failed"]
ARTIFACT_BASE_URL = ""


class ThumbnailStats(TypedDict):
    total: int
    attempted: int
    generated: int
    skipped: int
    failed: int


class QuietStaticHandler(SimpleHTTPRequestHandler):
    """Static file handler that suppresses per-request logging."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


class ArtifactServer:
    """Serve the repository root over HTTP for realistic thumbnail captures."""

    def __init__(self, directory: Path) -> None:
        handler = partial(QuietStaticHandler, directory=str(directory))
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def __enter__(self) -> ArtifactServer:
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def find_artifacts() -> list[Path]:
    """Find all artifact directories containing an index.html."""
    logger.debug("Scanning %s for artifacts", APPS_DIR)
    if not APPS_DIR.exists():
        return []
    artifacts = [
        item
        for item in sorted(APPS_DIR.iterdir())
        if item.is_dir()
        and not item.name.startswith(".")
        and (item / "index.html").exists()
    ]

    configured_slugs = [
        slug.strip()
        for slug in os.environ.get(THUMBNAIL_SLUGS_ENV_VAR, "").split(",")
        if slug.strip()
    ]
    if not configured_slugs:
        return artifacts

    requested = set(configured_slugs)
    return [artifact for artifact in artifacts if artifact.name in requested]


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


def artifact_url(artifact_dir: Path) -> str:
    """Return the best URL for one artifact page during thumbnail capture."""
    if ARTIFACT_BASE_URL:
        return f"{ARTIFACT_BASE_URL}/apps/{artifact_dir.name}/"
    return (artifact_dir / "index.html").resolve().as_uri()


def should_generate_thumbnail(artifact_dir: Path) -> bool:
    """Return True when a thumbnail is missing or stale for one artifact."""
    logger.debug("Checking staleness for %s", artifact_dir.name)
    thumb_path = artifact_dir / SCREENSHOT_FILE

    if not thumb_path.exists():
        return True

    thumbnail_mtime = thumb_path.stat().st_mtime
    return any(
        runtime_path.stat().st_mtime > thumbnail_mtime
        for runtime_path in artifact_runtime_paths(artifact_dir)
    )


def artifact_runtime_paths(artifact_dir: Path) -> list[Path]:
    """Return runtime paths that should invalidate one artifact thumbnail."""
    runtime_paths = [artifact_dir / "index.html"]

    for dirname in APP_RUNTIME_TOP_LEVELS:
        directory = artifact_dir / dirname
        if not directory.exists():
            continue
        runtime_paths.extend(path for path in directory.rglob("*") if path.is_file())

    if artifact_uses_shared_app_runtime(artifact_dir):
        runtime_paths.extend(path for path in SHARED_APP_RUNTIME_FILES if path.exists())

    return runtime_paths


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


def _strict_thumbnail_failures_enabled() -> bool:
    """Return True when any attempted thumbnail failure should fail the run."""

    return os.environ.get(STRICT_THUMBNAILS_ENV_VAR) == "1"


def _write_manifest(artifacts: list[Path], stats: ThumbnailStats) -> None:
    """Write a machine-readable manifest when requested by the environment."""
    manifest_path = os.environ.get(THUMBNAIL_MANIFEST_ENV_VAR, "").strip()
    if not manifest_path:
        return

    destination = Path(manifest_path).resolve()
    if not destination.is_relative_to(REPO_ROOT.resolve()):
        raise ValueError(f"Manifest path escapes repository root: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "artifacts": [artifact.name for artifact in artifacts],
        "stats": stats,
    }
    destination.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


async def _capture_screenshot(page: Any, file_url: str, artifact_name: str) -> bytes:
    """Capture one artifact screenshot with bounded retries for transient failures."""

    last_error: Exception | None = None

    for attempt in range(1, SCREENSHOT_RETRY_ATTEMPTS + 1):
        try:
            await page.goto(
                file_url, wait_until="networkidle", timeout=NAVIGATION_TIMEOUT_MS
            )
            await page.wait_for_function(
                "window.__ARTIFACT_READY__ !== false",
                timeout=READY_SIGNAL_TIMEOUT_MS,
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
) -> ThumbnailStatus:
    """Process one artifact and return its thumbnail generation status."""
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
            thumb_path = artifact_dir / SCREENSHOT_FILE
            file_url = artifact_url(artifact_dir)

            screenshot_bytes = await _capture_screenshot(
                page, file_url, artifact_dir.name
            )
            save_thumbnail(screenshot_bytes, thumb_path)
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

    if stats["failed"] > 0 and _strict_thumbnail_failures_enabled():
        raise RuntimeError(
            "Thumbnail generation failed for one or more attempted artifacts"
        )

    return stats


def generate_thumbnails() -> ThumbnailStats:
    """Generate thumbnail screenshots for all artifacts."""
    artifacts = find_artifacts()
    if not artifacts:
        logger.info("No artifacts found")
        stats: ThumbnailStats = {
            "total": 0,
            "attempted": 0,
            "generated": 0,
            "skipped": 0,
            "failed": 0,
        }
        _write_manifest([], stats)
        return stats

    logger.info("Found %d artifact(s) to screenshot", len(artifacts))

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error(
            "Playwright is not installed. Run `make setup-all` to install pinned "
            "dependencies and Chromium."
        )
        sys.exit(1)

    with ArtifactServer(REPO_ROOT) as server:
        global ARTIFACT_BASE_URL  # noqa: PLW0603
        ARTIFACT_BASE_URL = server.url.rstrip("/")
        try:
            stats = asyncio.run(_run_generation(artifacts, async_playwright))
        finally:
            ARTIFACT_BASE_URL = ""
    _write_manifest(artifacts, stats)
    return stats


if __name__ == "__main__":  # pragma: no cover
    try:
        generate_thumbnails()
    except RuntimeError as exc:
        logger.error("Thumbnail generation failed: %s", exc)
        sys.exit(1)
