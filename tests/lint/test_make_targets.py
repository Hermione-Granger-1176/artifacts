from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import scripts.lint.check_doc_commands as check_doc_commands
import scripts.lint.check_make_targets as check_make_targets
import scripts.lint.make_targets as make_targets

if TYPE_CHECKING:
    import pytest


def write_text(path: Path, content: str) -> None:
    """Write text."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_parse_makefile_targets_skips_special_targets() -> None:
    """Parse makefile targets skips special targets."""
    targets = make_targets.parse_makefile_targets(
        ".PHONY: lint\nsetup: install\nlint-js: ## Run eslint\n"
    )

    assert targets == {"setup", "lint-js"}


def test_parse_makefile_targets_adds_group_help_targets() -> None:
    """Parse makefile targets adds group help targets."""
    targets = make_targets.parse_makefile_targets(
        "# ─── Pull requests @pr ───\n"
        "pr: ## PR commands\n"
        "# ─── Quality gates @quality ───\n"
        "check-local: ## Run checks\n"
        "help-%: ## List one group\n"
    )

    assert {"help-pr", "help-quality"}.issubset(targets)


def test_iter_markdown_files_skips_build_directories(tmp_path: Path) -> None:
    """Iter markdown files skips build directories."""
    write_text(tmp_path / "README.md", "# Root\n")
    write_text(tmp_path / "docs" / "guide.md", "# Guide\n")
    write_text(tmp_path / "node_modules" / "pkg" / "README.md", "# Ignore\n")

    files = make_targets.iter_markdown_files(tmp_path)

    assert files == [tmp_path / "README.md", tmp_path / "docs" / "guide.md"]


def test_extract_make_references_handles_env_prefixes() -> None:
    """Extract make references handles env prefixes."""
    references = make_targets.extract_make_references(
        "Use `make check-local`\n"
        'Run `ARTIFACTS_BROWSER_APP_SLUGS="demo" make test-browser-apps`\n'
        "Generic `make <target>` guidance should be ignored.\n"
    )

    assert references == [
        make_targets.MakeReference(
            target="check-local",
            line_number=1,
            snippet="make check-local",
        ),
        make_targets.MakeReference(
            target="test-browser-apps",
            line_number=2,
            snippet='ARTIFACTS_BROWSER_APP_SLUGS="demo" make test-browser-apps',
        ),
    ]


def test_extract_make_references_ignores_plain_prose_make_mentions() -> None:
    """Extract make references ignores plain prose make mentions."""
    references = make_targets.extract_make_references(
        "Adding a new make target with ## description makes it appear automatically.\n"
        "CI and local workflows use the same make targets.\n"
    )

    assert references == []


def test_extract_markdown_code_snippets_ignores_shell_comments_in_fences() -> None:
    """Extract markdown code snippets ignores shell comments in fences."""
    snippets = make_targets.extract_markdown_code_snippets(
        "```bash\n# pytest is wrapped by make test-py\npytest\n```\n"
    )

    assert snippets == [make_targets.CodeSnippet(line_number=3, text="pytest")]


def test_check_make_targets_reports_unknown_target(tmp_path: Path) -> None:
    """Check make targets reports unknown target."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\ncheck-local:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "Run `make check-local` and `make nope`.\n")

    violations = check_make_targets.run_check(paths=[doc_path], root=tmp_path)

    assert violations == ["README.md:1: unknown Make target `nope`"]


def test_check_make_targets_main_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check make targets main reports success."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\ncheck-local:\n\t@true\n")
    write_text(tmp_path / "README.md", "Use `make check-local`.\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_make_targets, "MAKEFILE_PATH", tmp_path / "Makefile")

    exit_code = check_make_targets.main(["README.md"])

    assert exit_code == 0
    assert "Make target check passed for 1 file(s)" in capsys.readouterr().out


def test_check_make_targets_main_rejects_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check make targets main rejects missing path."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_make_targets, "MAKEFILE_PATH", tmp_path / "Makefile")

    exit_code = check_make_targets.main(["missing.md"])

    assert exit_code == 1
    assert "path does not exist" in capsys.readouterr().out


def test_main_rejects_path_escaping_workspace_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Main rejects path escaping workspace root."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_make_targets, "MAKEFILE_PATH", tmp_path / "Makefile")

    exit_code = check_make_targets.main(["../../../etc/passwd"])

    assert exit_code == 1
    assert "escapes workspace root" in capsys.readouterr().out


def test_iter_default_paths_limits_command_lint_scope(tmp_path: Path) -> None:
    """Iter default paths limits command lint scope."""
    write_text(tmp_path / "README.md", "# Readme\n")
    write_text(tmp_path / "CLAUDE.md", "# Agent\n")
    write_text(tmp_path / ".github" / "CONTRIBUTING.md", "# Contributing\n")
    write_text(tmp_path / ".github" / "pull_request_template.md", "# Template\n")
    write_text(tmp_path / "docs" / "operations.md", "# Operations\n")
    write_text(tmp_path / "docs" / "architecture.md", "# Internal\n")

    paths = check_doc_commands.iter_default_paths(tmp_path)

    assert paths == [
        tmp_path / "README.md",
        tmp_path / "CLAUDE.md",
        tmp_path / ".github" / "CONTRIBUTING.md",
        tmp_path / ".github" / "pull_request_template.md",
        tmp_path / "docs" / "operations.md",
    ]


def test_extract_markdown_code_snippets_reads_inline_and_fenced_blocks() -> None:
    """Extract markdown code snippets reads inline and fenced blocks."""
    snippets = make_targets.extract_markdown_code_snippets(
        "Use `make help`.\n\n```bash\npytest\nmake test-py\n```\n"
    )

    assert snippets == [
        make_targets.CodeSnippet(line_number=1, text="make help"),
        make_targets.CodeSnippet(line_number=4, text="pytest"),
        make_targets.CodeSnippet(line_number=5, text="make test-py"),
    ]


def test_extract_markdown_code_snippets_skips_blank_inline_code() -> None:
    """Extract markdown code snippets ignores whitespace-only inline code."""
    assert make_targets.extract_markdown_code_snippets("A blank ` ` span.\n") == []


def test_find_replacement_targets_uses_makefile_targets() -> None:
    """Find replacement targets uses makefile targets."""
    targets = check_doc_commands.find_replacement_targets(
        "python -m pytest --ignore=tests/browser",
        {"test-py", "lint-py"},
    )

    assert targets == ["test-py"]


def test_find_replacement_targets_ignores_make_only_commands() -> None:
    """Find replacement targets ignores make only commands."""
    targets = check_doc_commands.find_replacement_targets("make test-py", {"test-py"})

    assert targets == []


def test_find_replacement_targets_reports_make_and_raw_mix() -> None:
    """Find replacement targets reports make and raw mix."""
    targets = check_doc_commands.find_replacement_targets(
        "make setup && pytest && npm run lint:js",
        {"setup", "test-py", "lint-js"},
    )

    assert targets == ["test-py", "lint-js"]


def test_find_replacement_targets_prefers_full_match_rules() -> None:
    """Find replacement targets prefers full match rules."""
    targets = check_doc_commands.find_replacement_targets(
        "npm run test:coverage",
        {"coverage-js", "test-js"},
    )

    assert targets == ["coverage-js"]


def test_find_replacement_targets_deduplicates_repeated_targets() -> None:
    """Find replacement targets deduplicates repeated targets."""
    targets = check_doc_commands.find_replacement_targets(
        "pip-audit && npm audit",
        {"security"},
    )

    assert targets == ["security"]


def test_find_replacement_targets_ignores_empty_shell_segments() -> None:
    """Find replacement targets ignores empty shell segments."""
    targets = check_doc_commands.find_replacement_targets(
        " && pytest ; ",
        {"test-py"},
    )

    assert targets == ["test-py"]


def test_find_replacement_targets_covers_additional_make_equivalents() -> None:
    """Find replacement targets covers additional make equivalents."""
    targets = check_doc_commands.find_replacement_targets(
        "npm install --package-lock-only && npm run lint:js -- --fix && npm run lint:css -- --fix",
        {"lock-node", "fmt-js", "fmt-css"},
    )

    assert targets == ["lock-node", "fmt-js", "fmt-css"]


def test_find_replacement_targets_covers_quality_tooling() -> None:
    """Find replacement targets covers quality tooling."""
    targets = check_doc_commands.find_replacement_targets(
        "npm run format:check && python -m vulture && npm run dead-code",
        {"format-prettier-check", "dead-code-py", "dead-code-js"},
    )

    assert targets == ["format-prettier-check", "dead-code-py", "dead-code-js"]


def test_find_replacement_targets_ignores_descriptive_tool_names() -> None:
    """Find replacement targets ignores descriptive tool names."""
    targets = check_doc_commands.find_replacement_targets(
        "ruff scans Python files",
        {"lint-py"},
    )

    assert targets == []


def test_check_doc_commands_reports_direct_commands(tmp_path: Path) -> None:
    """Check doc commands reports direct commands."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\nlint-js:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(
        doc_path,
        "Use `python -m pytest --ignore=tests/browser` and `npm run lint:js`.\n",
    )

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == [
        "README.md:1: use `make test-py` instead of `python -m pytest --ignore=tests/browser`",
        "README.md:1: use `make lint-js` instead of `npm run lint:js`",
    ]


def test_check_doc_commands_reports_multiple_direct_commands_in_one_snippet(
    tmp_path: Path,
) -> None:
    """Check doc commands reports multiple direct commands in one snippet."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\nlint-js:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "Use `make setup && pytest && npm run lint:js`.\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == [
        "README.md:1: use `make test-py` instead of `make setup && pytest && npm run lint:js`",
        "README.md:1: use `make lint-js` instead of `make setup && pytest && npm run lint:js`",
    ]


def test_check_doc_commands_ignores_comment_only_fence_lines(tmp_path: Path) -> None:
    """Check doc commands ignores comment only fence lines."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "```bash\n# pytest is wrapped by make test-py\n```\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == []


def test_check_doc_commands_flags_fenced_commands(tmp_path: Path) -> None:
    """Check doc commands flags fenced commands."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "```bash\npytest\n```\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == ["README.md:2: use `make test-py` instead of `pytest`"]


def test_check_doc_commands_default_scope_avoids_internal_docs(tmp_path: Path) -> None:
    """Check doc commands default scope avoids internal docs."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    write_text(tmp_path / "README.md", "Use `make help`.\n")
    write_text(
        tmp_path / "docs" / "architecture.md",
        "Internal note: `pytest --cov=scripts/`.\n",
    )

    violations = check_doc_commands.run_check(root=tmp_path)

    assert violations == []


def test_check_doc_commands_ignores_descriptive_tool_mentions(tmp_path: Path) -> None:
    """Check doc commands ignores descriptive tool mentions."""
    write_text(tmp_path / "Makefile", "lint-py:\n\t@true\ntest-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(
        doc_path,
        "- `pytest` enforces coverage for Python tests.\n- `ruff` scans Python files.\n",
    )

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == []


def test_check_doc_commands_ignores_negated_commands(tmp_path: Path) -> None:
    """Check doc commands ignores negated commands."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "Do not run `pytest` directly.\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == []


def test_check_doc_commands_scopes_negation_to_the_current_clause(
    tmp_path: Path,
) -> None:
    """Check doc commands scopes negation to the current clause."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\nlint-js:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "Do not run `pytest`; instead run `npm run lint:js`.\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == ["README.md:1: use `make lint-js` instead of `npm run lint:js`"]


def test_check_doc_commands_scopes_negation_across_comma_clauses(
    tmp_path: Path,
) -> None:
    """Check doc commands scopes negation across comma clauses."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\nlint-js:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "Do not run `pytest`, instead run `npm run lint:js`.\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == ["README.md:1: use `make lint-js` instead of `npm run lint:js`"]


def test_check_doc_commands_flags_plain_bullets_with_explanatory_suffixes(
    tmp_path: Path,
) -> None:
    """Check doc commands flags plain bullets with explanatory suffixes."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\nlint-js:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(
        doc_path,
        "- `pytest` to run Python tests.\n- `npm run lint:js` for JS linting.\n",
    )

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == [
        "README.md:1: use `make test-py` instead of `pytest`",
        "README.md:2: use `make lint-js` instead of `npm run lint:js`",
    ]


def test_check_doc_commands_flags_checklist_commands(tmp_path: Path) -> None:
    """Check doc commands flags checklist commands."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "- [ ] `pytest`\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == ["README.md:1: use `make test-py` instead of `pytest`"]


def test_check_doc_commands_flags_ordered_command_steps(tmp_path: Path) -> None:
    """Check doc commands flags ordered command steps."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "1. `pytest`\n")

    violations = check_doc_commands.run_check(paths=[doc_path], root=tmp_path)

    assert violations == ["README.md:1: use `make test-py` instead of `pytest`"]


def test_check_doc_commands_main_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check doc commands main reports failure."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    write_text(tmp_path / "README.md", "Run `pytest`.\n")
    monkeypatch.setattr(check_doc_commands, "REPO_ROOT", tmp_path)

    exit_code = check_doc_commands.main(["README.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "Command lint failed:" in captured
    assert "use `make test-py` instead of `pytest`" in captured


def test_check_doc_commands_main_uses_default_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check doc commands main uses default paths."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    write_text(tmp_path / "README.md", "Run `make test-py`.\n")
    write_text(tmp_path / ".github" / "CONTRIBUTING.md", "Use `make test-py`.\n")
    monkeypatch.setattr(check_doc_commands, "REPO_ROOT", tmp_path)

    exit_code = check_doc_commands.main([])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "Command lint passed for 2 file(s)"


def test_check_doc_commands_main_reports_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check doc commands main reports success."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    write_text(tmp_path / "README.md", "Run `make test-py`.\n")
    monkeypatch.setattr(check_doc_commands, "REPO_ROOT", tmp_path)

    exit_code = check_doc_commands.main(["README.md"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "Command lint passed for 1 file(s)"


def test_check_doc_commands_main_rejects_missing_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check doc commands main rejects missing path."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    monkeypatch.setattr(check_doc_commands, "REPO_ROOT", tmp_path)

    exit_code = check_doc_commands.main(["missing.md"])

    assert exit_code == 1
    assert "path does not exist" in capsys.readouterr().out


def test_check_make_targets_main_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check make targets main reports failure."""
    write_text(tmp_path / "Makefile", "check-local:\n\t@true\n")
    write_text(tmp_path / "README.md", "Use `make missing-target`.\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_make_targets, "MAKEFILE_PATH", tmp_path / "Makefile")

    exit_code = check_make_targets.main(["README.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "Make target check failed:" in captured
    assert "unknown Make target `missing-target`" in captured


def test_check_make_targets_main_uses_default_markdown_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Check make targets main uses default markdown scope."""
    write_text(tmp_path / "Makefile", "check-local:\n\t@true\n")
    write_text(tmp_path / "README.md", "Use `make check-local`.\n")
    write_text(tmp_path / "docs" / "operations.md", "Use `make check-local`.\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_make_targets, "MAKEFILE_PATH", tmp_path / "Makefile")

    exit_code = check_make_targets.main([])

    assert exit_code == 0
    assert "Make target check passed for 2 file(s)" in capsys.readouterr().out
