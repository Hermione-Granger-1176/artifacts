"""Tests for the artifact CSP and same-origin reference lint check."""

from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path

from scripts import REPO_ROOT
from scripts.lint.check_artifact_csp import (
    _ROOT_IMG_SOURCES,
    _is_external_reference,
    check_page,
    discover_artifact_pages,
    main,
    run_check,
)

_GOOD_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'"
)
_ROOT_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data: https://img.shields.io; connect-src 'self'"
)


def _page(csp: str = _GOOD_CSP, *, head: str = "", body: str = "") -> str:
    """Build one artifact page with a chosen CSP and extra markup."""
    return (
        "<!doctype html>\n<html>\n<head>\n"
        f'  <meta http-equiv="Content-Security-Policy" content="{csp}">\n'
        '  <link rel="stylesheet" href="../../css/style.css">\n'
        '  <script src="../../js/app-theme.js"></script>\n'
        f"{head}"
        "</head>\n<body>\n"
        f"{body}"
        '  <script type="module" src="./js/app.js"></script>\n'
        "</body>\n</html>\n"
    )


def _write_page(root: Path, slug: str, html: str) -> Path:
    """Write an artifact page at ``apps/<slug>/index.html`` under a root."""
    path = root / "apps" / slug / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    return path


def _write_root_page(root: Path, csp: str = _ROOT_CSP) -> Path:
    """Write the root index with its documented shield-image CSP exception."""
    path = root / "index.html"
    path.write_text(_page(csp), encoding="utf-8")
    return path


def _inline_content_hash(html: str, tag_name: str) -> str:
    """Return the CSP SHA-256 source expression for one inline tag's contents."""
    match = re.search(rf"<{tag_name}>(.*?)</{tag_name}>", html, re.DOTALL)
    assert match is not None, f"404.html must include an inline {tag_name} block"
    digest = hashlib.sha256(match.group(1).encode("utf-8")).digest()
    return f"'sha256-{base64.b64encode(digest).decode('ascii')}'"


def test_404_csp_hashes_allow_its_self_contained_style_and_script() -> None:
    """The arbitrary-path 404 page allows only its exact inline resources."""
    html = (REPO_ROOT / "404.html").read_text(encoding="utf-8")
    policy_match = re.search(
        r'<meta http-equiv="Content-Security-Policy"\s+content="([^"]+)">', html
    )
    assert policy_match is not None
    policy = policy_match.group(1)

    assert "default-src 'self'" in policy
    assert "object-src 'none'" in policy
    missing_hashes = [
        content_hash
        for content_hash in (
            _inline_content_hash(html, "style"),
            _inline_content_hash(html, "script"),
        )
        if content_hash not in policy
    ]
    assert not missing_hashes, f"404.html is missing CSP hash(es): {missing_hashes}"


def test_check_page_passes_for_strict_page(tmp_path: Path) -> None:
    """Check page passes for strict page."""
    path = _write_page(tmp_path, "demo", _page())
    assert check_page(path, display_path="apps/demo/index.html") == []


def test_check_page_allows_the_root_badge_image_exception(tmp_path: Path) -> None:
    """The root may use shields.io while artifact pages remain self-hosted."""
    path = _write_root_page(tmp_path)
    assert (
        check_page(
            path,
            display_path="index.html",
            allowed_img_sources=_ROOT_IMG_SOURCES,
        )
        == []
    )


def test_check_page_rejects_the_root_badge_image_exception_for_an_artifact(tmp_path: Path) -> None:
    """Artifacts cannot inherit the root's narrow external image allowlist."""
    path = _write_page(tmp_path, "demo", _page(_ROOT_CSP))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any("img-src must use only approved image sources" in message for message in violations)


def test_check_page_rejects_unapproved_root_image_source(tmp_path: Path) -> None:
    """The root badge exception cannot become a general external image allowlist."""
    csp = "default-src 'self'; script-src 'self'; img-src 'self' https://example.com"
    path = _write_root_page(tmp_path, csp)
    violations = check_page(
        path,
        display_path="index.html",
        allowed_img_sources=_ROOT_IMG_SOURCES,
    )
    assert any("img-src must use only approved image sources" in message for message in violations)


def test_check_page_reports_non_utf8_page_as_violation(tmp_path: Path) -> None:
    """A binary page is reported as a violation instead of crashing."""
    path = tmp_path / "apps" / "demo" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    violations = check_page(path, display_path="apps/demo/index.html")
    assert len(violations) == 1
    assert violations[0].startswith("apps/demo/index.html: page could not be read as UTF-8 text")


def test_check_page_reports_unreadable_page_as_violation(tmp_path: Path) -> None:
    """An OSError while reading (here a directory) becomes a violation."""
    path = tmp_path / "apps" / "demo" / "index.html"
    path.mkdir(parents=True)
    violations = check_page(path, display_path="apps/demo/index.html")
    assert len(violations) == 1
    assert violations[0].startswith("apps/demo/index.html: page could not be read as UTF-8 text")


def test_check_page_flags_missing_csp(tmp_path: Path) -> None:
    """Check page flags missing csp."""
    # A non-CSP meta tag exercises the "skip other meta tags" path.
    html = '<html><head><meta charset="utf-8"><title>x</title></head><body></body></html>'
    path = _write_page(tmp_path, "demo", html)
    violations = check_page(path, display_path="apps/demo/index.html")
    assert violations == ["apps/demo/index.html: missing Content-Security-Policy meta tag"]


def test_check_page_flags_missing_default_src(tmp_path: Path) -> None:
    """Check page flags missing default src."""
    path = _write_page(tmp_path, "demo", _page(csp="script-src 'self'"))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any("missing a default-src directive" in message for message in violations)


def test_check_page_flags_relaxed_default_src(tmp_path: Path) -> None:
    """Check page flags relaxed default src."""
    path = _write_page(tmp_path, "demo", _page(csp="default-src *; script-src 'self'"))
    violations = check_page(path, display_path="apps/demo/index.html")
    expected = (
        "apps/demo/index.html: default-src must be restricted to 'self' or 'none' "
        "(found: default-src *)"
    )
    assert expected in violations


def test_check_page_flags_relaxed_script_src(tmp_path: Path) -> None:
    """Check page flags relaxed script src."""
    csp = "default-src 'self'; script-src 'self' https://cdn.example.com"
    path = _write_page(tmp_path, "demo", _page(csp=csp))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any(
        "script-src must be restricted to 'self' or 'none'" in message for message in violations
    )


def test_check_page_allows_script_src_falling_back_to_default(tmp_path: Path) -> None:
    """Check page allows script src falling back to default."""
    # The trailing semicolon exercises the empty-directive skip while script-src
    # falls back to the restrictive default-src.
    path = _write_page(tmp_path, "demo", _page(csp="default-src 'self';"))
    assert check_page(path, display_path="apps/demo/index.html") == []


def test_check_page_flags_empty_default_src(tmp_path: Path) -> None:
    """Check page flags empty default src."""
    path = _write_page(tmp_path, "demo", _page(csp="default-src; script-src 'self'"))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any(
        "default-src must be restricted to 'self' or 'none'" in message for message in violations
    )


def test_check_page_flags_missing_both_directives(tmp_path: Path) -> None:
    """Check page flags missing both directives without a script-src error."""
    path = _write_page(tmp_path, "demo", _page(csp="img-src 'self'"))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any("missing a default-src directive" in message for message in violations)
    assert not any("script-src" in message for message in violations)


def test_check_page_flags_external_script_src(tmp_path: Path) -> None:
    """Check page flags external script src."""
    head = '  <script src="https://cdn.example.com/lib.js"></script>\n'
    path = _write_page(tmp_path, "demo", _page(head=head))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert (
        "apps/demo/index.html: external script src not allowed: https://cdn.example.com/lib.js"
        in violations
    )


def test_check_page_flags_protocol_relative_script_src(tmp_path: Path) -> None:
    """Check page flags protocol relative script src."""
    head = '  <script src="//cdn.example.com/lib.js"></script>\n'
    path = _write_page(tmp_path, "demo", _page(head=head))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any("external script src not allowed: //cdn.example.com/lib.js" in m for m in violations)


def test_check_page_flags_external_stylesheet(tmp_path: Path) -> None:
    """Check page flags external stylesheet."""
    head = "  <link rel='stylesheet' href='https://fonts.example.com/style.css'>\n"
    path = _write_page(tmp_path, "demo", _page(head=head))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any(
        "external stylesheet href not allowed: https://fonts.example.com/style.css" in message
        for message in violations
    )


def test_check_page_ignores_non_stylesheet_external_link(tmp_path: Path) -> None:
    """Check page ignores non stylesheet external link."""
    head = '  <link rel="canonical" href="https://example.com/app/">\n'
    path = _write_page(tmp_path, "demo", _page(head=head))
    assert check_page(path, display_path="apps/demo/index.html") == []


def test_check_page_ignores_stylesheet_without_href(tmp_path: Path) -> None:
    """Check page ignores stylesheet without href."""
    head = "  <link rel=stylesheet>\n"
    path = _write_page(tmp_path, "demo", _page(head=head))
    assert check_page(path, display_path="apps/demo/index.html") == []


def test_check_page_flags_external_css_url(tmp_path: Path) -> None:
    """Check page flags external css url."""
    body = "  <style>.hero { background: url('https://cdn.example.com/bg.png'); }</style>\n"
    path = _write_page(tmp_path, "demo", _page(body=body))
    violations = check_page(path, display_path="apps/demo/index.html")
    assert any(
        "external url() reference not allowed: https://cdn.example.com/bg.png" in message
        for message in violations
    )


def test_check_page_allows_inline_data_and_relative_css_urls(tmp_path: Path) -> None:
    """Check page allows inline data and relative css urls."""
    body = (
        "  <style>\n"
        "    .a { background: url(data:image/png;base64,AAAA); }\n"
        '    .b { background: url("./assets/bg.png"); }\n'
        "    .c { clip-path: url(#mask); }\n"
        "  </style>\n"
    )
    path = _write_page(tmp_path, "demo", _page(body=body))
    assert check_page(path, display_path="apps/demo/index.html") == []


def test_check_page_allows_uppercase_data_url(tmp_path: Path) -> None:
    """Check page allows a data URL whose scheme is uppercased."""
    body = "  <style>.a { background: url(DATA:image/png;base64,AAAA); }</style>\n"
    path = _write_page(tmp_path, "demo", _page(body=body))
    assert check_page(path, display_path="apps/demo/index.html") == []


def test_is_external_reference_classifies_references() -> None:
    """Is external reference classifies references."""
    assert _is_external_reference("https://example.com/x.js")
    assert _is_external_reference("//example.com/x.js")
    assert _is_external_reference("data:text/js,alert(1)")
    assert not _is_external_reference("./local.js")
    assert not _is_external_reference("../../js/app.js")
    assert not _is_external_reference("/absolute/path.js")
    assert not _is_external_reference("   ")


def test_discover_artifact_pages_returns_sorted_pages(tmp_path: Path) -> None:
    """Discover artifact pages returns sorted pages."""
    _write_page(tmp_path, "beta", _page())
    _write_page(tmp_path, "alpha", _page())
    pages = discover_artifact_pages(tmp_path / "apps")
    assert [page.parent.name for page in pages] == ["alpha", "beta"]


def test_discover_artifact_pages_handles_missing_apps_dir(tmp_path: Path) -> None:
    """Discover artifact pages handles missing apps dir."""
    assert discover_artifact_pages(tmp_path / "apps") == []


def test_run_check_aggregates_violations(tmp_path: Path) -> None:
    """Run check aggregates violations."""
    _write_root_page(tmp_path)
    _write_page(tmp_path, "good", _page())
    _write_page(tmp_path, "bad", _page(csp="default-src *"))
    violations = run_check(tmp_path)
    assert any(message.startswith("apps/bad/index.html") for message in violations)
    assert not any(message.startswith("apps/good/index.html") for message in violations)


def test_main_returns_zero_when_clean(tmp_path: Path) -> None:
    """Main returns zero when clean."""
    _write_root_page(tmp_path)
    _write_page(tmp_path, "demo", _page())
    assert main(["--root", str(tmp_path)]) == 0


def test_main_returns_one_when_violations(tmp_path: Path) -> None:
    """Main returns one when violations."""
    _write_root_page(tmp_path)
    _write_page(tmp_path, "demo", _page(csp="default-src *"))
    assert main(["--root", str(tmp_path)]) == 1
