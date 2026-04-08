from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import scripts.build.prepare_site as prepare_site


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_source_tree(repo_root: Path) -> None:
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
            ]
        ),
    )
    write_text(
        repo_root / "css" / "style.css",
        "".join(
            [
                '@import url("./gallery/01-tokens.css");\n',
                '@import url("./gallery/09-cards.css");\n',
                '@import url("./gallery/13-responsive.css");\n',
            ]
        ),
    )
    gallery_dir = repo_root / "css" / "gallery"
    gallery_dir.mkdir(parents=True, exist_ok=True)
    write_text(gallery_dir / "01-tokens.css", "body {}\n")
    write_text(gallery_dir / "09-cards.css", ".artifact-card {}\n")
    write_text(
        gallery_dir / "13-responsive.css",
        "@media (max-width: 1px) {}\n",
    )
    write_text(repo_root / "js" / "app.js", "console.log('app')\n")
    write_text(
        repo_root / "js" / "gallery-config.js", "window.ARTIFACTS_CONFIG = {};\n"
    )
    write_text(repo_root / "js" / "data.js", "window.ARTIFACTS_DATA = [];\n")
    write_text(repo_root / "apps" / "sample" / "name.txt", "Sample App\n")
    write_text(
        repo_root / "apps" / "sample" / "description.txt", "Sample app description.\n"
    )
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
            ]
        ),
    )
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
    create_source_tree(tmp_path)
    linked_target = tmp_path / "shared.js"
    write_text(linked_target, "console.log('linked')\n")
    (tmp_path / "js" / "app.js").unlink()
    (tmp_path / "js" / "app.js").symlink_to(linked_target)

    monkeypatch.setattr(prepare_site, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", tmp_path / "_site")

    with pytest.raises(
        ValueError, match="Refusing to process tree containing symlink"
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


def test_patch_app_social_metadata_injects_per_app_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    assert (
        'content="https://example.com/demo/apps/sample/thumbnail.webp?v=abc123"'
        in content
    )


def test_patch_app_social_metadata_skips_apps_without_placeholders(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_social_metadata("https://example.com/demo/", "abc123")


def test_patch_app_social_metadata_skips_non_directory_entries_and_missing_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    apps_dir = deploy_dir / "apps"
    apps_dir.mkdir(parents=True)
    write_text(apps_dir / "notes.txt", "ignore\n")
    (apps_dir / "empty-app").mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_app_social_metadata("https://example.com/demo/", "abc123")


def test_inline_css_imports_concatenates_partials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    css_dir = deploy_dir / "css"
    gallery_dir = css_dir / "gallery"
    gallery_dir.mkdir(parents=True)
    write_text(gallery_dir / "01-tokens.css", ":root { --color-bg: #fff; }\n")
    write_text(gallery_dir / "02-reset.css", "* { margin: 0; }\n")
    write_text(
        css_dir / "style.css",
        '/* gallery */\n@import url("./gallery/01-tokens.css");\n'
        '@import url("./gallery/02-reset.css");\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._inline_css_imports(css_dir / "style.css")

    content = (css_dir / "style.css").read_text(encoding="utf-8")
    assert "@import" not in content
    assert ":root { --color-bg: #fff; }" in content
    assert "* { margin: 0; }" in content


def test_inline_all_css_imports_removes_partial_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    css_dir = deploy_dir / "css"
    gallery_dir = css_dir / "gallery"
    app_dir = css_dir / "app"
    gallery_dir.mkdir(parents=True)
    app_dir.mkdir(parents=True)
    write_text(gallery_dir / "01-tokens.css", "body {}\n")
    write_text(app_dir / "01-reset.css", "html {}\n")
    write_text(css_dir / "style.css", '@import url("./gallery/01-tokens.css");\n')
    write_text(css_dir / "app-shell.css", '@import url("./app/01-reset.css");\n')
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._inline_all_css_imports()

    assert not gallery_dir.exists()
    assert not app_dir.exists()
    assert "body {}" in (css_dir / "style.css").read_text(encoding="utf-8")
    assert "html {}" in (css_dir / "app-shell.css").read_text(encoding="utf-8")


def test_inline_css_imports_keeps_import_when_partial_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    css_dir = deploy_dir / "css"
    css_dir.mkdir(parents=True)
    write_text(
        css_dir / "style.css",
        '@import url("./gallery/missing.css");\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._inline_css_imports(css_dir / "style.css")

    content = (css_dir / "style.css").read_text(encoding="utf-8")
    assert '@import url("./gallery/missing.css");' in content


def test_inline_css_imports_blocks_path_traversal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    css_dir = deploy_dir / "css"
    css_dir.mkdir(parents=True)
    secret_file = tmp_path / "secret.css"
    write_text(secret_file, "body { color: red; }\n")
    write_text(
        css_dir / "style.css",
        '@import url("./../../secret.css");\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._inline_css_imports(css_dir / "style.css")

    content = (css_dir / "style.css").read_text(encoding="utf-8")
    assert '@import url("./../../secret.css");' in content
    assert "color: red" not in content


def test_inline_css_imports_skips_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    deploy_dir.mkdir()
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._inline_css_imports(deploy_dir / "css" / "nonexistent.css")


def test_patch_root_stylesheet_versions_imports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    deploy_dir = tmp_path / "_site"
    styles_dir = deploy_dir / "css"
    styles_dir.mkdir(parents=True)
    write_text(
        styles_dir / "style.css",
        '@import url("./gallery/01-tokens.css");\n'
        '@import url("./gallery/09-cards.css");\n',
    )
    monkeypatch.setattr(prepare_site, "DEPLOY_DIR", deploy_dir)

    prepare_site._patch_root_stylesheet("abc123")

    content = (styles_dir / "style.css").read_text(encoding="utf-8")
    assert '@import url("./gallery/01-tokens.css?v=abc123");' in content
    assert '@import url("./gallery/09-cards.css?v=abc123");' in content


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
    assert "@import" not in style_content
    assert "body {}" in style_content
    assert ".artifact-card {}" in style_content
    assert not (deploy_dir / "css" / "gallery").exists()
    assert 'data-site-path="/artifacts/"' in error_content
    assert (deploy_dir / ".nojekyll").exists()
    assert (deploy_dir / "apps" / "sample" / "index.html").exists()
    sample_content = (deploy_dir / "apps" / "sample" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'href="https://example.com/artifacts/apps/sample/"' in sample_content
    assert (
        'content="https://example.com/artifacts/apps/sample/thumbnail.webp?v=abc123"'
        in sample_content
    )
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
