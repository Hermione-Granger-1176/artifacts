from __future__ import annotations

import json
import os
import shutil
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright

import scripts.prepare_site as prepare_site

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRE_BROWSER_TESTS = os.environ.get("ARTIFACTS_REQUIRE_BROWSER_TESTS") == "1"


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, dirs_exist_ok=True)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build_smoke_site(
    tmp_path: Path,
    monkeypatch,
    *,
    site_path: str = "/",
    artifact_count: int = 13,
    config_override=None,
    artifacts_override=None,
) -> Path:
    source_root = tmp_path / "source"
    deploy_root = tmp_path / "_site"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "apps").mkdir(parents=True, exist_ok=True)

    shutil.copy2(REPO_ROOT / "index.html", source_root / "index.html")
    shutil.copy2(REPO_ROOT / "404.html", source_root / "404.html")
    copy_tree(REPO_ROOT / "assets", source_root / "assets")
    copy_tree(REPO_ROOT / "css", source_root / "css")
    copy_tree(REPO_ROOT / "js", source_root / "js")

    config = {
        "toolDisplayOrder": ["claude", "chatgpt", "gemini"],
        "tagDisplayOrder": ["finance", "calculator", "visualization"],
        "tools": {
            "claude": {"label": "Claude"},
            "chatgpt": {"label": "ChatGPT"},
            "gemini": {"label": "Gemini"},
        },
        "tags": {
            "finance": {"label": "Finance"},
            "calculator": {"label": "Calculator"},
            "visualization": {"label": "Visualization"},
        },
    }
    artifacts = [
        {
            "id": f"artifact-{index:02d}",
            "name": f"Artifact {index:02d}",
            "description": f"Interactive artifact {index:02d}.",
            "tags": ["finance"] if index % 2 == 0 else ["calculator"],
            "tools": ["claude"] if index % 2 == 0 else ["chatgpt"],
            "url": f"apps/artifact-{index:02d}/",
            "thumbnail": None,
        }
        for index in range(1, artifact_count + 1)
    ]

    if config_override is not None:
        config = config_override
    if artifacts_override is not None:
        artifacts = artifacts_override

    write_text(
        source_root / "js" / "gallery-config.js",
        f"window.ARTIFACTS_CONFIG = {json.dumps(config, indent=2)};\n",
    )
    write_text(
        source_root / "js" / "data.js",
        f"window.ARTIFACTS_DATA = {json.dumps(artifacts, indent=2)};\n",
    )
    if isinstance(artifacts, list):
        for artifact in artifacts:
            write_text(
                source_root / artifact["url"] / "index.html",
                f"<html><body><h1>{artifact['name']}</h1></body></html>\n",
            )

    write_text(
        source_root / "pyproject.toml", f'[tool.artifacts]\nsite_path = "{site_path}"\n'
    )

    monkeypatch.setattr(prepare_site, "REPO_ROOT", source_root)
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", source_root / "pyproject.toml")
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_root)
    monkeypatch.setenv("ARTIFACTS_DEPLOY_VERSION", "smoketest")

    prepare_site.prepare_site()

    return deploy_root


class StaticServer:
    def __init__(self, directory: Path) -> None:
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        self._httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self.url = f"http://127.0.0.1:{self._httpd.server_address[1]}"

    def __enter__(self) -> StaticServer:
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=5)


def launch_browser(playwright):
    try:
        return playwright.chromium.launch()
    except Exception as exc:  # pragma: no cover - environment specific
        if "Executable doesn't exist" not in str(exc):
            raise

        if REQUIRE_BROWSER_TESTS:
            pytest.fail("Playwright Chromium is required for this test run")

        pytest.skip("Playwright Chromium is not installed")


def test_gallery_smoke_covers_root_interactions(tmp_path: Path, monkeypatch) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        page.goto(f"{server.url}/", wait_until="networkidle")

        expect(page.locator(".artifact-card")).to_have_count(12)
        expect(page.locator("#pagination .page-btn")).to_have_count(6)
        expect(page.locator("html")).to_have_attribute("data-runtime-status", "ready")

        page.get_by_role("button", name="Page 2").click()
        expect(page.locator(".artifact-card")).to_have_count(1)

        page.fill("#search-input", "Artifact 13")
        page.wait_for_timeout(250)
        expect(page.locator(".artifact-card")).to_have_count(1)

        page.click("#tool-filter-toggle")
        page.locator('#tool-filter-panel input[value="chatgpt"]').check()
        expect(page.locator(".artifact-card")).to_have_count(1)

        page.locator(".artifact-card").first.click()
        expect(page.locator("#detail-overlay")).to_have_class(
            "detail-overlay visible open"
        )
        expect(page.locator("#detail-title")).to_have_text("Artifact 13")

        page.locator("button.detail-close").click()
        page.wait_for_timeout(450)
        expect(page.locator("#detail-overlay")).not_to_have_class(
            "detail-overlay visible open"
        )
        browser.close()


def test_404_links_handle_root_and_preview_paths(tmp_path: Path, monkeypatch) -> None:
    deploy_root = build_smoke_site(tmp_path, monkeypatch)
    preview_page = deploy_root / "pr-preview" / "pr-42" / "missing" / "index.html"
    preview_page.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(deploy_root / "404.html", preview_page)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()

        page.goto(f"{server.url}/404.html", wait_until="networkidle")
        expect(page.locator("#home-link")).to_have_attribute("href", "/")

        page.goto(f"{server.url}/pr-preview/pr-42/missing/", wait_until="networkidle")
        expect(page.locator("#home-link")).to_have_attribute(
            "href", "/pr-preview/pr-42/"
        )
        browser.close()


def test_gallery_shows_runtime_error_for_invalid_bootstrap_data(
    tmp_path: Path, monkeypatch
) -> None:
    deploy_root = build_smoke_site(
        tmp_path,
        monkeypatch,
        artifacts_override={"invalid": True},
    )

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        browser = launch_browser(playwright)
        page = browser.new_page()
        page.goto(f"{server.url}/", wait_until="networkidle")

        expect(page.locator("html")).to_have_attribute("data-runtime-status", "error")
        expect(page.locator("#runtime-error")).not_to_have_class("runtime-error hidden")
        expect(page.locator(".artifact-card")).to_have_count(0)
        browser.close()
