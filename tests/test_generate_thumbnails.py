from __future__ import annotations

import asyncio
import builtins
import os
import types
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

import scripts.generate_thumbnails as generate_thumbnails


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_find_artifacts_returns_only_visible_dirs_with_index_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()

    _write_text(apps_dir / "loan-tool" / "index.html", "<html></html>")
    _write_text(apps_dir / "budget-tool" / "index.html", "<html></html>")
    (apps_dir / ".hidden").mkdir()
    (apps_dir / "empty").mkdir()

    monkeypatch.setattr(generate_thumbnails, "APPS_DIR", apps_dir)

    artifacts = generate_thumbnails.find_artifacts()

    assert [artifact.name for artifact in artifacts] == ["budget-tool", "loan-tool"]


def test_find_artifacts_returns_empty_when_apps_dir_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(generate_thumbnails, "APPS_DIR", tmp_path / "missing-apps")

    assert generate_thumbnails.find_artifacts() == []


def test_save_thumbnail_resizes_and_writes_webp(tmp_path: Path) -> None:
    source = Image.new("RGB", (1920, 1080), color="#202020")
    buffer = BytesIO()
    source.save(buffer, format="PNG")

    thumb_path = tmp_path / "thumbnail.webp"
    generate_thumbnails.save_thumbnail(buffer.getvalue(), thumb_path)

    assert thumb_path.exists()
    with Image.open(thumb_path) as thumbnail:
        assert thumbnail.width == generate_thumbnails.THUMBNAIL_WIDTH
        assert thumbnail.height == 540


def test_should_generate_thumbnail_when_missing_or_stale(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")

    assert generate_thumbnails.should_generate_thumbnail(artifact_dir) is True

    thumb_path = artifact_dir / generate_thumbnails.SCREENSHOT_FILE
    thumb_path.write_bytes(b"thumb")

    assert generate_thumbnails.should_generate_thumbnail(artifact_dir) is False

    _write_text(artifact_dir / "index.html", "<html>updated</html>")
    future_mtime = thumb_path.stat().st_mtime + 2
    os.utime(artifact_dir / "index.html", (future_mtime, future_mtime))

    assert generate_thumbnails.should_generate_thumbnail(artifact_dir) is True


def test_should_generate_thumbnail_when_legacy_png_exists(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    (artifact_dir / generate_thumbnails.SCREENSHOT_FILE).write_bytes(b"webp")
    (artifact_dir / generate_thumbnails.LEGACY_SCREENSHOT_FILE).write_bytes(b"png")

    assert generate_thumbnails.should_generate_thumbnail(artifact_dir) is True


def test_summarize_formats_stats() -> None:
    summary = generate_thumbnails._summarize(
        {
            "total": 3,
            "attempted": 2,
            "generated": 1,
            "skipped": 1,
            "failed": 1,
        }
    )

    assert "attempted=2" in summary
    assert "failed=1" in summary


def test_retry_delay_seconds_is_bounded() -> None:
    assert generate_thumbnails._retry_delay_seconds(1) == 0.5
    assert generate_thumbnails._retry_delay_seconds(2) == 1.0
    assert generate_thumbnails._retry_delay_seconds(3) == 2.0
    assert generate_thumbnails._retry_delay_seconds(4) == 2.0


def test_generate_thumbnails_returns_early_when_no_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [])

    assert generate_thumbnails.generate_thumbnails() == {
        "total": 0,
        "attempted": 0,
        "generated": 0,
        "skipped": 0,
        "failed": 0,
    }


def test_generate_thumbnails_exits_when_playwright_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.async_api":
            raise ImportError("playwright unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(SystemExit, match="1"):
        generate_thumbnails.generate_thumbnails()


# Async fake helpers used by the browser-free thumbnail tests.


class FakePage:
    def __init__(
        self,
        fail_goto: bool = False,
        transient_failures: int = 0,
        fail_close: bool = False,
        screenshot_bytes: bytes = b"png-bytes",
    ) -> None:
        self._fail_goto = fail_goto
        self._transient_failures = transient_failures
        self._fail_close = fail_close
        self._screenshot_bytes = screenshot_bytes
        self._goto_calls = 0
        self.closed = False

    async def goto(self, url: str, wait_until: str, timeout: int) -> None:
        assert url.startswith("file://")
        assert wait_until == "networkidle"
        assert timeout == 30000
        self._goto_calls += 1
        if self._fail_goto:
            raise RuntimeError("boom")
        if self._goto_calls <= self._transient_failures:
            raise RuntimeError(f"transient-{self._goto_calls}")

    async def wait_for_timeout(self, milliseconds: int) -> None:
        assert milliseconds == generate_thumbnails.POST_LOAD_DELAY_MS

    async def screenshot(self, type: str) -> bytes:
        assert type == "png"
        return self._screenshot_bytes

    async def close(self) -> None:
        if self._fail_close:
            raise RuntimeError("close failed")
        self.closed = True


class FakeBrowser:
    def __init__(
        self,
        fail_goto: bool = False,
        transient_failures: int = 0,
        fail_new_page: bool = False,
        fail_page_close: bool = False,
        screenshot_bytes: bytes = b"png-bytes",
    ) -> None:
        self._fail_goto = fail_goto
        self._transient_failures = transient_failures
        self._fail_new_page = fail_new_page
        self._fail_page_close = fail_page_close
        self._screenshot_bytes = screenshot_bytes
        self.closed = False
        self.pages: list[FakePage] = []

    async def new_page(
        self, viewport: dict[str, int], device_scale_factor: int
    ) -> FakePage:
        if self._fail_new_page:
            raise RuntimeError("new_page failed")
        assert viewport == {
            "width": generate_thumbnails.VIEWPORT_WIDTH,
            "height": generate_thumbnails.VIEWPORT_HEIGHT,
        }
        assert device_scale_factor == 2
        page = FakePage(
            fail_goto=self._fail_goto,
            transient_failures=self._transient_failures,
            fail_close=self._fail_page_close,
            screenshot_bytes=self._screenshot_bytes,
        )
        self.pages.append(page)
        return page

    async def close(self) -> None:
        self.closed = True


class FakePlaywright:
    def __init__(
        self,
        fail_goto: bool = False,
        transient_failures: int = 0,
        fail_new_page: bool = False,
        fail_page_close: bool = False,
        screenshot_bytes: bytes = b"png-bytes",
    ) -> None:
        self.browser = FakeBrowser(
            fail_goto=fail_goto,
            transient_failures=transient_failures,
            fail_new_page=fail_new_page,
            fail_page_close=fail_page_close,
            screenshot_bytes=screenshot_bytes,
        )
        self.chromium = types.SimpleNamespace(
            launch=self.browser_launch,
        )

    async def browser_launch(self) -> FakeBrowser:
        return self.browser


class FakeAsyncPlaywright:
    def __init__(
        self,
        fail_goto: bool = False,
        transient_failures: int = 0,
        fail_new_page: bool = False,
        fail_page_close: bool = False,
        screenshot_bytes: bytes = b"png-bytes",
    ) -> None:
        self._fail_goto = fail_goto
        self._transient_failures = transient_failures
        self._fail_new_page = fail_new_page
        self._fail_page_close = fail_page_close
        self._screenshot_bytes = screenshot_bytes
        self.playwright: FakePlaywright | None = None

    async def __aenter__(self) -> FakePlaywright:
        self.playwright = FakePlaywright(
            fail_goto=self._fail_goto,
            transient_failures=self._transient_failures,
            fail_new_page=self._fail_new_page,
            fail_page_close=self._fail_page_close,
            screenshot_bytes=self._screenshot_bytes,
        )
        return self.playwright

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None


def _patch_playwright(
    monkeypatch: pytest.MonkeyPatch,
    fail_goto: bool = False,
    transient_failures: int = 0,
    fail_new_page: bool = False,
    fail_page_close: bool = False,
    screenshot_bytes: bytes = b"png-bytes",
) -> FakeAsyncPlaywright:
    """Patch the playwright import and return the fake context manager."""
    fake_cm = FakeAsyncPlaywright(
        fail_goto=fail_goto,
        transient_failures=transient_failures,
        fail_new_page=fail_new_page,
        fail_page_close=fail_page_close,
        screenshot_bytes=screenshot_bytes,
    )
    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.async_api":
            return types.SimpleNamespace(async_playwright=lambda: fake_cm)
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    return fake_cm


def _patch_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    """Patch asyncio.sleep to record calls and return immediately."""
    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr(asyncio, "sleep", fake_sleep)
    return sleep_calls


def test_generate_thumbnails_processes_artifacts_and_closes_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    (artifact_dir / generate_thumbnails.LEGACY_SCREENSHOT_FILE).write_bytes(b"legacy")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])

    save_calls: list[tuple[bytes, Path]] = []

    fake_cm = _patch_playwright(monkeypatch)
    monkeypatch.setattr(
        generate_thumbnails,
        "save_thumbnail",
        lambda image_bytes, thumb_path: save_calls.append((image_bytes, thumb_path)),
    )
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    stats = generate_thumbnails.generate_thumbnails()

    assert fake_cm.playwright is not None
    assert fake_cm.playwright.browser.closed is True
    assert all(page.closed for page in fake_cm.playwright.browser.pages)
    assert stats == {
        "total": 1,
        "attempted": 1,
        "generated": 1,
        "skipped": 0,
        "failed": 0,
    }
    assert save_calls == [
        (b"png-bytes", artifact_dir / generate_thumbnails.SCREENSHOT_FILE)
    ]
    assert not (artifact_dir / generate_thumbnails.LEGACY_SCREENSHOT_FILE).exists()


def test_generate_thumbnails_skips_up_to_date_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: False
    )

    _patch_playwright(monkeypatch)

    assert generate_thumbnails.generate_thumbnails() == {
        "total": 1,
        "attempted": 0,
        "generated": 0,
        "skipped": 1,
        "failed": 0,
    }


def test_generate_thumbnails_retries_transient_failures_then_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    save_calls: list[tuple[bytes, Path]] = []

    _patch_playwright(monkeypatch, transient_failures=2)
    sleep_calls = _patch_sleep(monkeypatch)
    monkeypatch.setattr(
        generate_thumbnails,
        "save_thumbnail",
        lambda image_bytes, thumb_path: save_calls.append((image_bytes, thumb_path)),
    )

    stats = generate_thumbnails.generate_thumbnails()

    assert sleep_calls == [0.5, 1.0]
    assert stats == {
        "total": 1,
        "attempted": 1,
        "generated": 1,
        "skipped": 0,
        "failed": 0,
    }
    assert save_calls == [
        (b"png-bytes", artifact_dir / generate_thumbnails.SCREENSHOT_FILE)
    ]


def test_generate_thumbnails_logs_warning_for_failed_screenshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    caplog.set_level("WARNING")
    fake_cm = _patch_playwright(monkeypatch, fail_goto=True)
    _patch_sleep(monkeypatch)

    with pytest.raises(RuntimeError, match="failed for every attempted artifact"):
        generate_thumbnails.generate_thumbnails()

    assert any(
        "Failed to screenshot loan-tool" in record.message for record in caplog.records
    )
    assert fake_cm.playwright is not None
    assert fake_cm.playwright.browser.closed is True
    assert all(page.closed for page in fake_cm.playwright.browser.pages)


def test_generate_thumbnails_raises_when_all_attempts_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    _patch_playwright(monkeypatch, fail_goto=True)
    _patch_sleep(monkeypatch)

    with pytest.raises(RuntimeError, match="failed for every attempted artifact"):
        generate_thumbnails.generate_thumbnails()


def test_generate_thumbnails_processes_multiple_artifacts_concurrently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dirs = []
    for name in ("alpha", "beta", "gamma"):
        d = tmp_path / name
        _write_text(d / "index.html", f"<html>{name}</html>")
        dirs.append(d)

    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: dirs)
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    save_calls: list[tuple[bytes, Path]] = []

    fake_cm = _patch_playwright(monkeypatch)
    monkeypatch.setattr(
        generate_thumbnails,
        "save_thumbnail",
        lambda image_bytes, thumb_path: save_calls.append((image_bytes, thumb_path)),
    )

    stats = generate_thumbnails.generate_thumbnails()

    assert stats == {
        "total": 3,
        "attempted": 3,
        "generated": 3,
        "skipped": 0,
        "failed": 0,
    }
    assert len(save_calls) == 3
    assert fake_cm.playwright is not None
    assert len(fake_cm.playwright.browser.pages) == 3
    assert all(page.closed for page in fake_cm.playwright.browser.pages)


def test_generate_thumbnails_handles_page_creation_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    fake_cm = _patch_playwright(monkeypatch, fail_new_page=True)
    _patch_sleep(monkeypatch)

    with pytest.raises(RuntimeError, match="failed for every attempted artifact"):
        generate_thumbnails.generate_thumbnails()

    assert fake_cm.playwright is not None
    assert fake_cm.playwright.browser.closed is True


def test_generate_thumbnails_tolerates_page_close_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    _write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    save_calls: list[tuple[bytes, Path]] = []

    fake_cm = _patch_playwright(monkeypatch, fail_page_close=True)
    monkeypatch.setattr(
        generate_thumbnails,
        "save_thumbnail",
        lambda image_bytes, thumb_path: save_calls.append((image_bytes, thumb_path)),
    )

    stats = generate_thumbnails.generate_thumbnails()

    assert stats == {
        "total": 1,
        "attempted": 1,
        "generated": 1,
        "skipped": 0,
        "failed": 0,
    }
    assert len(save_calls) == 1
    assert fake_cm.playwright is not None
    assert fake_cm.playwright.browser.closed is True


def test_generate_thumbnails_tolerates_partial_failures_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    successful = tmp_path / "alpha"
    failing = tmp_path / "beta"
    _write_text(successful / "index.html", "<html></html>")
    _write_text(failing / "index.html", "<html></html>")

    monkeypatch.setattr(
        generate_thumbnails, "find_artifacts", lambda: [successful, failing]
    )
    monkeypatch.delenv(generate_thumbnails.STRICT_THUMBNAILS_ENV_VAR, raising=False)

    original_process = generate_thumbnails._process_artifact

    async def fake_process_artifact(browser, artifact_dir, semaphore):
        if artifact_dir == failing:
            return "failed"
        return await original_process(browser, artifact_dir, semaphore)

    monkeypatch.setattr(generate_thumbnails, "_process_artifact", fake_process_artifact)
    monkeypatch.setattr(generate_thumbnails, "save_thumbnail", lambda *_args: None)

    fake_cm = _patch_playwright(monkeypatch)

    stats = generate_thumbnails.generate_thumbnails()

    assert stats == {
        "total": 2,
        "attempted": 2,
        "generated": 1,
        "skipped": 0,
        "failed": 1,
    }
    assert fake_cm.playwright is not None
    assert fake_cm.playwright.browser.closed is True


def test_generate_thumbnails_strict_mode_fails_on_partial_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    successful = tmp_path / "alpha"
    failing = tmp_path / "beta"
    _write_text(successful / "index.html", "<html></html>")
    _write_text(failing / "index.html", "<html></html>")

    monkeypatch.setattr(
        generate_thumbnails, "find_artifacts", lambda: [successful, failing]
    )
    monkeypatch.setenv(generate_thumbnails.STRICT_THUMBNAILS_ENV_VAR, "1")

    original_process = generate_thumbnails._process_artifact

    async def fake_process_artifact(browser, artifact_dir, semaphore):
        if artifact_dir == failing:
            return "failed"
        return await original_process(browser, artifact_dir, semaphore)

    monkeypatch.setattr(generate_thumbnails, "_process_artifact", fake_process_artifact)
    monkeypatch.setattr(generate_thumbnails, "save_thumbnail", lambda *_args: None)

    _patch_playwright(monkeypatch)

    with pytest.raises(
        RuntimeError, match="failed for one or more attempted artifacts"
    ):
        generate_thumbnails.generate_thumbnails()
