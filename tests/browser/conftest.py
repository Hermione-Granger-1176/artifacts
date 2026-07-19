from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import sync_playwright

from tests.browser.frontend_helpers import StaticServer, build_real_site, launch_browser


@dataclass
class AppBrowserHarness:
    """One shared built site, static server, and browser for an app-test shard."""

    deploy_root: Path
    server_url: str
    playwright: Any
    browser: Any


@pytest.fixture(scope="session")
def app_browser(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[AppBrowserHarness, None, None]:
    """Build and serve the mature-app site once for the current shard process."""
    build_root = tmp_path_factory.mktemp("app-shard-site")
    with pytest.MonkeyPatch.context() as patch:
        deploy_root = build_real_site(build_root, patch)

    with StaticServer(deploy_root) as server, sync_playwright() as playwright:
        browser = launch_browser(playwright)
        try:
            yield AppBrowserHarness(
                deploy_root=deploy_root,
                server_url=server.url,
                playwright=playwright,
                browser=browser,
            )
        finally:
            browser.close()
