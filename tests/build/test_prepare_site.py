from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

import scripts.build.prepare_site as prepare_site


def write_text(path: Path, content: str) -> None:
    """Write text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_source_tree(repo_root: Path) -> None:
    """Create source tree."""
    write_text(
        repo_root / "config" / "artifact_contract.json",
        '{"artifactIdPattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$", '
        '"artifactBasePath": "apps", "thumbnailFile": "thumbnail.webp"}\n',
    )
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
                "</head>\n",
            ]
        ),
    )
    write_text(
        repo_root / "css" / "style.css",
        "".join(
            [
                "body { margin: 0; }\n",
                ".artifact-card { display: block; }\n",
                "@media (max-width: 1px) {}\n",
            ]
        ),
    )
    write_text(repo_root / "css" / "src" / "01-tokens.css", "body { margin: 0; }\n")
    write_text(
        repo_root / "css" / "src" / "02-gallery.css",
        ".artifact-card { display: block; }\n",
    )
    write_text(
        repo_root / "js" / "app.js",
        'import { lib } from "./lib.js";\nconsole.log(lib);\n',
    )
    write_text(repo_root / "js" / "lib.js", 'export const lib = "lib";\n')
    write_text(repo_root / "js" / "app-theme.js", "console.log('theme')\n")
    write_text(repo_root / "js" / "gallery-config.js", "window.ARTIFACTS_CONFIG = {};\n")
    write_text(repo_root / "js" / "data.js", "window.ARTIFACTS_DATA = [];\n")
    write_text(repo_root / "apps" / "sample" / "name.txt", "Sample App\n")
    write_text(repo_root / "apps" / "sample" / "description.txt", "Sample app description.\n")
    write_text(
        repo_root / "apps" / "sample" / "index.html",
        "".join(
            [
                '<link rel="canonical" href="__APP_URL__">\n',
                '<meta property="og:url" content="__APP_URL__">\n',
                '<meta property="og:image" content="__APP_THUMBNAIL_URL__">\n',
                '<meta property="og:image:secure_url" content="__APP_THUMBNAIL_URL__">\n',
                '<meta name="twitter:image" content="__APP_THUMBNAIL_URL__">\n',
                '<meta property="og:title" content="__APP_TITLE__">\n',
                '<meta property="og:description" content="__APP_DESCRIPTION__">\n',
                '<link rel="stylesheet" href="../../css/style.css">\n',
                '<link rel="stylesheet" href="./css/app.css">\n',
                '<script src="../../js/app-theme.js"></script>\n',
                '<script type="module" src="./js/app.js"></script>\n',
            ]
        ),
    )
    write_text(repo_root / "apps" / "sample" / "css" / "app.css", ".sample { display: block; }\n")
    write_text(repo_root / "apps" / "sample" / "js" / "app.js", "console.log('app')\n")
    (repo_root / "apps" / "sample" / "thumbnail.webp").write_bytes(b"webp")
    write_text(
        repo_root / "assets" / "icons" / "manifest.webmanifest",
        '{\n  "start_url": "../../"\n}\n',
    )
    (repo_root / "assets" / "icons" / "favicon.ico").write_bytes(b"ico")
    (repo_root / "assets" / "icons" / "icon.svg").write_bytes(b"<svg/>")
    (repo_root / "assets" / "social").mkdir(parents=True, exist_ok=True)
    (repo_root / "assets" / "social" / "share-preview.png").write_bytes(b"png")


def test_normalize_site_path() -> None:
    """Test normalize site path."""
    assert prepare_site._normalize_site_path("/artifacts/") == "/artifacts/"
    assert prepare_site._normalize_site_path("artifacts") == "/artifacts/"
    assert prepare_site._normalize_site_path("/") == "/"


def test_load_site_path_reads_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test load site path reads pyproject."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_path = "artifacts"\n')
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    assert prepare_site._load_site_path() == "/artifacts/"


def test_load_site_url_reads_pyproject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test load site url reads pyproject."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, '[tool.artifacts]\nsite_url = "https://example.com/demo"\n')
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    assert prepare_site._load_site_url() == "https://example.com/demo/"


def test_load_site_url_errors_for_missing_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load site url errors for missing pyproject."""
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", tmp_path / "pyproject.toml")

    with pytest.raises(FileNotFoundError, match=r"pyproject.toml not found"):
        prepare_site._load_site_url()


def test_load_site_url_errors_for_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load site url errors for missing config."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.other]\nvalue = true\n")
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    with pytest.raises(ValueError, match=r"Missing tool.artifacts.site_url"):
        prepare_site._load_site_url()


def test_load_site_path_errors_for_missing_pyproject(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load site path errors for missing pyproject."""
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", tmp_path / "pyproject.toml")

    with pytest.raises(FileNotFoundError, match=r"pyproject.toml not found"):
        prepare_site._load_site_path()


def test_load_site_path_errors_for_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test load site path errors for missing config."""
    pyproject = tmp_path / "pyproject.toml"
    write_text(pyproject, "[tool.other]\nvalue = true\n")
    monkeypatch.setattr(prepare_site, "PYPROJECT_FILE", pyproject)

    with pytest.raises(ValueError, match=r"Missing tool.artifacts.site_path"):
        prepare_site._load_site_path()


def test_resolve_version_prefers_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolve version prefers environment."""
    monkeypatch.setenv(prepare_site.DEPLOY_VERSION_ENV_VAR, "abc123")

    assert prepare_site._resolve_version() == "abc123"


def test_resolve_version_uses_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolve version uses git."""
    monkeypatch.delenv(prepare_site.DEPLOY_VERSION_ENV_VAR, raising=False)

    observed: dict[str, object] = {}

    def fake_check_output(*_args: object, **kwargs: object) -> str:
        """Fake check output."""
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
    """Test resolve version propagates git timeout."""
    monkeypatch.delenv(prepare_site.DEPLOY_VERSION_ENV_VAR, raising=False)

    def raise_git_timeout(*_args: object, **_kwargs: object) -> str:
        """Raise git timeout."""
        raise subprocess.TimeoutExpired(["git", "rev-parse", "--short", "HEAD"], 10)

    monkeypatch.setattr(prepare_site.subprocess, "check_output", raise_git_timeout)

    with pytest.raises(subprocess.TimeoutExpired):
        prepare_site._resolve_version()


def test_replace_exact_requires_expected_content() -> None:
    """Test replace exact requires expected content."""
    assert prepare_site._replace_exact("hello world", "world", "repo") == "hello repo"

    with pytest.raises(ValueError, match="Expected content not found"):
        prepare_site._replace_exact("hello", "missing", "repo")


def test_copy_deploy_items_copies_expected_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test copy deploy items copies expected paths."""
    create_source_tree(tmp_path)
    deploy_dir = tmp_path / "_site"
    write_text(deploy_dir / "stale.txt", "stale\n")

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._copy_deploy_items()

    assert (deploy_dir / "404.html").exists()
    assert (deploy_dir / "apps" / "sample" / "index.html").exists()
    assert not (deploy_dir / "stale.txt").exists()


def test_remove_build_only_sources_removes_stylesheet_partials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build-only stylesheet partials are omitted from the deploy payload."""
    create_source_tree(tmp_path)
    write_text(tmp_path / "css" / "src" / "01-tokens.css", "/* tokens */\n")
    deploy_dir = tmp_path / "_site"

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._copy_deploy_items()
    prepare_site._remove_build_only_sources()

    assert (deploy_dir / "css" / "style.css").exists()
    assert not (deploy_dir / "css" / "src").exists()


def test_remove_build_only_sources_skips_missing_source_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Build-only source removal is safe when the directory is absent."""
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._remove_build_only_sources()


def test_copy_deploy_items_errors_for_missing_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test copy deploy items errors for missing source."""
    write_text(
        tmp_path / "config" / "artifact_contract.json",
        '{"artifactIdPattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$", '
        '"artifactBasePath": "apps", "thumbnailFile": "thumbnail.webp"}\n',
    )
    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path / "_site")

    with pytest.raises(FileNotFoundError, match="Required deploy path not found"):
        prepare_site._copy_deploy_items()


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_copy_deploy_items_rejects_symlinked_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test copy deploy items rejects symlinked inputs."""
    create_source_tree(tmp_path)
    linked_target = tmp_path / "shared.js"
    write_text(linked_target, "console.log('linked')\n")
    (tmp_path / "js" / "app.js").unlink()
    (tmp_path / "js" / "app.js").symlink_to(linked_target)

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path / "_site")

    with pytest.raises(ValueError, match="Refusing to process tree containing symlink"):
        prepare_site._copy_deploy_items()


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlinks unavailable")
def test_copy_deploy_items_rejects_top_level_symlinked_deploy_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test copy deploy items rejects top level symlinked deploy paths."""
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
    """Test patch index html applies cache busting."""
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


def test_patch_app_asset_references_versions_app_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch app asset references versions app assets."""
    deploy_dir = tmp_path / "_site"
    app_index = deploy_dir / "apps" / "sample" / "index.html"
    write_text(
        app_index,
        "".join(
            [
                '<link rel="stylesheet" href="../../css/style.css">\n',
                '<link rel="stylesheet" href="./css/app.css">\n',
                '<script src="../../js/app-theme.js"></script>\n',
                '<script type="module" src="./js/app.js"></script>\n',
            ]
        ),
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_asset_references("abc123")

    content = app_index.read_text(encoding="utf-8")
    assert 'href="../../css/style.css?v=abc123"' in content
    assert 'href="./css/app.css?v=abc123"' in content
    assert 'src="../../js/app-theme.js?v=abc123"' in content
    assert 'src="./js/app.js?v=abc123"' in content


def test_patch_app_asset_references_skips_missing_apps_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch app asset references skips missing apps dir."""
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_asset_references("abc123")


def test_patch_app_asset_references_skips_non_matching_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Patch app asset references skips non matching entries."""
    deploy_dir = tmp_path / "_site"
    apps_dir = deploy_dir / "apps"
    write_text(apps_dir / "notes.txt", "ignore\n")
    (apps_dir / "empty-app").mkdir()
    plain_index = apps_dir / "plain-app" / "index.html"
    write_text(plain_index, "<p>No shared stylesheet.</p>\n")
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_asset_references("abc123")

    assert plain_index.read_text(encoding="utf-8") == "<p>No shared stylesheet.</p>\n"


def test_patch_social_metadata_injects_absolute_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test patch social metadata injects absolute urls."""
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
    assert 'content="https://example.com/demo/assets/social/share-preview.png?v=abc123"' in content


def test_patch_app_social_metadata_injects_per_app_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test patch app social metadata injects per app values."""
    deploy_dir = tmp_path / "_site"
    app_dir = deploy_dir / "apps" / "sample"
    app_dir.mkdir(parents=True)
    write_text(app_dir / "name.txt", "Sample App\n")
    write_text(app_dir / "description.txt", "Sample app description.\n")
    write_text(
        app_dir / "index.html",
        '<link rel="canonical" href="__APP_URL__">\n'
        '<meta property="og:url" content="__APP_URL__">\n'
        '<meta property="og:image" content="__APP_THUMBNAIL_URL__">\n'
        '<meta property="og:image:secure_url" content="__APP_THUMBNAIL_URL__">\n'
        '<meta name="twitter:image" content="__APP_THUMBNAIL_URL__">\n'
        '<meta property="og:title" content="__APP_TITLE__">\n'
        '<meta property="og:description" content="__APP_DESCRIPTION__">\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_social_metadata("https://example.com/demo/", "abc123")

    content = (app_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="https://example.com/demo/apps/sample/"' in content
    assert 'content="https://example.com/demo/apps/sample/"' in content
    assert 'content="Sample App"' in content
    assert 'content="Sample app description."' in content
    assert 'content="https://example.com/demo/apps/sample/thumbnail.webp?v=abc123"' in content


def test_patch_app_social_metadata_skips_apps_without_placeholders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test patch app social metadata skips apps without placeholders."""
    deploy_dir = tmp_path / "_site"
    app_dir = deploy_dir / "apps" / "sample"
    app_dir.mkdir(parents=True)
    write_text(app_dir / "index.html", "<html><body>hello</body></html>\n")
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_social_metadata("https://example.com/demo/", "abc123")

    assert (app_dir / "index.html").read_text(
        encoding="utf-8"
    ) == "<html><body>hello</body></html>\n"


def test_patch_app_social_metadata_handles_missing_description(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test patch app social metadata handles missing description."""
    deploy_dir = tmp_path / "_site"
    app_dir = deploy_dir / "apps" / "sample"
    app_dir.mkdir(parents=True)
    write_text(app_dir / "name.txt", "Sample App\n")
    write_text(
        app_dir / "index.html",
        '<meta property="og:description" content="__APP_DESCRIPTION__">\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_social_metadata("https://example.com/demo/", "abc123")

    assert 'content=""' in (app_dir / "index.html").read_text(encoding="utf-8")


def test_patch_app_social_metadata_skips_when_apps_directory_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test patch app social metadata skips when apps directory is missing."""
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_social_metadata("https://example.com/demo/", "abc123")


def test_patch_app_social_metadata_skips_non_directory_entries_and_missing_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test patch app social metadata skips non directory entries and missing index."""
    deploy_dir = tmp_path / "_site"
    apps_dir = deploy_dir / "apps"
    apps_dir.mkdir(parents=True)
    write_text(apps_dir / "notes.txt", "ignore\n")
    (apps_dir / "empty-app").mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_social_metadata("https://example.com/demo/", "abc123")


def test_patch_404_html_injects_site_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test patch 404 html injects site path."""
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
    """Test patch 404 html preserves preview logic."""
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    original = (
        '<body data-site-path="/">\n'
        '<a id="home-link" href="/">Return to gallery</a>\n'
        "<script>"
        'const previewRoot = [...siteParts, "pr-preview", pathParts[siteParts.length + 1]];'
        "</script>\n"
    )
    write_text(deploy_dir / "404.html", original)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_404_html("/artifacts/")

    content = (deploy_dir / "404.html").read_text(encoding="utf-8")
    assert 'data-site-path="/artifacts/"' in content
    assert 'href="/artifacts/"' in content
    assert '"pr-preview"' in content


def test_patch_manifest_injects_site_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test patch manifest injects site path."""
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


def test_patch_manifest_skips_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test patch manifest skips when missing."""
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_manifest("/artifacts/")


def test_write_nojekyll_creates_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test write nojekyll creates marker."""
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._write_nojekyll()

    assert (deploy_dir / ".nojekyll").exists()


def test_resolve_commit_sha_prefers_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test resolve commit sha prefers environment."""
    monkeypatch.setenv(prepare_site.DEPLOY_COMMIT_SHA_ENV_VAR, "a" * 40)

    assert prepare_site._resolve_commit_sha() == "a" * 40


def test_resolve_commit_sha_uses_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolve commit sha uses git."""
    monkeypatch.delenv(prepare_site.DEPLOY_COMMIT_SHA_ENV_VAR, raising=False)

    observed: dict[str, object] = {}

    def fake_check_output(*_args: object, **kwargs: object) -> str:
        """Fake check output."""
        observed.update(kwargs)
        return "deadbeefcafefeed\n"

    monkeypatch.setattr(prepare_site.subprocess, "check_output", fake_check_output)

    assert prepare_site._resolve_commit_sha() == "deadbeefcafefeed"
    assert observed["timeout"] == prepare_site.GIT_COMMAND_TIMEOUT_SECONDS


def test_write_deploy_metadata_creates_expected_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test write deploy metadata creates expected json."""
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._write_deploy_metadata(
        commit_sha="a" * 40,
        version="abc1234",
        site_path="/artifacts/",
    )

    metadata = (deploy_dir / prepare_site.DEPLOY_METADATA_FILE).read_text(encoding="utf-8")
    assert '"commit_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"' in metadata
    assert '"version": "abc1234"' in metadata
    assert '"site_path": "/artifacts/"' in metadata


def test_prepare_site_builds_deploy_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test prepare site builds deploy output."""
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
    assert "@import" not in style_content
    if prepare_site.ESBUILD_BIN.exists():
        assert "body{margin:0}" in style_content
        assert ".artifact-card{display:block}" in style_content
    else:
        assert "body { margin: 0; }" in style_content
        assert ".artifact-card { display: block; }" in style_content
    assert not (deploy_dir / "css" / "src").exists()
    assert '<link rel="modulepreload" href="js/lib.js">' in index_content
    assert 'data-site-path="/artifacts/"' in error_content
    assert (deploy_dir / ".nojekyll").exists()
    assert (deploy_dir / "apps" / "sample" / "index.html").exists()
    sample_content = (deploy_dir / "apps" / "sample" / "index.html").read_text(encoding="utf-8")
    assert 'href="https://example.com/artifacts/apps/sample/"' in sample_content
    assert (
        'content="https://example.com/artifacts/apps/sample/thumbnail.webp?v=abc123"'
        in sample_content
    )
    assert 'href="../../css/style.css?v=abc123"' in sample_content
    assert 'href="./css/app.css?v=abc123"' in sample_content
    assert 'src="../../js/app-theme.js?v=abc123"' in sample_content
    assert 'src="./js/app.js?v=abc123"' in sample_content
    assert (deploy_dir / "apps" / "sample" / "css" / "app.css").exists()
    assert (deploy_dir / "assets" / "icons" / "favicon.ico").exists()
    assert (deploy_dir / "assets" / "social" / "share-preview.png").exists()
    metadata = (deploy_dir / prepare_site.DEPLOY_METADATA_FILE).read_text(encoding="utf-8")
    assert '"commit_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"' in metadata
    assert '"version": "abc123"' in metadata
    manifest = (deploy_dir / "assets" / "icons" / "manifest.webmanifest").read_text(
        encoding="utf-8"
    )
    assert '"start_url": "/artifacts/"' in manifest


def test_prepare_site_emits_debug_log_with_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test prepare site emits debug log with config."""
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

    with caplog.at_level(logging.DEBUG):
        prepare_site.prepare_site()

    assert "Config: site_path=" in caplog.text
    assert "/artifacts/" in caplog.text


def test_prepare_site_propagates_git_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test prepare site propagates git failures."""
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

    def raise_git_failure(*_args: object, **_kwargs: object) -> str:
        """Raise git failure."""
        raise subprocess.CalledProcessError(1, ["git", "rev-parse"])

    monkeypatch.setattr(prepare_site.subprocess, "check_output", raise_git_failure)

    with pytest.raises(subprocess.CalledProcessError):
        prepare_site.prepare_site()


# modulepreload hint injection


def test_resolve_module_tree_walks_imports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test resolve module tree walks imports."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(tmp_path / "js" / "app.js", 'import { init } from "./modules/init.js";\n')
    write_text(tmp_path / "js" / "modules" / "init.js", 'import { util } from "./util.js";\n')
    write_text(tmp_path / "js" / "modules" / "util.js", "export const util = 1;\n")

    deps = prepare_site._resolve_module_tree(tmp_path / "js" / "app.js")
    dep_names = [d.name for d in deps]
    assert "init.js" in dep_names
    assert "util.js" in dep_names


def test_resolve_module_tree_handles_cycles(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test resolve module tree handles cycles."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(tmp_path / "a.js", 'import { b } from "./b.js";\n')
    write_text(tmp_path / "b.js", 'import { a } from "./a.js";\n')

    deps = prepare_site._resolve_module_tree(tmp_path / "a.js")
    dep_names = [d.name for d in deps]
    assert "b.js" in dep_names
    assert len(deps) == 1


def test_resolve_module_tree_skips_missing_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test resolve module tree skips missing files."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(tmp_path / "app.js", 'import { x } from "./missing.js";\n')

    deps = prepare_site._resolve_module_tree(tmp_path / "app.js")
    assert deps == []


def test_resolve_module_tree_skips_outside_deploy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test resolve module tree skips outside deploy."""
    deploy = tmp_path / "deploy"
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy)
    write_text(deploy / "app.js", 'import { x } from "../../outside.js";\n')
    write_text(tmp_path / "outside.js", "export const x = 1;\n")

    deps = prepare_site._resolve_module_tree(deploy / "app.js")
    assert deps == []


def test_resolve_module_tree_follows_reexports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test resolve module tree follows reexports."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(tmp_path / "app.js", 'import { y } from "./barrel.js";\n')
    write_text(tmp_path / "barrel.js", 'export { y } from "./leaf.js";\n')
    write_text(tmp_path / "leaf.js", "export const y = 1;\n")

    dep_names = [d.name for d in prepare_site._resolve_module_tree(tmp_path / "app.js")]
    assert "barrel.js" in dep_names
    assert "leaf.js" in dep_names


def test_inject_modulepreload_hints_adds_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test inject modulepreload hints adds links."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(
        tmp_path / "index.html",
        '<head>\n</head>\n<body>\n<script type="module" src="js/app.js"></script>\n</body>\n',
    )
    write_text(tmp_path / "js" / "app.js", 'import { x } from "./lib.js";\n')
    write_text(tmp_path / "js" / "lib.js", "export const x = 1;\n")

    prepare_site._inject_modulepreload_hints()

    result = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<link rel="modulepreload" href="js/lib.js">' in result
    assert result.index("modulepreload") < result.index("</head>")


def test_inject_modulepreload_hints_handles_nested_apps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test inject modulepreload hints handles nested apps."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(
        tmp_path / "apps" / "demo" / "index.html",
        '<head>\n</head>\n<body>\n<script type="module" src="./js/app.js"></script>\n</body>\n',
    )
    write_text(
        tmp_path / "apps" / "demo" / "js" / "app.js",
        'import { init } from "../../../js/modules/runtime.js";\n',
    )
    write_text(tmp_path / "js" / "modules" / "runtime.js", "export const init = 1;\n")

    prepare_site._inject_modulepreload_hints()

    result = (tmp_path / "apps" / "demo" / "index.html").read_text(encoding="utf-8")
    assert '<link rel="modulepreload" href="../../js/modules/runtime.js">' in result


def test_inject_modulepreload_hints_strips_query_string(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test inject modulepreload hints strips query string."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(
        tmp_path / "index.html",
        "<head>\n</head>\n<body>\n"
        '<script type="module" src="js/app.js?v=abc123"></script>\n'
        "</body>\n",
    )
    write_text(tmp_path / "js" / "app.js", 'import { x } from "./lib.js";\n')
    write_text(tmp_path / "js" / "lib.js", "export const x = 1;\n")

    prepare_site._inject_modulepreload_hints()

    result = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<link rel="modulepreload" href="js/lib.js">' in result


def test_inject_modulepreload_hints_skips_html_without_module_script(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test inject modulepreload hints skips html without module script."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(tmp_path / "plain.html", "<head>\n</head>\n<body>\n</body>\n")

    prepare_site._inject_modulepreload_hints()

    result = (tmp_path / "plain.html").read_text(encoding="utf-8")
    assert "modulepreload" not in result


# -- minification tests --------------------------------------------------------

_requires_esbuild = pytest.mark.skipif(
    not prepare_site.ESBUILD_BIN.exists(),
    reason="esbuild not installed",
)


def test_is_minifiable_js_skips_vendor_and_min_files() -> None:
    """Test is minifiable js skips vendor and min files."""
    from pathlib import PurePosixPath

    assert prepare_site._is_minifiable_js(PurePosixPath("js/app.js"))
    assert prepare_site._is_minifiable_js(PurePosixPath("js/modules/gallery.js"))
    assert not prepare_site._is_minifiable_js(PurePosixPath("js/vendor/chart.umd.min.js"))
    assert not prepare_site._is_minifiable_js(PurePosixPath("js/lib.min.js"))
    assert not prepare_site._is_minifiable_js(PurePosixPath("data.json"))


@_requires_esbuild
def test_minify_file_reduces_css_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test minify file reduces css size."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    css_content = "/* comment */\nbody {\n  color: red;\n  margin: 0;\n}\n"
    css_file = tmp_path / "style.css"
    write_text(css_file, css_content)

    saved = prepare_site._minify_file(css_file)

    result = css_file.read_text(encoding="utf-8")
    assert saved > 0
    assert "/* comment */" not in result
    assert "color:" in result or "color:red" in result


@_requires_esbuild
def test_minify_file_reduces_js_size(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test minify file reduces js size."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    js_content = "// comment\nexport function hello() {\n  return 'world';\n}\n"
    js_file = tmp_path / "app.js"
    write_text(js_file, js_content)

    saved = prepare_site._minify_file(js_file)

    result = js_file.read_text(encoding="utf-8")
    assert saved > 0
    assert "// comment" not in result


@_requires_esbuild
def test_minify_site_assets_processes_css_and_js(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test minify site assets processes css and js."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    write_text(tmp_path / "css" / "style.css", "/* block */\nbody { margin: 0; }\n")
    write_text(tmp_path / "js" / "app.js", "// line\nconst x = 1;\n")
    write_text(
        tmp_path / "js" / "vendor" / "lib.min.js",
        "var a=1;",
    )

    vendor_content = (tmp_path / "js" / "vendor" / "lib.min.js").read_text(encoding="utf-8")

    prepare_site._minify_site_assets()

    css_result = (tmp_path / "css" / "style.css").read_text(encoding="utf-8")
    assert "/* block */" not in css_result

    js_result = (tmp_path / "js" / "app.js").read_text(encoding="utf-8")
    assert "// line" not in js_result

    vendor_result = (tmp_path / "js" / "vendor" / "lib.min.js").read_text(encoding="utf-8")
    assert vendor_result == vendor_content


def test_minify_site_assets_skips_when_esbuild_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test minify site assets skips when esbuild missing."""
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path)
    monkeypatch.setattr(prepare_site, "ESBUILD_BIN", tmp_path / "missing-bin")
    write_text(tmp_path / "css" / "style.css", "body { margin: 0; }\n")

    prepare_site._minify_site_assets()

    result = (tmp_path / "css" / "style.css").read_text(encoding="utf-8")
    assert result == "body { margin: 0; }\n"
