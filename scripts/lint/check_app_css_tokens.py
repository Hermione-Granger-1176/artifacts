#!/usr/bin/env python3
"""Check that per-app stylesheets stay on the shared design-token system.

Each artifact keeps its layout in ``apps/<slug>/css/*.css`` while shared color,
radius, spacing, and type tokens live in ``css/style.css``. Nothing re-validates
those app stylesheets after they are authored, so a hand edit can quietly drift
back to hard-coded colors or off-token sizes. This checker fails fast when an
app stylesheet:

    - hard-codes a hex color (``#fff``, ``#ffffff``, ``#ffffff80``) in a
      declaration value (id selectors and masked strings are not values);
    - writes a color function (``rgb()``, ``rgba()``, ``hsl()``, ``hsla()``,
      ``hwb()``, ``lab()``, ``lch()``, ``oklab()``, ``oklch()``, ``color()``)
      whose channel arguments do not begin with a ``var()`` reference or a
      ``color-mix()``, so ``rgba(255, 0, 0, var(--alpha))`` is still literal;
    - writes a ``color-mix()`` whose arguments reference no ``var()`` at all;
    - uses a named color keyword (``red``, ``salmon``, ...) in the value of a
      color-bearing declaration (``transparent`` and ``currentcolor`` stay
      allowed as CSS-wide non-palette keywords);
    - sets a ``border-radius`` (or a ``border-*-radius``) to a px literal above
      5px, instead of ``var(--radius-*)``, ``0``, or ``50%`` (px literals up to
      5px are allowed for deliberate sub-token decorative radii);
    - sets a ``font-size`` to a raw px literal instead of ``var(--font-size-*)``,
      a ``clamp()`` built on token or relative units (a px literal inside
      ``clamp()`` is still flagged), or an em / rem / % / inherit value; or
    - sets ``letter-spacing`` to anything other than exactly one
      ``var(--tracking-*)`` token, ``normal``, or a grandfathered allowlisted
      literal (a trailing ``!important`` is tolerated; a token buried inside a
      larger expression is not).

The rules are calibrated so the currently migrated app stylesheets pass as they
stand while regressions fail. A few deliberate literals that predate the shared
tokens are grandfathered through small, documented allowlists scoped to the one
stylesheet that owns them (see the ``*_ALLOWLIST`` constants below).

Scanning is line-based regex matching (the same approach as the other lints in
this package), not a full CSS parse. Comment blocks, quoted strings, and
``url()`` arguments are masked to same-length whitespace before scanning so a
value inside them never triggers a false positive while reported line numbers
stay stable.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scripts import REPO_ROOT

# Directory (relative to the workspace root) that holds artifact directories.
APPS_DIRNAME = "apps"

# Font-size px literals deliberately retained on fixed, display-only elements,
# scoped to the one stylesheet that owns each literal.
FONT_SIZE_PX_ALLOWLIST: dict[str, frozenset[str]] = {
    # .inf-cache-cell (hidden, color: transparent, cell label)
    "apps/prompt-caching/css/app.css": frozenset({"9px"}),
    # .card-icon (fixed-size glyph) and .sentence-display (sample sentence copy)
    "apps/tokenizer-explorer/css/app.css": frozenset({"15px", "17px"}),
}

# Letter-spacing literals deliberately retained where no shared tracking token
# fits (negative display-heading tightening and one uppercase label tracking),
# scoped to the one stylesheet that owns each literal.
LETTER_SPACING_ALLOWLIST: dict[str, frozenset[str]] = {
    # .pc h1 / .pc h2 heading tightening and .pc-section-num label tracking
    "apps/prompt-caching/css/app.css": frozenset({"-0.02em", "-0.01em", "0.16em"}),
    # hero heading tightening
    "apps/tokenizer-explorer/css/app.css": frozenset({"-0.01em"}),
}

# The largest px border-radius kept as a deliberate sub-token decorative value.
# Anything above it must move onto a shared --radius-* token.
MAX_DECORATIVE_RADIUS_PX = 5

# Every CSS named color keyword (CSS Color Module Level 4). ``transparent`` and
# ``currentcolor`` are deliberately absent: they are CSS-wide keywords rather
# than palette drift, and stay allowed.
NAMED_COLOR_KEYWORDS = frozenset(
    {
        "aliceblue",
        "antiquewhite",
        "aqua",
        "aquamarine",
        "azure",
        "beige",
        "bisque",
        "black",
        "blanchedalmond",
        "blue",
        "blueviolet",
        "brown",
        "burlywood",
        "cadetblue",
        "chartreuse",
        "chocolate",
        "coral",
        "cornflowerblue",
        "cornsilk",
        "crimson",
        "cyan",
        "darkblue",
        "darkcyan",
        "darkgoldenrod",
        "darkgray",
        "darkgreen",
        "darkgrey",
        "darkkhaki",
        "darkmagenta",
        "darkolivegreen",
        "darkorange",
        "darkorchid",
        "darkred",
        "darksalmon",
        "darkseagreen",
        "darkslateblue",
        "darkslategray",
        "darkslategrey",
        "darkturquoise",
        "darkviolet",
        "deeppink",
        "deepskyblue",
        "dimgray",
        "dimgrey",
        "dodgerblue",
        "firebrick",
        "floralwhite",
        "forestgreen",
        "fuchsia",
        "gainsboro",
        "ghostwhite",
        "gold",
        "goldenrod",
        "gray",
        "green",
        "greenyellow",
        "grey",
        "honeydew",
        "hotpink",
        "indianred",
        "indigo",
        "ivory",
        "khaki",
        "lavender",
        "lavenderblush",
        "lawngreen",
        "lemonchiffon",
        "lightblue",
        "lightcoral",
        "lightcyan",
        "lightgoldenrodyellow",
        "lightgray",
        "lightgreen",
        "lightgrey",
        "lightpink",
        "lightsalmon",
        "lightseagreen",
        "lightskyblue",
        "lightslategray",
        "lightslategrey",
        "lightsteelblue",
        "lightyellow",
        "lime",
        "limegreen",
        "linen",
        "magenta",
        "maroon",
        "mediumaquamarine",
        "mediumblue",
        "mediumorchid",
        "mediumpurple",
        "mediumseagreen",
        "mediumslateblue",
        "mediumspringgreen",
        "mediumturquoise",
        "mediumvioletred",
        "midnightblue",
        "mintcream",
        "mistyrose",
        "moccasin",
        "navajowhite",
        "navy",
        "oldlace",
        "olive",
        "olivedrab",
        "orange",
        "orangered",
        "orchid",
        "palegoldenrod",
        "palegreen",
        "paleturquoise",
        "palevioletred",
        "papayawhip",
        "peachpuff",
        "peru",
        "pink",
        "plum",
        "powderblue",
        "purple",
        "rebeccapurple",
        "red",
        "rosybrown",
        "royalblue",
        "saddlebrown",
        "salmon",
        "sandybrown",
        "seagreen",
        "seashell",
        "sienna",
        "silver",
        "skyblue",
        "slateblue",
        "slategray",
        "slategrey",
        "snow",
        "springgreen",
        "steelblue",
        "tan",
        "teal",
        "thistle",
        "tomato",
        "turquoise",
        "violet",
        "wheat",
        "white",
        "whitesmoke",
        "yellow",
        "yellowgreen",
    }
)

# One non-semantic region: a ``/* ... */`` comment block (DOTALL so it spans
# lines; non-greedy so adjacent comments stay separate), a single- or
# double-quoted CSS string on one line with backslash escapes consumed (so an
# escaped quote such as ``"\"#fff\""`` cannot end the string early), or a
# ``url(...)`` reference (so SVG fragments such as ``url(#blur)`` never read
# as hex colors). All three are alternatives of one regex so masking happens
# in a single left-to-right pass and the construct that starts first wins: a
# ``/*`` inside a string never opens a comment, and a quote inside a comment
# never opens a string.
_NON_SEMANTIC_RE = re.compile(
    r"/\*.*?\*/"
    r"|\"(?:\\.|[^\"\\\n])*\""
    r"|'(?:\\.|[^'\\\n])*'"
    r"|\burl\([^)]*\)",
    re.DOTALL | re.IGNORECASE,
)

# A hex color literal: '#' followed by exactly 3, 4, 6, or 8 hex digits (the
# only valid CSS hex lengths); 5- and 7-digit runs are not colors and pass.
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")

# One CSS color-function call, capturing its argument list up to the first
# closing paren (enough to see whether the channels start from a token).
_COLOR_FUNCTION_RE = re.compile(
    r"(?<![-\w])(rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(([^)]*)\)",
    re.IGNORECASE,
)

# The opening of a ``color-mix(...)`` call; its full argument list is then
# extracted by balancing nested parens, so a var() after a nested call counts.
_COLOR_MIX_RE = re.compile(r"(?<![-\w])color-mix\(", re.IGNORECASE)

# One declaration whose value can carry a color, and that value up to the next
# ';', '{', or '}'. Longer property alternatives come before their prefixes.
_COLOR_DECLARATION_RE = re.compile(
    r"(?<![-\w])("
    r"--[-\w]+|background-color|background-image|background|accent-color"
    r"|caret-color|column-rule(?:-[a-z]+)*|text-decoration(?:-[a-z]+)*"
    r"|box-shadow|text-shadow|border(?:-[a-z]+)*|outline(?:-[a-z]+)*"
    r"|fill|stroke|color"
    r")\s*:\s*([^;{}]*)",
    re.IGNORECASE,
)

# The name part of a ``var(--name`` reference, masked before the named-color
# scan so token names such as ``--note-red`` never read as color keywords.
_VAR_NAME_RE = re.compile(r"var\(\s*--[-\w]+", re.IGNORECASE)

# One candidate named-color keyword inside a declaration value.
_NAMED_COLOR_RE = re.compile(r"[a-zA-Z]+")

# One token-governed declaration: a border-radius, font-size, or letter-spacing
# property and its value up to the next ';', '{', or '}'. The leading lookbehind
# keeps custom-property names such as ``--font-size-sm`` from posing as the
# property, since they are never followed by a declaration colon.
_DECLARATION_RE = re.compile(
    r"(?<![-\w])(border-[a-z-]*radius|font-size|letter-spacing)\s*:\s*([^;{}]*)",
    re.IGNORECASE,
)

# A px length inside a value, for example ``12px``, ``.5px``, or ``6e1px``
# (CSS numbers allow scientific notation, and float() parses the same forms).
_PX_RE = re.compile(r"(\d*\.?\d+(?:e[+-]?\d+)?)px", re.IGNORECASE)

# A letter-spacing value that is exactly one tracking-token reference.
_TRACKING_VAR_RE = re.compile(r"var\(--tracking-[\w-]+\)", re.IGNORECASE)

# A trailing ``!important`` flag on a declaration value.
_IMPORTANT_RE = re.compile(r"\s*!important$", re.IGNORECASE)

# A declaration's leading ``property:`` part, used to tell a value position
# from a selector position when a bare hex token is found.
_PROPERTY_COLON_RE = re.compile(r"\s*-{0,2}[a-zA-Z][-\w]*\s*:")

# The guidance shared by every color rule's message.
_COLOR_GUIDANCE = "use a shared color token via var() or a token-derived color-mix()"


def _mask(css: str) -> str:
    """Return the stylesheet with non-semantic regions masked to whitespace.

    Comment blocks, quoted strings, and ``url()`` references are blanked to
    same-length whitespace (newlines preserved), so values inside them never
    match while character offsets (and therefore reported line numbers) stay
    identical to the source.
    """

    def _blank(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    return _NON_SEMANTIC_RE.sub(_blank, css)


def _line_number(css: str, index: int) -> int:
    """Return the 1-based line number for a character offset."""
    return css.count("\n", 0, index) + 1


def _normalize(value: str) -> str:
    """Return a value with surrounding and collapsed internal whitespace removed."""
    return " ".join(value.split())


def _in_declaration_value(css: str, index: int) -> bool:
    """Return True when the offset sits in a declaration value, not a selector.

    The segment since the nearest ``{``, ``}``, or ``;`` is a declaration value
    exactly when it starts with a ``property:`` prefix; an id selector such as
    ``#fff {`` has no such prefix in its segment.
    """
    boundary = max(css.rfind(char, 0, index) for char in "{};")
    return bool(_PROPERTY_COLON_RE.match(css[boundary + 1 : index]))


def _hex_violations(css: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for hard-coded hex colors in values."""
    violations: list[tuple[int, str]] = []
    for match in _HEX_RE.finditer(css):
        if not _in_declaration_value(css, match.start()):
            continue
        violations.append(
            (
                _line_number(css, match.start()),
                f"hex color '{match.group(0)}' is not allowed; {_COLOR_GUIDANCE}",
            )
        )
    return violations


def _color_function_violations(css: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for literal color-function calls.

    A call is token-derived only when its argument list begins with a ``var()``
    reference or a ``color-mix()``, so literal channels with a token buried
    later (``rgba(255, 0, 0, var(--alpha))``) are still flagged.
    """
    violations: list[tuple[int, str]] = []
    for match in _COLOR_FUNCTION_RE.finditer(css):
        arguments = match.group(2).lstrip().lower()
        if arguments.startswith("var(") or arguments.startswith("color-mix("):
            continue
        violations.append(
            (
                _line_number(css, match.start()),
                f"literal color '{_normalize(match.group(0))}' is not allowed; {_COLOR_GUIDANCE}",
            )
        )
    return violations


def _call_arguments(css: str, index: int) -> str:
    """Return the argument text from ``index`` to the call's matching close paren.

    ``index`` points just past a call's opening paren. Nested parens are
    balanced (comments, strings, and url() are already masked, so every paren
    is structural); an unterminated call yields the rest of the stylesheet.
    """
    depth = 1
    for position in range(index, len(css)):
        char = css[position]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return css[index:position]
    return css[index:]


def _color_mix_violations(css: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for color-mix() calls with no token input.

    The full argument list is extracted with balanced parens, so a ``var()``
    that follows a nested call (``color-mix(in srgb, rgb(...) 50%,
    var(--b))``) still counts as a token input.
    """
    violations: list[tuple[int, str]] = []
    for match in _COLOR_MIX_RE.finditer(css):
        arguments = _call_arguments(css, match.end())
        if "var(" in arguments.lower():
            continue
        violations.append(
            (
                _line_number(css, match.start()),
                f"literal color-mix 'color-mix({_normalize(arguments)})' mixes no "
                "var() token; mix shared color tokens instead",
            )
        )
    return violations


def _named_color_violations(css: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for named colors in color-bearing values.

    Token names inside ``var()`` references are masked first, so a reference
    such as ``var(--note-red)`` never reads as the keyword ``red``.
    """
    violations: list[tuple[int, str]] = []
    for match in _COLOR_DECLARATION_RE.finditer(css):
        value = _VAR_NAME_RE.sub("var(", match.group(2))
        for word in _NAMED_COLOR_RE.findall(value):
            if word.lower() not in NAMED_COLOR_KEYWORDS:
                continue
            violations.append(
                (
                    _line_number(css, match.start()),
                    f"named color '{word.lower()}' in '{match.group(1).lower()}' "
                    f"is not allowed; {_COLOR_GUIDANCE}",
                )
            )
    return violations


def _px_lengths(value: str) -> list[float]:
    """Return every px length found in a value as floats."""
    return [float(match.group(1)) for match in _PX_RE.finditer(value)]


def _radius_violation(value: str) -> str | None:
    """Return a message when a border-radius value uses an off-token px literal."""
    if any(length > MAX_DECORATIVE_RADIUS_PX for length in _px_lengths(value)):
        return (
            f"off-token border-radius '{_normalize(value)}'; use var(--radius-*), "
            f"0, or 50% (px literals above {MAX_DECORATIVE_RADIUS_PX}px are off-token)"
        )
    return None


def _font_size_violation(value: str, allowed: frozenset[str]) -> str | None:
    """Return a message when a font-size value uses a non-allowlisted px literal."""
    if not _px_lengths(value):
        return None
    if _normalize(value) in allowed:
        return None
    return (
        f"raw px font-size '{_normalize(value)}'; use var(--font-size-*), a clamp() "
        "built on token or relative units, or an em / rem / % / inherit value"
    )


def _letter_spacing_violation(value: str, allowed: frozenset[str]) -> str | None:
    """Return a message when a letter-spacing value is an off-token literal.

    The entire value (ignoring a trailing ``!important``) must be ``normal``, a
    single ``var(--tracking-*)`` reference, or a grandfathered allowlisted
    literal; a token buried in a larger expression such as
    ``calc(var(--tracking-label) + 0.01em)`` does not pass.
    """
    bare = _IMPORTANT_RE.sub("", _normalize(value))
    if bare.lower() == "normal" or _TRACKING_VAR_RE.fullmatch(bare):
        return None
    if bare in allowed:
        return None
    return f"off-token letter-spacing '{_normalize(value)}'; use var(--tracking-*) or normal"


def _declaration_violations(css: str, display_path: str) -> list[tuple[int, str]]:
    """Return (line, message) pairs for off-token radius, font-size, and tracking."""
    font_size_allowed = FONT_SIZE_PX_ALLOWLIST.get(display_path, frozenset())
    letter_spacing_allowed = LETTER_SPACING_ALLOWLIST.get(display_path, frozenset())
    violations: list[tuple[int, str]] = []
    for match in _DECLARATION_RE.finditer(css):
        property_name = match.group(1).lower()
        value = match.group(2)
        if property_name.endswith("radius"):
            message = _radius_violation(value)
        elif property_name == "font-size":
            message = _font_size_violation(value, font_size_allowed)
        else:
            message = _letter_spacing_violation(value, letter_spacing_allowed)
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
        css = _mask(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as error:
        # Report the exception class only: its message varies by OS and path,
        # and the violation output should stay deterministic.
        return [
            f"{display_path}: stylesheet could not be read as UTF-8 text ({type(error).__name__})"
        ]

    found = [
        *_hex_violations(css),
        *_color_function_violations(css),
        *_color_mix_violations(css),
        *_named_color_violations(css),
        *_declaration_violations(css, display_path),
    ]
    return [f"{display_path}:{line}: {message}" for line, message in sorted(found)]


def discover_app_stylesheets(apps_dir: Path) -> list[Path]:
    """Return every ``apps/<slug>/css/*.css`` stylesheet under the apps directory."""
    if not apps_dir.is_dir():
        return []
    return sorted(apps_dir.glob("*/css/*.css"))


def run_check(root: Path | None = None) -> list[str]:
    """Run the app-CSS token check and return all violations.

    Finding zero stylesheets is itself a violation: it means the checker
    scanned nothing (a wrong ``--root``, a broken checkout, or a layout
    change), and silently passing would defeat the gate.
    """
    workspace_root = root or REPO_ROOT
    apps_dir = workspace_root / APPS_DIRNAME
    stylesheets = discover_app_stylesheets(apps_dir)
    if not stylesheets:
        return [
            f"{APPS_DIRNAME}: no stylesheets matched {APPS_DIRNAME}/*/css/*.css "
            f"under '{workspace_root}'; nothing was checked (wrong --root?)"
        ]
    violations: list[str] = []
    for stylesheet in stylesheets:
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
