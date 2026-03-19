from __future__ import annotations

import builtins
import os
import types
from collections.abc import Mapping, Sequence
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

import scripts.generate_thumbnails as generate_thumbnails


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_find_artifacts_returns_only_visible_dirs_with_index_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    apps_dir = tmp_path / "apps"
    apps_dir.mkdir()

    write_text(apps_dir / "loan-tool" / "index.html", "<html></html>")
    write_text(apps_dir / "budget-tool" / "index.html", "<html></html>")
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
    write_text(artifact_dir / "index.html", "<html></html>")

    assert generate_thumbnails.should_generate_thumbnail(artifact_dir) is True

    thumb_path = artifact_dir / generate_thumbnails.SCREENSHOT_FILE
    thumb_path.write_bytes(b"thumb")

    assert generate_thumbnails.should_generate_thumbnail(artifact_dir) is False

    write_text(artifact_dir / "index.html", "<html>updated</html>")
    future_mtime = thumb_path.stat().st_mtime + 2
    os.utime(artifact_dir / "index.html", (future_mtime, future_mtime))

    assert generate_thumbnails.should_generate_thumbnail(artifact_dir) is True


def test_should_generate_thumbnail_when_legacy_png_exists(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "loan-tool"
    write_text(artifact_dir / "index.html", "<html></html>")
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
    write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.sync_api":
            raise ImportError("playwright unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(SystemExit, match="1"):
        generate_thumbnails.generate_thumbnails()


def test_generate_thumbnails_processes_artifacts_and_closes_browser(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    write_text(artifact_dir / "index.html", "<html></html>")
    (artifact_dir / generate_thumbnails.LEGACY_SCREENSHOT_FILE).write_bytes(b"legacy")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])

    browser_closed = False
    save_calls: list[tuple[bytes, Path]] = []

    class FakePage:
        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            assert url.startswith("file://")
            assert wait_until == "networkidle"
            assert timeout == 30000

        def wait_for_timeout(self, milliseconds: int) -> None:
            assert milliseconds == 1000

        def screenshot(self, type: str) -> bytes:
            assert type == "png"
            return b"png-bytes"

    class FakeBrowser:
        def new_page(
            self, viewport: dict[str, int], device_scale_factor: int
        ) -> FakePage:
            assert viewport == {
                "width": generate_thumbnails.VIEWPORT_WIDTH,
                "height": generate_thumbnails.VIEWPORT_HEIGHT,
            }
            assert device_scale_factor == 2
            return FakePage()

        def close(self) -> None:
            nonlocal browser_closed
            browser_closed = True

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = types.SimpleNamespace(launch=lambda: FakeBrowser())

    class FakeSyncPlaywright:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.sync_api":
            return types.SimpleNamespace(sync_playwright=lambda: FakeSyncPlaywright())
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(
        generate_thumbnails,
        "save_thumbnail",
        lambda image_bytes, thumb_path: save_calls.append((image_bytes, thumb_path)),
    )
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    stats = generate_thumbnails.generate_thumbnails()

    assert browser_closed is True
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
    write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: False
    )

    class FakeBrowser:
        def new_page(
            self, viewport: dict[str, int], device_scale_factor: int
        ) -> object:
            return object()

        def close(self) -> None:
            return None

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = types.SimpleNamespace(launch=lambda: FakeBrowser())

    class FakeSyncPlaywright:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.sync_api":
            return types.SimpleNamespace(sync_playwright=lambda: FakeSyncPlaywright())
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

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
    write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    save_calls: list[tuple[bytes, Path]] = []
    sleep_calls: list[float] = []
    goto_calls = 0

    class FakePage:
        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            nonlocal goto_calls
            goto_calls += 1
            if goto_calls < 3:
                raise RuntimeError(f"transient-{goto_calls}")

        def wait_for_timeout(self, milliseconds: int) -> None:
            assert milliseconds == generate_thumbnails.POST_LOAD_DELAY_MS

        def screenshot(self, type: str) -> bytes:
            assert type == "png"
            return b"png-bytes"

    class FakeBrowser:
        def new_page(
            self, viewport: dict[str, int], device_scale_factor: int
        ) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = types.SimpleNamespace(launch=lambda: FakeBrowser())

    class FakeSyncPlaywright:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.sync_api":
            return types.SimpleNamespace(sync_playwright=lambda: FakeSyncPlaywright())
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(generate_thumbnails, "sleep", sleep_calls.append)
    monkeypatch.setattr(
        generate_thumbnails,
        "save_thumbnail",
        lambda image_bytes, thumb_path: save_calls.append((image_bytes, thumb_path)),
    )

    stats = generate_thumbnails.generate_thumbnails()

    assert goto_calls == 3
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])

    browser_closed = False

    class FakePage:
        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            raise RuntimeError("boom")

        def wait_for_timeout(self, milliseconds: int) -> None:
            raise AssertionError("wait_for_timeout should not be reached")

        def screenshot(self, type: str) -> bytes:
            raise AssertionError("screenshot should not be reached")

    class FakeBrowser:
        def new_page(
            self, viewport: dict[str, int], device_scale_factor: int
        ) -> FakePage:
            return FakePage()

        def close(self) -> None:
            nonlocal browser_closed
            browser_closed = True

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = types.SimpleNamespace(launch=lambda: FakeBrowser())

    class FakeSyncPlaywright:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.sync_api":
            return types.SimpleNamespace(sync_playwright=lambda: FakeSyncPlaywright())
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )
    monkeypatch.setattr(generate_thumbnails, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="failed for every attempted artifact"):
        generate_thumbnails.generate_thumbnails()

    assert browser_closed is True


def test_generate_thumbnails_raises_when_all_attempts_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_dir = tmp_path / "loan-tool"
    write_text(artifact_dir / "index.html", "<html></html>")
    monkeypatch.setattr(generate_thumbnails, "find_artifacts", lambda: [artifact_dir])
    monkeypatch.setattr(
        generate_thumbnails, "should_generate_thumbnail", lambda _path: True
    )

    class FakePage:
        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            raise RuntimeError("boom")

        def wait_for_timeout(self, milliseconds: int) -> None:
            raise AssertionError("wait_for_timeout should not be reached")

        def screenshot(self, type: str) -> bytes:
            raise AssertionError("screenshot should not be reached")

    class FakeBrowser:
        def new_page(
            self, viewport: dict[str, int], device_scale_factor: int
        ) -> FakePage:
            return FakePage()

        def close(self) -> None:
            return None

    class FakePlaywright:
        def __init__(self) -> None:
            self.chromium = types.SimpleNamespace(launch=lambda: FakeBrowser())

    class FakeSyncPlaywright:
        def __enter__(self) -> FakePlaywright:
            return FakePlaywright()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    original_import = builtins.__import__

    def fake_import(
        name: str,
        globals: Mapping[str, object] | None = None,
        locals: Mapping[str, object] | None = None,
        fromlist: Sequence[str] = (),
        level: int = 0,
    ) -> object:
        if name == "playwright.sync_api":
            return types.SimpleNamespace(sync_playwright=lambda: FakeSyncPlaywright())
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(generate_thumbnails, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError, match="failed for every attempted artifact"):
        generate_thumbnails.generate_thumbnails()
