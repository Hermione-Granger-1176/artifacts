#!/usr/bin/env python3
"""Check that per-app stylesheets stay on the shared design-token system.

Each artifact keeps its layout in ``apps/<slug>/css/*.css`` while shared color,
radius, spacing, and type tokens live in ``css/style.css``. Nothing re-validates
those app stylesheets after they are authored, so a hand edit can quietly drift
back to hard-coded colors or off-token sizes. This checker fails fast when an
app stylesheet:

    - hard-codes a hex color (``#fff``, ``#ffffff``, ``#ffffff80``);
    - hard-codes a literal ``rgb()`` / ``rgba()`` color (all-numeric arguments),
      rather than a shared token, a ``var()`` reference, or a ``color-mix()``;
    - sets a ``border-radius`` (or a ``border-*-radius``) to a px literal of 6px
      or more, instead of ``var(--radius-*)``, ``0``, or ``50%`` (px literals of
      1px through 5px are allowed for deliberate sub-token decorative radii);
    - sets a ``font-size`` to a raw px literal instead of ``var(--font-size-*)``,
      ``clamp()``, or an em / rem / % / inherit value; or
    - sets ``letter-spacing`` to a raw literal instead of ``var(--tracking-*)``
      or ``normal``.

The rules are calibrated so the currently migrated app stylesheets pass as they
stand while regressions fail. A few deliberate literals that predate the shared
tokens are grandfathered through small, documented allowlists (see the
``*_ALLOWLIST`` constants below).

Scanning is line-based regex matching (the same approach as the other lints in
this package), not a full CSS parse. Comment blocks are masked to same-length
whitespace before scanning so a value inside a ``/* ... */`` comment never
triggers a false positive while reported line numbers stay stable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scripts import REPO_ROOT

# Directory (relative to the workspace root) that holds artifact directories.
APPS_DIRNAME = "apps"

# Font-size px literals deliberately retained on fixed, display-only elements.
# Keyed by the exact normalized value; each entry names its owning selector.
FONT_SIZE_PX_ALLOWLIST = frozenset(
    {
        "9px",  # prompt-caching .inf-cache-cell (hidden, color: transparent, cell label)
        "15px",  # tokenizer-explorer .card-icon (fixed-size glyph)
        "17px",  # tokenizer-explorer .sentence-display (sample sentence body copy)
    }
)

# Letter-spacing literals deliberately retained where no shared tracking token
# fits: negative display-heading tightening and one uppercase label tracking.
LETTER_SPACING_ALLOWLIST = frozenset(
    {
        "-0.02em",  # prompt-caching .pc h1 display-heading tightening
        "-0.01em",  # prompt-caching .pc h2 and tokenizer hero heading tightening
        "0.16em",  # prompt-caching .pc-section-num uppercase label tracking
    }
)

# The largest px border-radius kept as a deliberate sub-token decorative value.
# 6px and above must move onto a shared --radius-* token.
MAX_DECORATIVE_RADIUS_PX = 5

# One ``/* ... */`` comment block. DOTALL so a multi-line comment is masked in
# full; non-greedy so adjacent comments stay separate.
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

# A hex color literal: '#' followed by 3, 4, 6, or 8 hex digits.
_HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")

# One ``rgb(...)`` / ``rgba(...)`` call, capturing its argument list up to the
# first closing paren (enough to tell a literal color from a var()/color-mix one).
_RGB_RE = re.compile(r"\brgba?\(([^)]*)\)", re.IGNORECASE)

# One token-governed declaration: a border-radius, font-size, or letter-spacing
# property and its value up to the next ';', '{', or '}'. The leading lookbehind
# keeps custom-property names such as ``--font-size-sm`` from posing as the
# property, since they are never followed by a declaration colon.
_DECLARATION_RE = re.compile(
    r"(?<![-\w])(border-[a-z-]*radius|font-size|letter-spacing)\s*:\s*([^;{}]*)",
    re.IGNORECASE,
)

# A px length inside a value, for example ``12px`` or ``0.5px``.
_PX_RE = re.compile(r"(\d+(?:\.\d+)?)px", re.IGNORECASE)


def _mask_comments(css: str) -> str:
    """Return the stylesheet with comment blocks masked to same-length whitespace.

    Every non-newline character inside a ``/* ... */`` block becomes a space and
    newlines are preserved, so commented-out values never match while character
    offsets (and therefore reported line numbers) stay identical to the source.
    """

    def _blank(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return _COMMENT_RE.sub(_blank, css)


def _line_number(css: str, index: int) -> int:
    """Return the 1-based line number for a character offset."""
    return css.count("\n", 0, index) + 1


def _normalize(value: str) -> str:
    """Return a value with surrounding and collapsed internal whitespace removed."""
    return " ".join(value.split())


def _hex_violations(css: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for hard-coded hex colors."""
    violations: list[tuple[int, str]] = []
    for match in _HEX_RE.finditer(css):
        violations.append(
            (
                _line_number(css, match.start()),
                f"hex color '{match.group(0)}' is not allowed; "
                "use a shared color token, rgb()/rgba(), or color-mix()",
            )
        )
    return violations


def _literal_color_violations(css: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for literal rgb()/rgba() colors.

    A call whose arguments reference ``var()`` or ``color-mix()`` is a
    token-derived color and stays allowed; only all-literal numeric arguments
    are flagged.
    """
    violations: list[tuple[int, str]] = []
    for match in _RGB_RE.finditer(css):
        arguments = match.group(1).lower()
        if "var(" in arguments or "color-mix" in arguments:
            continue
        violations.append(
            (
                _line_number(css, match.start()),
                f"literal color '{_normalize(match.group(0))}' is not allowed; "
                "use a shared color token, a var() reference, or color-mix()",
            )
        )
    return violations


def _px_lengths(value: str) -> list[float]:
    """Return every px length found in a value as floats."""
    return [float(match.group(1)) for match in _PX_RE.finditer(value)]


def _radius_violation(value: str) -> str | None:
    """Return a message when a border-radius value uses an off-token px literal."""
    if any(length >= MAX_DECORATIVE_RADIUS_PX + 1 for length in _px_lengths(value)):
        return (
            f"off-token border-radius '{_normalize(value)}'; use var(--radius-xs/sm/md), "
            f"0, or 50% (px literals of {MAX_DECORATIVE_RADIUS_PX + 1}px and up are off-token)"
        )
    return None


def _font_size_violation(value: str) -> str | None:
    """Return a message when a font-size value uses a non-allowlisted px literal."""
    if not _px_lengths(value):
        return None
    if _normalize(value) in FONT_SIZE_PX_ALLOWLIST:
        return None
    return (
        f"raw px font-size '{_normalize(value)}'; use var(--font-size-*), clamp(), "
        "or an em / rem / % / inherit value"
    )


def _letter_spacing_violation(value: str) -> str | None:
    """Return a message when a letter-spacing value is an off-token literal."""
    normalized = _normalize(value)
    if normalized.lower() == "normal" or "var(" in normalized:
        return None
    if normalized in LETTER_SPACING_ALLOWLIST:
        return None
    return f"off-token letter-spacing '{normalized}'; use var(--tracking-label) or normal"


def _declaration_violations(css: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for off-token radius, font-size, and tracking."""
    violations: list[tuple[int, str]] = []
    for match in _DECLARATION_RE.finditer(css):
        property_name = match.group(1).lower()
        value = match.group(2)
        if property_name.endswith("radius"):
            message = _radius_violation(value)
        elif property_name == "font-size":
            message = _font_size_violation(value)
        else:
            message = _letter_spacing_violation(value)
        if message is not None:
            violations.append((_line_number(css, match.start()), message))
    return violations


def check_stylesheet(path: Path, *, display_path: str) -> list[str]:
    """Return all token violations for one app stylesheet.

    A file that cannot be read as UTF-8 text (binary content, a bad encoding, or
    any ``OSError``) is reported as a single deterministic violation rather than
    crashing the whole check with a traceback.
    """
    try:
        css = _mask_comments(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        return [f"{display_path}: stylesheet could not be read as UTF-8 text ({error})"]

    found = [
        *_hex_violations(css),
        *_literal_color_violations(css),
        *_declaration_violations(css),
    ]
    return [f"{display_path}:{line}: {message}" for line, message in sorted(found)]


def discover_app_stylesheets(apps_dir: Path) -> list[Path]:
    """Return every ``apps/<slug>/css/*.css`` stylesheet under the apps directory."""
    if not apps_dir.is_dir():
        return []
    return sorted(apps_dir.glob("*/css/*.css"))


def run_check(root: Path | None = None) -> list[str]:
    """Run the app-CSS token check and return all violations."""
    workspace_root = root or REPO_ROOT
    apps_dir = workspace_root / APPS_DIRNAME
    violations: list[str] = []
    for stylesheet in discover_app_stylesheets(apps_dir):
        display_path = stylesheet.relative_to(workspace_root).as_posix()
        violations.extend(check_stylesheet(stylesheet, display_path=display_path))
    return violations


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the app-CSS token checker."""
    parser = argparse.ArgumentParser(
        description="Check app stylesheets stay on the shared design-token system."
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
        print("App CSS token check passed")
        return 0

    print(f"App CSS token check failed: {len(violations)} violation(s)")
    for violation in violations:
        print(f"  {violation}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
