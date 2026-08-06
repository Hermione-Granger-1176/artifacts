from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from scripts.ci import refresh_ci_pins as pins

if TYPE_CHECKING:
    from urllib.request import Request


DIGEST = f"sha256:{'a' * 64}"


class Response:
    """Small urlopen response seam for JSON and registry-header tests."""

    def __init__(self, payload: object = None, digest: str | None = None) -> None:
        self._payload = payload
        self.headers = {"Docker-Content-Digest": digest} if digest is not None else {}

    def read(self, amount: int | None = None) -> bytes:
        """Return the JSON payload bytes expected by json.load."""
        del amount
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self) -> Response:
        """Enter the fake response context."""
        return self

    def __exit__(self, *args: object) -> None:
        """Exit the fake response context."""
        del args


def test_retry_returns_a_first_success_without_sleep() -> None:
    """A healthy registry does not incur backoff."""
    sleeps: list[float] = []

    assert pins.retry(lambda: "ok", sleep=sleeps.append) == "ok"
    assert sleeps == []


def test_retry_retries_transient_failures() -> None:
    """Transient failures use bounded backoff before succeeding."""
    results: list[object] = [RuntimeError("first"), "ok"]
    sleeps: list[float] = []

    def fetch() -> str:
        result = results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    assert pins.retry(fetch, sleep=sleeps.append) == "ok"
    assert sleeps == [0.25]


def test_retry_re_raises_the_final_failure() -> None:
    """The final failure remains visible after all retry attempts."""
    with pytest.raises(RuntimeError, match="boom"):
        pins.retry(lambda: (_ for _ in ()).throw(RuntimeError("boom")), attempts=1)


def test_retry_requires_a_positive_attempt_count() -> None:
    """A maintenance helper cannot silently skip all network attempts."""
    with pytest.raises(ValueError, match="at least 1"):
        pins.retry(lambda: "never", attempts=0)


def test_pypi_latest_version_reads_a_stable_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """Read the exact stable version advertised by PyPI."""
    requests: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> Response:
        requests.append(request)
        assert timeout == 15
        return Response({"info": {"version": "1.62.0"}})

    monkeypatch.setattr(pins, "urlopen", fake_urlopen)

    assert pins.pypi_latest_version() == "1.62.0"
    assert requests[0].full_url == pins.PYPI_URL
    assert requests[0].headers["Accept"] == "application/json"


@pytest.mark.parametrize(
    "payload",
    [None, {}, {"info": {}}, {"info": {"version": "1.62.0rc1"}}, {"info": {"version": 1}}],
)
def test_pypi_latest_version_rejects_invalid_payloads(
    monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    """Never write a dependency version that is not a stable semantic release."""
    monkeypatch.setattr(pins, "urlopen", lambda *_args, **_kwargs: Response(payload))

    with pytest.raises(ValueError, match="invalid latest Playwright version"):
        pins.pypi_latest_version()


def test_locked_playwright_version_reads_uv_lock(tmp_path: Path) -> None:
    """Read the package version that uv actually resolved."""
    path = tmp_path / "uv.lock"
    path.write_text(
        '[[package]]\nname = "other"\nversion = "1.0.0"\n\n'
        '[[package]]\nname = "playwright"\nversion = "1.61.0"\n',
        encoding="utf-8",
    )

    assert pins.locked_playwright_version(path) == "1.61.0"


@pytest.mark.parametrize(
    "lock_text",
    [
        "",
        'package = [{name = "playwright", version = "1.61.0"}, '
        '{name = "playwright", version = "1.62.0"}]\n',
        '[[package]]\nname = "playwright"\nversion = "1.62.0rc1"\n',
        '[[package]]\nname = "playwright"\nversion = 1\n',
    ],
)
def test_locked_playwright_version_rejects_ambiguous_or_invalid_locks(
    tmp_path: Path, lock_text: str
) -> None:
    """Fail closed when the lock cannot identify one exact stable package."""
    path = tmp_path / "uv.lock"
    path.write_text(lock_text, encoding="utf-8")

    with pytest.raises(ValueError, match="no exact Playwright semantic version"):
        pins.locked_playwright_version(path)


def test_registry_digest_reads_the_immutable_python_image_digest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve a versioned Python image through the MCR manifest endpoint."""
    requests: list[Request] = []

    def fake_urlopen(request: Request, *, timeout: float) -> Response:
        requests.append(request)
        assert timeout == 15
        return Response(digest=DIGEST)

    monkeypatch.setattr(pins, "urlopen", fake_urlopen)
    image = "mcr.microsoft.com/playwright/python:v1.61.0-noble"

    assert pins.registry_digest(image) == DIGEST
    assert requests[0].method == "HEAD"
    assert requests[0].full_url.endswith("/manifests/v1.61.0-noble")


@pytest.mark.parametrize(
    ("image", "digest"),
    [
        ("docker.io/playwright:v1.61.0", DIGEST),
        ("mcr.microsoft.com/playwright/python:", DIGEST),
        ("mcr.microsoft.com/playwright/python:v1.61.0-noble", None),
        ("mcr.microsoft.com/playwright/python:v1.61.0-noble", "sha256:short"),
    ],
)
def test_registry_digest_rejects_unsupported_images_and_bad_headers(
    monkeypatch: pytest.MonkeyPatch, image: str, digest: str | None
) -> None:
    """Never write a digest from the wrong registry or an invalid response."""
    monkeypatch.setattr(pins, "urlopen", lambda *_args, **_kwargs: Response(digest=digest))

    with pytest.raises(ValueError, match=r"Unsupported|invalid digest"):
        pins.registry_digest(image)


def test_replace_one_changes_a_pin_and_detects_a_noop(tmp_path: Path) -> None:
    """Require one owned pin while avoiding needless writes."""
    path = tmp_path / "config"
    path.write_text("pin=old\n", encoding="utf-8")
    pattern = pins.re.compile(r"(?m)^pin=\S+$")

    assert pins.replace_one(path, pattern, "pin=new", label="test pin")
    assert not pins.replace_one(path, pattern, "pin=new", label="test pin")


@pytest.mark.parametrize("text", ["none\n", "pin=a\npin=b\n"])
def test_replace_one_rejects_missing_or_duplicate_pins(tmp_path: Path, text: str) -> None:
    """Fail when a refactor makes pin ownership ambiguous."""
    path = tmp_path / "config"
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="Expected exactly one"):
        pins.replace_one(path, pins.re.compile(r"(?m)^pin=\S+$"), "pin=new", label="test pin")


def test_upgrade_project_dependency_updates_only_the_exact_requirement(tmp_path: Path) -> None:
    """Update the project requirement before uv regenerates its lock."""
    path = tmp_path / "pyproject.toml"
    path.write_text('dependencies = [\n  "playwright==1.61.0",\n]\n', encoding="utf-8")

    assert pins.upgrade_project_dependency(path, "1.62.0")
    assert '"playwright==1.62.0",' in path.read_text(encoding="utf-8")
    assert not pins.upgrade_project_dependency(path, "1.62.0")


def test_upgrade_project_dependency_rejects_invalid_versions(tmp_path: Path) -> None:
    """A project pin must stay on a stable semantic release."""
    path = tmp_path / "pyproject.toml"
    path.write_text('dependencies = ["playwright==1.61.0"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid Playwright semantic version"):
        pins.upgrade_project_dependency(path, "1.62.0rc1")


def test_refresh_workflow_images_updates_every_browser_workflow(tmp_path: Path) -> None:
    """Keep each browser-only workflow on the same versioned image digest."""
    paths = [tmp_path / "one.yml", tmp_path / "two.yml"]
    old = f"{pins.PLAYWRIGHT_IMAGE_PREFIX}v1.61.0-noble@{DIGEST}"
    for path in paths:
        path.write_text(f"image: {old}\n", encoding="utf-8")
    new_digest = f"sha256:{'b' * 64}"

    assert pins.refresh_workflow_images(version="1.62.0", digest=new_digest, paths=paths) == paths
    for path in paths:
        assert f"{pins.PLAYWRIGHT_IMAGE_PREFIX}v1.62.0-noble@{new_digest}" in path.read_text(
            encoding="utf-8"
        )
    assert pins.refresh_workflow_images(version="1.62.0", digest=new_digest, paths=paths) == []


def test_refresh_workflow_images_replaces_all_owned_references(tmp_path: Path) -> None:
    """Update every browser job when one workflow reuses the image twice."""
    path = tmp_path / "workflow.yml"
    old = f"{pins.PLAYWRIGHT_IMAGE_PREFIX}v1.61.0-noble@{DIGEST}"
    path.write_text(f"first: {old}\nsecond: {old}\n", encoding="utf-8")
    new_digest = f"sha256:{'b' * 64}"

    assert pins.refresh_workflow_images(version="1.62.0", digest=new_digest, paths=[path]) == [path]
    new = f"{pins.PLAYWRIGHT_IMAGE_PREFIX}v1.62.0-noble@{new_digest}"
    assert path.read_text(encoding="utf-8").count(new) == 2


def test_refresh_workflow_images_rejects_a_missing_pin(tmp_path: Path) -> None:
    """Fail when a browser workflow loses its owned image reference."""
    path = tmp_path / "workflow.yml"
    path.write_text("jobs: {}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected at least one Playwright image pin"):
        pins.refresh_workflow_images(version="1.62.0", digest=DIGEST, paths=[path])


@pytest.mark.parametrize(
    ("version", "digest"),
    [("1.62.0rc1", DIGEST), ("1.62.0", "sha256:short")],
)
def test_refresh_workflow_images_rejects_invalid_pins(
    tmp_path: Path, version: str, digest: str
) -> None:
    """Do not write malformed image references."""
    path = tmp_path / "workflow.yml"
    path.write_text(
        f"image: {pins.PLAYWRIGHT_IMAGE_PREFIX}v1.61.0-noble@{DIGEST}\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Invalid Playwright"):
        pins.refresh_workflow_images(version=version, digest=digest, paths=[path])


def test_refresh_locked_image_uses_the_locked_version_and_registry_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The image refresh is coupled to uv.lock, not to an independent version."""
    lock = tmp_path / "uv.lock"
    workflow = tmp_path / "workflow.yml"
    monkeypatch.setattr(pins, "registry_digest", lambda _image: DIGEST)
    workflow.write_text(
        f"image: {pins.PLAYWRIGHT_IMAGE_PREFIX}v1.60.0-noble@{DIGEST}\n", encoding="utf-8"
    )
    lock.write_text('[[package]]\nname = "playwright"\nversion = "1.61.0"\n', encoding="utf-8")

    assert pins.refresh_locked_image(lock, paths=[workflow]) == [workflow]


def test_main_runs_project_upgrade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Make target reports a changed project requirement."""
    project = tmp_path / "pyproject.toml"
    project.write_text('dependencies = [\n  "playwright==1.61.0",\n]\n', encoding="utf-8")
    monkeypatch.setattr(pins, "PYPROJECT_PATH", project)
    monkeypatch.setattr(pins, "pypi_latest_version", lambda: "1.62.0")

    assert pins.main(["upgrade-project"]) == 0
    assert capsys.readouterr().out.strip() == f"Updated {project}"


def test_main_runs_image_refresh(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The Make target reports image files changed from the lock."""
    changed = [Path(".github/workflows/update.yml")]
    monkeypatch.setattr(pins, "refresh_locked_image", lambda _path: changed)

    assert pins.main(["refresh-image"]) == 0
    assert capsys.readouterr().out.strip() == f"Updated {changed[0]}"
