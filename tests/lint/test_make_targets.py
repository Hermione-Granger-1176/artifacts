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


def test_iter_markdown_files_never_descends_into_skipped_directories(
    tmp_path: Path, scanned_directories: list[Path]
) -> None:
    """Iter markdown files never opens a skipped directory."""
    write_text(tmp_path / "docs" / "guide.md", "# Guide\n")
    write_text(tmp_path / "node_modules" / "pkg" / "README.md", "# Ignore\n")
    write_text(tmp_path / ".venv" / "lib" / "notes.md", "# Ignore\n")

    make_targets.iter_markdown_files(tmp_path)

    assert tmp_path in scanned_directories, "the recording scandir was not installed"
    assert tmp_path / "docs" in scanned_directories
    assert tmp_path / "node_modules" not in scanned_directories
    assert tmp_path / ".venv" not in scanned_directories


def test_iter_markdown_files_skips_symlinked_files_and_directories(tmp_path: Path) -> None:
    """Repository scans do not follow or return symlinked Markdown."""
    write_text(tmp_path / "README.md", "# Root\n")
    external = tmp_path.parent / f"{tmp_path.name}-external-docs"
    write_text(external / "outside.md", "# Outside\n")
    (tmp_path / "linked.md").symlink_to(tmp_path / "README.md")
    (tmp_path / "linked-docs").symlink_to(external, target_is_directory=True)

    assert make_targets.iter_markdown_files(tmp_path) == [tmp_path / "README.md"]


def test_extract_make_references_handles_env_prefixes() -> None:
    """Extract make references handles env prefixes."""
    references = make_targets.extract_make_references(
        "Use `make check-local`\n"
        'Run `ARTIFACTS_BROWSER_APP_SLUGS="demo" make test-browser-apps`\n'
        "Run `make --no-print-directory playwright-version`\n"
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
        make_targets.MakeReference(
            target="playwright-version",
            line_number=3,
            snippet="make --no-print-directory playwright-version",
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
    assert "path must stay within the repository" in capsys.readouterr().out


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


def test_find_shell_control_flow_flags_if_and_for() -> None:
    """Raw shell if/for at the start of a recipe line are flagged."""
    violations = make_targets.find_shell_control_flow(
        'target-a:\n\t@if [ -n "$(x)" ]; then echo hi; fi\n\tfor f in a b; do echo $$f; done\n'
    )

    assert [(v.target, v.keyword) for v in violations] == [
        ("target-a", "if"),
        ("target-a", "for"),
    ]


def test_find_shell_control_flow_ignores_make_if_function() -> None:
    """The Make ``$(if ...)`` function is not shell control flow."""
    violations = make_targets.find_shell_control_flow(
        "target-a:\n\t$(if $(src),--from-html $(src)) build\n"
    )

    assert violations == []


def test_find_shell_control_flow_ignores_define_blocks() -> None:
    """Control flow inside a define...endef helper is ignored."""
    violations = make_targets.find_shell_control_flow(
        "define helper\nif [ 1 ]; then true; fi\nendef\n\ntarget-a:\n\t@true\n"
    )

    assert violations == []


def test_find_shell_control_flow_ignores_quoted_program_bodies() -> None:
    """An if inside a quoted awk program spanning continuations is ignored."""
    violations = make_targets.find_shell_control_flow(
        "target-a:\n\t@awk ' \\\n\t\tif (ti == 0) next; \\\n\t' $(FILE)\n"
    )

    assert violations == []


def test_find_shell_control_flow_ignores_variable_continuations() -> None:
    """A tab-indented shell continuation of a variable assignment is ignored."""
    violations = make_targets.find_shell_control_flow(
        "VAR ?= $(shell \\\n\tif [ -z x ]; then echo a; fi)\n"
    )

    assert violations == []


def test_find_shell_control_flow_respects_allowlist() -> None:
    """Allowlisted targets may keep inline control flow."""
    content = 'coverage-js:\n\t@if [ -n "$(C)" ]; then a; else b; fi\n'

    assert make_targets.find_shell_control_flow(content) == []
    assert make_targets.find_shell_control_flow(content, allowlist=frozenset()) != []


def test_repository_makefile_has_no_raw_shell_control_flow() -> None:
    """The committed Makefile passes the raw shell control-flow check."""
    content = make_targets.MAKEFILE_PATH.read_text(encoding="utf-8")

    assert make_targets.find_shell_control_flow(content) == []


def test_run_control_flow_check_formats_violations(tmp_path: Path) -> None:
    """run_control_flow_check renders a greppable violation line."""
    makefile = tmp_path / "Makefile"
    write_text(makefile, "target-a:\n\tfor f in a; do :; done\n")

    violations = check_make_targets.run_control_flow_check(makefile)

    assert violations == [
        "Makefile:2: recipe for `target-a` begins raw shell control flow "
        "(`for`); move the logic into scripts/ or add the target to "
        "CONTROL_FLOW_ALLOWLIST with a reason"
    ]


def test_run_control_flow_check_defaults_to_repository_makefile() -> None:
    """With no path, the check reads the committed Makefile and finds nothing."""
    assert check_make_targets.run_control_flow_check() == []


def test_check_make_targets_main_reports_control_flow_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Raw shell control flow in the Makefile fails the make-targets lint."""
    write_text(tmp_path / "Makefile", "check-local:\n\t@while true; do :; done\n")
    write_text(tmp_path / "README.md", "Use `make check-local`.\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(check_make_targets, "MAKEFILE_PATH", tmp_path / "Makefile")

    exit_code = check_make_targets.main(["README.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "begins raw shell control flow" in captured
    assert "`while`" in captured


def test_parse_makefile_targets_does_not_invent_group_help_without_pattern() -> None:
    """Group comments alone do not create invokable help targets."""
    targets = make_targets.parse_makefile_targets(
        "# ─── Pull requests @pr ───\npr: ## PR commands\n"
    )

    assert "help-pr" not in targets


def test_extract_make_references_requires_standalone_make_command() -> None:
    """Executable-name substrings and paths are not mistaken for Make commands."""
    references = make_targets.extract_make_references(
        "Ignore `remake check-local`, `gmake check-local`, and `foo-make check-local`.\n"
        "Ignore `./make check-local` and `$make check-local`.\n"
        "Accept `make check-local&&make lint-py`.\n"
    )

    assert [reference.target for reference in references] == ["check-local", "lint-py"]


def test_run_check_reports_non_utf8_markdown(tmp_path: Path) -> None:
    """Invalid UTF-8 documentation fails without a traceback."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    doc_path.write_bytes(b"\x80bad")

    violations = check_make_targets.run_check(paths=[doc_path], root=tmp_path)

    assert violations == ["README.md: not valid UTF-8 text (invalid start byte)"]


def test_run_check_skips_default_path_symlink(tmp_path: Path) -> None:
    """Default scans skip Markdown symlinks instead of reading their targets."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    target = tmp_path / "target.md"
    write_text(target, "Run `make help`.\n")
    (tmp_path / "README.md").symlink_to(target)

    assert check_make_targets.run_check(root=tmp_path) == []


def test_main_reports_unknown_targets_consistently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unknown targets use shared CI failure context."""
    write_text(tmp_path / "Makefile", "check-local:\n\t@true\n")
    write_text(tmp_path / "README.md", "Use `make missing-target`.\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)

    exit_code = check_make_targets.main(["README.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert captured.startswith("Make target check failed:\n")
    assert "  README.md:1: unknown Make target `missing-target`" in captured


def test_main_rejects_invalid_paths_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing, unscannable, and escaping paths are rejected together."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    write_text(tmp_path / "notes.txt", "Use make help.\n")
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)

    exit_code = check_make_targets.main(["missing.md", "notes.txt", "../outside.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert "missing.md: path does not exist" in captured
    assert "notes.txt: path must be Markdown, YAML under .github" in captured
    assert "../outside.md: path must stay within the repository" in captured


def test_extract_source_code_snippets_requires_backticks() -> None:
    """Source prose is only a reference when the command is backticked."""
    references = make_targets.extract_path_make_references(
        Path("scripts/gh/pr_watch.py"),
        "# Run `make lint-py` first.\n"
        'raise GhError("inspect `make pr-review-comments` before merging")\n'
        "# We should make sure this works and make it fast.\n",
    )

    assert [reference.target for reference in references] == ["lint-py", "pr-review-comments"]


def test_extract_workflow_run_snippets_reads_block_scalars_and_inline_values() -> None:
    """Workflow shell is read directly, since every make word there is an invocation."""
    references = make_targets.extract_path_make_references(
        Path(".github/workflows/ci.yml"),
        "jobs:\n"
        "  build:\n"
        "    steps:\n"
        "      - name: Audit\n"
        "        run: |\n"
        "          make audit-node\n"
        "          make ci-alert-issue \\\n"
        "            title=x\n"
        "      - name: Lint\n"
        "        run: make lint-py\n"
        "      - name: Not shell\n"
        "        with:\n"
        "          args: make not-a-reference\n",
    )

    assert [reference.target for reference in references] == [
        "audit-node",
        "ci-alert-issue",
        "lint-py",
    ]


def test_extract_workflow_run_snippets_stops_at_the_next_key() -> None:
    """A block scalar ends at the next key rather than swallowing later steps."""
    snippets = make_targets.extract_workflow_run_snippets(
        "      - name: One\n        run: |\n          make lint-py\n      - name: Two\n"
    )

    assert [snippet.text for snippet in snippets] == ["make lint-py"]


def test_extract_workflow_run_snippets_stops_at_sibling_keys_of_a_dash_step() -> None:
    """A `- run: |` block ends at its sibling keys, not at nested env values."""
    snippets = make_targets.extract_workflow_run_snippets(
        "      - run: |\n"
        "          make lint-py\n"
        "        shell: bash\n"
        "        env:\n"
        "          CMD: make not-shell\n"
    )

    assert [snippet.text for snippet in snippets] == ["make lint-py"]


def test_extract_workflow_run_snippets_allows_a_comment_after_the_indicator() -> None:
    """A commented block indicator still opens a shell block."""
    snippets = make_targets.extract_workflow_run_snippets(
        "      - run: | # keep this in one step\n          make lint-py\n"
    )

    assert [snippet.text for snippet in snippets] == ["make lint-py"]


def test_extract_workflow_run_snippets_records_body_line_numbers() -> None:
    """Reported line numbers point at the shell line, not the run key."""
    snippets = make_targets.extract_workflow_run_snippets("steps:\n  run: |\n    make lint-py\n")

    assert [(snippet.line_number, snippet.text) for snippet in snippets] == [(3, "make lint-py")]


def test_extract_source_code_snippets_ignores_empty_backticks() -> None:
    """A backticked span holding only whitespace is not a command."""
    assert make_targets.extract_source_code_snippets("x = ` `  # ` `\n") == []


def test_extract_workflow_run_snippets_ignores_an_empty_run_value() -> None:
    """A `run:` key with no value and no block indicator yields nothing."""
    assert make_targets.extract_workflow_run_snippets("steps:\n  run:\n") == []


def test_extract_workflow_run_snippets_skips_blank_lines_inside_a_block() -> None:
    """Blank lines inside a block neither end it nor become snippets."""
    snippets = make_targets.extract_workflow_run_snippets(
        "  run: |\n    make lint-py\n\n    make test-py\n"
    )

    assert [snippet.text for snippet in snippets] == ["make lint-py", "make test-py"]


def test_extract_path_make_references_returns_nothing_for_unscanned_paths() -> None:
    """An unscanned path yields no references even when its text names a target."""
    assert make_targets.extract_path_make_references(Path("notes.txt"), "run `make help`") == []


def test_is_test_path_covers_directory_and_filename_conventions() -> None:
    """Test fixtures naming absent targets are excluded by path convention."""
    assert make_targets.is_test_path(Path("tests/test_check_make_targets.py"))
    assert make_targets.is_test_path(Path("web/tests/tutorial.test.js"))
    assert make_targets.is_test_path(Path("e2e/smoke.spec.js"))
    assert make_targets.is_test_path(Path("scripts/gh/test_helper.py"))
    assert not make_targets.is_test_path(Path("scripts/gh/pr_watch.py"))
    assert not make_targets.is_test_path(Path("docs/development.md"))


def test_snippet_extractor_selects_a_rule_per_file_kind() -> None:
    """Each scanned kind gets the extractor that avoids its false positives."""
    assert (
        make_targets.snippet_extractor(Path("README.md"))
        is make_targets.extract_markdown_code_snippets
    )
    assert (
        make_targets.snippet_extractor(Path(".github/workflows/ci.yml"))
        is make_targets.extract_workflow_run_snippets
    )
    assert (
        make_targets.snippet_extractor(Path(".github/actions/ci-setup/action.yml"))
        is make_targets.extract_workflow_run_snippets
    )
    assert (
        make_targets.snippet_extractor(Path(".github/dependabot.yml"))
        is make_targets.extract_workflow_run_snippets
    )
    assert (
        make_targets.snippet_extractor(Path("scripts/gh/pr_watch.py"))
        is make_targets.extract_source_code_snippets
    )


def test_snippet_extractor_skips_unscanned_paths() -> None:
    """Config YAML, test code, and other suffixes are not scanned."""
    assert make_targets.snippet_extractor(Path("config/anything.yml")) is None
    assert make_targets.snippet_extractor(Path("tests/test_pr_watch.py")) is None
    assert make_targets.snippet_extractor(Path("notes.txt")) is None
    assert make_targets.snippet_extractor(Path("web/src/styles.css")) is None


def test_iter_reference_files_covers_workflows_and_source_but_not_tests(tmp_path: Path) -> None:
    """The default scan reaches beyond Markdown without picking up fixtures."""
    write_text(tmp_path / "README.md", "# Root\n")
    write_text(tmp_path / ".github" / "workflows" / "ci.yml", "on: push\n")
    write_text(tmp_path / "scripts" / "tool.py", "x = 1\n")
    write_text(tmp_path / "tests" / "test_tool.py", "x = 1\n")
    write_text(tmp_path / "config" / "tool.yml", "x: 1\n")
    write_text(tmp_path / "node_modules" / "pkg" / "index.js", "x = 1\n")

    files = make_targets.iter_reference_files(tmp_path)

    assert sorted(path.relative_to(tmp_path).as_posix() for path in files) == [
        ".github/workflows/ci.yml",
        "README.md",
        "scripts/tool.py",
    ]


def test_run_check_reports_an_unknown_target_in_workflow_shell(tmp_path: Path) -> None:
    """A renamed target referenced by CI shell fails the lint."""
    write_text(tmp_path / "Makefile", "lint-py:\n\t@true\n")
    workflow = tmp_path / ".github" / "workflows" / "ci.yml"
    write_text(workflow, "steps:\n  - run: |\n      make lint-py\n      make lint-typo\n")

    assert check_make_targets.run_check(paths=[workflow], root=tmp_path) == [
        ".github/workflows/ci.yml:4: unknown Make target `lint-typo`",
    ]


def test_run_check_reports_an_unknown_target_in_source_strings(tmp_path: Path) -> None:
    """A wrong target named in an error message is caught before it misleads anyone."""
    write_text(tmp_path / "Makefile", "pr-review-comments:\n\t@true\n")
    module = tmp_path / "scripts" / "gh" / "pr_watch.py"
    write_text(module, 'raise GhError("inspect `make pr-comment-typo` before merging")\n')

    assert check_make_targets.run_check(paths=[module], root=tmp_path) == [
        "scripts/gh/pr_watch.py:1: unknown Make target `pr-comment-typo`",
    ]


def test_resolve_requested_paths_reports_an_inaccessible_path(tmp_path: Path) -> None:
    """Descending through a regular file is reported, not raised as a traceback."""
    write_text(tmp_path / "README.md", "# Root\n")

    _, errors = check_make_targets.resolve_requested_paths(["README.md/nested.md"], tmp_path)

    assert errors == ["README.md/nested.md: path could not be accessed"]


def test_resolve_requested_paths_rejects_a_directory(tmp_path: Path) -> None:
    """A directory that merely looks like Markdown is not read as a file."""
    (tmp_path / "docs.md").mkdir()

    _, errors = check_make_targets.resolve_requested_paths(["docs.md"], tmp_path)

    assert errors == ["docs.md: path does not exist or is not a file"]


def test_resolve_requested_paths_rejects_a_path_resolving_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A path that resolves out of the repository is refused before it is read."""
    write_text(tmp_path / "README.md", "# Root\n")
    outside = tmp_path.parent / f"{tmp_path.name}-outside" / "README.md"
    original = Path.resolve

    def escaping_resolve(self: Path, strict: bool = False) -> Path:
        """Resolve the candidate file to a location outside the repository."""
        if self.name == "README.md":
            return outside
        return original(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", escaping_resolve)

    _, errors = check_make_targets.resolve_requested_paths(["README.md"], tmp_path)

    assert errors == ["README.md: path resolves outside the repository"]


def test_run_check_reports_a_candidate_outside_the_workspace(tmp_path: Path) -> None:
    """A candidate from outside the workspace is refused rather than read."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"

    assert check_make_targets.run_check(paths=[outside], root=tmp_path) == [
        f"{outside}: path must stay within the repository"
    ]


def test_run_check_surfaces_path_errors_for_candidates(tmp_path: Path) -> None:
    """A candidate that fails validation is reported instead of silently skipped."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")

    assert check_make_targets.run_check(paths=[tmp_path / "missing.md"], root=tmp_path) == [
        "missing.md: path does not exist"
    ]


def test_main_without_paths_scans_the_whole_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Omitting paths falls back to the full repository scan."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    write_text(tmp_path / "README.md", "Use `make help`.\n")
    write_text(tmp_path / "scripts" / "tool.py", '"""Run `make help`."""\n')
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)

    exit_code = check_make_targets.main([])

    assert exit_code == 0
    assert "Make target check passed for 2 file(s)" in capsys.readouterr().out


def test_run_check_ignores_absent_targets_in_test_fixtures(tmp_path: Path) -> None:
    """Checker fixtures may name targets that deliberately do not exist."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    fixture = tmp_path / "tests" / "test_check_make_targets.py"
    write_text(fixture, 'doc = "Use `make missing-target`."\n')

    assert check_make_targets.run_check(root=tmp_path) == []


def test_main_rejects_symlink_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Explicit paths cannot traverse file or directory symbolic links."""
    write_text(tmp_path / "Makefile", "help:\n\t@true\n")
    target = tmp_path / "target.md"
    write_text(target, "Use `make help`.\n")
    (tmp_path / "linked.md").symlink_to(target)
    directory = tmp_path / "directory"
    write_text(directory / "guide.md", "Use `make help`.\n")
    (tmp_path / "linked-directory").symlink_to(directory, target_is_directory=True)
    monkeypatch.setattr(check_make_targets, "REPO_ROOT", tmp_path)

    exit_code = check_make_targets.main(["linked.md", "linked-directory/guide.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert captured.count("symbolic links are not supported") == 2


def test_control_flow_allowlist_has_no_unused_entries() -> None:
    """The allowlist is a ratchet and every entry must still match the Makefile."""
    content = make_targets.MAKEFILE_PATH.read_text(encoding="utf-8")
    offenders = {
        violation.target
        for violation in make_targets.find_shell_control_flow(content, allowlist=frozenset())
    }

    assert offenders == make_targets.CONTROL_FLOW_ALLOWLIST


def test_find_replacement_targets_covers_git_and_github_commands() -> None:
    """Direct Git and GitHub commands map to the repository Make interface."""
    targets = check_doc_commands.find_replacement_targets(
        "git add README.md && git commit && git push && git rebase origin/main; "
        "gh issue list && gh pr comment",
        {"stage", "commit", "push", "rebase-main", "issue-list", "pr-comment"},
    )

    assert targets == ["stage", "commit", "push", "rebase-main", "issue-list", "pr-comment"]


def test_check_doc_commands_reports_non_utf8_markdown(tmp_path: Path) -> None:
    """Invalid UTF-8 contributor documents fail without a traceback."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    doc_path.write_bytes(b"\x80bad")

    assert check_doc_commands.run_check(paths=[doc_path], root=tmp_path) == [
        "README.md: not valid UTF-8 text (invalid start byte)"
    ]


def test_check_doc_commands_rejects_default_path_symlink(tmp_path: Path) -> None:
    """Default contributor documents cannot read through symbolic links."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    target = tmp_path / "target.md"
    write_text(target, "Run `make test-py`.\n")
    (tmp_path / "README.md").symlink_to(target)

    assert check_doc_commands.run_check(root=tmp_path) == [
        "README.md: symbolic links are not supported"
    ]


def test_check_doc_commands_rejects_paths_outside_the_workspace(tmp_path: Path) -> None:
    """A candidate document from outside the workspace is refused before reading."""
    root = tmp_path / "repo"
    write_text(root / "Makefile", "test-py:\n\t@true\n")
    outside = tmp_path / "outside.md"
    write_text(outside, "Run `pytest`.\n")

    assert check_doc_commands.run_check(paths=[outside], root=root) == [
        f"{outside}: path must stay within the repository"
    ]


def test_resolve_doc_paths_reports_inaccessible_paths(tmp_path: Path) -> None:
    """A path routed through a regular file is reported, not raised as a traceback."""
    write_text(tmp_path / "notes.md", "# Notes\n")

    resolved, errors = check_doc_commands.resolve_requested_paths(["notes.md/nested.md"], tmp_path)

    assert resolved == []
    assert errors == ["notes.md/nested.md: path could not be accessed"]


def test_resolve_doc_paths_rejects_a_target_that_resolves_outside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolved-path containment remains a defence-in-depth check."""
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.md"
    write_text(outside, "# Outside\n")
    (root / "linked.md").symlink_to(outside)
    monkeypatch.setattr(check_doc_commands, "_contains_symlink", lambda _path, _root: False)

    resolved, errors = check_doc_commands.resolve_requested_paths(["linked.md"], root)

    assert resolved == []
    assert errors == ["linked.md: path resolves outside the repository"]


def test_resolve_doc_paths_rejects_directories(tmp_path: Path) -> None:
    """A directory whose name ends in .md is not treated as a document."""
    (tmp_path / "guides.md").mkdir()

    resolved, errors = check_doc_commands.resolve_requested_paths(["guides.md"], tmp_path)

    assert resolved == []
    assert errors == ["guides.md: path does not exist or is not a file"]


def test_check_doc_commands_tracks_repeated_inline_snippet_occurrences(tmp_path: Path) -> None:
    """Identical snippets in separate clauses keep independent actionability."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "Do not run `pytest`; instead run `pytest`.\n")

    assert check_doc_commands.run_check(paths=[doc_path], root=tmp_path) == [
        "README.md:1: use `make test-py` instead of `pytest`"
    ]


def test_check_doc_commands_preserves_padded_inline_code(tmp_path: Path) -> None:
    """Whitespace inside backticks does not bypass negation analysis."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(doc_path, "Do not run ` pytest ` directly.\n")

    assert check_doc_commands.run_check(paths=[doc_path], root=tmp_path) == []


def test_check_doc_commands_keeps_negation_across_neighboring_code_spans(
    tmp_path: Path,
) -> None:
    """Punctuation and verbs inside code spans do not strand a negation."""
    write_text(tmp_path / "Makefile", "web:\n\t@true\n")
    doc_path = tmp_path / "README.md"
    write_text(
        doc_path,
        "Never run `.venv/bin/*`, `pytest`, `npm run`, or `vite` directly.\n",
    )

    assert check_doc_commands.run_check(paths=[doc_path], root=tmp_path) == []


def test_mask_inline_code_preserves_offsets_and_blanks_contents() -> None:
    """Masking keeps line length stable for clause analysis."""
    masked = check_doc_commands._mask_inline_code("Run `npm run` then `a.b` now")

    assert masked == "Run `_______` then `___` now"


def test_check_doc_commands_main_rejects_invalid_target_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Missing, non-Markdown, and escaping paths are rejected together."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    write_text(tmp_path / "notes.txt", "Run pytest.\n")
    monkeypatch.setattr(check_doc_commands, "REPO_ROOT", tmp_path)

    exit_code = check_doc_commands.main(["missing.md", "notes.txt", "../outside.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert captured.startswith("Command lint failed:\n")
    assert "missing.md: path does not exist" in captured
    assert "notes.txt: path must be a Markdown file" in captured
    assert "../outside.md: path must stay within the repository" in captured


def test_check_doc_commands_main_rejects_symlink_components(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Explicit paths cannot traverse file or directory symbolic links."""
    write_text(tmp_path / "Makefile", "test-py:\n\t@true\n")
    target = tmp_path / "target.md"
    write_text(target, "Run `make test-py`.\n")
    (tmp_path / "linked.md").symlink_to(target)
    target_directory = tmp_path / "target-directory"
    write_text(target_directory / "guide.md", "Run `make test-py`.\n")
    (tmp_path / "linked-directory").symlink_to(target_directory, target_is_directory=True)
    monkeypatch.setattr(check_doc_commands, "REPO_ROOT", tmp_path)

    exit_code = check_doc_commands.main(["linked.md", "linked-directory/guide.md"])

    captured = capsys.readouterr().out
    assert exit_code == 1
    assert captured.count("symbolic links are not supported") == 2
