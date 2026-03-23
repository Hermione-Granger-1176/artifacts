from __future__ import annotations

import urllib.error
from pathlib import Path

import pytest

import scripts.verify_deploy as verify_deploy


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_normalize_site_url_adds_trailing_slash() -> None:
    assert verify_deploy._normalize_site_url("https://example.com/demo") == (
        "https://example.com/demo/"
    )


def test_load_site_url_reads_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com/demo"\n')
    monkeypatch.setattr(verify_deploy, "PYPROJECT_FILE", pyproject)

    assert verify_deploy._load_site_url() == "https://example.com/demo/"


def test_load_site_url_errors_for_missing_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verify_deploy, "PYPROJECT_FILE", tmp_path / "pyproject.toml")

    with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
        verify_deploy._load_site_url()


def test_load_site_url_errors_for_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.other]\nvalue = true\n")
    monkeypatch.setattr(verify_deploy, "PYPROJECT_FILE", pyproject)

    with pytest.raises(ValueError, match="Missing tool.artifacts.site_url"):
        verify_deploy._load_site_url()


def test_fetch_text_reads_status_and_decodes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeHeaders:
        def get_content_charset(self, default: str) -> str:
            assert default == "utf-8"
            return "utf-8"

    class FakeResponse:
        headers = FakeHeaders()

        def __enter__(self) -> FakeResponse:
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def getcode(self) -> int:
            return 200

        def read(self) -> bytes:
            return b"<html>ok</html>"

    monkeypatch.setattr(
        verify_deploy.urllib.request,
        "urlopen",
        lambda url, timeout: FakeResponse(),
    )

    assert verify_deploy._fetch_text("https://example.com/demo/", 5.0) == (
        200,
        "<html>ok</html>",
    )


def test_fetch_json_parses_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verify_deploy,
        "_fetch_text",
        lambda url, timeout_seconds: (200, '{"commit_sha": "abc123"}'),
    )

    assert verify_deploy._fetch_json(
        "https://example.com/deploy-metadata.json", 5.0
    ) == (
        200,
        {"commit_sha": "abc123"},
    )


def test_fetch_json_rejects_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verify_deploy,
        "_fetch_text",
        lambda url, timeout_seconds: (200, "not-json"),
    )

    with pytest.raises(RuntimeError, match="returned invalid JSON"):
        verify_deploy._fetch_json("https://example.com/deploy-metadata.json", 5.0)


def test_build_metadata_url_joins_root_and_metadata_path() -> None:
    assert (
        verify_deploy._build_metadata_url(
            "https://example.com/demo/", "deploy-metadata.json"
        )
        == "https://example.com/demo/deploy-metadata.json"
    )


def test_validate_metadata_payload_rejects_non_object() -> None:
    with pytest.raises(RuntimeError, match="returned non-object deploy metadata"):
        verify_deploy._validate_metadata_payload([], "abc123")


def test_validate_metadata_payload_rejects_wrong_sha() -> None:
    with pytest.raises(RuntimeError, match="reported commit SHA"):
        verify_deploy._validate_metadata_payload({"commit_sha": "wrong"}, "abc123")


def test_normalize_metadata_path_rejects_blank_value() -> None:
    with pytest.raises(ValueError, match="metadata-path must not be empty"):
        verify_deploy._normalize_metadata_path("   ")


def test_normalize_metadata_path_rejects_leading_slash() -> None:
    with pytest.raises(
        ValueError, match="metadata-path must be relative and must not start with '/'"
    ):
        verify_deploy._normalize_metadata_path("/deploy-metadata.json")


def test_normalize_metadata_path_rejects_full_url() -> None:
    with pytest.raises(
        ValueError,
        match="metadata-path must be relative and must not be a full URL",
    ):
        verify_deploy._normalize_metadata_path("https://example.com/deploy.json")


def test_verify_deploy_retries_until_expected_substring_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            (200, "<html>stale</html>"),
            (200, '<script src="js/app.js?v=abc123"></script>'),
        ]
    )
    metadata_responses = iter(
        [
            (200, {"commit_sha": "abc123"}),
        ]
    )
    seen_urls: list[str] = []
    sleep_calls: list[float] = []

    def fake_fetch(url: str, timeout_seconds: float) -> tuple[int, str]:
        assert timeout_seconds == 5.0
        seen_urls.append(url)
        return next(responses)

    def fake_fetch_json(url: str, timeout_seconds: float) -> tuple[int, object]:
        seen_urls.append(url)
        return next(metadata_responses)

    monkeypatch.setattr(verify_deploy, "_fetch_text", fake_fetch)
    monkeypatch.setattr(verify_deploy, "_fetch_json", fake_fetch_json)
    monkeypatch.setattr(verify_deploy.time, "sleep", sleep_calls.append)

    verify_deploy.verify_deploy(
        "https://example.com/demo/",
        "js/app.js?v=abc123",
        "abc123",
        attempts=2,
        delay_seconds=1.5,
        timeout_seconds=5.0,
    )

    assert "artifacts-deploy-check=1" in seen_urls[0]
    assert "artifacts-deploy-check=2" in seen_urls[1]
    assert any("deploy-metadata.json" in url for url in seen_urls)
    assert all(url.startswith("https://example.com/demo/") for url in seen_urls)
    assert sleep_calls == [1.5]


def test_verify_deploy_retries_non_200_status_codes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            (503, "<html>stale</html>"),
            (200, '<script src="js/app.js?v=abc123"></script>'),
        ]
    )
    metadata_responses = iter(
        [
            (200, {"commit_sha": "abc123"}),
        ]
    )
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        verify_deploy, "_fetch_text", lambda url, timeout: next(responses)
    )
    monkeypatch.setattr(
        verify_deploy, "_fetch_json", lambda url, timeout: next(metadata_responses)
    )
    monkeypatch.setattr(verify_deploy.time, "sleep", sleep_calls.append)

    verify_deploy.verify_deploy(
        "https://example.com/demo/",
        "js/app.js?v=abc123",
        "abc123",
        attempts=2,
        delay_seconds=2.0,
        timeout_seconds=5.0,
    )

    assert sleep_calls == [2.0]


def test_verify_deploy_fails_after_all_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_fetch(url: str, timeout_seconds: float) -> tuple[int, str]:
        raise urllib.error.URLError("temporary failure")

    monkeypatch.setattr(verify_deploy, "_fetch_text", fake_fetch)
    monkeypatch.setattr(verify_deploy.time, "sleep", lambda seconds: None)

    with pytest.raises(RuntimeError, match="Failed to verify deployed URL"):
        verify_deploy.verify_deploy(
            "https://example.com/demo/",
            "needle",
            "abc123",
            attempts=2,
            delay_seconds=0.0,
            timeout_seconds=5.0,
        )


def test_verify_deploy_requires_positive_attempt_count() -> None:
    with pytest.raises(ValueError, match="attempts must be at least 1"):
        verify_deploy.verify_deploy(
            "https://example.com/demo/",
            "needle",
            "abc123",
            attempts=0,
        )


def test_verify_deploy_retries_when_metadata_sha_is_wrong(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([(200, '<script src="js/app.js?v=abc123"></script>')] * 2)
    metadata_responses = iter(
        [
            (200, {"commit_sha": "wrong"}),
            (200, {"commit_sha": "abc123"}),
        ]
    )
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        verify_deploy, "_fetch_text", lambda url, timeout: next(responses)
    )
    monkeypatch.setattr(
        verify_deploy, "_fetch_json", lambda url, timeout: next(metadata_responses)
    )
    monkeypatch.setattr(verify_deploy.time, "sleep", sleep_calls.append)

    verify_deploy.verify_deploy(
        "https://example.com/demo/",
        "js/app.js?v=abc123",
        "abc123",
        attempts=2,
        delay_seconds=1.0,
        timeout_seconds=5.0,
    )

    assert sleep_calls == [1.0]


def test_verify_deploy_retries_when_metadata_status_is_non_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter([(200, '<script src="js/app.js?v=abc123"></script>')] * 2)
    metadata_responses = iter(
        [
            (503, {"commit_sha": "abc123"}),
            (200, {"commit_sha": "abc123"}),
        ]
    )
    sleep_calls: list[float] = []

    monkeypatch.setattr(
        verify_deploy, "_fetch_text", lambda url, timeout: next(responses)
    )
    monkeypatch.setattr(
        verify_deploy, "_fetch_json", lambda url, timeout: next(metadata_responses)
    )
    monkeypatch.setattr(verify_deploy.time, "sleep", sleep_calls.append)

    verify_deploy.verify_deploy(
        "https://example.com/demo/",
        "js/app.js?v=abc123",
        "abc123",
        attempts=2,
        delay_seconds=1.0,
        timeout_seconds=5.0,
    )

    assert sleep_calls == [1.0]


def test_main_uses_explicit_url(monkeypatch: pytest.MonkeyPatch) -> None:
    observed: dict[str, object] = {}

    def fake_verify_deploy(
        url: str,
        expected_substring: str,
        expected_commit_sha: str,
        *,
        attempts: int,
        delay_seconds: float,
        timeout_seconds: float,
        metadata_path: str,
    ) -> None:
        observed.update(
            {
                "url": url,
                "expected_substring": expected_substring,
                "expected_commit_sha": expected_commit_sha,
                "attempts": attempts,
                "delay_seconds": delay_seconds,
                "timeout_seconds": timeout_seconds,
                "metadata_path": metadata_path,
            }
        )

    monkeypatch.setattr(verify_deploy, "verify_deploy", fake_verify_deploy)

    exit_code = verify_deploy.main(
        [
            "--url",
            "https://example.com/preview",
            "--expected-substring",
            "js/app.js?v=abc123",
            "--expected-commit-sha",
            "abc123",
            "--attempts",
            "3",
            "--delay-seconds",
            "2.5",
            "--timeout-seconds",
            "7.0",
            "--metadata-path",
            "meta/deploy.json",
        ]
    )

    assert exit_code == 0
    assert observed == {
        "url": "https://example.com/preview/",
        "expected_substring": "js/app.js?v=abc123",
        "expected_commit_sha": "abc123",
        "attempts": 3,
        "delay_seconds": 2.5,
        "timeout_seconds": 7.0,
        "metadata_path": "meta/deploy.json",
    }


def test_main_uses_configured_site_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        verify_deploy, "_load_site_url", lambda: "https://example.com/demo/"
    )
    seen: dict[str, str] = {}

    def fake_verify_deploy(
        url: str,
        expected_substring: str,
        expected_commit_sha: str,
        *,
        attempts: int,
        delay_seconds: float,
        timeout_seconds: float,
        metadata_path: str,
    ) -> None:
        seen["url"] = url
        seen["expected_substring"] = expected_substring
        seen["expected_commit_sha"] = expected_commit_sha
        seen["metadata_path"] = metadata_path

    monkeypatch.setattr(verify_deploy, "verify_deploy", fake_verify_deploy)

    exit_code = verify_deploy.main(
        [
            "--expected-substring",
            "js/app.js?v=abc123",
            "--expected-commit-sha",
            "abc123",
        ]
    )

    assert exit_code == 0
    assert seen == {
        "url": "https://example.com/demo/",
        "expected_substring": "js/app.js?v=abc123",
        "expected_commit_sha": "abc123",
        "metadata_path": verify_deploy.DEFAULT_METADATA_PATH,
    }
