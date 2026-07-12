#!/usr/bin/env python3
"""Check that the root and every artifact page ship a strict CSP and no external references.

Artifact pages under ``apps/<slug>/index.html`` receive a Content-Security-Policy
meta tag at scaffold time, but nothing re-validates a hand-pasted or hand-edited
page. This checker fails fast when an artifact:

    - is missing the Content-Security-Policy meta tag, or its policy does not
      restrict ``default-src`` and ``script-src`` to ``'self'`` or ``'none'``
      sources; or
    - references an external (scheme or protocol-relative) URL from a
      ``<script src>``, a stylesheet ``<link href>``, or a ``url()`` inside an
      inline ``<style>`` block. Inline ``data:`` URIs and ``#fragment``
      references inside ``url()`` are same-document content and stay allowed.

The root ``index.html`` shares the same posture, except its documented
``img-src https://img.shields.io`` badge-image exception. Artifact pages remain
limited to same-origin and inline ``data:`` image sources.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scripts import REPO_ROOT

# Directory (relative to the workspace root) that holds artifact pages.
APPS_DIRNAME = "apps"
ROOT_INDEX_FILENAME = "index.html"

# Source tokens that keep a directive restricted to same-origin content.
_RESTRICTIVE_SOURCES = frozenset({"'self'", "'none'"})
_APP_IMG_SOURCES = frozenset({"'self'", "'none'", "data:"})
_ROOT_IMG_SOURCES = _APP_IMG_SOURCES | frozenset({"https://img.shields.io"})

# Opening tags and inline style blocks. Artifact markup keeps attribute values
# free of ``>``, so a non-greedy attribute scan is robust enough here.
_META_TAG_PATTERN = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_SCRIPT_TAG_PATTERN = re.compile(r"<script\b[^>]*>", re.IGNORECASE)
_LINK_TAG_PATTERN = re.compile(r"<link\b[^>]*>", re.IGNORECASE)
_STYLE_BLOCK_PATTERN = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)

# One HTML attribute: double-quoted, single-quoted, or unquoted value.
_ATTRIBUTE_PATTERN = re.compile(
    r"""([a-zA-Z_:][-\w:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'>]+))"""
)

# One ``url(...)`` reference from a CSS declaration.
_CSS_URL_PATTERN = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*?))\s*\)""", re.IGNORECASE)

# A URL scheme prefix such as ``https:`` or ``data:``.
_SCHEME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _attribute_value(match: re.Match[str]) -> str:
    """Return the populated capture group from one attribute match."""
    return match.group(2) or match.group(3) or match.group(4) or ""


def _parse_attributes(tag: str) -> dict[str, str]:
    """Parse one HTML tag into a lower-cased attribute mapping."""
    attributes: dict[str, str] = {}
    for match in _ATTRIBUTE_PATTERN.finditer(tag):
        attributes[match.group(1).lower()] = _attribute_value(match)
    return attributes


def _extract_csp_policy(html: str) -> str | None:
    """Return the Content-Security-Policy meta tag content, if any."""
    for match in _META_TAG_PATTERN.finditer(html):
        attributes = _parse_attributes(match.group(0))
        if attributes.get("http-equiv", "").lower() == "content-security-policy":
            return attributes.get("content", "")
    return None


def _parse_csp_directives(policy: str) -> dict[str, list[str]]:
    """Parse a CSP policy string into a directive-to-sources mapping."""
    directives: dict[str, list[str]] = {}
    for chunk in policy.split(";"):
        tokens = chunk.split()
        if not tokens:
            continue
        directives[tokens[0].lower()] = tokens[1:]
    return directives


def _directive_has_only_allowed_sources(
    sources: list[str], allowed_sources: frozenset[str]
) -> bool:
    """Return whether every source in a directive belongs to its approved set.

    Per the CSP spec ``'none'`` is only meaningful as the sole source
    expression, so a directive that mixes it with other tokens is rejected.
    """
    if "'none'" in sources and len(sources) > 1:
        return False
    return bool(sources) and all(source in allowed_sources for source in sources)


def _csp_violations(
    html: str, display_path: str, *, allowed_img_sources: frozenset[str]
) -> list[str]:
    """Return CSP policy violations for one root or artifact page."""
    policy = _extract_csp_policy(html)
    if policy is None:
        return [f"{display_path}: missing Content-Security-Policy meta tag"]

    directives = _parse_csp_directives(policy)
    violations: list[str] = []

    default_src = directives.get("default-src")
    if default_src is None:
        violations.append(
            f"{display_path}: Content-Security-Policy is missing a default-src directive"
        )
    elif not _directive_has_only_allowed_sources(default_src, _RESTRICTIVE_SOURCES):
        violations.append(
            f"{display_path}: default-src must be restricted to 'self' or 'none' "
            f"(found: default-src {' '.join(default_src)})"
        )

    script_src = directives.get("script-src", default_src)
    if script_src is not None and not _directive_has_only_allowed_sources(
        script_src, _RESTRICTIVE_SOURCES
    ):
        violations.append(
            f"{display_path}: script-src must be restricted to 'self' or 'none' "
            f"(found: script-src {' '.join(script_src)})"
        )

    img_src = directives.get("img-src")
    if img_src is not None and not _directive_has_only_allowed_sources(
        img_src, allowed_img_sources
    ):
        allowed = " ".join(sorted(allowed_img_sources))
        violations.append(
            f"{display_path}: img-src must use only approved image sources "
            f"({allowed}; found: img-src {' '.join(img_src)})"
        )

    return violations


def _is_external_reference(reference: str) -> bool:
    """Return whether a URL is external (has a scheme or is protocol-relative)."""
    reference = reference.strip()
    if not reference:
        return False
    if reference.startswith("//"):
        return True
    return bool(_SCHEME_PATTERN.match(reference))


def _script_violations(html: str, display_path: str) -> list[str]:
    """Return violations for external ``<script src>`` references."""
    violations: list[str] = []
    for match in _SCRIPT_TAG_PATTERN.finditer(html):
        src = _parse_attributes(match.group(0)).get("src")
        if src and _is_external_reference(src):
            violations.append(f"{display_path}: external script src not allowed: {src}")
    return violations


def _stylesheet_violations(html: str, display_path: str) -> list[str]:
    """Return violations for external stylesheet ``<link href>`` references."""
    violations: list[str] = []
    for match in _LINK_TAG_PATTERN.finditer(html):
        attributes = _parse_attributes(match.group(0))
        rel_tokens = attributes.get("rel", "").lower().split()
        href = attributes.get("href")
        if "stylesheet" in rel_tokens and href and _is_external_reference(href):
            violations.append(f"{display_path}: external stylesheet href not allowed: {href}")
    return violations


def _extract_css_urls(style_block: str) -> list[str]:
    """Return every ``url(...)`` reference inside a CSS block."""
    references: list[str] = []
    for match in _CSS_URL_PATTERN.finditer(style_block):
        references.append((match.group(1) or match.group(2) or match.group(3) or "").strip())
    return references


def _inline_style_violations(html: str, display_path: str) -> list[str]:
    """Return violations for external ``url()`` references in inline styles."""
    violations: list[str] = []
    for block_match in _STYLE_BLOCK_PATTERN.finditer(html):
        for reference in _extract_css_urls(block_match.group(1)):
            # Inline data URIs and in-document fragments are same-document, not
            # external network fetches, so they stay allowed. URL schemes are
            # case-insensitive, so match data: against a lowercased scheme.
            if reference[:5].lower() == "data:" or reference.startswith("#"):
                continue
            if _is_external_reference(reference):
                violations.append(
                    f"{display_path}: external url() reference not allowed: {reference}"
                )
    return violations


def check_page(
    path: Path,
    *,
    display_path: str,
    allowed_img_sources: frozenset[str] = _APP_IMG_SOURCES,
) -> list[str]:
    """Return all CSP and same-origin violations for one root or artifact page.

    A page that cannot be read as UTF-8 text (binary content, a bad encoding,
    or any ``OSError``) is reported as a single deterministic violation rather
    than crashing the whole check with a traceback.
    """
    try:
        html = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        return [f"{display_path}: page could not be read as UTF-8 text ({error})"]
    return [
        *_csp_violations(html, display_path, allowed_img_sources=allowed_img_sources),
        *_script_violations(html, display_path),
        *_stylesheet_violations(html, display_path),
        *_inline_style_violations(html, display_path),
    ]


def discover_artifact_pages(apps_dir: Path) -> list[Path]:
    """Return every ``apps/<slug>/index.html`` page under the apps directory."""
    if not apps_dir.is_dir():
        return []
    return sorted(apps_dir.glob("*/index.html"))


def run_check(root: Path | None = None) -> list[str]:
    """Run the root and artifact CSP check and return all violations."""
    workspace_root = root or REPO_ROOT
    apps_dir = workspace_root / APPS_DIRNAME
    violations: list[str] = []
    root_index = workspace_root / ROOT_INDEX_FILENAME
    violations.extend(
        check_page(
            root_index,
            display_path=ROOT_INDEX_FILENAME,
            allowed_img_sources=_ROOT_IMG_SOURCES,
        )
    )
    for page in discover_artifact_pages(apps_dir):
        display_path = page.relative_to(workspace_root).as_posix()
        violations.extend(check_page(page, display_path=display_path))
    return violations


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the artifact CSP checker."""
    parser = argparse.ArgumentParser(
        description="Check root and artifact pages ship a strict CSP and no external references."
    )
    parser.add_argument(
        "--root",
        default=None,
        help="Repository root (defaults to auto-detected REPO_ROOT)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the CLI entry point and return a shell exit code."""
    args = parse_args(argv)
    workspace_root = Path(args.root) if args.root else REPO_ROOT
    violations = run_check(workspace_root)

    if not violations:
        print("Artifact CSP check passed")
        return 0

    print(f"Artifact CSP check failed: {len(violations)} violation(s)")
    for violation in violations:
        print(f"  {violation}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
