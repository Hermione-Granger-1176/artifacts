from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import scripts.prepare_site as prepare_site


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_source_tree(repo_root: Path) -> None:
    write_text(
        repo_root / "404.html",
        "".join(
            [
                '<body data-site-path="/">\n',
                '<a id="home-link" href="/">Return to gallery</a>\n',
                "</body>\n",
            ]
        ),
    )
    write_text(
        repo_root / "index.html",
        "".join(
            [
                '<link rel="canonical" href="__ARTIFACTS_SITE_URL__">\n',
                '<meta property="og:url" content="__ARTIFACTS_SITE_URL__">\n',
                '<meta property="og:image" content="__ARTIFACTS_SHARE_IMAGE__">\n',
                '<meta property="og:image:secure_url" content="__ARTIFACTS_SHARE_IMAGE__">\n',
                '<meta name="twitter:image" content="__ARTIFACTS_SHARE_IMAGE__">\n',
                '<link rel="stylesheet" href="css/style.css">\n',
                '<script src="js/gallery-config.js"></script>\n',
                '<script src="js/data.js"></script>\n',
                '<script type="module" src="js/app.js"></script>\n',
            ]
        ),
    )
    write_text(
        repo_root / "css" / "style.css",
        "".join(
            [
                '@import url("./root-gallery-foundation.css");\n',
                '@import url("./root-gallery-artifacts.css");\n',
                '@import url("./root-gallery-responsive.css");\n',
            ]
        ),
    )
    write_text(repo_root / "css" / "root-gallery-foundation.css", "body {}\n")
    write_text(repo_root / "css" / "root-gallery-artifacts.css", ".artifact-card {}\n")
    write_text(
        repo_root / "css" / "root-gallery-responsive.css",
        "@media (max-width: 1px) {}\n",
    )
    write_text(repo_root / "js" / "app.js", "console.log('app')\n")
    write_text(
        repo_root / "js" / "gallery-config.js", "window.ARTIFACTS_CONFIG = {};\n"
    )
    write_text(repo_root / "js" / "data.js", "window.ARTIFACTS_DATA = [];\n")
    write_text(repo_root / "apps" / "sample" / "index.html", "<html></html>\n")
    write_text(
        repo_root / "assets" / "icons" / "manifest.webmanifest",
        '{\n  "start_url": "../../"\n}\n',
    )
    (repo_root / "assets" / "icons" / "favicon.ico").write_bytes(b"ico")
    (repo_root / "assets" / "icons" / "icon.svg").write_bytes(b"<svg/>")
    (repo_root / "assets" / "social").mkdir(parents=True, exist_ok=True)
    (repo_root / "assets" / "social" / "share-preview.png").write_bytes(b"png")


def test_normalize_site_path() -> None:
    assert prepare_site._normalize_site_path("/artifacts/") == "/artifacts/"
    assert prepare_site._normalize_site_path("artifacts") == "/artifacts/"
    assert prepare_site._normalize_site_path("/") == "/"


def test_load_site_path_reads_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_path = "artifacts"\n')
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    assert prepare_site._load_site_path() == "/artifacts/"


def test_normalize_site_url() -> None:
    assert prepare_site._normalize_site_url("https://example.com/demo") == (
        "https://example.com/demo/"
    )
    assert prepare_site._normalize_site_url("https://example.com/demo/") == (
        "https://example.com/demo/"
    )


def test_load_site_url_reads_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com/demo"\n')
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    assert prepare_site._load_site_url() == "https://example.com/demo/"


def test_load_site_url_errors_for_missing_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", tmp_path / "pyproject.toml")

    with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
        prepare_site._load_site_url()


def test_load_site_url_errors_for_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.other]\nvalue = true\n")
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    with pytest.raises(ValueError, match="Missing tool.artifacts.site_url"):
        prepare_site._load_site_url()


def test_load_site_path_errors_for_missing_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", tmp_path / "pyproject.toml")

    with pytest.raises(FileNotFoundError, match="pyproject.toml not found"):
        prepare_site._load_site_path()


def test_load_site_path_errors_for_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.other]\nvalue = true\n")
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    with pytest.raises(ValueError, match="Missing tool.artifacts.site_path"):
        prepare_site._load_site_path()


def test_resolve_version_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(prepare_site.DEPLOY_VERSION_ENV_VAR, "abc123")

    assert prepare_site._resolve_version() == "abc123"


def test_resolve_version_uses_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(prepare_site.DEPLOY_VERSION_ENV_VAR, raising=False)

    observed: dict[str, object] = {}

    def fake_check_output(*args: object, **kwargs: object) -> str:
        observed.update(kwargs)
        return "deadbee\n"

    monkeypatch.setattr(
        prepare_site.subprocess,
        "check_output",
        fake_check_output,
    )

    assert prepare_site._resolve_version() == "deadbee"
    assert observed["timeout"] == prepare_site.GIT_COMMAND_TIMEOUT_SECONDS


def test_resolve_version_propagates_git_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(prepare_site.DEPLOY_VERSION_ENV_VAR, raising=False)

    def raise_git_timeout(*args: object, **kwargs: object) -> str:
        raise subprocess.TimeoutExpired(["git", "rev-parse", "--short", "HEAD"], 10)

    monkeypatch.setattr(prepare_site.subprocess, "check_output", raise_git_timeout)

    with pytest.raises(subprocess.TimeoutExpired):
        prepare_site._resolve_version()


def test_replace_exact_requires_expected_content() -> None:
    assert prepare_site._replace_exact("hello world", "world", "repo") == "hello repo"

    with pytest.raises(ValueError, match="Expected content not found"):
        prepare_site._replace_exact("hello", "missing", "repo")


def test_copy_deploy_items_copies_expected_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_source_tree(tmp_path)
    deploy_dir = tmp_path / "_site"
    write_text(deploy_dir / "stale.txt", "stale\n")

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._copy_deploy_items()

    assert (deploy_dir / "404.html").exists()
    assert (deploy_dir / "apps" / "sample" / "index.html").exists()
    assert not (deploy_dir / "stale.txt").exists()


def test_copy_deploy_items_errors_for_missing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path / "_site")

    with pytest.raises(FileNotFoundError, match="Required deploy path not found"):
        prepare_site._copy_deploy_items()


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_copy_deploy_items_rejects_symlinked_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_source_tree(tmp_path)
    linked_target = tmp_path / "shared.js"
    write_text(linked_target, "console.log('linked')\n")
    (tmp_path / "js" / "app.js").unlink()
    (tmp_path / "js" / "app.js").symlink_to(linked_target)

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path / "_site")

    with pytest.raises(
        ValueError, match="Refusing to copy deploy tree containing symlink"
    ):
        prepare_site._copy_deploy_items()


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_copy_deploy_items_rejects_top_level_symlinked_deploy_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_source_tree(tmp_path)
    linked_assets = tmp_path / "shared-assets"
    linked_assets.mkdir()
    (tmp_path / "assets").rename(linked_assets)
    (tmp_path / "assets").symlink_to(linked_assets, target_is_directory=True)

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path / "_site")

    with pytest.raises(ValueError, match="Refusing to copy symlinked deploy path"):
        prepare_site._copy_deploy_items()


def test_patch_index_html_applies_cache_busting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    write_text(
        deploy_dir / "index.html",
        'href="css/style.css" src="js/gallery-config.js" src="js/data.js" src="js/app.js"\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_index_html("abc123")

    content = (deploy_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="css/style.css?v=abc123"' in content
    assert 'src="js/gallery-config.js?v=abc123"' in content
    assert 'src="js/data.js?v=abc123"' in content
    assert 'src="js/app.js?v=abc123"' in content


def test_patch_social_metadata_injects_absolute_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    write_text(
        deploy_dir / "index.html",
        '<link rel="canonical" href="__ARTIFACTS_SITE_URL__">\n'
        '<meta property="og:url" content="__ARTIFACTS_SITE_URL__">\n'
        '<meta property="og:image" content="__ARTIFACTS_SHARE_IMAGE__">\n'
        '<meta property="og:image:secure_url" content="__ARTIFACTS_SHARE_IMAGE__">\n'
        '<meta name="twitter:image" content="__ARTIFACTS_SHARE_IMAGE__">\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_social_metadata("https://example.com/demo/", "abc123")

    content = (deploy_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="https://example.com/demo/"' in content
    assert 'content="https://example.com/demo/"' in content
    assert (
        'content="https://example.com/demo/assets/social/share-preview.png?v=abc123"'
        in content
    )


def test_patch_root_stylesheet_versions_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    styles_dir = deploy_dir / "css"
    styles_dir.mkdir(parents=True)
    write_text(
        styles_dir / "style.css",
        '@import url("./root-gallery-foundation.css");\n'
        '@import url("./root-gallery-artifacts.css");\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_root_stylesheet("abc123")

    content = (styles_dir / "style.css").read_text(encoding="utf-8")
    assert '@import url("./root-gallery-foundation.css?v=abc123");' in content
    assert '@import url("./root-gallery-artifacts.css?v=abc123");' in content


def test_patch_root_stylesheet_skips_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_root_stylesheet("abc123")


def test_patch_404_html_injects_site_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    write_text(
        deploy_dir / "404.html",
        '<body data-site-path="/"><a id="home-link" href="/">Home</a></body>\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_404_html("/artifacts/")

    content = (deploy_dir / "404.html").read_text(encoding="utf-8")
    assert 'data-site-path="/artifacts/"' in content
    assert 'href="/artifacts/"' in content


def test_patch_404_html_preserves_preview_logic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    original = (
        '<body data-site-path="/">\n'
        '<a id="home-link" href="/">Return to gallery</a>\n'
        '<script>const previewRoot = [...siteParts, "pr-preview", pathParts[siteParts.length + 1]];</script>\n'
    )
    write_text(deploy_dir / "404.html", original)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_404_html("/artifacts/")

    content = (deploy_dir / "404.html").read_text(encoding="utf-8")
    assert 'data-site-path="/artifacts/"' in content
    assert 'href="/artifacts/"' in content
    assert '"pr-preview"' in content


def test_patch_manifest_injects_site_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    icons_dir = deploy_dir / "assets" / "icons"
    icons_dir.mkdir(parents=True)
    write_text(
        icons_dir / "manifest.webmanifest",
        '{\n  "start_url": "../../"\n}\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_manifest("/artifacts/")

    content = (icons_dir / "manifest.webmanifest").read_text(encoding="utf-8")
    assert '"start_url": "/artifacts/"' in content


def test_patch_manifest_skips_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_manifest("/artifacts/")


def test_write_nojekyll_creates_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._write_nojekyll()

    assert (deploy_dir / ".nojekyll").exists()


def test_resolve_commit_sha_prefers_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(prepare_site.DEPLOY_COMMIT_SHA_ENV_VAR, "a" * 40)

    assert prepare_site._resolve_commit_sha() == "a" * 40


def test_resolve_commit_sha_uses_git(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(prepare_site.DEPLOY_COMMIT_SHA_ENV_VAR, raising=False)

    observed: dict[str, object] = {}

    def fake_check_output(*args: object, **kwargs: object) -> str:
        observed.update(kwargs)
        return "deadbeefcafefeed\n"

    monkeypatch.setattr(prepare_site.subprocess, "check_output", fake_check_output)

    assert prepare_site._resolve_commit_sha() == "deadbeefcafefeed"
    assert observed["timeout"] == prepare_site.GIT_COMMAND_TIMEOUT_SECONDS


def test_write_deploy_metadata_creates_expected_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._write_deploy_metadata(
        commit_sha="a" * 40,
        version="abc1234",
        site_path="/artifacts/",
    )

    metadata = (deploy_dir / prepare_site.DEPLOY_METADATA_FILE).read_text(
        encoding="utf-8"
    )
    assert '"commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"' in metadata
    assert '"version": "abc1234"' in metadata
    assert '"site_path": "/artifacts/"' in metadata


def test_prepare_site_builds_deploy_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_source_tree(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    write_text(
        pyproject,
        '[tool.artifacts]\nsite_path = "/artifacts/"\nsite_url = "https://example.com/artifacts"\n',
    )
    deploy_dir = tmp_path / "_site"

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)
    monkeypatch.setenv(prepare_site.DEPLOY_VERSION_ENV_VAR, "abc123")
    monkeypatch.setenv(prepare_site.DEPLOY_COMMIT_SHA_ENV_VAR, "b" * 40)

    prepare_site.prepare_site()

    index_content = (deploy_dir / "index.html").read_text(encoding="utf-8")
    style_content = (deploy_dir / "css" / "style.css").read_text(encoding="utf-8")
    error_content = (deploy_dir / "404.html").read_text(encoding="utf-8")
    assert "css/style.css?v=abc123" in index_content
    assert 'href="https://example.com/artifacts/"' in index_content
    assert (
        'content="https://example.com/artifacts/assets/social/share-preview.png?v=abc123"'
        in index_content
    )
    assert '@import url("./root-gallery-foundation.css?v=abc123");' in style_content
    assert 'data-site-path="/artifacts/"' in error_content
    assert (deploy_dir / ".nojekyll").exists()
    assert (deploy_dir / "apps" / "sample" / "index.html").exists()
    assert (deploy_dir / "assets" / "icons" / "favicon.ico").exists()
    assert (deploy_dir / "assets" / "social" / "share-preview.png").exists()
    metadata = (deploy_dir / prepare_site.DEPLOY_METADATA_FILE).read_text(
        encoding="utf-8"
    )
    assert '"commit_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"' in metadata
    assert '"version": "abc123"' in metadata
    manifest = (deploy_dir / "assets" / "icons" / "manifest.webmanifest").read_text(
        encoding="utf-8"
    )
    assert '"start_url": "/artifacts/"' in manifest


def test_prepare_site_propagates_git_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    create_source_tree(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    write_text(
        pyproject,
        '[tool.artifacts]\nsite_path = "/artifacts/"\nsite_url = "https://example.com/artifacts"\n',
    )

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path / "_site")
    monkeypatch.delenv(prepare_site.DEPLOY_VERSION_ENV_VAR, raising=False)
    monkeypatch.delenv(prepare_site.DEPLOY_COMMIT_SHA_ENV_VAR, raising=False)

    def raise_git_failure(*args: object, **kwargs: object) -> str:
        raise subprocess.CalledProcessError(1, ["git", "rev-parse"])

    monkeypatch.setattr(prepare_site.subprocess, "check_output", raise_git_failure)

    with pytest.raises(subprocess.CalledProcessError):
        prepare_site.prepare_site()
