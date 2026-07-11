from __future__ import annotations

from pathlib import Path

import pytest

import scripts.build.scaffold_artifact as scaffold_artifact


def _install_temp_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """Point the scaffolder at throwaway apps/ and tests/ roots."""
    apps_dir = tmp_path / "apps"
    tests_js_apps_dir = tmp_path / "tests" / "js" / "apps"
    monkeypatch.setattr(scaffold_artifact, "APPS_DIR", apps_dir)
    monkeypatch.setattr(scaffold_artifact, "TESTS_JS_APPS_DIR", tests_js_apps_dir)
    return apps_dir, tests_js_apps_dir


def test_title_from_slug_formats_words() -> None:
    """Test title from slug formats words."""
    assert scaffold_artifact._title_from_slug("budget-tracker") == "Budget Tracker"


def test_index_template_includes_title() -> None:
    """Test index template includes title."""
    template = scaffold_artifact._index_template("Budget Tracker")

    assert "<title>Budget Tracker | Artifacts</title>" in template
    assert '<html lang="en" data-theme="light">' in template
    assert '<script src="../../js/app-theme.js"></script>' in template
    assert '<link rel="stylesheet" href="../../css/style.css">' in template
    assert '<link rel="stylesheet" href="./css/app.css">' in template
    assert '<body class="artifact-app">' in template
    assert '<script type="module" src="./js/app.js"></script>' in template
    assert 'data-app-shell="header"' in template
    assert 'data-app-shell="runtime-error"' in template
    assert 'data-app-shell="scroll-top"' in template
    assert '<h1 class="page-title">Budget Tracker</h1>' in template
    assert scaffold_artifact.CSP_CONTENT in template


def test_app_css_template_documents_palette_convention() -> None:
    """Test app css template keeps the rgb-only palette convention."""
    css = scaffold_artifact._app_css_template("Budget Tracker")

    assert css.startswith("/* Budget Tracker app layout. */\n")
    assert "rgb(...)" in css
    assert "never hex" in css


def test_app_test_template_imports_app_and_asserts_ready() -> None:
    """Test app test template imports the scaffolded app and checks a real state."""
    test_source = scaffold_artifact._app_test_template("budget-tracker", "Budget Tracker")

    assert "../../../../apps/budget-tracker/js/app.js" in test_source
    assert "../../common/app-entry-test-support.js" in test_source
    assert "__ARTIFACT_READY__" in test_source
    assert "'ready'" in test_source


def test_readme_template_drop_in_note_only_for_drop_ins() -> None:
    """Test readme template mentions optional shell wiring only for drop-ins."""
    standard = scaffold_artifact._readme_template("Budget Tracker")
    drop_in = scaffold_artifact._readme_template("Budget Tracker", drop_in=True)

    assert "optional for a" not in standard
    assert "optional for a" in drop_in


def test_find_external_references_detects_off_origin_resources() -> None:
    """Test external reference detection covers attributes and url() targets."""
    html = (
        '<link rel="stylesheet" href="https://cdn.example.com/app.css">'
        '<script src="//cdn.example.com/app.js"></script>'
        '<link rel="stylesheet" href="./css/app.css">'
        "<style>body { background: url('http://img.example.com/bg.png'); }</style>"
    )

    references = scaffold_artifact.find_external_references(html)

    assert references == [
        "//cdn.example.com/app.js",
        "http://img.example.com/bg.png",
        "https://cdn.example.com/app.css",
    ]


def test_find_external_references_returns_empty_for_self_contained() -> None:
    """Test external reference detection ignores local references."""
    html = '<link rel="stylesheet" href="./css/app.css"><script src="./js/app.js"></script>'

    assert scaffold_artifact.find_external_references(html) == []


def test_apply_contract_injects_missing_pieces() -> None:
    """Test contract application injects the CSP meta and stylesheet links."""
    html = "<html><head><title>Demo</title></head><body></body></html>"

    result = scaffold_artifact.apply_contract_to_source(html)

    assert scaffold_artifact.CSP_META in result
    assert scaffold_artifact.SHARED_STYLESHEET_LINK in result
    assert scaffold_artifact.APP_STYLESHEET_LINK in result
    # CSP lands after the opening head tag, the stylesheet links before its close.
    assert result.index(scaffold_artifact.CSP_META) < result.index(
        scaffold_artifact.SHARED_STYLESHEET_LINK
    )


def test_apply_contract_preserves_existing_pieces() -> None:
    """Test contract application leaves an already-compliant document untouched."""
    html = (
        "<html><head>"
        f"{scaffold_artifact.CSP_META}"
        f"{scaffold_artifact.SHARED_STYLESHEET_LINK}"
        f"{scaffold_artifact.APP_STYLESHEET_LINK}"
        "</head><body></body></html>"
    )

    assert scaffold_artifact.apply_contract_to_source(html) == html


def test_apply_contract_skips_existing_lowercase_csp() -> None:
    """Test contract application detects an existing CSP meta case-insensitively."""
    html = (
        "<html><head>"
        '<meta http-equiv="content-security-policy" content="default-src \'self\'">'
        f"{scaffold_artifact.SHARED_STYLESHEET_LINK}"
        f"{scaffold_artifact.APP_STYLESHEET_LINK}"
        "</head><body></body></html>"
    )

    assert scaffold_artifact.apply_contract_to_source(html) == html


def test_inject_after_head_open_without_head_uses_html_tag() -> None:
    """Test the head-open injector falls back to the opening html tag."""
    result = scaffold_artifact._inject_after_head_open(
        '<!DOCTYPE html><html lang="en"><body></body></html>', "SNIPPET"
    )

    assert result == '<!DOCTYPE html><html lang="en">\n  SNIPPET<body></body></html>'


def test_inject_after_head_open_without_html_uses_doctype() -> None:
    """Test the head-open injector keeps the doctype first when no html tag exists."""
    result = scaffold_artifact._inject_after_head_open("<!doctype html><body></body>", "SNIPPET")

    assert result == "<!doctype html>\n  SNIPPET<body></body>"


def test_inject_after_head_open_ignores_header_elements() -> None:
    """Test a body header element is not mistaken for an opening head tag."""
    result = scaffold_artifact._inject_after_head_open(
        '<header class="page-intro">x</header>', "SNIPPET"
    )

    assert result == 'SNIPPET\n<header class="page-intro">x</header>'


def test_inject_after_head_open_ignores_html5_like_tag() -> None:
    """Test an <html5>-style tag is not mistaken for an opening html tag."""
    result = scaffold_artifact._inject_after_head_open(
        "<html5-widget>x</html5-widget>", "SNIPPET"
    )

    assert result == "SNIPPET\n<html5-widget>x</html5-widget>"


def test_inject_after_head_open_without_head_prepends() -> None:
    """Test the head-open injector falls back to prepending when no head exists."""
    result = scaffold_artifact._inject_after_head_open("<body></body>", "SNIPPET")

    assert result == "SNIPPET\n<body></body>"


def test_inject_before_head_close_without_close_appends() -> None:
    """Test the head-close injector falls back to appending when no close exists."""
    result = scaffold_artifact._inject_before_head_close("<head>", "SNIPPET")

    assert result == "<head>\nSNIPPET"


def test_read_source_html_missing_file_raises(tmp_path: Path) -> None:
    """Test reading a missing drop-in HTML file raises FileNotFoundError."""
    missing = tmp_path / "missing.html"

    with pytest.raises(FileNotFoundError, match="Source HTML file not found"):
        scaffold_artifact._read_source_html(str(missing))


def test_scaffold_artifact_creates_expected_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test scaffold artifact creates expected files."""
    apps_dir, tests_js_apps_dir = _install_temp_roots(tmp_path, monkeypatch)

    artifact_dir = scaffold_artifact.scaffold_artifact("budget-tracker")

    assert artifact_dir == apps_dir / "budget-tracker"
    assert (artifact_dir / "index.html").exists()
    assert (artifact_dir / "css" / "app.css").exists()
    assert (artifact_dir / "js" / "app.js").exists()
    assert (artifact_dir / "README.md").exists()
    assert (artifact_dir / "docs" / "architecture.md").exists()
    assert (artifact_dir / "docs" / "verification.md").exists()
    assert (artifact_dir / "docs" / "decisions.md").exists()
    assert (tests_js_apps_dir / "budget-tracker").is_dir()
    assert (tests_js_apps_dir / "budget-tracker" / "app.test.js").exists()
    assert (artifact_dir / "name.txt").read_text(encoding="utf-8") == "Budget Tracker\n"
    assert (artifact_dir / "description.txt").read_text(encoding="utf-8") == "\n"
    assert (artifact_dir / "tags.txt").read_text(encoding="utf-8") == "\n"
    assert (artifact_dir / "tools.txt").read_text(encoding="utf-8") == "\n"

    index_html = (artifact_dir / "index.html").read_text(encoding="utf-8")
    app_js = (artifact_dir / "js" / "app.js").read_text(encoding="utf-8")
    app_test = (tests_js_apps_dir / "budget-tracker" / "app.test.js").read_text(encoding="utf-8")
    readme = (artifact_dir / "README.md").read_text(encoding="utf-8")

    assert "__APP_THUMBNAIL_URL__" in index_html
    assert '<script type="module" src="./js/app.js"></script>' in index_html
    assert '<link rel="stylesheet" href="../../css/style.css">' in index_html
    assert '<link rel="stylesheet" href="./css/app.css">' in index_html
    assert '<body class="artifact-app app-budget-tracker">' in index_html
    assert "renderAppShell();" in app_js
    assert "initAppShell" in app_js
    assert "initializeMatureApp" in app_js
    assert "../../../../apps/budget-tracker/js/app.js" in app_test
    assert (
        (artifact_dir / "css" / "app.css")
        .read_text(encoding="utf-8")
        .startswith("/* Budget Tracker app layout. */\n")
    )
    assert "# Budget Tracker" in readme
    assert "optional for a" not in readme


def test_scaffold_artifact_installs_source_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the drop-in flow installs the provided HTML and guarantees the contract."""
    _install_temp_roots(tmp_path, monkeypatch)
    source = tmp_path / "provided.html"
    source.write_text(
        "<html><head><title>Provided</title></head><body><h1>Provided body</h1></body></html>",
        encoding="utf-8",
    )

    artifact_dir = scaffold_artifact.scaffold_artifact("budget-tracker", source_html=str(source))

    index_html = (artifact_dir / "index.html").read_text(encoding="utf-8")
    readme = (artifact_dir / "README.md").read_text(encoding="utf-8")
    captured = capsys.readouterr()

    assert "<h1>Provided body</h1>" in index_html
    assert scaffold_artifact.CSP_META in index_html
    assert scaffold_artifact.SHARED_STYLESHEET_LINK in index_html
    assert scaffold_artifact.APP_STYLESHEET_LINK in index_html
    # The scaffold still emits the standard app-local files and test.
    assert (artifact_dir / "js" / "app.js").exists()
    assert (artifact_dir / "css" / "app.css").exists()
    assert "optional for a" in readme
    # A clean self-contained page produces no external-resource warning.
    assert captured.err == ""


def test_scaffold_artifact_reports_external_references(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test the drop-in flow reports off-origin references without rewriting them."""
    _install_temp_roots(tmp_path, monkeypatch)
    source = tmp_path / "provided.html"
    source.write_text(
        "<html><head>"
        '<script src="https://cdn.example.com/lib.js"></script>'
        "</head><body></body></html>",
        encoding="utf-8",
    )

    artifact_dir = scaffold_artifact.scaffold_artifact("budget-tracker", source_html=str(source))

    index_html = (artifact_dir / "index.html").read_text(encoding="utf-8")
    captured = capsys.readouterr()

    # Reported, not rewritten: the reference remains in the installed page.
    assert 'src="https://cdn.example.com/lib.js"' in index_html
    assert "off-origin resources" in captured.err
    assert "https://cdn.example.com/lib.js" in captured.err


def test_scaffold_artifact_rejects_missing_name() -> None:
    """Test scaffold artifact rejects missing name."""
    with pytest.raises(ValueError, match="Artifact name is required"):
        scaffold_artifact.scaffold_artifact("")


def test_scaffold_artifact_rejects_non_kebab_case_name() -> None:
    """Test scaffold artifact rejects non kebab case name."""
    with pytest.raises(ValueError, match="Artifact name must use kebab-case"):
        scaffold_artifact.scaffold_artifact("BudgetTracker")


def test_scaffold_artifact_rejects_existing_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test scaffold artifact rejects existing directory."""
    apps_dir, _ = _install_temp_roots(tmp_path, monkeypatch)
    (apps_dir / "budget-tracker").mkdir(parents=True)

    with pytest.raises(FileExistsError, match="Artifact directory already exists"):
        scaffold_artifact.scaffold_artifact("budget-tracker")


def test_scaffold_artifact_rejects_existing_directory_before_reading_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test an existing directory fails before the source HTML is read or warned about."""
    apps_dir, _ = _install_temp_roots(tmp_path, monkeypatch)
    (apps_dir / "budget-tracker").mkdir(parents=True)
    source = tmp_path / "provided.html"
    source.write_text(
        "<html><head>"
        '<script src="https://cdn.example.com/lib.js"></script>'
        "</head><body></body></html>",
        encoding="utf-8",
    )

    def _fail_read(_path: str) -> str:
        raise AssertionError("source HTML must not be read when the directory exists")

    monkeypatch.setattr(scaffold_artifact, "_read_source_html", _fail_read)

    with pytest.raises(FileExistsError, match="Artifact directory already exists"):
        scaffold_artifact.scaffold_artifact("budget-tracker", source_html=str(source))

    assert capsys.readouterr().err == ""


def test_main_scaffolds_artifact_and_returns_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main scaffolds artifact and returns zero."""
    _install_temp_roots(tmp_path, monkeypatch)

    result = scaffold_artifact.main(["budget-tracker"])

    captured = capsys.readouterr()
    assert result == 0
    assert "Created artifact scaffold" in captured.out


def test_main_accepts_from_html_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main installs a drop-in HTML file through the --from-html flag."""
    apps_dir, _ = _install_temp_roots(tmp_path, monkeypatch)
    source = tmp_path / "provided.html"
    source.write_text("<html><head></head><body><p>Drop in</p></body></html>", encoding="utf-8")

    result = scaffold_artifact.main(["budget-tracker", "--from-html", str(source)])

    captured = capsys.readouterr()
    assert result == 0
    assert "Created artifact scaffold" in captured.out
    index_html = (apps_dir / "budget-tracker" / "index.html").read_text(encoding="utf-8")
    assert "<p>Drop in</p>" in index_html


def test_scaffold_artifact_creates_tests_directory_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test scaffold artifact creates tests directory when missing."""
    _, tests_js_apps_dir = _install_temp_roots(tmp_path, monkeypatch)

    scaffold_artifact.scaffold_artifact("budget-tracker")

    assert tests_js_apps_dir.is_dir()
    assert (tests_js_apps_dir / "budget-tracker").is_dir()


def test_main_requires_exactly_one_positional_argument() -> None:
    """Test main requires a name argument."""
    with pytest.raises(ValueError, match="Usage: make new name=<artifact-name>"):
        scaffold_artifact.main([])


def test_parse_args_rejects_unknown_flag() -> None:
    """Test the CLI parser rejects an unexpected trailing argument."""
    with pytest.raises(ValueError, match="Usage: make new name=<artifact-name>"):
        scaffold_artifact._parse_args(["budget-tracker", "--bogus", "value"])
