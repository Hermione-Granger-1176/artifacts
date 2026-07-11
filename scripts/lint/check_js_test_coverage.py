#!/usr/bin/env python3
"""Check that every JS/MJS source file is imported by at least one test file."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from scripts import REPO_ROOT
from scripts.lint import SKIP_DIRECTORIES as _BASE_SKIP_DIRECTORIES

# Directories containing JS source files that must have test coverage.
SOURCE_DIRS = (
    Path("js"),
    Path("apps"),
)

# Auto-generated files that don't need dedicated tests.
GENERATED_FILES = frozenset(
    {
        "js/data.js",
        "js/gallery-config.js",
    }
)


TEST_DIR = Path("tests/js")

# Matches ESM static import paths: import ... from '../../path/to/file.js';
_IMPORT_PATTERN = re.compile(
    r"""(?:import|export)\s+.*?\s+from\s+['"]([^'"]+)['"]""",
    re.DOTALL,
)

# Matches dynamic import paths: import('../../path/to/file.js') with optional query strings
_DYNAMIC_IMPORT_PATTERN = re.compile(r"""import\s*\(\s*[`'"]([^`'"?]+)""")

# Matches path.resolve('js/file.js'), used by tests that load via fs/vm
_PATH_RESOLVE_PATTERN = re.compile(r"""path\.resolve\s*\(\s*['"]([^'"]+\.(?:js|mjs))['"]""")

SKIP_DIRECTORIES = _BASE_SKIP_DIRECTORIES | {"docs"}


def _should_skip_path(path: Path) -> bool:
    """Return whether one path sits inside a skipped directory."""
    return any(part in SKIP_DIRECTORIES for part in path.parts)


def discover_source_files(root: Path) -> list[Path]:
    """Find all JS/MJS source files under the configured source directories."""
    source_files: list[Path] = []
    for source_dir in SOURCE_DIRS:
        abs_dir = root / source_dir
        if not abs_dir.is_dir():
            continue
        for pattern in ("*.js", "*.mjs"):
            for path in sorted(abs_dir.rglob(pattern)):
                if _should_skip_path(path):
                    continue
                source_files.append(path)
    return source_files


def discover_test_files(root: Path) -> list[Path]:
    """Find all JS test files under the test directory."""
    test_dir = root / TEST_DIR
    if not test_dir.is_dir():
        return []
    return sorted(test_dir.rglob("*.test.js"))


def extract_test_imports(test_file: Path, root: Path) -> set[Path]:
    """Extract resolved source file paths from a test file's imports."""
    text = test_file.read_text(encoding="utf-8")
    imported_paths: set[Path] = set()

    for pattern in (_IMPORT_PATTERN, _DYNAMIC_IMPORT_PATTERN):
        for match in pattern.finditer(text):
            import_path = match.group(1)
            if import_path.startswith("."):
                resolved = (test_file.parent / import_path).resolve()
                imported_paths.add(resolved)

    # Handle path.resolve('js/file.js'), resolved from repo root
    for match in _PATH_RESOLVE_PATTERN.finditer(text):
        import_path = match.group(1)
        resolved = (root / import_path).resolve()
        imported_paths.add(resolved)

    return imported_paths


def build_coverage_map(root: Path) -> dict[Path, bool]:
    """Map each source file to whether it is imported by at least one test."""
    test_files = discover_test_files(root)
    all_imported = {
        imported_path
        for test_file in test_files
        for imported_path in extract_test_imports(test_file, root)
    }

    source_files = discover_source_files(root)
    return {
        source_file: source_file.resolve() in all_imported
        for source_file in source_files
        if source_file.relative_to(root).as_posix() not in GENERATED_FILES
    }


def coverage_violations(coverage: dict[Path, bool], root: Path) -> list[str]:
    """Return JS test coverage violations from an already-built coverage map."""
    violations: list[str] = []
    for source_file, is_covered in sorted(coverage.items()):
        if not is_covered:
            relative = source_file.relative_to(root).as_posix()
            violations.append(f"{relative}: not imported by any test file in {TEST_DIR}/")
    return violations


def run_check(root: Path | None = None) -> list[str]:
    """Run the JS test coverage check and return all violations."""
    workspace_root = root or REPO_ROOT
    coverage = build_coverage_map(workspace_root)
    return coverage_violations(coverage, workspace_root)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the JS test coverage checker."""
    parser = argparse.ArgumentParser(
        description="Check that every JS/MJS source file is imported by at least one test."
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

    coverage = build_coverage_map(workspace_root)
    violations = coverage_violations(coverage, workspace_root)
    total = len(coverage)
    covered = sum(1 for v in coverage.values() if v)

    if not violations:
        print(f"JS test coverage check passed: {covered}/{total} source files covered")
        return 0

    print(f"JS test coverage check failed: {total - covered} file(s) missing test imports")
    for violation in violations:
        print(f"  {violation}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
