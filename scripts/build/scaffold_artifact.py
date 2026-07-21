#!/usr/bin/env python3
"""Scaffold a new artifact directory under ``apps/``.

This module backs `make new name=<artifact-name> [src=<path-to-html>]`.

It creates a new artifact directory under ``apps/`` with the required metadata
files, an HTML entry point, an app-local stylesheet and bootstrap module,
internal docs, and a matching app test under ``tests/js/apps/<slug>/``. Every
emitted file is designed to pass the repository gates (`make validate`, the JS
test-coverage check, ESLint, stylelint, Knip, and tsc) without hand edits.

Two flows are supported:

* Without ``--from-html`` the scaffold emits a semantic placeholder page wired
  to the shared stylesheet and app shell.
* With ``--from-html <path>`` an existing AI-generated HTML file is installed as
  ``index.html``. The shared contract is still guaranteed: the self-only
  Content-Security-Policy meta and the shared stylesheet links are injected when
  absent, and any external script/style references are reported (never silently
  rewritten) so the author can vendor or remove them before the security lint
  runs.

Run through the Makefile in normal workflows; direct invocation is mainly for
maintainers working on the build internals.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from scripts import REPO_ROOT
from scripts.build.index_config import IndexConfig
from scripts.build.prepare_site import APP_SHARE_IMAGE_PLACEHOLDER, APP_URL_PLACEHOLDER
from scripts.lib.app_discovery import artifact_base_path

if TYPE_CHECKING:
    from collections.abc import Iterable

APPS_DIR = REPO_ROOT / artifact_base_path()
TESTS_JS_APPS_DIR = REPO_ROOT / "tests" / "js" / "apps"

INDEX_FILE = "index.html"
NAME_FILE = "name.txt"
DESCRIPTION_FILE = "description.txt"
TAGS_FILE = "tags.txt"
TOOLS_FILE = "tools.txt"

# Self-only policy shared by every artifact. Kept as a constant so the drop-in
# flow can inject the exact same meta the placeholder template ships with.
CSP_CONTENT = (
    "default-src 'self'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'"
)
CSP_META = f'<meta http-equiv="Content-Security-Policy" content="{CSP_CONTENT}">'

SHARED_STYLESHEET_HREF = "../../css/style.css"
APP_STYLESHEET_HREF = "./css/app.css"
SHARED_STYLESHEET_LINK = f'<link rel="stylesheet" href="{SHARED_STYLESHEET_HREF}">'
APP_STYLESHEET_LINK = f'<link rel="stylesheet" href="{APP_STYLESHEET_HREF}">'

# Strip HTML comment blocks before any presence or reference scan so a commented-out
# tag (for example an example CSP meta, stylesheet link, or script src left in a
# comment) never poses as live markup. Non-greedy so adjacent comments stay separate,
# and DOTALL so a comment spanning multiple lines is removed in full.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# The word boundary keeps `<header>` elements from matching as an opening head tag.
_HEAD_OPEN_RE = re.compile(r"<head\b[^>]*>", re.IGNORECASE)
_HEAD_CLOSE_RE = re.compile(r"</head\s*>", re.IGNORECASE)
_BODY_CLOSE_RE = re.compile(r"</body\s*>", re.IGNORECASE)
_HTML_CLOSE_RE = re.compile(r"</html\s*>", re.IGNORECASE)
_HTML_OPEN_RE = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
_DOCTYPE_RE = re.compile(r"<!doctype[^>]*>", re.IGNORECASE)

# Detect an existing CSP only inside a real <meta http-equiv="Content-Security-Policy">
# tag, never loose prose or script text that merely names the header. Attribute
# names and values are case-insensitive in HTML, order is free, and the value may be
# single-quoted, double-quoted, or unquoted, so the pattern stays tolerant of all
# three. The leading lookahead requires a content attribute so a meta that names the
# header but carries no policy still gets the enforced one injected. The lookbehinds
# keep data-http-equiv / data-content style attributes from posing as the real ones.
# The trailing negative lookahead requires a value terminator so a longer header such
# as Content-Security-Policy-Report-Only cannot pose as the enforced one.
_CSP_PRESENT_RE = re.compile(
    r"""<meta\b(?=[^>]*(?<![\w-])content\s*=)"""
    r"""[^>]*(?<![\w-])http-equiv\s*=\s*["']?\s*content-security-policy(?![\w-])""",
    re.IGNORECASE,
)

# Matches src/href attributes and CSS url() targets that point off-origin,
# including protocol-relative references (//host/path). Attribute values may be
# double-quoted, single-quoted, or unquoted; external URLs never contain unencoded
# whitespace, quotes, or ">", so the value class stops at all of them and works for
# every quoting style. The lookbehind keeps data-src / data-href style attributes
# from posing as the real ones, matching the other presence checks in this module.
_EXTERNAL_ATTR_RE = re.compile(
    r"""(?<![\w-])(?:src|href)\s*=\s*["']?\s*((?:https?:)?//[^\s"'>]+)""",
    re.IGNORECASE,
)
_EXTERNAL_URL_RE = re.compile(
    r"""url\(\s*["']?\s*((?:https?:)?//[^\s)"']+)""",
    re.IGNORECASE,
)


def _stylesheet_link_re(href: str) -> re.Pattern[str]:
    """Build a regex that detects a real stylesheet ``<link>`` for one exact href.

    Presence must anchor to a ``<link>`` tag whose ``rel`` is ``stylesheet``,
    never loose prose or script text that merely names the path. Attribute order
    is free, values may be double-quoted, single-quoted, or unquoted, and the
    lookbehinds keep data-rel / data-href style attributes from posing as the
    real ones. The trailing lookahead requires a value terminator so a longer
    path that merely starts with the href cannot match.
    """
    return re.compile(
        rf"""<link\b(?=[^>]*(?<![\w-])rel\s*=\s*["']?\s*stylesheet\b)"""
        rf"""[^>]*(?<![\w-])href\s*=\s*["']?\s*{re.escape(href)}(?=["'\s>])""",
        re.IGNORECASE,
    )


_SHARED_STYLESHEET_PRESENT_RE = _stylesheet_link_re(SHARED_STYLESHEET_HREF)
_APP_STYLESHEET_PRESENT_RE = _stylesheet_link_re(APP_STYLESHEET_HREF)


def is_kebab_case(name: str) -> bool:
    """Return True when a directory name follows kebab-case."""
    return IndexConfig.create_default().is_kebab_case(name)


def _title_from_slug(slug: str) -> str:
    """Convert a kebab-case slug to a human-readable title."""
    return " ".join(word.capitalize() for word in slug.split("-"))


def _index_template(title: str, slug: str | None = None) -> str:
    """Return a mature HTML starting point for a new artifact."""
    app_class = f" app-{slug}" if slug else ""
    description = "Replace this description with a concise summary of your artifact."
    lede = (
        "Replace this scaffold with your artifact and keep shared visual "
        "styling in the shared stylesheet while keeping app-specific layout local."
    )
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="description" content="{description}">
  <link rel="canonical" href="{APP_URL_PLACEHOLDER}">
  <meta property="og:title" content="{title} | Artifacts">
  <meta property="og:description" content="{description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{APP_URL_PLACEHOLDER}">
  <meta property="og:site_name" content="Artifacts">
  <meta property="og:image" content="{APP_SHARE_IMAGE_PLACEHOLDER}">
  <meta property="og:image:secure_url" content="{APP_SHARE_IMAGE_PLACEHOLDER}">
  <meta property="og:image:alt" content="Preview card for the {title} app.">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{title} | Artifacts">
  <meta name="twitter:description" content="{description}">
  <meta name="twitter:image" content="{APP_SHARE_IMAGE_PLACEHOLDER}">
  <meta name="twitter:image:alt" content="Preview card for the {title} app.">
  <meta name="theme-color" content="rgb(245, 239, 230)">
  <meta name="referrer" content="strict-origin-when-cross-origin">
  <meta http-equiv="Content-Security-Policy" content="{CSP_CONTENT}">
  <title>{title} | Artifacts</title>
  <script src="../../js/app-theme.js"></script>
  <link rel="icon" href="../../assets/icons/favicon.ico" sizes="32x32">
  <link rel="icon" href="../../assets/icons/icon.svg" type="image/svg+xml">
  <link rel="apple-touch-icon" href="../../assets/icons/apple-touch-icon.png">
  <link rel="manifest" href="../../assets/icons/manifest.webmanifest">
  <link rel="stylesheet" href="{SHARED_STYLESHEET_HREF}">
  <link rel="stylesheet" href="{APP_STYLESHEET_HREF}">
</head>
<body class="artifact-app{app_class}">
  <div data-app-shell="header"></div>

  <main class="page-shell">
    <div data-app-shell="runtime-error"></div>

    <header class="page-intro">
      <h1 class="page-title">{title}</h1>
      <p class="page-lede">{lede}</p>
    </header>

    <section class="page-card placeholder-card">
      <h2>Get started</h2>
      <p>Build the interaction here and document the architecture in <code>docs/</code>.</p>
    </section>
  </main>

  <div data-app-shell="scroll-top"></div>

  <script type="module" src="./js/app.js"></script>
</body>
</html>
"""


def _app_js_template() -> str:
    """Return starter app bootstrap code."""
    return """import { initializeMatureApp } from "../../../js/modules/app-runtime.js";
import { initAppShell, renderAppShell } from "../../../js/modules/app-shell.js";

renderAppShell();

initializeMatureApp({
  run: () => {
    initAppShell();
  }
});
"""


def _app_css_template(title: str) -> str:
    """Return a starter app stylesheet.

    Points new apps at the shared components before they write new CSS and keeps
    the design-token rules (enforced by ``make lint-app-css-tokens``) front and
    center: no hex or literal colors, and radius, font-size, and letter-spacing
    values sized through the shared tokens.
    """
    return (
        f"/* {title} app layout. */\n"
        "/* Scope every selector under body.app-<slug> and reuse the shared components */\n"
        "/* in ../../css/style.css before writing new CSS: .control-field for labeled */\n"
        "/* inputs, .stat-grid / .stat for metric tiles, .chip for pills and badges, */\n"
        "/* .segmented for toggles, .meter for bars, .app-callout (with its tone */\n"
        "/* modifiers) for callouts, and .section-kicker for eyebrow labels. */\n"
        "/* Stay on the shared design tokens: no hex colors, no literal color functions */\n"
        "/* such as rgb() / hsl(), and no named colors (use a color token, var(), or a */\n"
        "/* color-mix() over tokens); size radii with */\n"
        "/* var(--radius-*), font sizes with var(--font-size-*) or relative units (no px, */\n"
        "/* even inside clamp()), and letter-spacing with a var(--tracking-*) token or */\n"
        "/* normal. */\n"
    )


def _app_test_template(slug: str, title: str) -> str:
    """Return a starter app test that boots the emitted bootstrap module.

    The assertion is intentionally behavioral: importing ``app.js`` under the
    shared mocks must reach a ``ready`` runtime state, proving the bootstrap
    wiring is intact rather than merely that the file parses.
    """
    return f"""import assert from 'node:assert/strict';
import test from 'node:test';

import {{ cleanupMocks, setupFullMocks }} from '../../common/app-entry-test-support.js';

test('{slug} app.js boots the shared runtime without error', async () => {{
  setupFullMocks();
  try {{
    // Cache-bust the import so repeat runs re-evaluate the module.
    await import(`../../../../apps/{slug}/js/app.js?t=${{Date.now()}}-${{Math.random()}}`);

    assert.equal(
      globalThis.window.__ARTIFACT_READY__,
      true,
      'the {title} bootstrap should finish without a fatal error'
    );
    assert.equal(
      globalThis.document.documentElement.dataset.runtimeStatus,
      'ready',
      'the shared runtime should reach the ready state'
    );
  }} finally {{
    cleanupMocks();
  }}
}});
"""


def _readme_template(title: str, *, drop_in: bool = False) -> str:
    """Return starter app documentation."""
    note = ""
    if drop_in:
        note = (
            "\n\n> Note: This page was installed from an existing HTML file. "
            "Wiring `js/app.js` through the shared app shell is optional for a "
            "self-contained drop-in. Keep the emitted bootstrap module and its "
            "test, or replace the app behavior with your own module of the same name."
        )
    return f"""# {title}

Describe what this artifact does.

## Highlights

- Replace this with the app's core features

## Made with

- List AI tools used
- List runtime dependencies. Vendor them under `js/vendor/` to keep the CSP self-only.

## Structure

```text
index.html
css/app.css
js/
├── app.js
└── modules/
docs/
```{note}

## Docs

See `docs/` for architecture, verification, and implementation decisions.
"""


def _doc_template(title: str, heading: str) -> str:
    """Return a starter internal doc page."""
    return f"""# {heading}

## {title}

Fill in this document as the app grows.
"""


def _strip_html_comments(html: str) -> str:
    """Return the document with HTML comment blocks removed.

    Used only to build the copy scanned for presence and reference checks, so
    commented-out markup never poses as live tags. The original document is left
    untouched for injection.
    """
    return _HTML_COMMENT_RE.sub("", html)


def _first_live_match(html: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    """Return the first match of ``pattern`` that sits outside HTML comments.

    Used when an injection needs a position inside the original document, where
    comment stripping would shift every offset.
    """
    comment_spans = [match.span() for match in _HTML_COMMENT_RE.finditer(html)]
    for match in pattern.finditer(html):
        if not any(start <= match.start() < end for start, end in comment_spans):
            return match
    return None


def find_external_references(html: str) -> list[str]:
    """Return sorted unique off-origin references found in an HTML document.

    Detects ``src`` / ``href`` attributes (quoted or unquoted) and CSS ``url()``
    targets that use an absolute or protocol-relative URL. These are the
    references the security lint hard-fails on, so the scaffolder surfaces them
    instead of rewriting. Commented-out markup is skipped so an example URL left
    in an HTML comment never triggers a misleading warning.
    """
    scannable = _strip_html_comments(html)
    references: set[str] = set()
    for pattern in (_EXTERNAL_ATTR_RE, _EXTERNAL_URL_RE):
        references.update(match.group(1) for match in pattern.finditer(scannable))
    return sorted(references)


def _inject_after_head_open(html: str, snippet: str) -> str:
    """Insert a snippet immediately after the opening ``<head>`` tag.

    Falls back to the opening ``<html>`` tag, then the doctype, and only then
    to a plain prepend, so a headless document never gains markup ahead of its
    doctype (content before the doctype puts the page into quirks mode).
    """
    for pattern in (_HEAD_OPEN_RE, _HTML_OPEN_RE, _DOCTYPE_RE):
        match = pattern.search(html)
        if match is not None:
            index = match.end()
            return f"{html[:index]}\n  {snippet}{html[index:]}"
    return f"{snippet}\n{html}"


def _inject_before_head_close(html: str, snippet: str) -> str:
    """Insert a snippet immediately before the closing ``</head>`` tag.

    Falls back to injecting before ``</body>``, then before ``</html>``, and
    only then to appending, so a headless document keeps the snippet inside the
    document where browsers still apply it. Inserting before a closing tag
    (rather than after an opening one) preserves the relative order of
    successive injections, which keeps the shared stylesheet ahead of the
    app-local one.
    """
    for pattern in (_HEAD_CLOSE_RE, _BODY_CLOSE_RE, _HTML_CLOSE_RE):
        match = pattern.search(html)
        if match is not None:
            index = match.start()
            return f"{html[:index]}  {snippet}\n{html[index:]}"
    return f"{html}\n{snippet}"


def apply_contract_to_source(html: str) -> str:
    """Guarantee the shared contract inside a provided HTML document.

    Injects the self-only CSP meta and the shared stylesheet links only when a
    real meta or link tag already provides them, so an author who already wired
    them keeps their exact markup while prose, script text, or commented-out
    markup that merely names the header or the paths never suppresses the
    contract.
    """
    # Run the presence checks against a comment-free copy so a commented-out tag
    # does not suppress injection, while injecting into the original untouched html.
    scannable = _strip_html_comments(html)
    if _CSP_PRESENT_RE.search(scannable) is None:
        html = _inject_after_head_open(html, CSP_META)
    if _SHARED_STYLESHEET_PRESENT_RE.search(scannable) is None:
        # An already-present app link must stay after the shared one so app rules
        # keep overriding shared rules, so inject ahead of it instead of at head-close.
        app_link = _first_live_match(html, _APP_STYLESHEET_PRESENT_RE)
        if app_link is None:
            html = _inject_before_head_close(html, SHARED_STYLESHEET_LINK)
        else:
            index = app_link.start()
            html = f"{html[:index]}{SHARED_STYLESHEET_LINK}\n  {html[index:]}"
    if _APP_STYLESHEET_PRESENT_RE.search(scannable) is None:
        html = _inject_before_head_close(html, APP_STYLESHEET_LINK)
    return html


def _read_source_html(source_html: str) -> str:
    """Read the provided drop-in HTML file, failing loudly when missing."""
    source_path = Path(source_html)
    if not source_path.is_file():
        raise FileNotFoundError(f"Source HTML file not found: {source_path}")
    return source_path.read_text(encoding="utf-8")


def _report_external_references(references: Iterable[str]) -> None:
    """Print an actionable warning about off-origin references."""
    reference_list = list(references)
    if not reference_list:
        return
    print(
        "Warning: the provided HTML references off-origin resources. The "
        "self-only Content-Security-Policy will block them and the security "
        "lint will fail. Vendor them under js/vendor/ or remove them:",
        file=sys.stderr,
    )
    for reference in reference_list:
        print(f"  - {reference}", file=sys.stderr)


def _resolve_index_html(title: str, name: str, source_html: str | None) -> str:
    """Return the index.html body for either the placeholder or drop-in flow."""
    if source_html is None:
        return _index_template(title, name)
    provided = _read_source_html(source_html)
    _report_external_references(find_external_references(provided))
    return apply_contract_to_source(provided)


def scaffold_artifact(name: str, *, source_html: str | None = None) -> Path:
    """Create a new artifact scaffold and return the artifact directory path.

    When ``source_html`` is provided the file is installed as ``index.html``
    (with the shared contract guaranteed); otherwise a placeholder page is
    emitted. Every other emitted file is identical across both flows.
    """
    if not name:
        raise ValueError("Artifact name is required")
    if not is_kebab_case(name):
        raise ValueError("Artifact name must use kebab-case")

    # Fail on an existing directory before reading or warning about the source
    # HTML, so a re-run against a taken slug is a clean no-op with no output.
    artifact_dir = APPS_DIR / name
    if artifact_dir.exists():
        raise FileExistsError(f"Artifact directory already exists: {artifact_dir}")

    title = _title_from_slug(name)
    index_html = _resolve_index_html(title, name, source_html)

    APPS_DIR.mkdir(parents=True, exist_ok=True)
    TESTS_JS_APPS_DIR.mkdir(parents=True, exist_ok=True)

    artifact_dir.mkdir()
    tests_dir = TESTS_JS_APPS_DIR / name
    tests_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "css").mkdir()
    (artifact_dir / "js").mkdir()
    (artifact_dir / "docs").mkdir()
    (artifact_dir / INDEX_FILE).write_text(index_html, encoding="utf-8")
    (artifact_dir / "css" / "app.css").write_text(_app_css_template(title), encoding="utf-8")
    (artifact_dir / "js" / "app.js").write_text(_app_js_template(), encoding="utf-8")
    (tests_dir / "app.test.js").write_text(_app_test_template(name, title), encoding="utf-8")
    (artifact_dir / "README.md").write_text(
        _readme_template(title, drop_in=source_html is not None), encoding="utf-8"
    )
    (artifact_dir / "docs" / "architecture.md").write_text(
        _doc_template(title, "Architecture"), encoding="utf-8"
    )
    (artifact_dir / "docs" / "verification.md").write_text(
        _doc_template(title, "Verification"), encoding="utf-8"
    )
    (artifact_dir / "docs" / "decisions.md").write_text(
        _doc_template(title, "Decisions"), encoding="utf-8"
    )
    (artifact_dir / NAME_FILE).write_text(title + "\n", encoding="utf-8")
    (artifact_dir / DESCRIPTION_FILE).write_text("\n", encoding="utf-8")
    (artifact_dir / TAGS_FILE).write_text("\n", encoding="utf-8")
    (artifact_dir / TOOLS_FILE).write_text("\n", encoding="utf-8")
    return artifact_dir


def _parse_args(args: list[str]) -> tuple[str, str | None]:
    """Parse the scaffold CLI into (name, optional source-HTML path)."""
    usage = (
        "Usage: make new name=<artifact-name> [src=<path-to-html>] "
        "(direct CLI form: scaffold_artifact.py <artifact-name> [--from-html <path-to-html>])"
    )
    if not args:
        raise ValueError(usage)

    name = args[0]
    rest = args[1:]
    if not rest:
        return name, None
    if len(rest) != 2 or rest[0] != "--from-html":
        raise ValueError(usage)
    return name, rest[1]


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for artifact scaffolding."""
    args = list(sys.argv[1:] if argv is None else argv)
    name, source_html = _parse_args(args)

    artifact_dir = scaffold_artifact(name, source_html=source_html)
    print(f"Created artifact scaffold: {artifact_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    try:
        raise SystemExit(main())
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
