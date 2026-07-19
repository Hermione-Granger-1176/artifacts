"""Tests for the app-CSS design-token lint check."""

from __future__ import annotations

from pathlib import Path

from scripts.lint.check_app_css_tokens import (
    _font_size_violation,
    _hex_violations,
    _letter_spacing_violation,
    _literal_color_violations,
    _mask_comments,
    _radius_violation,
    check_stylesheet,
    discover_app_stylesheets,
    main,
    parse_args,
    run_check,
)


def _write_css(root: Path, slug: str, css: str, *, filename: str = "app.css") -> Path:
    """Write a stylesheet at ``apps/<slug>/css/<filename>`` under a root."""
    path = root / "apps" / slug / "css" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(css, encoding="utf-8")
    return path


# --- comment masking -------------------------------------------------------


def test_mask_comments_blanks_content_and_keeps_line_numbers() -> None:
    """Comment text is masked to spaces while newlines are preserved."""
    css = "a {\n/* off-token 12px\n#fff literal */\n}\n"
    masked = _mask_comments(css)

    # Same length and newline positions, so offsets and line numbers stay stable.
    assert len(masked) == len(css)
    assert masked.count("\n") == css.count("\n")
    assert "12px" not in masked
    assert "#fff" not in masked


def test_mask_comments_hides_values_from_scanners() -> None:
    """A hex color inside a comment produces no violation."""
    css = "body.app-x .a {\n  /* background: #ffffff; */\n  color: var(--color-text);\n}\n"
    assert _hex_violations(_mask_comments(css)) == []


# --- hex colors ------------------------------------------------------------


def test_hex_violations_flags_hex_color() -> None:
    """A literal hex color is flagged with its line number."""
    css = "body.app-x .a {\n  color: #ffffff;\n}\n"
    violations = _mask_comments(css)
    result = _hex_violations(violations)
    assert result == [(2, result[0][1])]
    assert "#ffffff" in result[0][1]


def test_hex_violations_ignores_invalid_hex_lengths() -> None:
    """Runs of 5 or 7 hex digits are not valid CSS colors and pass."""
    css = "body.app-x .a {\n  content: '#12345 #1234567';\n}\n"
    assert _hex_violations(css) == []


# --- literal rgb / rgba colors ---------------------------------------------


def test_literal_color_flags_all_numeric_arguments() -> None:
    """An all-numeric rgba() call is flagged as a literal color."""
    css = "body.app-x .a { color: rgba(255, 0, 0, 0.5); }\n"
    result = _literal_color_violations(_mask_comments(css))
    assert len(result) == 1
    assert "rgba(255, 0, 0, 0.5)" in result[0][1]


def test_literal_color_allows_var_arguments() -> None:
    """An rgb() call built from a var() reference is allowed."""
    css = "body.app-x .a { color: rgb(var(--rgb-channels) / 0.5); }\n"
    assert _literal_color_violations(_mask_comments(css)) == []


def test_literal_color_allows_color_mix_arguments() -> None:
    """An rgb() call wrapping a color-mix() is allowed."""
    css = "body.app-x .a { color: rgb(color-mix(in srgb, red 50%, blue)); }\n"
    assert _literal_color_violations(_mask_comments(css)) == []


def test_literal_color_flags_color_mix_lookalike_identifier() -> None:
    """An identifier merely containing 'color-mix' is not a color-mix() call."""
    css = "body.app-x .a { color: rgb(my-color-mix-channels); }\n"
    result = _literal_color_violations(_mask_comments(css))
    assert len(result) == 1


# --- border-radius ---------------------------------------------------------


def test_radius_violation_flags_px_of_six_or_more() -> None:
    """A 6px radius is off-token and flagged."""
    message = _radius_violation("6px")
    assert message is not None
    assert "6px" in message


def test_radius_violation_allows_sub_token_decorative_radii() -> None:
    """A 5px decorative radius is allowed."""
    assert _radius_violation("5px") is None


def test_radius_violation_flags_fractional_px_above_the_cap() -> None:
    """A 5.5px radius sits above the decorative cap and is flagged."""
    message = _radius_violation("5.5px")
    assert message is not None
    assert "5.5px" in message


def test_radius_violation_allows_tokens_and_keywords() -> None:
    """Token, zero, and percentage radii carry no px literal and pass."""
    assert _radius_violation("var(--radius-md)") is None
    assert _radius_violation("0") is None
    assert _radius_violation("50%") is None


# --- font-size -------------------------------------------------------------


def test_font_size_violation_flags_raw_px() -> None:
    """A raw px font-size that is not allowlisted is flagged."""
    message = _font_size_violation("13px")
    assert message is not None
    assert "13px" in message


def test_font_size_violation_flags_leading_decimal_px() -> None:
    """A leading-decimal px font-size such as .5px is still a raw px literal."""
    message = _font_size_violation(".5px")
    assert message is not None
    assert ".5px" in message


def test_font_size_violation_allows_allowlisted_px() -> None:
    """A grandfathered display px font-size is allowed."""
    assert _font_size_violation("17px") is None


def test_font_size_violation_allows_token_and_relative_units() -> None:
    """A tokenized or relative font-size carries no px literal and passes."""
    assert _font_size_violation("var(--font-size-sm)") is None
    assert _font_size_violation("clamp(1rem, 2vw, 1.5rem)") is None


# --- letter-spacing --------------------------------------------------------


def test_letter_spacing_violation_flags_off_token_literal() -> None:
    """A non-allowlisted letter-spacing literal is flagged."""
    message = _letter_spacing_violation("0.08em")
    assert message is not None
    assert "0.08em" in message


def test_letter_spacing_violation_allows_normal_var_and_allowlist() -> None:
    """Keyword, tracking token, and grandfathered letter-spacing values pass."""
    assert _letter_spacing_violation("normal") is None
    assert _letter_spacing_violation("var(--tracking-label)") is None
    assert _letter_spacing_violation("0.16em") is None


def test_letter_spacing_violation_flags_non_tracking_var() -> None:
    """A var() reference outside the tracking token family is flagged."""
    message = _letter_spacing_violation("var(--color-text)")
    assert message is not None
    assert "var(--color-text)" in message


# --- whole-stylesheet checks ----------------------------------------------


def test_check_stylesheet_passes_for_token_based_css(tmp_path: Path) -> None:
    """A fully tokenized stylesheet reports no violations."""
    css = (
        "body.app-demo .a {\n"
        "  color: var(--color-text);\n"
        "  border-radius: var(--radius-sm);\n"
        "  font-size: var(--font-size-md);\n"
        "  letter-spacing: var(--tracking-label);\n"
        "}\n"
    )
    path = _write_css(tmp_path, "demo", css)
    assert check_stylesheet(path, display_path="apps/demo/css/app.css") == []


def test_check_stylesheet_reports_sorted_violations(tmp_path: Path) -> None:
    """Every rule fires and violations are ordered by line number."""
    css = (
        "body.app-demo .a {\n"
        "  border-radius: 10px;\n"
        "  color: #abcdef;\n"
        "  background: rgb(1, 2, 3);\n"
        "  font-size: 21px;\n"
        "  letter-spacing: 0.3em;\n"
        "}\n"
    )
    path = _write_css(tmp_path, "demo", css)
    violations = check_stylesheet(path, display_path="apps/demo/css/app.css")

    line_numbers = [int(message.split(":")[1]) for message in violations]
    assert line_numbers == sorted(line_numbers)
    assert any("border-radius" in message for message in violations)
    assert any("hex color" in message for message in violations)
    assert any("literal color" in message for message in violations)
    assert any("px font-size" in message for message in violations)
    assert any("letter-spacing" in message for message in violations)


def test_check_stylesheet_reports_non_utf8_file_as_violation(tmp_path: Path) -> None:
    """A binary stylesheet is reported as a violation instead of crashing."""
    path = tmp_path / "apps" / "demo" / "css" / "app.css"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfe\x00\x01not utf-8")
    violations = check_stylesheet(path, display_path="apps/demo/css/app.css")
    assert len(violations) == 1
    assert violations[0].startswith(
        "apps/demo/css/app.css: stylesheet could not be read as UTF-8 text"
    )


def test_check_stylesheet_reports_unreadable_file_as_violation(tmp_path: Path) -> None:
    """An OSError while reading (here a directory) becomes a violation."""
    path = tmp_path / "apps" / "demo" / "css" / "app.css"
    path.mkdir(parents=True)
    violations = check_stylesheet(path, display_path="apps/demo/css/app.css")
    assert len(violations) == 1
    assert violations[0].startswith(
        "apps/demo/css/app.css: stylesheet could not be read as UTF-8 text"
    )


# --- discovery and aggregation --------------------------------------------


def test_discover_app_stylesheets_returns_sorted_paths(tmp_path: Path) -> None:
    """Stylesheets are discovered in sorted order."""
    _write_css(tmp_path, "beta", "body.app-beta {}\n")
    _write_css(tmp_path, "alpha", "body.app-alpha {}\n", filename="extra.css")
    paths = discover_app_stylesheets(tmp_path / "apps")
    assert [path.parent.parent.name for path in paths] == ["alpha", "beta"]


def test_discover_app_stylesheets_handles_missing_apps_dir(tmp_path: Path) -> None:
    """A missing apps directory yields no stylesheets."""
    assert discover_app_stylesheets(tmp_path / "apps") == []


def test_run_check_aggregates_violations(tmp_path: Path) -> None:
    """run_check surfaces violating files and skips clean ones."""
    _write_css(tmp_path, "good", "body.app-good .a { border-radius: var(--radius-sm); }\n")
    _write_css(tmp_path, "bad", "body.app-bad .a { border-radius: 12px; }\n")
    violations = run_check(tmp_path)
    assert any(message.startswith("apps/bad/css/app.css") for message in violations)
    assert not any(message.startswith("apps/good/css/app.css") for message in violations)


def test_run_check_passes_on_the_current_app_stylesheets() -> None:
    """The migrated app stylesheets on this branch stay on the shared tokens."""
    assert run_check() == []


# --- CLI -------------------------------------------------------------------


def test_parse_args_defaults_root_to_none() -> None:
    """The root argument defaults to None for auto-detection."""
    assert parse_args([]).root is None


def test_parse_args_accepts_root() -> None:
    """The root argument is captured when provided."""
    assert parse_args(["--root", "/tmp/x"]).root == "/tmp/x"


def test_main_returns_zero_when_clean() -> None:
    """Main returns 0 against the passing repository tree."""
    assert main([]) == 0


def test_main_returns_one_when_violations(tmp_path: Path) -> None:
    """Main returns 1 when a stylesheet drifts off the tokens."""
    _write_css(tmp_path, "demo", "body.app-demo .a { color: #fff; }\n")
    assert main(["--root", str(tmp_path)]) == 1
