from __future__ import annotations

import json
import os
import re
import shutil
import threading
from dataclasses import dataclass, field
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import urljoin, urlsplit

import pytest

import scripts.prepare_site as prepare_site

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRE_BROWSER_TESTS = os.environ.get("ARTIFACTS_REQUIRE_BROWSER_TESTS") == "1"
AXE_SOURCE_FILE = REPO_ROOT / "node_modules" / "axe-core" / "axe.min.js"
ROOT_A11Y_STYLE_CONTENT = "\n".join(
    [
        (REPO_ROOT / "css" / "root-gallery-foundation.css").read_text(encoding="utf-8"),
        (REPO_ROOT / "css" / "root-gallery-artifacts.css").read_text(encoding="utf-8"),
        (REPO_ROOT / "css" / "root-gallery-responsive.css").read_text(encoding="utf-8"),
    ]
)
ARTIFACT_DIR_ENV = "ARTIFACTS_BROWSER_ARTIFACT_DIR"
IGNORED_EXTERNAL_HOSTS = {"fonts.googleapis.com", "fonts.gstatic.com"}


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

    normalized_site_path = site_path.strip("/")
    site_url = (
        f"https://example.com/{normalized_site_path}/"
        if normalized_site_path
        else "https://example.com/"
    )

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
        source_root / "pyproject.toml",
        "".join(
            [
                "[tool.artifacts]\n",
                f'site_path = "{site_path}"\n',
                f'site_url = "{site_url}"\n',
            ]
        ),
    )

    monkeypatch.setattr(prepare_site, "REPO_ROOT", source_root)
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", source_root / "pyproject.toml")
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_root)
    monkeypatch.setenv(prepare_site.DEPLOY_VERSION_ENV_VAR, "smoketest")
    monkeypatch.setenv(prepare_site.DEPLOY_COMMIT_SHA_ENV_VAR, "smoketest" * 5)

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


def _normalize_url_host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def _sanitize_artifact_name(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-") or "browser-test"


def _artifact_dir(name: str) -> Path | None:
    root = os.environ.get(ARTIFACT_DIR_ENV)
    if not root:
        return None
    path = Path(root) / _sanitize_artifact_name(name)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _matches_allowed(message: str, allowed_patterns: tuple[str, ...]) -> bool:
    return any(pattern in message for pattern in allowed_patterns)


@dataclass
class RuntimeMonitor:
    base_url: str
    allowed_console_errors: tuple[str, ...] = ()
    allowed_page_errors: tuple[str, ...] = ()
    console_errors: list[str] = field(default_factory=list)
    page_errors: list[str] = field(default_factory=list)
    request_failures: list[str] = field(default_factory=list)
    response_errors: list[str] = field(default_factory=list)

    def bind(self, page) -> None:
        base_host = _normalize_url_host(self.base_url)

        def track_console(message) -> None:
            if message.type != "error":
                return

            location = message.location or {}
            location_url = location.get("url", "")
            if self._should_ignore_url(location_url, base_host) and any(
                host in message.text for host in IGNORED_EXTERNAL_HOSTS
            ):
                return

            if _matches_allowed(message.text, self.allowed_console_errors):
                return

            self.console_errors.append(message.text)

        def track_page_error(error) -> None:
            message = str(error)
            if _matches_allowed(message, self.allowed_page_errors):
                return
            self.page_errors.append(message)

        def track_request_failure(request) -> None:
            if self._should_ignore_url(request.url, base_host):
                return
            failure = request.failure or "unknown failure"
            self.request_failures.append(f"{request.method} {request.url} -> {failure}")

        def track_response(response) -> None:
            if response.status < 400 or self._should_ignore_url(
                response.url, base_host
            ):
                return
            self.response_errors.append(
                f"{response.request.method} {response.url} -> HTTP {response.status}"
            )

        page.on("console", track_console)
        page.on("pageerror", track_page_error)
        page.on("requestfailed", track_request_failure)
        page.on("response", track_response)

    def _should_ignore_url(self, url: str, base_host: str) -> bool:
        if not url:
            return False
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            return True
        if parts.netloc.lower() == base_host:
            return False
        return parts.netloc.lower() in IGNORED_EXTERNAL_HOSTS

    def has_failures(self) -> bool:
        return bool(
            self.console_errors
            or self.page_errors
            or self.request_failures
            or self.response_errors
        )

    def failure_summary(self) -> str:
        sections = []
        if self.page_errors:
            sections.append("Page errors:\n- " + "\n- ".join(self.page_errors))
        if self.console_errors:
            sections.append("Console errors:\n- " + "\n- ".join(self.console_errors))
        if self.request_failures:
            sections.append(
                "Request failures:\n- " + "\n- ".join(self.request_failures)
            )
        if self.response_errors:
            sections.append("HTTP errors:\n- " + "\n- ".join(self.response_errors))
        return "\n\n".join(sections)

    def assert_clean(self) -> None:
        if self.has_failures():
            raise AssertionError(self.failure_summary())


class MonitoredPage:
    def __init__(
        self,
        playwright,
        base_url: str,
        *,
        name: str,
        viewport: tuple[int, int] = (1100, 1100),
        color_scheme: str = "light",
        reduced_motion: str = "no-preference",
        allowed_console_errors: tuple[str, ...] = (),
        allowed_page_errors: tuple[str, ...] = (),
    ) -> None:
        self._playwright = playwright
        self._base_url = base_url.rstrip("/") + "/"
        self._name = name
        self._viewport = {"width": viewport[0], "height": viewport[1]}
        self._color_scheme = color_scheme
        self._reduced_motion = reduced_motion
        self._artifact_dir = _artifact_dir(name)
        self._browser = None
        self._context = None
        self._trace_started = False
        self.monitor = RuntimeMonitor(
            self._base_url,
            allowed_console_errors=allowed_console_errors,
            allowed_page_errors=allowed_page_errors,
        )
        self.page = None

    def __enter__(self) -> MonitoredPage:
        self._browser = launch_browser(self._playwright)
        self._context = self._browser.new_context(
            viewport=self._viewport,
            color_scheme=self._color_scheme,
            reduced_motion=self._reduced_motion,
        )
        if self._artifact_dir is not None:
            self._context.tracing.start(screenshots=True, snapshots=True, sources=True)
            self._trace_started = True
        self.page = self._context.new_page()
        self.monitor.bind(self.page)
        return self

    def goto(self, path: str = "/", *, wait_until: str = "networkidle") -> None:
        if self.page is None:
            raise RuntimeError("Browser page is not initialized")
        if path.startswith("http://") or path.startswith("https://"):
            target = path
        else:
            target = urljoin(self._base_url, path.lstrip("/"))
        self.page.goto(target, wait_until=wait_until)

    def assert_runtime_clean(self) -> None:
        self.monitor.assert_clean()

    def __exit__(self, exc_type, exc, tb) -> bool:
        monitor_error: AssertionError | None = None
        try:
            if exc_type is None:
                try:
                    self.monitor.assert_clean()
                except AssertionError as caught:
                    monitor_error = caught
            should_capture = exc_type is not None or self.monitor.has_failures()
            if (
                self._artifact_dir is not None
                and self.page is not None
                and should_capture
            ):
                self._write_artifacts()
            if self._context is not None and self._trace_started:
                if self._artifact_dir is not None and should_capture:
                    self._context.tracing.stop(
                        path=str(self._artifact_dir / "trace.zip")
                    )
                else:
                    self._context.tracing.stop()
        finally:
            if self._context is not None:
                self._context.close()
            if self._browser is not None:
                self._browser.close()

        if monitor_error is not None:
            raise monitor_error
        return False

    def _write_artifacts(self) -> None:
        if self._artifact_dir is None or self.page is None:
            return

        if not self.page.is_closed():
            self.page.screenshot(
                path=str(self._artifact_dir / "failure.png"), full_page=True
            )

        (self._artifact_dir / "runtime-failures.txt").write_text(
            self.monitor.failure_summary() or "No runtime failures recorded.\n",
            encoding="utf-8",
        )
        (self._artifact_dir / "page-errors.txt").write_text(
            "\n".join(self.monitor.page_errors)
            + ("\n" if self.monitor.page_errors else ""),
            encoding="utf-8",
        )
        (self._artifact_dir / "console-errors.txt").write_text(
            "\n".join(self.monitor.console_errors)
            + ("\n" if self.monitor.console_errors else ""),
            encoding="utf-8",
        )
        (self._artifact_dir / "request-failures.txt").write_text(
            "\n".join(self.monitor.request_failures)
            + ("\n" if self.monitor.request_failures else ""),
            encoding="utf-8",
        )
        (self._artifact_dir / "response-errors.txt").write_text(
            "\n".join(self.monitor.response_errors)
            + ("\n" if self.monitor.response_errors else ""),
            encoding="utf-8",
        )


def ensure_axe_loaded(page) -> None:
    if page.evaluate("Boolean(window.axe)"):
        return
    if not AXE_SOURCE_FILE.exists():
        raise FileNotFoundError(f"axe-core bundle not found: {AXE_SOURCE_FILE}")
    page.add_script_tag(path=str(AXE_SOURCE_FILE))


def ensure_axe_styles(page) -> None:
    needs_root_styles = page.evaluate(
        "Boolean(document.querySelector('link[href^=\"css/style.css\"]') || document.getElementById('artifacts-grid'))"
    )
    if not needs_root_styles:
        return

    already_injected = page.evaluate(
        "Boolean(document.getElementById('axe-inline-styles'))"
    )
    if already_injected:
        return

    page.evaluate(
        """(cssContent) => {
            const rootStylesheet = document.querySelector('link[href^="css/style.css"]');
            if (rootStylesheet) {
                rootStylesheet.disabled = true;
            }
            const style = document.createElement('style');
            style.id = 'axe-inline-styles';
            style.textContent = cssContent;
            document.head.appendChild(style);
        }""",
        ROOT_A11Y_STYLE_CONTENT,
    )


def run_axe(
    page,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    run_only: list[str] | None = None,
):
    ensure_axe_loaded(page)
    ensure_axe_styles(page)
    context: dict[str, list[list[str]]] | None = None
    if include or exclude:
        context = {}
        if include:
            context["include"] = [[selector] for selector in include]
        if exclude:
            context["exclude"] = [[selector] for selector in exclude]
    options: dict[str, object] = {}
    if run_only:
        options["runOnly"] = {"type": "rule", "values": run_only}

    return page.evaluate(
        """async ({ context, options }) => {
            const axeContext = context && context.include ? context : document;
            return await window.axe.run(axeContext, options);
        }""",
        {"context": context, "options": options},
    )


def assert_no_blocking_axe_violations(
    results, *, impacts: tuple[str, ...] = ("serious", "critical")
) -> None:
    violations = [
        violation
        for violation in results["violations"]
        if violation.get("impact") in impacts
    ]
    if not violations:
        return

    lines = []
    for violation in violations:
        lines.append(
            f"{violation['id']} ({violation.get('impact', 'unknown')}): {violation['help']}"
        )
        for node in violation.get("nodes", [])[:5]:
            targets = ", ".join(" > ".join(target) for target in node.get("target", []))
            lines.append(f"  - {targets or 'unknown target'}")
    raise AssertionError("Blocking axe violations found:\n" + "\n".join(lines))


def contrast_ratio(
    page, selector: str, *, background_selector: str | None = None
) -> dict[str, object]:
    return page.evaluate(
        r"""({ selector, backgroundSelector }) => {
            function parseColor(value) {
                if (!value || value === 'transparent') {
                    return [0, 0, 0, 0];
                }
                const parts = value.match(/[\d.]+/g);
                if (!parts || (parts.length !== 3 && parts.length !== 4)) {
                    throw new Error(`Unsupported color format: ${value}`);
                }
                return [
                    Number(parts[0]),
                    Number(parts[1]),
                    Number(parts[2]),
                    parts.length === 4 ? Number(parts[3]) : 1,
                ];
            }

            function blend(top, bottom) {
                const alpha = top[3] + bottom[3] * (1 - top[3]);
                if (alpha === 0) {
                    return [0, 0, 0, 0];
                }
                return [
                    (top[0] * top[3] + bottom[0] * bottom[3] * (1 - top[3])) / alpha,
                    (top[1] * top[3] + bottom[1] * bottom[3] * (1 - top[3])) / alpha,
                    (top[2] * top[3] + bottom[2] * bottom[3] * (1 - top[3])) / alpha,
                    alpha,
                ];
            }

            function relativeLuminance(color) {
                const channels = color.slice(0, 3).map((value) => {
                    const channel = value / 255;
                    return channel <= 0.03928
                        ? channel / 12.92
                        : ((channel + 0.055) / 1.055) ** 2.4;
                });
                return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
            }

            function resolveBackground(node) {
                const ancestry = [];
                for (let current = node; current; current = current.parentElement) {
                    ancestry.unshift(current);
                }

                let background = [255, 255, 255, 1];
                for (const current of ancestry) {
                    const bg = parseColor(getComputedStyle(current).backgroundColor);
                    if (bg[3] > 0) {
                        background = blend(bg, background);
                    }
                }
                return background;
            }

            const foregroundNode = document.querySelector(selector);
            if (!foregroundNode) {
                throw new Error(`Missing foreground element: ${selector}`);
            }

            const backgroundNode = backgroundSelector
                ? document.querySelector(backgroundSelector)
                : foregroundNode;
            if (!backgroundNode) {
                throw new Error(`Missing background element: ${backgroundSelector}`);
            }

            const foreground = parseColor(getComputedStyle(foregroundNode).color);
            const background = resolveBackground(backgroundNode);
            const compositedForeground = blend(foreground, background);
            const foregroundLum = relativeLuminance(compositedForeground);
            const backgroundLum = relativeLuminance(background);
            const lighter = Math.max(foregroundLum, backgroundLum);
            const darker = Math.min(foregroundLum, backgroundLum);

            return {
                ratio: (lighter + 0.05) / (darker + 0.05),
                foreground: compositedForeground,
                background,
            };
        }""",
        {"selector": selector, "backgroundSelector": background_selector},
    )


def assert_minimum_contrast(
    page,
    selector: str,
    *,
    minimum_ratio: float = 4.5,
    background_selector: str | None = None,
) -> None:
    result = cast(
        dict[str, Any],
        contrast_ratio(page, selector, background_selector=background_selector),
    )
    ratio_value = result.get("ratio")
    if not isinstance(ratio_value, (int, float)):
        raise AssertionError(
            f"Contrast ratio for {selector} was not numeric: {ratio_value!r}"
        )
    ratio = float(ratio_value)
    if ratio >= minimum_ratio:
        return

    raise AssertionError(
        f"Contrast ratio for {selector} was {ratio:.2f}, expected at least {minimum_ratio:.2f}. "
        f"Foreground={result['foreground']} Background={result['background']}"
    )
