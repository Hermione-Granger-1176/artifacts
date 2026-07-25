from __future__ import annotations

import argparse
import ctypes
import dataclasses
import fcntl
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import scripts.setup.playwright_local_runtime as runtime

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

OS_RELEASE = Path("/etc/os-release")


def install_fake_playwright(repo_root: Path, version: str = "1.61.0") -> Path:
    """Install a virtual-environment Playwright CLI and distribution metadata."""
    executable = repo_root / runtime.VENV_DIRECTORY / "bin" / "playwright"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    dist_info = (
        repo_root
        / runtime.VENV_DIRECTORY
        / "lib"
        / "python3.12"
        / "site-packages"
        / f"playwright-{version}.dist-info"
    )
    dist_info.mkdir(parents=True, exist_ok=True)
    return executable


def make_manifest(
    version: str = "1.61.0",
    engines: tuple[str, ...] = runtime.ENGINES,
) -> runtime.CacheManifest:
    """Build a manifest matching the fixtures below."""
    return runtime.CacheManifest(
        schema=runtime.MANIFEST_SCHEMA,
        host=runtime.current_host(),
        playwright_version=version,
        engines=engines,
        packages=(runtime.PackageVersion(name="libdemo0", version="1:2.0-1ubuntu1"),),
    )


def write_webkit_launcher(paths: runtime.RuntimePaths, *, patched: bool) -> Path:
    """Create an executable WebKit bundle launcher in the shared browser cache."""
    launcher = paths.browser_root / "webkit-test" / "minibrowser-wpe" / "MiniBrowser"
    launcher.parent.mkdir(parents=True, exist_ok=True)
    line = runtime.WEBKIT_LAUNCHER_LOCAL_LD_LINE if patched else runtime.WEBKIT_LAUNCHER_LD_LINE
    launcher.write_text(f"#!/bin/sh\n{line}\n", encoding="utf-8")
    launcher.chmod(0o755)
    return launcher


def ready_paths(
    tmp_path: Path,
    engines: tuple[str, ...] = runtime.ENGINES,
) -> runtime.RuntimePaths:
    """Build a fully prepared runtime cache backed by fake browsers and metadata."""
    paths = runtime.RuntimePaths.from_repo(tmp_path, browser_root=tmp_path / "shared-browsers")
    install_fake_playwright(paths.repo_root)
    runtime.ensure_cache_root(paths)
    paths.extracted_root.mkdir(parents=True)
    runtime.write_manifest(paths.manifest, make_manifest(engines=engines))
    for engine in engines:
        (paths.browser_root / f"{engine}-test").mkdir(parents=True, exist_ok=True)
    if "webkit" in engines:
        write_webkit_launcher(paths, patched=True)
    return paths


def fake_os_release(monkeypatch: pytest.MonkeyPatch, content: str | None) -> None:
    """Serve fixed /etc/os-release content without touching the host file."""
    original = Path.read_text

    def read_text(self: Path, *args: object, **kwargs: object) -> str:
        if self == OS_RELEASE:
            if content is None:
                raise OSError("boom")
            return content
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "read_text", read_text)


# ─── Dependency dry-run parsing ──────────────────────────────────────────────


def test_parse_dependency_seeds_accepts_only_package_tokens() -> None:
    """Accept the legacy printed install command without evaluating it."""
    output = """
Installing dependencies...
sudo apt-get install -y --no-install-recommends \\
  libgtk-3-0 libnss3
"""

    assert runtime.parse_dependency_seeds(output) == ("libgtk-3-0", "libnss3")


def test_parse_dependency_seeds_accepts_playwright_missing_package_report() -> None:
    """Accept the current Playwright dry-run missing-package report."""
    output = """
Missing system dependencies (2):
  libgtk-3-0
  libnss3
"""

    assert runtime.parse_dependency_seeds(output) == ("libgtk-3-0", "libnss3")


def test_parse_dependency_seeds_rejects_shell_syntax() -> None:
    """Reject shell operators in dry-run output even though it is never executed."""
    output = "sudo apt-get install libgtk-3-0; touch unexpected\n"

    with pytest.raises(runtime.RuntimeSetupError, match="unsafe shell syntax"):
        runtime.parse_dependency_seeds(output)


def test_parse_dependency_seeds_rejects_incomplete_missing_package_report() -> None:
    """Require the declared dry-run package count to match the parsed list."""
    output = "Missing system dependencies (2):\n  libgtk-3-0\n"

    with pytest.raises(runtime.RuntimeSetupError, match="incomplete package list"):
        runtime.parse_dependency_seeds(output)


def test_parse_dependency_seeds_accepts_a_satisfied_host() -> None:
    """A host that already has every dependency yields an empty seed set."""
    assert runtime.parse_dependency_seeds("All system dependencies are installed.\n") == ()


def test_parse_dependency_seeds_requires_a_recognized_report() -> None:
    """Refuse to guess when Playwright prints neither report shape."""
    with pytest.raises(runtime.RuntimeSetupError, match="did not provide package seeds"):
        runtime.parse_dependency_seeds("something unexpected\n")


def test_parse_dependency_seeds_rejects_invalid_names_in_both_report_shapes() -> None:
    """Reject package tokens that could escape the private archive directory."""
    with pytest.raises(runtime.RuntimeSetupError, match="invalid package name"):
        runtime.parse_dependency_seeds("apt-get install ../escape\n")

    with pytest.raises(runtime.RuntimeSetupError, match="invalid package name"):
        runtime.parse_dependency_seeds("Missing system dependencies (1):\n  ../escape\n")


def test_parse_dependency_seeds_ignores_unrelated_apt_get_lines() -> None:
    """Only an ``apt-get install`` command contributes seeds."""
    output = "sudo apt-get update\napt-get\nMissing system dependencies (1):\n  libnss3\n"

    assert runtime.parse_dependency_seeds(output) == ("libnss3",)


def test_parse_dependency_seeds_stops_at_the_end_of_the_indented_block() -> None:
    """Trailing unindented output after the report is not read as a package."""
    output = "Missing system dependencies (1):\n  libnss3\nRun the command above.\n"

    assert runtime.parse_dependency_seeds(output) == ("libnss3",)


def test_normalize_shell_lines_rejects_an_unterminated_command() -> None:
    """A dangling backslash continuation is a malformed report, not a package list."""
    with pytest.raises(runtime.RuntimeSetupError, match="unterminated"):
        runtime.normalize_shell_lines("apt-get install \\\n")


def test_parse_dependency_seeds_rejects_unparsable_quoting() -> None:
    """Unbalanced quoting in the dry-run output is reported, never evaluated."""
    with pytest.raises(runtime.RuntimeSetupError, match="cannot parse"):
        runtime.parse_dependency_seeds("apt-get install 'unclosed\n")


# ─── APT simulation parsing ──────────────────────────────────────────────────


def test_parse_simulated_packages_requires_safe_exact_versions() -> None:
    """Parse only exact safe package names and versions from APT simulation."""
    output = """
Inst libdemo0:amd64 (1:2.0~rc1-3ubuntu1.4 Ubuntu:26.04/oracular [amd64])
Inst libother0 (4.5-1 Ubuntu:26.04/oracular [amd64])
"""

    assert runtime.parse_simulated_packages(output) == (
        runtime.PackageVersion(name="libdemo0:amd64", version="1:2.0~rc1-3ubuntu1.4"),
        runtime.PackageVersion(name="libother0", version="4.5-1"),
    )


def test_parse_simulated_packages_rejects_malformed_package_data() -> None:
    """Reject a package name that could escape the private archive directory."""
    output = "Inst ../outside (1.0 Ubuntu:26.04/oracular [amd64])\n"

    with pytest.raises(runtime.RuntimeSetupError, match="malformed package data"):
        runtime.parse_simulated_packages(output)


def test_parse_simulated_packages_rejects_conflicting_versions() -> None:
    """Two different versions for one package mean the solver output is unusable."""
    output = "Inst libdemo0 (1.0 Ubuntu [amd64])\nInst libdemo0 (2.0 Ubuntu [amd64])\n"

    with pytest.raises(runtime.RuntimeSetupError, match="conflicting package versions"):
        runtime.parse_simulated_packages(output)


def test_parse_simulated_packages_requires_a_resolved_closure() -> None:
    """An APT simulation that installs nothing cannot produce a runtime."""
    with pytest.raises(runtime.RuntimeSetupError, match="did not resolve any package archives"):
        runtime.parse_simulated_packages("Reading package lists...\n")


def test_resolve_packages_skips_apt_without_seeds(tmp_path: Path) -> None:
    """A satisfied host resolves to an empty closure without running APT."""
    assert runtime.resolve_packages([], tmp_path) == ()


def test_resolve_packages_uses_the_non_mutating_simulation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve the exact closure through ``apt-get --simulate`` only."""
    commands: list[list[str]] = []

    def fake_checked_run(
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, env
        commands.append(list(command))
        return subprocess.CompletedProcess(list(command), 0, "Inst libdemo0 (1.0 Ubuntu [amd64])\n")

    monkeypatch.setattr(runtime, "checked_run", fake_checked_run)

    resolved = runtime.resolve_packages(["libdemo0"], tmp_path)

    assert resolved == (runtime.PackageVersion(name="libdemo0", version="1.0"),)
    assert commands[0][0] == "apt-get"
    assert "--simulate" in commands[0]
    assert "--no-install-recommends" in commands[0]
    assert f"Dir::Cache={tmp_path / 'apt-cache'}" in commands[0]


# ─── Host platform detection ─────────────────────────────────────────────────


def test_current_host_rejects_non_linux_platforms(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse hosts where extracted Debian archives cannot apply."""
    monkeypatch.setattr(sys, "platform", "darwin")

    with pytest.raises(runtime.RuntimeSetupError, match="Linux Debian and Ubuntu hosts only"):
        runtime.current_host()


def test_current_host_requires_a_debian_family_release(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse a distribution whose archives this utility cannot resolve."""
    fake_os_release(monkeypatch, 'ID=fedora\nVERSION_ID="42"\n')

    with pytest.raises(runtime.RuntimeSetupError, match="requires Debian or Ubuntu"):
        runtime.current_host()


def test_current_host_rejects_unsupported_architectures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse an architecture with no Playwright browser build."""
    fake_os_release(monkeypatch, 'ID=ubuntu\nVERSION_ID="26.04"\n')
    monkeypatch.setattr(runtime.platform, "machine", lambda: "riscv64")

    with pytest.raises(runtime.RuntimeSetupError, match="unsupported CPU architecture"):
        runtime.current_host()


def test_current_host_maps_supported_architectures(monkeypatch: pytest.MonkeyPatch) -> None:
    """Normalize the machine name onto the Debian architecture tuple."""
    fake_os_release(monkeypatch, 'ID=Debian\nVERSION_ID="13"\n')
    monkeypatch.setattr(runtime.platform, "machine", lambda: "aarch64")

    assert runtime.current_host() == runtime.HostPlatform(
        distribution="debian",
        version="13",
        architecture="arm64",
    )


def test_read_os_release_skips_comments_and_blank_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Parse the shell-style file without executing it."""
    fake_os_release(monkeypatch, "# comment\n\nnokey\nID=ubuntu\nEMPTY=\n")

    assert runtime.read_os_release() == {"ID": "ubuntu", "EMPTY": ""}


def test_read_os_release_rejects_malformed_content(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject keys and values that a naive shell source would have executed."""
    fake_os_release(monkeypatch, "bad-key=value\n")
    with pytest.raises(runtime.RuntimeSetupError, match="malformed /etc/os-release key"):
        runtime.read_os_release()

    fake_os_release(monkeypatch, "ID='unterminated\n")
    with pytest.raises(runtime.RuntimeSetupError, match="malformed /etc/os-release value"):
        runtime.read_os_release()

    fake_os_release(monkeypatch, "ID=one two\n")
    with pytest.raises(runtime.RuntimeSetupError, match="malformed /etc/os-release value"):
        runtime.read_os_release()


def test_read_os_release_reports_an_unreadable_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail before mutation when the host identity cannot be read."""
    fake_os_release(monkeypatch, None)

    with pytest.raises(runtime.RuntimeSetupError, match="cannot read /etc/os-release"):
        runtime.read_os_release()


# ─── Virtual-environment Playwright discovery ────────────────────────────────


def test_playwright_cli_requires_the_virtual_environment_command(tmp_path: Path) -> None:
    """Resolve the CLI from .venv/bin instead of a global lookup."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)

    with pytest.raises(runtime.RuntimeSetupError, match="repository Playwright is missing"):
        runtime.playwright_cli(paths)

    executable = install_fake_playwright(paths.repo_root)

    assert runtime.playwright_cli(paths) == executable


def test_playwright_version_reads_the_virtual_environment_distribution(tmp_path: Path) -> None:
    """Key the manifest on the version actually installed in the virtual environment."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)

    with pytest.raises(runtime.RuntimeSetupError, match="cannot resolve the installed"):
        runtime.playwright_version(paths)

    install_fake_playwright(paths.repo_root, version="1.61.0")

    assert runtime.playwright_version(paths) == "1.61.0"


def test_playwright_version_rejects_an_ambiguous_environment(tmp_path: Path) -> None:
    """Two distribution directories mean the environment is not trustworthy."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    install_fake_playwright(paths.repo_root, version="1.61.0")
    install_fake_playwright(paths.repo_root, version="1.62.0")

    with pytest.raises(runtime.RuntimeSetupError, match="cannot resolve the installed"):
        runtime.playwright_version(paths)


def test_playwright_version_rejects_an_unsafe_version(tmp_path: Path) -> None:
    """Reject a version string that would not be safe to embed in a manifest."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    install_fake_playwright(paths.repo_root, version="1!2.0")

    with pytest.raises(runtime.RuntimeSetupError, match="invalid version"):
        runtime.playwright_version(paths)


def test_dependency_seeds_asks_the_virtual_environment_cli(tmp_path: Path) -> None:
    """Ask the installed CLI for seeds and accept its documented exit codes."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    executable = install_fake_playwright(paths.repo_root)
    executable.write_text(
        '#!/bin/sh\nprintf "Missing system dependencies (1):\\n  libnss3\\n"\nexit 1\n',
        encoding="utf-8",
    )
    executable.chmod(0o755)

    assert runtime.dependency_seeds(paths, ["chromium"]) == ("libnss3",)


def test_dependency_seeds_reports_an_unexpected_exit_status(tmp_path: Path) -> None:
    """Any exit status outside Playwright's documented pair is a hard failure."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    executable = install_fake_playwright(paths.repo_root)
    executable.write_text("#!/bin/sh\necho broken\nexit 3\n", encoding="utf-8")
    executable.chmod(0o755)

    with pytest.raises(runtime.RuntimeSetupError, match="dependency dry run failed"):
        runtime.dependency_seeds(paths, ["chromium"])


def test_dependency_seeds_reports_an_unrunnable_cli(tmp_path: Path) -> None:
    """A CLI that cannot execute is reported instead of crashing the setup."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    executable = install_fake_playwright(paths.repo_root)
    executable.chmod(0o644)

    with pytest.raises(runtime.RuntimeSetupError, match="cannot run"):
        runtime.dependency_seeds(paths, ["chromium"])


# ─── Fixed-argv command execution ────────────────────────────────────────────


def test_checked_run_returns_the_captured_output() -> None:
    """A successful package command hands its captured output back to the caller."""
    completed = runtime.checked_run([sys.executable, "-c", "print('resolved')"])

    assert completed.returncode == 0
    assert completed.stdout.strip() == "resolved"


def test_checked_run_reports_a_missing_executable(tmp_path: Path) -> None:
    """Missing tooling is reported as a setup error, not an OSError traceback."""
    with pytest.raises(runtime.RuntimeSetupError, match="cannot run"):
        runtime.checked_run([str(tmp_path / "missing-binary")])


def test_checked_run_reports_failures_with_bounded_output() -> None:
    """Show a useful but bounded diagnostic when a package command fails."""
    with pytest.raises(runtime.RuntimeSetupError, match=r"exit 3.*hello"):
        runtime.checked_run([sys.executable, "-c", "print('hello'); raise SystemExit(3)"])

    with pytest.raises(runtime.RuntimeSetupError, match="output truncated"):
        runtime.checked_run(
            [sys.executable, "-c", "print('x' * 5000); raise SystemExit(1)"],
        )

    with pytest.raises(runtime.RuntimeSetupError, match=r"exit 4\)$"):
        runtime.checked_run([sys.executable, "-c", "raise SystemExit(4)"])


# ─── Download, extraction, and validation ────────────────────────────────────


def test_is_within_returns_a_verdict_for_unresolvable_paths(tmp_path: Path) -> None:
    """Hostile filesystem entries get a verdict instead of an escaping exception.

    The containment guard validates untrusted extracted trees, so it has to answer
    even when resolution fails. A symlink loop raises RuntimeError from pathlib's
    ELOOP check on Python 3.12 and resolves best-effort on 3.13+, so the boolean
    for that case is interpreter-dependent and only "does not raise" is asserted.
    Denial is asserted where it is version-stable, since a guard that fails open
    on an unresolvable path would let an escaping entry through.
    """
    loop = tmp_path / "loop"
    other = tmp_path / "other"
    loop.symlink_to(other)
    other.symlink_to(loop)

    assert isinstance(runtime.is_within(loop, tmp_path), bool)
    assert runtime.is_within(loop, tmp_path / "elsewhere") is False

    dangling = tmp_path / "dangling"
    dangling.symlink_to(tmp_path / "missing" / "target")

    assert runtime.is_within(dangling, tmp_path) is True

    blocked = tmp_path / "blocked"
    (blocked / "inner").mkdir(parents=True)
    blocked.chmod(0o000)
    try:
        assert runtime.is_within(blocked / "inner", tmp_path) is True
    finally:
        blocked.chmod(0o700)

    assert runtime.is_within(tmp_path / "escape", Path(tmp_path.anchor) / "nowhere") is False


def test_download_and_extract_uses_only_approved_package_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Download with apt and extract with dpkg-deb without invoking installation."""
    commands: list[list[str]] = []

    def fake_checked_run(
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del env
        command_list = list(command)
        commands.append(command_list)
        assert cwd is not None
        if command_list[0] == "apt":
            (cwd / "libdemo0_1.0_amd64.deb").write_bytes(b"archive")
        elif command_list[:2] == ["dpkg-deb", "-x"]:
            extracted = Path(command_list[-1])
            library = extracted / "usr" / "lib" / "x86_64-linux-gnu" / "libdemo.so.1"
            library.parent.mkdir(parents=True, exist_ok=True)
            library.write_bytes(b"library")
        return subprocess.CompletedProcess(command_list, 0, "")

    monkeypatch.setattr(runtime, "checked_run", fake_checked_run)

    extracted_root = runtime.download_and_extract(
        [runtime.PackageVersion(name="libdemo0", version="1.0")],
        tmp_path,
    )

    assert (extracted_root / "usr/lib/x86_64-linux-gnu/libdemo.so.1").is_file()
    assert not list((tmp_path / "debs").glob("*.deb"))
    assert [command[0] for command in commands] == ["apt", "dpkg-deb"]
    assert "download" in commands[0]
    assert commands[1][:2] == ["dpkg-deb", "-x"]


def test_download_and_extract_accepts_an_already_satisfied_host(tmp_path: Path) -> None:
    """An empty closure produces an empty runtime root without running APT."""
    extracted_root = runtime.download_and_extract([], tmp_path)

    assert extracted_root.is_dir()


def test_download_and_extract_requires_one_archive_per_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Refuse a partial download rather than extracting an incomplete closure."""

    def fake_checked_run(
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del cwd, env
        return subprocess.CompletedProcess(list(command), 0, "")

    monkeypatch.setattr(runtime, "checked_run", fake_checked_run)

    with pytest.raises(runtime.RuntimeSetupError, match="exactly one archive"):
        runtime.download_and_extract(
            [runtime.PackageVersion(name="libdemo0", version="1.0")],
            tmp_path,
        )


def test_download_and_extract_rejects_an_unsafe_archive_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A symlinked archive could redirect extraction input outside staging."""

    def fake_checked_run(
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del env
        assert cwd is not None
        outside = tmp_path / "outside.deb"
        outside.write_bytes(b"archive")
        (cwd / "libdemo0_1.0_amd64.deb").symlink_to(outside)
        return subprocess.CompletedProcess(list(command), 0, "")

    monkeypatch.setattr(runtime, "checked_run", fake_checked_run)

    with pytest.raises(runtime.RuntimeSetupError, match="unsafe package archive path"):
        runtime.download_and_extract(
            [runtime.PackageVersion(name="libdemo0", version="1.0")],
            tmp_path,
        )


def test_download_and_extract_requires_empty_archive_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anything left beside the archives means the staging area is not trustworthy."""

    def fake_checked_run(
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        del env
        command_list = list(command)
        assert cwd is not None
        if command_list[0] == "apt":
            (cwd / "libdemo0_1.0_amd64.deb").write_bytes(b"archive")
            (cwd / "leftover.txt").write_text("unexpected", encoding="utf-8")
        return subprocess.CompletedProcess(command_list, 0, "")

    monkeypatch.setattr(runtime, "checked_run", fake_checked_run)

    with pytest.raises(runtime.RuntimeSetupError, match="unexpected files remained"):
        runtime.download_and_extract(
            [runtime.PackageVersion(name="libdemo0", version="1.0")],
            tmp_path,
        )


def test_validate_extracted_root_rejects_host_libc_and_escaping_symlinks(tmp_path: Path) -> None:
    """Reject loader overlays and links that resolve outside the runtime root."""
    libc_root = tmp_path / "libc-root"
    libc = libc_root / "usr" / "lib" / "x86_64-linux-gnu" / "libc.so.6"
    libc.parent.mkdir(parents=True)
    libc.write_text("not a library", encoding="utf-8")

    with pytest.raises(runtime.RuntimeSetupError, match="loader or libc overlay"):
        runtime.validate_extracted_root(libc_root)

    symlink_root = tmp_path / "symlink-root"
    escaped_link = symlink_root / "usr" / "lib" / "x86_64-linux-gnu" / "escape"
    escaped_link.parent.mkdir(parents=True)
    escaped_link.symlink_to(tmp_path / "outside")

    with pytest.raises(runtime.RuntimeSetupError, match="escaped"):
        runtime.validate_extracted_root(symlink_root)


def test_validate_extracted_root_rejects_usr_lib64_host_overlay(tmp_path: Path) -> None:
    """Guard usr/lib64 loader and libc overlays that runtime discovery would trust."""
    loader_root = tmp_path / "loader-root"
    loader = loader_root / "usr" / "lib64" / "ld-linux-x86-64.so.2"
    loader.parent.mkdir(parents=True)
    loader.write_text("not a loader", encoding="utf-8")

    with pytest.raises(runtime.RuntimeSetupError, match="loader or libc overlay"):
        runtime.validate_extracted_root(loader_root)

    libc_root = tmp_path / "libc64-root"
    libc = libc_root / "usr" / "lib64" / "libc.so.6"
    libc.parent.mkdir(parents=True)
    libc.write_text("not a library", encoding="utf-8")

    with pytest.raises(runtime.RuntimeSetupError, match="loader or libc overlay"):
        runtime.validate_extracted_root(libc_root)


def test_validate_extracted_root_rejects_absolute_symlinks(tmp_path: Path) -> None:
    """An absolute link is refused even when its target sits inside the root."""
    root = tmp_path / "root"
    library_dir = root / "usr" / "lib"
    library_dir.mkdir(parents=True)
    (library_dir / "real.so").write_text("", encoding="utf-8")
    (library_dir / "absolute.so").symlink_to(library_dir / "real.so")

    with pytest.raises(runtime.RuntimeSetupError, match="escapes the private runtime root"):
        runtime.validate_extracted_root(root)


def test_validate_extracted_root_accepts_relative_links_and_plain_files(
    tmp_path: Path,
) -> None:
    """A self-contained tree with relative links passes validation unchanged."""
    root = tmp_path / "root"
    library_dir = root / "usr" / "lib"
    library_dir.mkdir(parents=True)
    (library_dir / "real.so").write_text("", encoding="utf-8")
    (library_dir / "link.so").symlink_to("real.so")
    (root / "usr" / "share").mkdir()

    runtime.validate_extracted_root(root)


def test_validate_extracted_root_requires_an_extracted_tree(tmp_path: Path) -> None:
    """A missing runtime root means extraction silently produced nothing."""
    with pytest.raises(runtime.RuntimeSetupError, match="did not create a runtime root"):
        runtime.validate_extracted_root(tmp_path / "missing")


# ─── Cache identity, reuse, and the engine union ─────────────────────────────


def test_cache_reuse_requires_the_complete_manifest_and_runtime_root(tmp_path: Path) -> None:
    """Invalidate reuse on identity changes or an incomplete extracted root."""
    paths = ready_paths(tmp_path)

    assert runtime.cache_matches(paths, make_manifest())
    assert not runtime.cache_matches(paths, make_manifest(version="1.62.0"))

    paths.extracted_root.rmdir()

    assert not runtime.cache_matches(paths, make_manifest())


def test_cache_matches_rejects_a_symlinked_library_cache(tmp_path: Path) -> None:
    """A redirected library cache is never treated as a reusable hit."""
    paths = ready_paths(tmp_path)
    real_root = tmp_path / "real-root"
    paths.extracted_root.rename(real_root)
    paths.extracted_root.symlink_to(real_root, target_is_directory=True)

    assert not runtime.cache_matches(paths, make_manifest())


def test_load_manifest_rejects_unreadable_or_malformed_documents(tmp_path: Path) -> None:
    """Only a manifest with the exact schema and types is trusted."""
    missing = tmp_path / "missing.json"
    assert runtime.load_manifest(missing) is None

    invalid_json = tmp_path / "invalid.json"
    invalid_json.write_text("{", encoding="utf-8")
    assert runtime.load_manifest(invalid_json) is None

    wrong_type = tmp_path / "list.json"
    wrong_type.write_text("[]", encoding="utf-8")
    assert runtime.load_manifest(wrong_type) is None

    wrong_schema = tmp_path / "schema.json"
    wrong_schema.write_text('{"schema": 99}', encoding="utf-8")
    assert runtime.load_manifest(wrong_schema) is None

    bad_fields = tmp_path / "fields.json"
    bad_fields.write_text(
        '{"schema": 1, "host": {}, "playwright_version": "1.0", "engines": [], "packages": []}',
        encoding="utf-8",
    )
    assert runtime.load_manifest(bad_fields) is None

    bad_package = tmp_path / "package.json"
    bad_package.write_text(
        '{"schema": 1, "host": {"distribution": "ubuntu", "version": "26.04",'
        ' "architecture": "amd64"}, "playwright_version": "1.0",'
        ' "engines": ["chromium"], "packages": [{"name": "../x", "version": "1"}]}',
        encoding="utf-8",
    )
    assert runtime.load_manifest(bad_package) is None


def test_regular_file_rejects_unstattable_paths() -> None:
    """A path the operating system refuses to stat is never a regular file."""
    assert not runtime.regular_file(Path("a" * 5000))


def test_recorded_engines_ignores_unsupported_manifest_entries(tmp_path: Path) -> None:
    """Never feed an unrecognized engine name back into the Playwright CLI."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    paths.local_libraries.mkdir(parents=True)

    assert runtime.recorded_engines(paths) == ()

    runtime.write_manifest(
        paths.manifest,
        dataclasses.replace(make_manifest(), engines=("chromium", "netscape")),
    )

    assert runtime.recorded_engines(paths) == ("chromium",)


def test_requested_engines_extends_a_chromium_only_manifest(tmp_path: Path) -> None:
    """Preparing WebKit must widen, never replace, the recorded Chromium closure."""
    paths = ready_paths(tmp_path, engines=("chromium",))

    assert runtime.requested_engines(paths, ["webkit"]) == ("chromium", "webkit")
    assert runtime.requested_engines(paths, ["chromium"]) == ("chromium",)


def test_requested_engines_starts_from_the_request_without_a_manifest(
    tmp_path: Path,
) -> None:
    """A first preparation records exactly the engines the Make target asked for."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)

    assert runtime.requested_engines(paths, ["webkit"]) == ("webkit",)


# ─── Cache roots, locking, and staging ───────────────────────────────────────


def test_cache_root_refuses_symlink(tmp_path: Path) -> None:
    """Refuse a cache root that redirects writes outside the repository."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".playwright").symlink_to(outside, target_is_directory=True)

    with pytest.raises(runtime.RuntimeSetupError, match="not a symlink"):
        runtime.ensure_cache_root(runtime.RuntimePaths.from_repo(tmp_path))


def test_cache_root_refuses_dangling_symlink(tmp_path: Path) -> None:
    """Reject a broken symlink root that exists() would silently skip."""
    (tmp_path / ".playwright").symlink_to(tmp_path / "missing", target_is_directory=True)

    with pytest.raises(runtime.RuntimeSetupError, match="not a symlink"):
        runtime.ensure_cache_root(runtime.RuntimePaths.from_repo(tmp_path))


def test_cache_root_must_sit_directly_below_the_repository(tmp_path: Path) -> None:
    """Never create the cache anywhere but the repository's own ignored directory."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    escaped = dataclasses.replace(paths, cache_root=tmp_path / "nested" / ".playwright")

    with pytest.raises(runtime.RuntimeSetupError, match="directly below the repository root"):
        runtime.ensure_cache_root(escaped)


def test_cache_lock_serializes_preparation(tmp_path: Path) -> None:
    """Hold an exclusive lock on a private regular file below the cache root."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)

    with runtime.cache_lock(paths):
        lock_path = paths.cache_root / "setup.lock"
        assert lock_path.is_file()
        assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600


def test_cache_lock_reports_an_unopenable_lock(tmp_path: Path) -> None:
    """A missing cache root is reported instead of surfacing a raw OSError."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)

    with (
        pytest.raises(runtime.RuntimeSetupError, match="cannot open"),
        runtime.cache_lock(paths),
    ):
        pass


def test_cache_lock_rejects_a_non_regular_lock(tmp_path: Path) -> None:
    """A FIFO planted at the lock path must not be accepted as a lock file."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    os.mkfifo(paths.cache_root / "setup.lock")

    with (
        pytest.raises(runtime.RuntimeSetupError, match="must be a regular file"),
        runtime.cache_lock(paths),
    ):
        pass


def test_cache_lock_reports_a_descriptor_that_cannot_be_secured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Close the descriptor and report clearly when it cannot be made private."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    monkeypatch.setattr(
        runtime.os,
        "fchmod",
        lambda *_args: (_ for _ in ()).throw(OSError("read-only")),
    )

    with (
        pytest.raises(runtime.RuntimeSetupError, match="cannot use"),
        runtime.cache_lock(paths),
    ):
        pass


def test_cache_lock_reports_a_failed_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Surface a lock failure as a setup error instead of an OSError traceback."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    monkeypatch.setattr(
        fcntl,
        "flock",
        lambda *_args: (_ for _ in ()).throw(OSError("locked")),
    )

    with (
        pytest.raises(runtime.RuntimeSetupError, match="cannot lock"),
        runtime.cache_lock(paths),
    ):
        pass


def test_remove_stale_staging_deletes_only_owned_stage_directories(tmp_path: Path) -> None:
    """Clear archives abandoned by an interrupted setup and keep other cache files."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    stale = paths.cache_root / ".stage-abandoned"
    stale.mkdir()
    (stale / "archive.deb").write_bytes(b"archive")
    marker = paths.cache_root / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    runtime.remove_stale_staging(paths)

    assert not stale.exists()
    assert marker.read_text(encoding="utf-8") == "keep"


def test_remove_stale_staging_rejects_a_forged_stage_symlink(tmp_path: Path) -> None:
    """Never follow a planted staging symlink into an unrelated directory."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    outside = tmp_path / "outside"
    outside.mkdir()
    (paths.cache_root / ".stage-forged").symlink_to(outside, target_is_directory=True)

    with pytest.raises(runtime.RuntimeSetupError, match="unsafe Playwright staging path"):
        runtime.remove_stale_staging(paths)


# ─── Atomic publication ──────────────────────────────────────────────────────


def test_atomic_publish_failure_keeps_the_previous_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep the active cache intact when an atomic directory exchange fails."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    (paths.extracted_root).mkdir(parents=True)
    old_marker = paths.local_libraries / "old-cache"
    old_marker.write_text("keep", encoding="utf-8")
    staged = paths.cache_root / ".stage-test" / "local-libs"
    (staged / "root").mkdir(parents=True)

    def fail_exchange(_left: Path, _right: Path) -> None:
        raise runtime.RuntimeSetupError("injected exchange failure")

    monkeypatch.setattr(runtime, "exchange_directories", fail_exchange)

    with pytest.raises(runtime.RuntimeSetupError, match="injected exchange failure"):
        runtime.publish_local_libraries(paths, staged)

    assert old_marker.read_text(encoding="utf-8") == "keep"
    assert (staged / "root").is_dir()


def test_publish_local_libraries_installs_a_first_cache(tmp_path: Path) -> None:
    """The first publication renames staging into place without an exchange."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    staged = paths.cache_root / ".stage-test" / "local-libs"
    (staged / "root").mkdir(parents=True)

    runtime.publish_local_libraries(paths, staged)

    assert paths.extracted_root.is_dir()
    assert not staged.exists()


def test_publish_local_libraries_swaps_an_existing_cache(tmp_path: Path) -> None:
    """Replace an active cache atomically and then drop the old contents."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    paths.extracted_root.mkdir(parents=True)
    (paths.local_libraries / "old-marker").write_text("old", encoding="utf-8")
    staged = paths.cache_root / ".stage-test" / "local-libs"
    (staged / "root").mkdir(parents=True)
    (staged / "new-marker").write_text("new", encoding="utf-8")

    runtime.publish_local_libraries(paths, staged)

    assert (paths.local_libraries / "new-marker").read_text(encoding="utf-8") == "new"
    assert not (paths.local_libraries / "old-marker").exists()
    assert not staged.exists()


def test_publish_local_libraries_refuses_staging_outside_the_cache(tmp_path: Path) -> None:
    """Never publish from a staging directory outside the repository cache."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    runtime.ensure_cache_root(paths)
    outside = tmp_path / "outside-stage"
    outside.mkdir()

    with pytest.raises(runtime.RuntimeSetupError, match="must remain below"):
        runtime.publish_local_libraries(paths, outside)


def test_exchange_directories_swaps_two_directories(tmp_path: Path) -> None:
    """renameat2 exchanges the two trees in one atomic step."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "marker").write_text("left", encoding="utf-8")
    (right / "marker").write_text("right", encoding="utf-8")

    runtime.exchange_directories(left, right)

    assert (left / "marker").read_text(encoding="utf-8") == "right"
    assert (right / "marker").read_text(encoding="utf-8") == "left"


def test_exchange_directories_reports_a_kernel_failure(tmp_path: Path) -> None:
    """A refused exchange is reported with the operating system's reason."""
    left = tmp_path / "left"
    left.mkdir()

    with pytest.raises(runtime.RuntimeSetupError, match="cannot atomically publish"):
        runtime.exchange_directories(left, tmp_path / "missing")


def test_exchange_directories_requires_renameat2(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse to publish non-atomically on a host without renameat2."""

    class LibraryWithoutRenameat2:
        """A C library handle that does not expose renameat2."""

        def __getattr__(self, name: str) -> object:
            raise AttributeError(name)

    monkeypatch.setattr(ctypes, "CDLL", lambda *_args, **_kwargs: LibraryWithoutRenameat2())

    with pytest.raises(runtime.RuntimeSetupError, match="lacks renameat2"):
        runtime.exchange_directories(Path("left"), Path("right"))


# ─── Preparation ─────────────────────────────────────────────────────────────


def test_prepare_reuses_a_current_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A matching manifest short-circuits the download entirely."""
    paths = ready_paths(tmp_path)
    monkeypatch.setattr(
        runtime,
        "expected_manifest",
        lambda _paths, _stage, engines: make_manifest(engines=tuple(engines)),
    )

    runtime.prepare(paths, ["chromium"])

    assert "Playwright local runtime is current." in capsys.readouterr().out
    assert not list(paths.cache_root.glob(".stage-*"))


def test_prepare_extends_the_recorded_engine_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Preparing WebKit after Chromium rebuilds against the union of both closures."""
    paths = ready_paths(tmp_path, engines=("chromium",))
    requested: list[tuple[str, ...]] = []

    def fake_expected_manifest(
        _paths: runtime.RuntimePaths,
        _stage: Path,
        engines: Sequence[str],
    ) -> runtime.CacheManifest:
        requested.append(tuple(engines))
        return make_manifest(engines=tuple(engines))

    def fake_download_and_extract(
        _packages: Sequence[runtime.PackageVersion],
        stage: Path,
    ) -> Path:
        extracted = stage / "local-libs" / "root"
        extracted.mkdir(parents=True)
        return extracted

    monkeypatch.setattr(runtime, "expected_manifest", fake_expected_manifest)
    monkeypatch.setattr(runtime, "download_and_extract", fake_download_and_extract)

    runtime.prepare(paths, ["webkit"])

    assert requested == [("chromium", "webkit")]
    manifest = runtime.load_manifest(paths.manifest)
    assert manifest is not None
    assert manifest.engines == ("chromium", "webkit")
    assert "chromium, webkit" in capsys.readouterr().out


def test_prepare_removes_staging_even_when_resolution_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed preparation leaves no staging directory and no partial cache."""
    paths = ready_paths(tmp_path)

    def explode(
        _paths: runtime.RuntimePaths,
        _stage: Path,
        _engines: Sequence[str],
    ) -> runtime.CacheManifest:
        raise runtime.RuntimeSetupError("injected resolution failure")

    monkeypatch.setattr(runtime, "expected_manifest", explode)

    with pytest.raises(runtime.RuntimeSetupError, match="injected resolution failure"):
        runtime.prepare(paths, ["chromium"])

    assert not list(paths.cache_root.glob(".stage-*"))


def test_prepare_tolerates_staging_already_removed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A step that cleans up its own staging must not break the outer cleanup."""
    paths = ready_paths(tmp_path)

    def remove_stage_and_fail(
        _paths: runtime.RuntimePaths,
        stage: Path,
        _engines: Sequence[str],
    ) -> runtime.CacheManifest:
        shutil.rmtree(stage)
        raise runtime.RuntimeSetupError("injected failure after cleanup")

    monkeypatch.setattr(runtime, "expected_manifest", remove_stage_and_fail)

    with pytest.raises(runtime.RuntimeSetupError, match="injected failure after cleanup"):
        runtime.prepare(paths, ["chromium"])

    assert not list(paths.cache_root.glob(".stage-*"))


def test_expected_manifest_records_every_invalidating_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bind the cache identity to host, Playwright version, engines, and closure."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    install_fake_playwright(paths.repo_root)
    monkeypatch.setattr(runtime, "dependency_seeds", lambda _paths, _engines: ("libdemo0",))
    monkeypatch.setattr(
        runtime,
        "resolve_packages",
        lambda _seeds, _stage: (runtime.PackageVersion(name="libdemo0", version="1.0"),),
    )

    manifest = runtime.expected_manifest(paths, tmp_path, ("chromium", "webkit"))

    assert manifest.schema == runtime.MANIFEST_SCHEMA
    assert manifest.host == runtime.current_host()
    assert manifest.playwright_version == "1.61.0"
    assert manifest.engines == ("chromium", "webkit")
    assert manifest.packages == (runtime.PackageVersion(name="libdemo0", version="1.0"),)


# ─── Runtime environment construction ────────────────────────────────────────


def test_runtime_environment_prepends_only_discovered_private_paths(tmp_path: Path) -> None:
    """Build runtime paths from extracted content while preserving host values."""
    paths = ready_paths(tmp_path)
    library_dir = paths.extracted_root / "usr" / "lib" / "x86_64-linux-gnu"
    library_dir.mkdir(parents=True)
    (library_dir / "libdemo.so.1").write_text("", encoding="utf-8")
    (paths.extracted_root / "usr" / "bin").mkdir(parents=True)
    (paths.extracted_root / "usr" / "share").mkdir(parents=True)
    (library_dir / "girepository-1.0").mkdir()
    plugin_dir = library_dir / "gstreamer-1.0"
    plugin_dir.mkdir()
    (plugin_dir / "libgstplugin.so").write_text("", encoding="utf-8")
    schema_dir = paths.extracted_root / "usr" / "share" / "glib-2.0" / "schemas"
    schema_dir.mkdir(parents=True)

    environment = runtime.runtime_environment(
        paths,
        {
            "HOME": "/host/home",
            "LD_LIBRARY_PATH": "/host/lib",
            "PATH": "/host/bin",
            "XDG_DATA_DIRS": "/host/share",
            "GI_TYPELIB_PATH": "/host/typelibs",
            "GST_PLUGIN_PATH_1_0": "/host/plugins",
            "GSETTINGS_SCHEMA_DIR": "/host/schemas",
        },
    )

    assert environment["PLAYWRIGHT_BROWSERS_PATH"] == str(paths.browser_root)
    assert environment["HOME"] == str(paths.runtime_home)
    assert environment["XDG_CACHE_HOME"] == str(paths.runtime_cache)
    assert environment["XDG_CONFIG_HOME"] == str(paths.runtime_config)
    assert environment["XDG_RUNTIME_DIR"] == str(paths.runtime_run)
    assert environment["TMPDIR"] == str(paths.runtime_tmp)
    assert environment["npm_config_cache"] == str(paths.runtime_cache / "npm")
    assert environment["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] == "1"
    assert environment["LD_LIBRARY_PATH"] == f"{library_dir}{os.pathsep}/host/lib"
    assert str(plugin_dir) not in environment["LD_LIBRARY_PATH"]
    assert environment["PATH"] == f"{paths.extracted_root / 'usr' / 'bin'}{os.pathsep}/host/bin"
    assert environment["XDG_DATA_DIRS"] == (
        f"{paths.extracted_root / 'usr' / 'share'}{os.pathsep}/host/share"
    )
    assert environment["GI_TYPELIB_PATH"].endswith(f"{os.pathsep}/host/typelibs")
    assert environment["GST_PLUGIN_PATH_1_0"].endswith(f"{os.pathsep}/host/plugins")
    assert environment["GSETTINGS_SCHEMA_DIR"].endswith(f"{os.pathsep}/host/schemas")


def test_runtime_environment_inherits_the_process_environment(tmp_path: Path) -> None:
    """Without an explicit base the wrapper starts from the caller's environment."""
    paths = ready_paths(tmp_path)

    environment = runtime.runtime_environment(paths)

    assert environment["PLAYWRIGHT_BROWSERS_PATH"] == str(paths.browser_root)


def test_discovered_directories_finds_root_level_library_trees(tmp_path: Path) -> None:
    """Bare lib/, bin/, and share/ trees are discovered alongside their usr/ twins."""
    root = tmp_path / "root"
    library_dir = root / "lib" / "x86_64-linux-gnu"
    library_dir.mkdir(parents=True)
    (library_dir / "libdemo.so.1").write_text("", encoding="utf-8")
    (root / "bin").mkdir()
    (root / "share").mkdir()
    (root / "usr" / "local" / "share").mkdir(parents=True)

    discovered = runtime.discovered_directories(root)

    assert discovered["libraries"] == [library_dir]
    assert discovered["path"] == [root / "bin"]
    assert set(discovered["data"]) == {root / "share", root / "usr" / "local" / "share"}


def test_discovered_directories_handles_a_missing_root(tmp_path: Path) -> None:
    """An unbuilt runtime root contributes no environment entries."""
    assert runtime.discovered_directories(tmp_path / "missing") == {
        "libraries": [],
        "path": [],
        "data": [],
        "typelibs": [],
        "gstreamer": [],
        "schemas": [],
    }


def test_prepend_environment_keeps_unset_variables_unset() -> None:
    """Never introduce an empty variable when nothing was discovered."""
    environment: dict[str, str] = {}

    runtime.prepend_environment(environment, "LD_LIBRARY_PATH", [])

    assert environment == {}


def test_browser_root_defaults_to_the_shared_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Resolve browsers to the shared cache, honoring an explicit override."""
    monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path / "explicit"))
    override_paths = runtime.RuntimePaths.from_repo(tmp_path)
    assert override_paths.browser_root == tmp_path / "explicit"

    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    shared_paths = runtime.RuntimePaths.from_repo(tmp_path)
    assert shared_paths.browser_root == tmp_path / "home" / ".cache" / "ms-playwright"
    # The shared browsers are never placed under the repository-local cache.
    assert not runtime.is_within(shared_paths.browser_root, shared_paths.cache_root)


def test_browser_root_falls_back_to_the_account_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty HOME still resolves through the account's own home directory."""
    monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
    monkeypatch.setenv("HOME", "")

    assert runtime.default_shared_browser_root() == Path.home() / ".cache" / "ms-playwright"


# ─── Readiness gating ────────────────────────────────────────────────────────


def test_browser_cache_ready_accepts_a_symlinked_shared_cache(tmp_path: Path) -> None:
    """A symlinked user browser cache (a common ~/.cache redirect) stays usable."""
    paths = ready_paths(tmp_path)
    assert runtime.browser_cache_ready(paths, runtime.ENGINES)

    real_cache = tmp_path / "real-cache"
    paths.browser_root.rename(real_cache)
    paths.browser_root.symlink_to(real_cache, target_is_directory=True)

    assert paths.browser_root.is_symlink()
    assert runtime.browser_cache_ready(paths, runtime.ENGINES)


def test_browser_cache_ready_requires_every_prepared_engine(tmp_path: Path) -> None:
    """Report the cache as unready until each recorded engine is installed."""
    paths = ready_paths(tmp_path, engines=("chromium",))

    assert runtime.browser_cache_ready(paths, ("chromium",))
    assert not runtime.browser_cache_ready(paths, ("chromium", "webkit"))


def test_browser_cache_ready_requires_a_browser_root(tmp_path: Path) -> None:
    """A missing shared browser cache is never treated as prepared."""
    paths = runtime.RuntimePaths.from_repo(tmp_path, browser_root=tmp_path / "missing")

    assert not runtime.browser_cache_ready(paths, ("chromium",))


def test_browser_cache_ready_requires_patched_webkit_launchers(tmp_path: Path) -> None:
    """WebKit is only ready once its launcher appends the inherited library path."""
    paths = ready_paths(tmp_path)
    write_webkit_launcher(paths, patched=False)

    assert not runtime.browser_cache_ready(paths, runtime.ENGINES)


def test_browser_cache_ready_requires_a_webkit_launcher(tmp_path: Path) -> None:
    """A WebKit bundle without a launcher cannot be library-path patched."""
    paths = ready_paths(tmp_path)
    launcher = paths.browser_root / "webkit-test" / "minibrowser-wpe" / "MiniBrowser"
    launcher.unlink()

    assert not runtime.browser_cache_ready(paths, runtime.ENGINES)


def test_browser_cache_ready_rejects_a_symlinked_engine_directory(tmp_path: Path) -> None:
    """A symlinked engine directory is not a real installed browser."""
    paths = ready_paths(tmp_path, engines=("chromium",))
    engine = paths.browser_root / "chromium-test"
    engine.rmdir()
    engine.symlink_to(tmp_path / "elsewhere", target_is_directory=True)

    assert not runtime.browser_cache_ready(paths, ("chromium",))


def test_require_ready_reports_each_missing_precondition(tmp_path: Path) -> None:
    """Refuse to run before a verified cache, matching host, and installed browsers."""
    paths = ready_paths(tmp_path)

    assert runtime.require_ready(paths) == runtime.ENGINES

    runtime.write_manifest(paths.manifest, make_manifest(version="0.0.1"))
    with pytest.raises(runtime.RuntimeSetupError, match="stale"):
        runtime.require_ready(paths)

    runtime.write_manifest(paths.manifest, make_manifest(engines=()))
    with pytest.raises(runtime.RuntimeSetupError, match="stale"):
        runtime.require_ready(paths)

    runtime.write_manifest(paths.manifest, make_manifest(engines=("netscape",)))
    with pytest.raises(runtime.RuntimeSetupError, match="stale"):
        runtime.require_ready(paths)

    paths.manifest.unlink()
    with pytest.raises(runtime.RuntimeSetupError, match="not prepared"):
        runtime.require_ready(paths)


def test_require_ready_rejects_missing_browsers(tmp_path: Path) -> None:
    """A prepared library cache without browsers cannot launch anything."""
    paths = ready_paths(tmp_path)
    (paths.browser_root / "chromium-test").rmdir()

    with pytest.raises(runtime.RuntimeSetupError, match="browsers are not prepared"):
        runtime.require_ready(paths)


# ─── WebKit launcher patching ────────────────────────────────────────────────


def test_patch_webkit_launchers_preserves_inherited_private_libraries(tmp_path: Path) -> None:
    """Patch only the shared launcher and keep the browser wrapper executable."""
    paths = runtime.RuntimePaths.from_repo(tmp_path, browser_root=tmp_path / "shared-browsers")
    launcher = write_webkit_launcher(paths, patched=False)

    runtime.patch_webkit_launchers(paths)
    first_content = launcher.read_text(encoding="utf-8")
    runtime.patch_webkit_launchers(paths)

    assert runtime.WEBKIT_LAUNCHER_LOCAL_LD_LINE in first_content
    assert launcher.read_text(encoding="utf-8") == first_content
    assert launcher.stat().st_mode & stat.S_IXUSR


def test_patch_webkit_launchers_rejects_an_unexpected_format(tmp_path: Path) -> None:
    """Never rewrite a launcher whose library-path line is not the known one."""
    paths = runtime.RuntimePaths.from_repo(tmp_path, browser_root=tmp_path / "shared-browsers")
    launcher = write_webkit_launcher(paths, patched=False)
    launcher.write_text("#!/bin/sh\nexec MiniBrowser\n", encoding="utf-8")

    with pytest.raises(runtime.RuntimeSetupError, match="unexpected shared WebKit launcher"):
        runtime.patch_webkit_launchers(paths)


def test_webkit_launchers_skips_unusable_bundles(tmp_path: Path) -> None:
    """Only real, executable launchers inside the browser cache are patched."""
    missing_root = runtime.RuntimePaths.from_repo(tmp_path, browser_root=tmp_path / "missing")
    assert runtime.webkit_launchers(missing_root) == []

    paths = runtime.RuntimePaths.from_repo(tmp_path, browser_root=tmp_path / "shared-browsers")
    launcher = write_webkit_launcher(paths, patched=True)
    paths.browser_root.mkdir(parents=True, exist_ok=True)
    (paths.browser_root / "webkit-linked").symlink_to(
        launcher.parent.parent,
        target_is_directory=True,
    )
    (paths.browser_root / "webkit-file").write_text("not a bundle", encoding="utf-8")

    assert runtime.webkit_launchers(paths) == [launcher]

    launcher.chmod(0o644)

    assert runtime.webkit_launchers(paths) == []


def test_webkit_launcher_is_patched_handles_unreadable_launchers(tmp_path: Path) -> None:
    """An unreadable launcher is reported as unpatched rather than crashing."""
    assert not runtime.webkit_launcher_is_patched(tmp_path)


# ─── Wrapped execution ───────────────────────────────────────────────────────


def test_run_in_runtime_propagates_the_child_exit_status(tmp_path: Path) -> None:
    """Return the exact status from a wrapped command."""
    paths = ready_paths(tmp_path)

    exit_code = runtime.run_in_runtime(
        paths,
        [sys.executable, "-c", "import sys; sys.exit(17)"],
        base={},
    )

    assert exit_code == 17


def test_run_in_runtime_reports_a_signalled_child(tmp_path: Path) -> None:
    """A signal-terminated child maps onto the conventional 128+signal status."""
    paths = ready_paths(tmp_path)

    exit_code = runtime.run_in_runtime(
        paths,
        [sys.executable, "-c", "import os, signal; os.kill(os.getpid(), signal.SIGTERM)"],
        base={},
    )

    assert exit_code == 143


def test_run_in_runtime_requires_a_command(tmp_path: Path) -> None:
    """An empty wrapper invocation is a usage error, not a silent success."""
    paths = ready_paths(tmp_path)

    with pytest.raises(runtime.RuntimeSetupError, match="requires a command after"):
        runtime.run_in_runtime(paths, [])


def test_run_in_runtime_reports_an_unrunnable_command(tmp_path: Path) -> None:
    """A missing wrapped executable is reported through the Make-facing error."""
    paths = ready_paths(tmp_path)

    with pytest.raises(runtime.RuntimeSetupError, match="cannot run wrapped command"):
        runtime.run_in_runtime(paths, [str(tmp_path / "missing-binary")], base={})


def test_probe_launches_every_prepared_engine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate launches exactly the engines the manifest records as prepared."""
    paths = ready_paths(tmp_path, engines=("chromium",))
    seen: list[list[str]] = []

    def fake_run_in_runtime(
        _paths: runtime.RuntimePaths,
        command: Sequence[str],
        base: Mapping[str, str] | None = None,
    ) -> int:
        del base
        seen.append(list(command))
        return 0

    monkeypatch.setattr(runtime, "run_in_runtime", fake_run_in_runtime)

    assert runtime.probe(paths) == 0
    assert seen == [[sys.executable, "-c", runtime.PROBE_PROGRAM, "chromium"]]


# ─── Status and cleanup ──────────────────────────────────────────────────────


def test_status_reports_a_prepared_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Summarize the cache identity without downloading or inspecting user data."""
    paths = ready_paths(tmp_path)

    assert runtime.status(paths) == 0

    output = capsys.readouterr().out
    assert "READY: repository-local Playwright runtime" in output
    assert "Playwright: 1.61.0" in output
    assert "engines: chromium, webkit" in output
    assert "packages: 1" in output


def test_status_reports_an_unprepared_runtime(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Report a non-zero status with the reason instead of raising."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)

    assert runtime.status(paths) == 1
    assert "NOT READY:" in capsys.readouterr().out


def test_clean_removes_only_the_repository_local_cache(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Remove the ignored runtime cache without touching a sibling or shared browsers."""
    paths = ready_paths(tmp_path)
    sibling = tmp_path / "keep.txt"
    sibling.write_text("keep", encoding="utf-8")

    runtime.clean(paths)

    assert not paths.cache_root.exists()
    assert sibling.read_text(encoding="utf-8") == "keep"
    # Browsers live outside the repository cache, so cleaning leaves them shared.
    assert paths.browser_root.is_dir()
    assert "shared browsers kept" in capsys.readouterr().out


def test_clean_is_idempotent(tmp_path: Path) -> None:
    """Cleaning an absent cache succeeds instead of failing the Make target."""
    runtime.clean(runtime.RuntimePaths.from_repo(tmp_path))


# ─── Command-line surface ────────────────────────────────────────────────────


def test_run_action_drops_the_make_wrapper_separator() -> None:
    """Strip the leading -- so the wrapped command reaches exec unaltered."""
    wrapped = runtime.parse_args(["run", "--", "python", "-m", "pytest", "--", "tests/browser"])
    assert wrapped.command == ["python", "-m", "pytest", "--", "tests/browser"]

    direct = runtime.parse_args(["run", "python", "-c", "code"])
    assert direct.command == ["python", "-c", "code"]


def test_prepare_action_requires_supported_engines() -> None:
    """Only engines this repository installs may enter the Playwright command."""
    parsed = runtime.parse_args(["prepare", "--engine", "chromium", "--engine", "webkit"])
    assert parsed.engines == ["chromium", "webkit"]

    with pytest.raises(SystemExit):
        runtime.parse_args(["prepare", "--engine", "netscape"])

    with pytest.raises(SystemExit):
        runtime.parse_args(["prepare"])


def test_main_dispatches_every_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Route each Make-facing subcommand to its handler and return its status."""
    paths = ready_paths(tmp_path)
    monkeypatch.setattr(
        runtime.RuntimePaths,
        "from_repo",
        staticmethod(lambda *_args, **_kwargs: paths),
    )
    prepared: list[list[str]] = []
    monkeypatch.setattr(
        runtime,
        "prepare",
        lambda _paths, engines: prepared.append(list(engines)),
    )
    monkeypatch.setattr(runtime, "probe", lambda _paths: 7)
    monkeypatch.setattr(runtime, "run_in_runtime", lambda _paths, command: len(command))

    assert runtime.main(["prepare", "--engine", "chromium"]) == 0
    assert prepared == [["chromium"]]
    assert runtime.main(["status"]) == 0
    assert runtime.main(["probe"]) == 7
    assert runtime.main(["run", "--", "true"]) == 1
    assert runtime.main(["clean"]) == 0
    assert not paths.cache_root.exists()
    assert "READY" in capsys.readouterr().out


def test_main_reads_the_process_arguments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without explicit arguments the entry point uses the process command line."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    monkeypatch.setattr(
        runtime.RuntimePaths,
        "from_repo",
        staticmethod(lambda *_args, **_kwargs: paths),
    )
    monkeypatch.setattr(sys, "argv", ["playwright_local_runtime.py", "status"])

    assert runtime.main() == 1
    assert "NOT READY:" in capsys.readouterr().out


def test_main_reports_setup_errors_concisely(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Expected setup failures become a one-line message and exit status 1."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    monkeypatch.setattr(
        runtime.RuntimePaths,
        "from_repo",
        staticmethod(lambda *_args, **_kwargs: paths),
    )

    assert runtime.main(["probe"]) == 1
    assert "ERROR: local Playwright runtime is not prepared" in capsys.readouterr().err


def test_main_refuses_an_unknown_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An action with no handler is a programming error, not a silent success."""
    paths = runtime.RuntimePaths.from_repo(tmp_path)
    monkeypatch.setattr(
        runtime.RuntimePaths,
        "from_repo",
        staticmethod(lambda *_args, **_kwargs: paths),
    )
    monkeypatch.setattr(
        runtime,
        "parse_args",
        lambda _arguments: argparse.Namespace(action="unsupported"),
    )

    with pytest.raises(AssertionError, match="unhandled action: unsupported"):
        runtime.main(["status"])
