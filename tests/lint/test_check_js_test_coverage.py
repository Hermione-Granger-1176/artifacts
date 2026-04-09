"""Tests for the JS test coverage lint check."""

from __future__ import annotations

from pathlib import Path

from scripts.lint.check_js_test_coverage import (
    build_coverage_map,
    discover_source_files,
    discover_test_files,
    extract_test_imports,
    main,
    run_check,
)


def _create_tree(tmp_path: Path) -> Path:
    """Create a minimal source + test tree."""
    root = tmp_path / "repo"
    (root / "js" / "modules").mkdir(parents=True)
    (root / "apps" / "demo" / "js" / "modules").mkdir(parents=True)
    (root / "tests" / "js" / "home").mkdir(parents=True)
    (root / "tests" / "js" / "apps" / "demo").mkdir(parents=True)

    (root / "js" / "modules" / "config.js").write_text("export function validate() {}")
    (root / "js" / "modules" / "untested.js").write_text("export function helper() {}")
    (root / "js" / "data.js").write_text("// generated")
    (root / "apps" / "demo" / "js" / "modules" / "math.js").write_text(
        "export function add(a, b) { return a + b; }"
    )

    (root / "tests" / "js" / "home" / "config.test.js").write_text(
        "import { validate } from '../../../js/modules/config.js';\n"
    )
    (root / "tests" / "js" / "apps" / "demo" / "math.test.js").write_text(
        "import { add } from '../../../../apps/demo/js/modules/math.js';\n"
    )

    return root


def test_discover_source_files(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    files = discover_source_files(root)
    relative = {f.relative_to(root).as_posix() for f in files}
    assert "js/modules/config.js" in relative
    assert "js/modules/untested.js" in relative
    assert "js/data.js" in relative
    assert "apps/demo/js/modules/math.js" in relative


def test_discover_test_files(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    files = discover_test_files(root)
    names = {f.name for f in files}
    assert "config.test.js" in names
    assert "math.test.js" in names


def test_extract_test_imports_resolves_relative_paths(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    test_file = root / "tests" / "js" / "home" / "config.test.js"
    imports = extract_test_imports(test_file, root)
    resolved_source = (root / "js" / "modules" / "config.js").resolve()
    assert resolved_source in imports


def test_extract_test_imports_handles_path_resolve(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    test_file = root / "tests" / "js" / "home" / "resolve.test.js"
    test_file.write_text("const p = path.resolve('js/modules/config.js');\n")
    imports = extract_test_imports(test_file, root)
    resolved_source = (root / "js" / "modules" / "config.js").resolve()
    assert resolved_source in imports


def test_extract_test_imports_handles_dynamic_import(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    test_file = root / "tests" / "js" / "home" / "dynamic.test.js"
    test_file.write_text(
        "await import(`../../../js/modules/config.js?t=${Date.now()}`);\n"
    )
    imports = extract_test_imports(test_file, root)
    resolved_source = (root / "js" / "modules" / "config.js").resolve()
    assert resolved_source in imports


def test_build_coverage_map_excludes_generated(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    coverage = build_coverage_map(root)
    relative_keys = {f.relative_to(root).as_posix() for f in coverage}
    assert "js/data.js" not in relative_keys


def test_run_check_reports_untested_files(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    violations = run_check(root=root)
    assert len(violations) == 1
    assert "untested.js" in violations[0]


def test_run_check_passes_when_all_covered(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    # Add test for the untested file
    (root / "tests" / "js" / "home" / "untested.test.js").write_text(
        "import { helper } from '../../../js/modules/untested.js';\n"
    )
    violations = run_check(root=root)
    assert violations == []


def test_main_returns_zero_when_all_covered(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    (root / "tests" / "js" / "home" / "untested.test.js").write_text(
        "import { helper } from '../../../js/modules/untested.js';\n"
    )
    assert main(["--root", str(root)]) == 0


def test_main_returns_one_when_uncovered(tmp_path: Path) -> None:
    root = _create_tree(tmp_path)
    assert main(["--root", str(root)]) == 1


def test_discover_source_files_skips_missing_dirs(tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    # No js/ or apps/ directories exist
    files = discover_source_files(root)
    assert files == []


def test_discover_source_files_skips_node_modules(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "js" / "node_modules").mkdir(parents=True)
    (root / "js" / "node_modules" / "lib.js").write_text("// vendor")
    (root / "js" / "ok.js").write_text("export default 1;")
    files = discover_source_files(root)
    relative = {f.relative_to(root).as_posix() for f in files}
    assert "js/ok.js" in relative
    assert "js/node_modules/lib.js" not in relative


def test_discover_source_files_skips_mjs_in_node_modules(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "js" / "node_modules").mkdir(parents=True)
    (root / "js" / "node_modules" / "vendor.mjs").write_text("// vendor")
    (root / "js" / "ok.mjs").write_text("export default 1;")
    files = discover_source_files(root)
    relative = {f.relative_to(root).as_posix() for f in files}
    assert "js/ok.mjs" in relative
    assert "js/node_modules/vendor.mjs" not in relative


def test_discover_source_files_skips_vendor(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "apps" / "my-app" / "js" / "vendor").mkdir(parents=True)
    (root / "apps" / "my-app" / "js" / "vendor" / "lib.min.js").write_text("// vendor")
    (root / "apps" / "my-app" / "js").mkdir(parents=True, exist_ok=True)
    (root / "apps" / "my-app" / "js" / "app.js").write_text("export default 1;")
    files = discover_source_files(root)
    relative = {f.relative_to(root).as_posix() for f in files}
    assert "apps/my-app/js/app.js" in relative
    assert "apps/my-app/js/vendor/lib.min.js" not in relative


def test_discover_source_files_finds_mjs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "js").mkdir(parents=True)
    (root / "js" / "helper.mjs").write_text("export default 1;")
    files = discover_source_files(root)
    relative = {f.relative_to(root).as_posix() for f in files}
    assert "js/helper.mjs" in relative


def test_discover_test_files_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    # No tests/js/ directory
    files = discover_test_files(root)
    assert files == []
