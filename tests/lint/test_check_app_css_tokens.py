"""Tests for the app-CSS design-token lint check."""

from __future__ import annotations

from pathlib import Path

from scripts.lint.check_app_css_tokens import (
    _color_function_violations,
    _color_mix_violations,
    _font_size_violation,
    _hex_violations,
    _in_declaration_value,
    _letter_spacing_violation,
    _mask,
    _named_color_violations,
    _radius_violation,
    check_stylesheet,
    discover_app_stylesheets,
    main,
    parse_args,
    run_check,
)

NO_ALLOWED = frozenset[str]()


def _write_css(root: Path, slug: str, css: str, *, filename: str = "app.css") -> Path:
    """Write a stylesheet at ``apps/<slug>/css/<filename>`` under a root."""
    path = root / "apps" / slug / "css" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(css, encoding="utf-8")
    return path


# --- masking ----------------------------------------------------------------


def test_mask_blanks_content_and_keeps_line_numbers() -> None:
    """Comment text is masked to spaces while newlines are preserved."""
    css = "a {\n/* off-token 12px\n#fff literal */\n}\n"
    masked = _mask(css)

    # Same length and newline positions, so offsets and line numbers stay stable.
    assert len(masked) == len(css)
    assert masked.count("\n") == css.count("\n")
    assert "12px" not in masked
    assert "#fff" not in masked


def test_mask_hides_comments_strings_and_urls_from_scanners() -> None:
    """Hex colors inside comments, strings, and url() produce no violations."""
    css = (
        "body.app-x .a {\n"
        "  /* background: #ffffff; */\n"
        '  content: "#fff";\n'
        "  quotes: '#abc';\n"
        "  filter: url(#abcdef12);\n"
        "  color: var(--color-text);\n"
        "}\n"
    )
    assert _hex_violations(_mask(css)) == []


def test_mask_handles_escaped_quotes_inside_strings() -> None:
    """An escaped quote cannot end a string early and leak its contents."""
    css = 'body.app-x .a::before {\n  content: "\\"#fff\\"";\n  color: var(--color-text);\n}\n'
    assert _hex_violations(_mask(css)) == []


# --- value-position gating ---------------------------------------------------


def test_in_declaration_value_distinguishes_value_from_selector() -> None:
    """An offset after 'property:' is a value; a selector offset is not."""
    css = "#fff {\n  color: #fff;\n}\n"
    selector_index = css.index("#fff")
    value_index = css.index("#fff", selector_index + 1)
    assert not _in_declaration_value(css, selector_index)
    assert _in_declaration_value(css, value_index)


# --- hex colors ------------------------------------------------------------


def test_hex_violations_flags_hex_color() -> None:
    """A literal hex color in a value is flagged with its line number."""
    css = "body.app-x .a {\n  color: #ffffff;\n}\n"
    result = _hex_violations(_mask(css))
    assert result == [(2, result[0][1])]
    assert "#ffffff" in result[0][1]


def test_hex_violations_ignores_id_selector() -> None:
    """A hex-looking id selector is not a color value and passes."""
    css = "#fff {\n  color: var(--color-text);\n}\n"
    assert _hex_violations(_mask(css)) == []


def test_hex_violations_ignores_invalid_hex_lengths() -> None:
    """Runs of 5 or 7 hex digits are not valid CSS colors and pass."""
    css = "body.app-x .a {\n  color: #12345;\n  background: #1234567;\n}\n"
    assert _hex_violations(_mask(css)) == []


# --- literal color functions -------------------------------------------------


def test_color_function_flags_all_numeric_arguments() -> None:
    """An all-numeric rgba() call is flagged as a literal color."""
    css = "body.app-x .a { color: rgba(255, 0, 0, 0.5); }\n"
    result = _color_function_violations(_mask(css))
    assert len(result) == 1
    assert "rgba(255, 0, 0, 0.5)" in result[0][1]


def test_color_function_flags_var_only_in_alpha() -> None:
    """Literal channels with a token buried in the alpha are still literal."""
    css = "body.app-x .a { color: rgba(255, 0, 0, var(--alpha)); }\n"
    result = _color_function_violations(_mask(css))
    assert len(result) == 1
    assert "rgba(255, 0, 0," in result[0][1]


def test_color_function_flags_other_color_spaces() -> None:
    """Literal hsl() and oklch() calls are flagged like rgb()."""
    css = "body.app-x .a { color: hsl(10 50% 50%); background: oklch(0.7 0.1 200); }\n"
    assert len(_color_function_violations(_mask(css))) == 2


def test_color_function_allows_var_arguments() -> None:
    """An rgb() call whose channels start from a var() reference is allowed."""
    css = "body.app-x .a { color: rgb(var(--rgb-channels) / 0.5); }\n"
    assert _color_function_violations(_mask(css)) == []


def test_color_function_allows_color_mix_arguments() -> None:
    """An rgb() call wrapping a color-mix() is allowed by the function rule."""
    css = "body.app-x .a { color: rgb(color-mix(in srgb, var(--a) 50%, var(--b))); }\n"
    assert _color_function_violations(_mask(css)) == []


def test_color_function_flags_color_mix_lookalike_identifier() -> None:
    """An identifier merely containing 'color-mix' is not a color-mix() call."""
    css = "body.app-x .a { color: rgb(my-color-mix-channels); }\n"
    assert len(_color_function_violations(_mask(css))) == 1


# --- color-mix -------------------------------------------------------------


def test_color_mix_flags_literal_mix() -> None:
    """A color-mix() that references no var() token is flagged."""
    css = "body.app-x .a { color: color-mix(in srgb, red, blue); }\n"
    result = _color_mix_violations(_mask(css))
    assert len(result) == 1
    assert "color-mix" in result[0][1]


def test_color_mix_allows_token_mix() -> None:
    """A color-mix() built on a var() token is allowed."""
    css = "body.app-x .a { color: color-mix(in srgb, var(--color-blue) 40%, transparent); }\n"
    assert _color_mix_violations(_mask(css)) == []


def test_color_mix_sees_var_after_a_nested_call() -> None:
    """A var() that follows a nested call still counts as a token input."""
    css = "body.app-x .a { color: color-mix(in srgb, rgb(1 2 3) 50%, var(--b)); }\n"
    # The outer mix is token-derived; the literal inner rgb() is the function
    # rule's finding, not a color-mix one.
    assert _color_mix_violations(_mask(css)) == []
    assert len(_color_function_violations(_mask(css))) == 1


def test_color_mix_flags_unterminated_literal_call() -> None:
    """An unterminated literal color-mix() is still flagged."""
    css = "body.app-x .a { color: color-mix(in srgb, red"
    result = _color_mix_violations(_mask(css))
    assert len(result) == 1


# --- named colors -----------------------------------------------------------


def test_named_color_flags_keyword_in_color_declaration() -> None:
    """A named color in a color-bearing declaration is flagged."""
    css = "body.app-x .a {\n  border: 1px solid salmon;\n}\n"
    result = _named_color_violations(_mask(css))
    assert len(result) == 1
    assert "salmon" in result[0][1]
    assert result[0][0] == 2


def test_named_color_flags_custom_property_definition() -> None:
    """A named color assigned to an app custom property is flagged."""
    css = "body.app-x { --pc-warn: gold; }\n"
    result = _named_color_violations(_mask(css))
    assert len(result) == 1
    assert "gold" in result[0][1]


def test_named_color_ignores_var_token_names_and_keywords() -> None:
    """Token names, non-color words, and CSS-wide keywords are not flagged."""
    css = (
        "body.app-x .a {\n"
        "  background: var(--note-red);\n"
        "  border-color: transparent;\n"
        "  color: currentcolor;\n"
        "  outline: none;\n"
        "}\n"
    )
    assert _named_color_violations(_mask(css)) == []


def test_named_color_ignores_non_color_properties() -> None:
    """Color words in non-color declarations (or selectors) are not scanned."""
    css = ".card-icon.blue {\n  white-space: pre;\n  animation-name: tomato;\n}\n"
    assert _named_color_violations(_mask(css)) == []


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


def test_radius_violation_flags_scientific_notation_px() -> None:
    """A 6e1px radius is 60px and cannot sneak past the cap."""
    message = _radius_violation("6e1px")
    assert message is not None
    assert "6e1px" in message


def test_radius_violation_allows_tokens_and_keywords() -> None:
    """Token, zero, and percentage radii carry no px literal and pass."""
    assert _radius_violation("var(--radius-md)") is None
    assert _radius_violation("0") is None
    assert _radius_violation("50%") is None


# --- font-size -------------------------------------------------------------


def test_font_size_violation_flags_raw_px() -> None:
    """A raw px font-size that is not allowlisted is flagged."""
    message = _font_size_violation("13px", NO_ALLOWED)
    assert message is not None
    assert "13px" in message


def test_font_size_violation_flags_leading_decimal_px() -> None:
    """A leading-decimal px font-size such as .5px is still a raw px literal."""
    message = _font_size_violation(".5px", NO_ALLOWED)
    assert message is not None
    assert ".5px" in message


def test_font_size_violation_respects_the_passed_allowlist() -> None:
    """A grandfathered px literal passes only with its file's allowlist."""
    assert _font_size_violation("17px", frozenset({"17px"})) is None
    assert _font_size_violation("17px", NO_ALLOWED) is not None


def test_font_size_violation_allows_token_and_relative_units() -> None:
    """A tokenized or relative font-size carries no px literal and passes."""
    assert _font_size_violation("var(--font-size-sm)", NO_ALLOWED) is None
    assert _font_size_violation("clamp(1rem, 2vw, 1.5rem)", NO_ALLOWED) is None


# --- letter-spacing --------------------------------------------------------


def test_letter_spacing_violation_flags_off_token_literal() -> None:
    """A non-allowlisted letter-spacing literal is flagged."""
    message = _letter_spacing_violation("0.08em", NO_ALLOWED)
    assert message is not None
    assert "0.08em" in message


def test_letter_spacing_violation_allows_normal_var_and_allowlist() -> None:
    """Keyword, tracking token, and per-file allowlisted values pass."""
    assert _letter_spacing_violation("normal", NO_ALLOWED) is None
    assert _letter_spacing_violation("var(--tracking-label)", NO_ALLOWED) is None
    assert _letter_spacing_violation("0.16em", frozenset({"0.16em"})) is None
    assert _letter_spacing_violation("0.16em", NO_ALLOWED) is not None


def test_letter_spacing_violation_flags_non_tracking_var() -> None:
    """A var() reference outside the tracking token family is flagged."""
    message = _letter_spacing_violation("var(--color-text)", NO_ALLOWED)
    assert message is not None
    assert "var(--color-text)" in message


def test_letter_spacing_violation_flags_token_inside_larger_expression() -> None:
    """A tracking token buried in a calc() expression is flagged."""
    message = _letter_spacing_violation("calc(var(--tracking-label) + 0.01em)", NO_ALLOWED)
    assert message is not None
    assert "calc(var(--tracking-label) + 0.01em)" in message


def test_letter_spacing_violation_tolerates_trailing_important() -> None:
    """A lone tracking token with !important still passes."""
    assert _letter_spacing_violation("var(--tracking-label) !important", NO_ALLOWED) is None


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
        "  border-color: color-mix(in srgb, red, blue);\n"
        "  outline-color: rebeccapurple;\n"
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
    assert any("literal color 'rgb(1, 2, 3)'" in message for message in violations)
    assert any("literal color-mix" in message for message in violations)
    assert any("named color 'rebeccapurple'" in message for message in violations)
    assert any("px font-size" in message for message in violations)
    assert any("letter-spacing" in message for message in violations)


def test_check_stylesheet_scopes_allowlists_to_the_owning_file(tmp_path: Path) -> None:
    """A grandfathered literal passes in its owning file and fails elsewhere."""
    css = "body.app-x .a {\n  font-size: 9px;\n}\n"
    owner = _write_css(tmp_path, "prompt-caching", css)
    other = _write_css(tmp_path, "demo", css)
    assert check_stylesheet(owner, display_path="apps/prompt-caching/css/app.css") == []
    flagged = check_stylesheet(other, display_path="apps/demo/css/app.css")
    assert len(flagged) == 1
    assert "9px" in flagged[0]


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


def test_run_check_fails_closed_when_no_stylesheets_found(tmp_path: Path) -> None:
    """Scanning nothing is a violation, not a silent pass."""
    violations = run_check(tmp_path)
    assert len(violations) == 1
    assert violations[0].startswith("apps: no stylesheets matched")


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
