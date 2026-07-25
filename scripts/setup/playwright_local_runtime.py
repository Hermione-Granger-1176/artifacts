#!/usr/bin/env python3
"""Build and use a private, no-sudo Linux runtime for Playwright browsers.

The utility deliberately uses only Python's standard library.  It obtains package
names from Playwright's dependency dry run, resolves that set with a simulated
APT transaction, downloads the resulting archives with ``apt download``, and
extracts them below the repository's ignored ``.playwright`` directory.  It never
installs a package or changes the system package database.

Browsers themselves are not copied per repository: they use Playwright's shared
``$HOME/.cache/ms-playwright`` cache so every project reuses one copy.  Only the
extracted shared libraries and per-run scratch stay under ``.playwright``.

Chromium and WebKit are installed by separate Make targets, so a preparation run
extends the recorded engine set instead of replacing it.  The active package
closure is therefore always the union required by every engine prepared so far.
"""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import json
import os
import platform
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence


MANIFEST_SCHEMA = 1
ENGINES = ("chromium", "webkit")
VENV_DIRECTORY = ".venv"
PACKAGE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.-]*(?::[A-Za-z0-9][A-Za-z0-9+_.-]*)?$")
PACKAGE_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.:~%-]*$")
DIST_INFO_RE = re.compile(r"^playwright-([A-Za-z0-9][A-Za-z0-9+_.!-]*)\.dist-info$")
UNSAFE_SHELL_CHARS = (";", "&", "|", "<", ">", "`", "$", "(", ")")
AT_FDCWD = -100
RENAME_EXCHANGE = 0x2
WEBKIT_LAUNCHER_LD_LINE = 'export LD_LIBRARY_PATH="${MYDIR}/lib:${MYDIR}/sys/lib"'
WEBKIT_LAUNCHER_LOCAL_LD_LINE = (
    'export LD_LIBRARY_PATH="${MYDIR}/lib:${MYDIR}/sys/lib${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}"'
)

# Launch every prepared engine, load a trivial in-memory document, and evaluate a
# title so the gate proves a real browser process started rather than only that an
# executable exists.  Engine names arrive as arguments after ``python -c``.
PROBE_PROGRAM = """
import sys

from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    for name in sys.argv[1:]:
        print(f"PROBE: launching {name}")
        browser = getattr(playwright, name).launch(timeout=45000)
        print(f"PROBE: launched {name}")
        page = browser.new_page()
        page.set_content("<title>probe</title>")
        if page.title() != "probe":
            raise SystemExit(f"FAIL: {name} did not render a page")
        page.close()
        browser.close()
        print(f"OK: {name}")
"""


class RuntimeSetupError(RuntimeError):
    """Raised when a private runtime cannot be built or used safely."""


@dataclass(frozen=True)
class HostPlatform:
    """The supported operating-system facts that scope one cache manifest."""

    distribution: str
    version: str
    architecture: str


@dataclass(frozen=True, order=True)
class PackageVersion:
    """An exact package version resolved by APT's simulated transaction."""

    name: str
    version: str


@dataclass(frozen=True)
class CacheManifest:
    """The complete cache identity used for reuse and invalidation."""

    schema: int
    host: HostPlatform
    playwright_version: str
    engines: tuple[str, ...]
    packages: tuple[PackageVersion, ...]

    def to_json(self) -> dict[str, object]:
        """Return a deterministic JSON-safe representation."""
        return {
            "schema": self.schema,
            "host": asdict(self.host),
            "playwright_version": self.playwright_version,
            "engines": list(self.engines),
            "packages": [asdict(package) for package in self.packages],
        }


def default_shared_browser_root() -> Path:
    """Return Playwright's shared browser cache so every project reuses one copy.

    Browsers are large and version-stable, so they live in Playwright's normal
    user-level cache (``$HOME/.cache/ms-playwright``) rather than a per-repository
    copy. An explicit ``PLAYWRIGHT_BROWSERS_PATH`` in the environment wins, mirroring
    Playwright's own precedence. Only the extracted shared libraries and per-run
    scratch stay under the repository's ignored ``.playwright`` cache.
    """
    override = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if override:
        return Path(override)
    home = os.environ.get("HOME") or str(Path.home())
    return Path(home) / ".cache" / "ms-playwright"


@dataclass(frozen=True)
class RuntimePaths:
    """Paths owned by one repository-local runtime cache and the shared browsers."""

    repo_root: Path
    cache_root: Path
    local_libraries: Path
    extracted_root: Path
    manifest: Path
    browser_root: Path
    runtime_state: Path
    runtime_home: Path
    runtime_cache: Path
    runtime_config: Path
    runtime_tmp: Path
    runtime_run: Path

    @classmethod
    def from_repo(cls, repo_root: Path, browser_root: Path | None = None) -> RuntimePaths:
        """Create cache paths without following a user-controlled cache symlink.

        ``browser_root`` defaults to the shared Playwright browser cache; callers
        (and tests) may pass an explicit path to isolate the browser location.
        """
        resolved_root = repo_root.resolve()
        cache_root = resolved_root / ".playwright"
        libraries = cache_root / "local-libs"
        runtime_state = cache_root / "runtime"
        return cls(
            repo_root=resolved_root,
            cache_root=cache_root,
            local_libraries=libraries,
            extracted_root=libraries / "root",
            manifest=libraries / "manifest.json",
            browser_root=(
                browser_root if browser_root is not None else default_shared_browser_root()
            ),
            runtime_state=runtime_state,
            runtime_home=runtime_state / "home",
            runtime_cache=runtime_state / "cache",
            runtime_config=runtime_state / "config",
            runtime_tmp=runtime_state / "tmp",
            runtime_run=runtime_state / "run",
        )


def fail(message: str) -> RuntimeSetupError:
    """Create a concise error that is safe to show from a Make target."""
    return RuntimeSetupError(message)


def is_within(path: Path, parent: Path) -> bool:
    """Return whether a resolved path remains under the resolved parent."""
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def require_regular_directory(path: Path, label: str) -> None:
    """Reject symlinked roots before reading, creating, or deleting their contents."""
    # lstat (unlike exists) does not follow symlinks, so a dangling symlink is
    # still rejected here instead of surfacing later as a raw mkdir/rmtree error.
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        raise fail(f"{label} must be a real directory, not a symlink or non-directory: {path}")


def ensure_private_directory(path: Path, label: str) -> None:
    """Create a mode-0700 directory only below the repository-local cache."""
    require_regular_directory(path, label)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    require_regular_directory(path, label)
    path.chmod(0o700)


def ensure_cache_root(paths: RuntimePaths) -> None:
    """Create and validate the cache root without accepting an escaped path."""
    if paths.cache_root.parent != paths.repo_root:
        raise fail("the Playwright cache must be directly below the repository root")
    ensure_private_directory(paths.cache_root, "Playwright cache root")


def ensure_runtime_state(paths: RuntimePaths) -> None:
    """Create private home, cache, configuration, runtime, and temporary roots."""
    ensure_private_directory(paths.runtime_state, "local Playwright runtime state")
    for directory, label in (
        (paths.runtime_home, "local Playwright home"),
        (paths.runtime_cache, "local Playwright runtime cache"),
        (paths.runtime_config, "local Playwright runtime configuration"),
        (paths.runtime_tmp, "local Playwright temporary directory"),
        (paths.runtime_run, "local Playwright runtime directory"),
    ):
        ensure_private_directory(directory, label)


@contextmanager
def cache_lock(paths: RuntimePaths) -> Iterator[None]:
    """Serialize cache preparation without following a forged lock symlink."""
    lock_path = paths.cache_root / "setup.lock"

    try:
        no_follow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR | no_follow, 0o600)
    except OSError as error:
        raise fail(f"cannot open the repository-local Playwright cache lock: {error}") from error
    # Validate and tighten the descriptor before wrapping it in a stream. Opening
    # a stream over a non-regular file (a planted FIFO, say) can fail *after* it
    # takes ownership of the descriptor, which would replace this guard's message
    # with an unhandled double-close error.
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise fail("Playwright cache lock must be a regular file")
        os.fchmod(descriptor, 0o600)
    except OSError as error:
        os.close(descriptor)
        raise fail(f"cannot use the repository-local Playwright cache lock: {error}") from error
    except RuntimeSetupError:
        os.close(descriptor)
        raise
    with os.fdopen(descriptor, "a+b") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except OSError as error:
            raise fail(f"cannot lock the repository-local Playwright cache: {error}") from error
        yield


def remove_stale_staging(paths: RuntimePaths) -> None:
    """Remove abandoned private staging directories while holding the cache lock."""
    for entry in paths.cache_root.iterdir():
        if not entry.name.startswith(".stage-"):
            continue
        mode = entry.lstat().st_mode
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode) or not is_within(entry, paths.cache_root):
            raise fail(f"unsafe Playwright staging path: {entry}")
        shutil.rmtree(entry)


def read_os_release() -> dict[str, str]:
    """Read the small shell-style OS release file without executing it."""
    data: dict[str, str] = {}
    os_release = Path("/etc/os-release")
    try:
        lines = os_release.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise fail(f"cannot read {os_release}: {error}") from error
    for line in lines:
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Z0-9_]+", key) is None:
            raise fail("malformed /etc/os-release key")
        try:
            parsed = shlex.split(value, posix=True)
        except ValueError as error:
            raise fail("malformed /etc/os-release value") from error
        if len(parsed) > 1:
            raise fail("malformed /etc/os-release value")
        data[key] = parsed[0] if parsed else ""
    return data


def current_host() -> HostPlatform:
    """Return a supported Linux Debian or Ubuntu host identity."""
    if sys.platform != "linux":
        raise fail(
            "the repository-local Playwright runtime supports Linux Debian and Ubuntu hosts only"
        )
    os_release = read_os_release()
    distribution = os_release.get("ID", "").lower()
    version = os_release.get("VERSION_ID", "")
    if distribution not in {"debian", "ubuntu"} or not version:
        raise fail(
            "the repository-local Playwright runtime requires Debian or Ubuntu with VERSION_ID"
        )
    machine = platform.machine().lower()
    architecture_by_machine = {
        "x86_64": "amd64",
        "amd64": "amd64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }
    architecture = architecture_by_machine.get(machine)
    if architecture is None:
        raise fail(f"unsupported CPU architecture for the Playwright runtime: {machine}")
    return HostPlatform(distribution=distribution, version=version, architecture=architecture)


def playwright_cli(paths: RuntimePaths) -> Path:
    """Find the virtual-environment Playwright command without a global lookup."""
    executable = paths.repo_root / VENV_DIRECTORY / "bin" / "playwright"
    if not executable.is_file() or not is_within(executable, paths.repo_root):
        raise fail("repository Playwright is missing; run make setup before local runtime setup")
    return executable


def playwright_version(paths: RuntimePaths) -> str:
    """Read the installed Playwright version from the virtual environment's metadata.

    The distribution directory name is the resolved version pip installed, so the
    manifest keys on what the environment actually runs rather than on a declared
    range. Reading the directory name keeps this dependency-free and fast enough
    to re-check before every wrapped command.
    """
    versions = {
        match.group(1)
        for site_packages in (paths.repo_root / VENV_DIRECTORY / "lib").glob(
            "python*/site-packages"
        )
        for entry in site_packages.glob("playwright-*.dist-info")
        if (match := DIST_INFO_RE.fullmatch(entry.name)) is not None
    }
    if len(versions) != 1:
        raise fail("cannot resolve the installed Playwright version; run make setup")
    version = versions.pop()
    if PACKAGE_VERSION_RE.fullmatch(version) is None:
        raise fail("the installed Playwright has an invalid version")
    return version


def checked_run(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one fixed argv command and provide its bounded diagnostic on failure."""
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            env=dict(env) if env is not None else None,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as error:
        raise fail(f"cannot run {command[0]}: {error}") from error
    if completed.returncode != 0:
        output = completed.stdout.strip()
        if len(output) > 4000:
            output = f"{output[:2000]}\n... output truncated ...\n{output[-2000:]}"
        detail = f": {output}" if output else ""
        raise fail(f"command failed ({command[0]}, exit {completed.returncode}){detail}")
    return completed


def normalize_shell_lines(output: str) -> list[str]:
    """Join backslash-continued dry-run lines without executing any text."""
    lines: list[str] = []
    current = ""
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.endswith("\\"):
            current += f"{line[:-1]} "
            continue
        lines.append(f"{current}{line}")
        current = ""
    if current:
        raise fail("unterminated Playwright dependency command")
    return lines


def parse_dependency_seeds(output: str) -> tuple[str, ...]:
    """Extract safe package names from Playwright's dependency dry-run report."""
    packages: list[str] = []
    for line in normalize_shell_lines(output):
        if "apt-get" not in line:
            continue
        try:
            tokens = shlex.split(line, posix=True)
        except ValueError as error:
            raise fail("cannot parse Playwright's dependency dry-run output") from error
        if any(any(char in token for char in UNSAFE_SHELL_CHARS) for token in tokens):
            raise fail("unsafe shell syntax in Playwright's dependency dry-run output")
        if not tokens or tokens[0] == "sudo":
            tokens = tokens[1:]
        if len(tokens) < 3 or tokens[0] != "apt-get" or tokens[1] != "install":
            continue
        for token in tokens[2:]:
            if token.startswith("-"):
                continue
            if PACKAGE_NAME_RE.fullmatch(token) is None:
                raise fail("invalid package name in Playwright's dependency dry-run output")
            packages.append(token)
    if packages:
        return tuple(sorted(set(packages)))

    lines = output.splitlines()
    header_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(r"Missing system dependencies \((\d+)\):", line.strip()) is not None
        ),
        None,
    )
    if header_index is None:
        if any(line.strip() == "All system dependencies are installed." for line in lines):
            return ()
        raise fail("Playwright dependency dry run did not provide package seeds")
    header = re.fullmatch(r"Missing system dependencies \((\d+)\):", lines[header_index].strip())
    assert header is not None
    expected_count = int(header.group(1))
    for line in lines[header_index + 1 :]:
        if not line.startswith((" ", "\t")):
            break
        package = line.strip()
        if PACKAGE_NAME_RE.fullmatch(package) is None:
            raise fail("invalid package name in Playwright's dependency dry-run output")
        packages.append(package)
    if len(packages) != expected_count:
        raise fail("Playwright dependency dry run reported an incomplete package list")
    return tuple(sorted(set(packages)))


def dependency_seeds(paths: RuntimePaths, engines: Sequence[str]) -> tuple[str, ...]:
    """Ask Playwright for dependency seeds without running its printed command."""
    command = [str(playwright_cli(paths)), "install-deps", "--dry-run", *engines]
    try:
        completed = subprocess.run(
            command,
            cwd=paths.repo_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except OSError as error:
        raise fail(f"cannot run {command[0]}: {error}") from error
    if completed.returncode not in {0, 1}:
        output = completed.stdout.strip()
        detail = f": {output[-2000:]}" if output else ""
        raise fail(f"Playwright dependency dry run failed (exit {completed.returncode}){detail}")
    return parse_dependency_seeds(completed.stdout)


def parse_simulated_packages(output: str) -> tuple[PackageVersion, ...]:
    """Parse exact package versions from an APT simulation in the C locale."""
    resolved: dict[str, str] = {}
    for line in output.splitlines():
        match = re.match(r"^Inst\s+(\S+)(?:\s+\[[^]]+\])?\s+\((\S+)", line)
        if match is None:
            continue
        name, version = match.groups()
        if PACKAGE_NAME_RE.fullmatch(name) is None or PACKAGE_VERSION_RE.fullmatch(version) is None:
            raise fail("APT simulation returned malformed package data")
        existing = resolved.setdefault(name, version)
        if existing != version:
            raise fail("APT simulation returned conflicting package versions")
    if not resolved:
        raise fail("APT simulation did not resolve any package archives")
    return tuple(
        PackageVersion(name=name, version=version) for name, version in sorted(resolved.items())
    )


def apt_environment(stage: Path) -> dict[str, str]:
    """Keep APT's possible user cache writes inside the private staging directory."""
    temporary_directory = stage / "tmp"
    xdg_cache = stage / "xdg-cache"
    apt_cache = stage / "apt-cache"
    ensure_private_directory(temporary_directory, "private command temporary directory")
    ensure_private_directory(xdg_cache, "private command cache directory")
    ensure_private_directory(apt_cache, "private APT cache directory")
    ensure_private_directory(apt_cache / "archives", "private APT archive cache")
    environment = os.environ.copy()
    environment.update(
        {
            "HOME": str(stage),
            "XDG_CACHE_HOME": str(xdg_cache),
            "TMPDIR": str(temporary_directory),
            "LC_ALL": "C",
            "LANG": "C",
        }
    )
    return environment


def apt_cache_options(stage: Path) -> list[str]:
    """Keep APT caches private while continuing to read configured system sources."""
    cache = stage / "apt-cache"
    return [
        "-o",
        f"Dir::Cache={cache}",
        "-o",
        "Dir::Cache::pkgcache=",
        "-o",
        "Dir::Cache::srcpkgcache=",
        "-o",
        "APT::Get::AllowUnauthenticated=false",
    ]


def resolve_packages(seeds: Sequence[str], stage: Path) -> tuple[PackageVersion, ...]:
    """Resolve package closure through APT's non-mutating simulation mode."""
    if not seeds:
        return ()
    completed = checked_run(
        [
            "apt-get",
            *apt_cache_options(stage),
            "--simulate",
            "--no-install-recommends",
            "install",
            *seeds,
        ],
        cwd=stage,
        env=apt_environment(stage),
    )
    return parse_simulated_packages(completed.stdout)


def download_and_extract(packages: Sequence[PackageVersion], stage: Path) -> Path:
    """Download exact archives into staging and extract them with dpkg-deb only."""
    archives = stage / "debs"
    extracted_root = stage / "local-libs" / "root"
    ensure_private_directory(archives, "package archive staging directory")
    ensure_private_directory(extracted_root, "package extraction directory")
    environment = apt_environment(stage)
    if packages:
        package_specs = [f"{package.name}={package.version}" for package in packages]
        checked_run(
            [
                "apt",
                *apt_cache_options(stage),
                "download",
                *package_specs,
            ],
            cwd=archives,
            env=environment,
        )
    debs = sorted(archives.glob("*.deb"))
    if len(debs) != len(packages):
        raise fail("apt download did not create exactly one archive for every resolved package")
    for archive in debs:
        if archive.is_symlink() or not archive.is_file() or not is_within(archive, archives):
            raise fail("APT produced an unsafe package archive path")
        checked_run(
            ["dpkg-deb", "-x", str(archive), str(extracted_root)],
            cwd=stage,
            env=environment,
        )
    # Validate once after every archive is extracted: nothing uses the tree until
    # this passes, so a single full scan keeps the same safety at O(files) cost.
    validate_extracted_root(extracted_root)
    for archive in debs:
        archive.unlink()
    if any(archives.iterdir()):
        raise fail("unexpected files remained in package archive staging")
    return extracted_root


def validate_extracted_root(extracted_root: Path) -> None:
    """Reject symlink escapes and extracted host loader or libc replacements."""
    require_regular_directory(extracted_root, "extracted Playwright runtime root")
    if not extracted_root.exists():
        raise fail("package extraction did not create a runtime root")
    for entry in extracted_root.rglob("*"):
        if not is_within(entry, extracted_root):
            raise fail("extracted package path escaped the private runtime root")
        if entry.is_symlink():
            target = entry.readlink()
            if target.is_absolute() or not is_within(entry.parent / target, extracted_root):
                raise fail(
                    "extracted package contains a symlink that escapes the private runtime root"
                )
        name = entry.name
        relative = entry.relative_to(extracted_root)
        in_library_tree = relative.parts[0] in {"lib", "lib64"} or relative.parts[:2] in {
            ("usr", "lib"),
            ("usr", "lib64"),
        }
        is_host_runtime = name.startswith("ld-linux") or (
            re.fullmatch(r"libc\.so(?:\.\d+)*", name) is not None
        )
        if in_library_tree and is_host_runtime:
            raise fail("refusing an extracted host loader or libc overlay")


def write_manifest(path: Path, manifest: CacheManifest) -> None:
    """Write one deterministic private manifest after extraction validation succeeds."""
    content = f"{json.dumps(manifest.to_json(), indent=2, sort_keys=True)}\n"
    path.write_text(content, encoding="utf-8")
    path.chmod(0o600)


def regular_file(path: Path) -> bool:
    """Return whether a path is a non-symlink regular file."""
    try:
        return stat.S_ISREG(path.lstat().st_mode)
    except OSError:
        return False


def load_manifest(path: Path) -> CacheManifest | None:
    """Load a manifest only when its JSON has the exact expected schema and types."""
    if not regular_file(path):
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or raw.get("schema") != MANIFEST_SCHEMA:
        return None
    host = raw.get("host")
    engines = raw.get("engines")
    packages = raw.get("packages")
    version = raw.get("playwright_version")
    if (
        not isinstance(host, dict)
        or not isinstance(host.get("distribution"), str)
        or not isinstance(host.get("version"), str)
        or not isinstance(host.get("architecture"), str)
        or not isinstance(version, str)
        or not isinstance(engines, list)
        or not all(isinstance(engine, str) for engine in engines)
        or not isinstance(packages, list)
    ):
        return None
    parsed_packages: list[PackageVersion] = []
    for package in packages:
        if (
            not isinstance(package, dict)
            or not isinstance(package.get("name"), str)
            or not isinstance(package.get("version"), str)
            or PACKAGE_NAME_RE.fullmatch(package["name"]) is None
            or PACKAGE_VERSION_RE.fullmatch(package["version"]) is None
        ):
            return None
        parsed_packages.append(PackageVersion(name=package["name"], version=package["version"]))
    return CacheManifest(
        schema=MANIFEST_SCHEMA,
        host=HostPlatform(
            distribution=host["distribution"],
            version=host["version"],
            architecture=host["architecture"],
        ),
        playwright_version=version,
        engines=tuple(engines),
        packages=tuple(parsed_packages),
    )


def recorded_engines(paths: RuntimePaths) -> tuple[str, ...]:
    """Return the supported engines an existing manifest already covers."""
    manifest = load_manifest(paths.manifest)
    if manifest is None:
        return ()
    return tuple(engine for engine in manifest.engines if engine in ENGINES)


def requested_engines(paths: RuntimePaths, engines: Sequence[str]) -> tuple[str, ...]:
    """Return the union of the newly requested engines and the recorded engine set.

    Chromium and WebKit are installed by separate Make targets, so preparing one
    must extend rather than replace the closure the other already needs. Taking the
    union here means the manifest's engine set only ever grows, and the resolved
    package closure is always the union that every prepared engine requires.
    """
    return tuple(sorted({*engines, *recorded_engines(paths)}))


def cache_matches(paths: RuntimePaths, expected: CacheManifest) -> bool:
    """Return whether a complete, non-symlinked active cache matches exactly."""
    try:
        require_regular_directory(paths.local_libraries, "local library cache")
        require_regular_directory(paths.extracted_root, "extracted Playwright runtime root")
        validate_extracted_root(paths.extracted_root)
    except RuntimeSetupError:
        return False
    return paths.extracted_root.is_dir() and load_manifest(paths.manifest) == expected


def exchange_directories(left: Path, right: Path) -> None:
    """Atomically swap two existing directories through Linux renameat2."""
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise fail(
            "this Linux host lacks renameat2, so the runtime cache cannot be published atomically"
        )
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        AT_FDCWD,
        os.fsencode(left),
        AT_FDCWD,
        os.fsencode(right),
        RENAME_EXCHANGE,
    )
    if result != 0:
        error_number = ctypes.get_errno()
        detail = os.strerror(error_number)
        raise fail(f"cannot atomically publish the local Playwright runtime: {detail}")


def publish_local_libraries(paths: RuntimePaths, staged_libraries: Path) -> None:
    """Publish a validated cache atomically without first deleting the active cache."""
    require_regular_directory(staged_libraries, "staged local library cache")
    if not is_within(staged_libraries, paths.cache_root):
        raise fail("staged runtime must remain below the repository-local cache")
    require_regular_directory(paths.local_libraries, "local library cache")
    if paths.local_libraries.exists():
        exchange_directories(staged_libraries, paths.local_libraries)
        shutil.rmtree(staged_libraries)
    else:
        staged_libraries.replace(paths.local_libraries)


def expected_manifest(
    paths: RuntimePaths,
    stage: Path,
    engines: Sequence[str],
) -> CacheManifest:
    """Compute all inputs whose changes invalidate a local runtime cache."""
    host = current_host()
    packages = resolve_packages(dependency_seeds(paths, engines), stage)
    return CacheManifest(
        schema=MANIFEST_SCHEMA,
        host=host,
        playwright_version=playwright_version(paths),
        engines=tuple(engines),
        packages=packages,
    )


def prepare(paths: RuntimePaths, engines: Sequence[str]) -> None:
    """Build or reuse a verified local runtime without changing system packages."""
    ensure_cache_root(paths)
    ensure_runtime_state(paths)
    with cache_lock(paths):
        remove_stale_staging(paths)
        prepare_locked(paths, engines)


def prepare_locked(paths: RuntimePaths, engines: Sequence[str]) -> None:
    """Build the cache while the caller holds the repository-local setup lock."""
    stage = Path(tempfile.mkdtemp(prefix=".stage-", dir=paths.cache_root))
    stage.chmod(0o700)
    try:
        manifest = expected_manifest(paths, stage, requested_engines(paths, engines))
        if cache_matches(paths, manifest):
            patch_webkit_launchers(paths)
            print("Playwright local runtime is current.")
            return
        extracted_root = download_and_extract(manifest.packages, stage)
        validate_extracted_root(extracted_root)
        staged_libraries = stage / "local-libs"
        write_manifest(staged_libraries / "manifest.json", manifest)
        publish_local_libraries(paths, staged_libraries)
        patch_webkit_launchers(paths)
        print(f"Prepared repository-local Playwright runtime for {', '.join(manifest.engines)}.")
    finally:
        # ignore_errors keeps a cleanup problem from masking the real setup error
        # this finally may be unwinding. Anything left behind is swept by
        # remove_stale_staging on the next preparation.
        shutil.rmtree(stage, ignore_errors=True)


def discovered_directories(root: Path) -> dict[str, list[Path]]:
    """Discover only extracted locations relevant to dynamic libraries and browser data."""
    found: dict[str, list[Path]] = {
        "libraries": [],
        "path": [],
        "data": [],
        "typelibs": [],
        "gstreamer": [],
        "schemas": [],
    }
    if not root.is_dir():
        return found
    directories = (path for path in root.rglob("*") if path.is_dir() and not path.is_symlink())
    for directory in sorted(directories, key=str):
        relative = directory.relative_to(root)
        if relative in {Path("bin"), Path("usr/bin")}:
            found["path"].append(directory)
        if relative in {Path("share"), Path("usr/share"), Path("usr/local/share")}:
            found["data"].append(directory)
        if directory.name == "girepository-1.0":
            found["typelibs"].append(directory)
        if directory.name == "gstreamer-1.0":
            found["gstreamer"].append(directory)
        if relative.parts[-2:] == ("glib-2.0", "schemas"):
            found["schemas"].append(directory)
        contains_shared_library = any(
            child.name.startswith("lib") and ".so" in child.name
            for child in directory.iterdir()
            if child.is_file()
        )
        parts = relative.parts
        is_loader_directory = (
            bool(parts) and parts[0] in {"lib", "lib64"} and len(parts) <= 2
        ) or (
            len(parts) >= 2 and parts[:2] in {("usr", "lib"), ("usr", "lib64")} and len(parts) <= 3
        )
        if contains_shared_library and is_loader_directory:
            found["libraries"].append(directory)
    return found


def prepend_environment(environment: dict[str, str], name: str, values: Sequence[Path]) -> None:
    """Prepend discovered private directories and retain the caller's existing value."""
    private_values = [str(value) for value in values]
    if not private_values:
        return
    existing = environment.get(name, "")
    environment[name] = os.pathsep.join([*private_values, *([existing] if existing else [])])


def runtime_environment(
    paths: RuntimePaths,
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Build the inherited environment used by wrapped browser commands and probes."""
    require_ready(paths)
    environment = dict(os.environ if base is None else base)
    discovered = discovered_directories(paths.extracted_root)
    ensure_runtime_state(paths)
    environment["PLAYWRIGHT_BROWSERS_PATH"] = str(paths.browser_root)
    environment["HOME"] = str(paths.runtime_home)
    environment["XDG_CACHE_HOME"] = str(paths.runtime_cache)
    environment["XDG_CONFIG_HOME"] = str(paths.runtime_config)
    environment["XDG_RUNTIME_DIR"] = str(paths.runtime_run)
    environment["TMPDIR"] = str(paths.runtime_tmp)
    environment["npm_config_cache"] = str(paths.runtime_cache / "npm")
    # Playwright's dlopen preflight consults only the system ldconfig cache and
    # cannot see repository-local libraries. The real engine probe below remains
    # authoritative for this wrapper.
    environment["PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS"] = "1"
    prepend_environment(environment, "LD_LIBRARY_PATH", discovered["libraries"])
    prepend_environment(environment, "PATH", discovered["path"])
    prepend_environment(environment, "XDG_DATA_DIRS", discovered["data"])
    prepend_environment(environment, "GI_TYPELIB_PATH", discovered["typelibs"])
    prepend_environment(environment, "GST_PLUGIN_PATH_1_0", discovered["gstreamer"])
    prepend_environment(environment, "GSETTINGS_SCHEMA_DIR", discovered["schemas"])
    return environment


def browser_cache_ready(paths: RuntimePaths, engines: Sequence[str]) -> bool:
    """Require every prepared engine in the shared browser cache before a wrapped run."""
    # browser_root is the user-owned shared cache (for example ~/.cache/ms-playwright),
    # which is only read and launcher-patched in place and never deleted here, so a
    # symlinked cache (a common redirect to another disk) is accepted; is_dir follows it.
    if not paths.browser_root.is_dir():
        return False
    for engine in engines:
        engine_directories = paths.browser_root.glob(f"{engine}-*")
        if not any(path.is_dir() and not path.is_symlink() for path in engine_directories):
            return False
    if "webkit" not in engines:
        return True
    launchers = webkit_launchers(paths)
    return bool(launchers) and all(webkit_launcher_is_patched(launcher) for launcher in launchers)


def webkit_launchers(paths: RuntimePaths) -> list[Path]:
    """Return real WebKit bundle launchers contained by the shared browser cache."""
    launchers: list[Path] = []
    if not paths.browser_root.is_dir():
        return launchers
    for webkit_root in sorted(paths.browser_root.glob("webkit-*")):
        if webkit_root.is_symlink() or not webkit_root.is_dir():
            continue
        for launcher in sorted(webkit_root.glob("minibrowser-*/MiniBrowser")):
            if (
                regular_file(launcher)
                and os.access(launcher, os.X_OK)
                and is_within(launcher, paths.browser_root)
            ):
                launchers.append(launcher)
    return launchers


def webkit_launcher_is_patched(launcher: Path) -> bool:
    """Return whether a WebKit launcher preserves the inherited private library path."""
    try:
        content = launcher.read_text(encoding="utf-8")
    except OSError:
        return False
    return WEBKIT_LAUNCHER_LOCAL_LD_LINE in content


def patch_webkit_launchers(paths: RuntimePaths) -> None:
    """Patch shared WebKit wrappers to retain the repository-local library path."""
    for launcher in webkit_launchers(paths):
        content = launcher.read_text(encoding="utf-8")
        if WEBKIT_LAUNCHER_LOCAL_LD_LINE in content:
            continue
        if content.count(WEBKIT_LAUNCHER_LD_LINE) != 1:
            raise fail(f"unexpected shared WebKit launcher format: {launcher}")
        updated = content.replace(WEBKIT_LAUNCHER_LD_LINE, WEBKIT_LAUNCHER_LOCAL_LD_LINE)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".MiniBrowser.",
            dir=launcher.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as temporary_file:
                temporary_file.write(updated)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            temporary.chmod(stat.S_IMODE(launcher.stat().st_mode))
            temporary.replace(launcher)
        finally:
            temporary.unlink(missing_ok=True)


def require_ready(paths: RuntimePaths) -> tuple[str, ...]:
    """Refuse fallback to global browsers or an unverified local library cache."""
    require_regular_directory(paths.cache_root, "Playwright cache root")
    require_regular_directory(paths.local_libraries, "local library cache")
    require_regular_directory(paths.extracted_root, "extracted Playwright runtime root")
    # Establish that a cache exists at all before validating its contents, so an
    # untouched repository is told to run setup instead of being handed a
    # confusing extraction diagnostic.
    manifest = load_manifest(paths.manifest)
    if manifest is None or not paths.extracted_root.is_dir():
        raise fail("local Playwright runtime is not prepared; run make setup-playwright-local")
    validate_extracted_root(paths.extracted_root)
    if (
        manifest.host != current_host()
        or manifest.playwright_version != playwright_version(paths)
        or not manifest.engines
        or not set(manifest.engines).issubset(ENGINES)
    ):
        raise fail("local Playwright runtime is stale; run make setup-playwright-local")
    if not browser_cache_ready(paths, manifest.engines):
        raise fail("local Playwright browsers are not prepared; run make setup-playwright-local")
    return manifest.engines


def run_in_runtime(
    paths: RuntimePaths,
    command: Sequence[str],
    base: Mapping[str, str] | None = None,
) -> int:
    """Run an already-prepared browser command and preserve its exit status."""
    if not command:
        raise fail("playwright-local run requires a command after --")
    try:
        completed = subprocess.run(
            list(command),
            cwd=paths.repo_root,
            env=runtime_environment(paths, base),
            check=False,
        )
    except OSError as error:
        raise fail(f"cannot run wrapped command {command[0]}: {error}") from error
    return completed.returncode if completed.returncode >= 0 else 128 - completed.returncode


def probe(paths: RuntimePaths) -> int:
    """Launch and close every prepared engine with the private runtime.

    The probe program imports Playwright, so it reuses the running interpreter
    rather than resolving ``.venv/bin/python``. Every entry point is the Make
    target, which already runs this module under the virtual-environment
    interpreter, and that path is a symlink to the system interpreter, so the
    containment guard used for the Playwright CLI cannot validate it.
    """
    engines = require_ready(paths)
    return run_in_runtime(paths, [sys.executable, "-c", PROBE_PROGRAM, *engines])


def status(paths: RuntimePaths) -> int:
    """Report cache facts without downloading packages or inspecting user data."""
    try:
        require_ready(paths)
    except RuntimeSetupError as error:
        print(f"NOT READY: {error}")
        return 1
    manifest = load_manifest(paths.manifest)
    assert manifest is not None
    print("READY: repository-local Playwright runtime")
    print(f"  cache: {paths.cache_root}")
    print(f"  browsers: {paths.browser_root}")
    print(f"  Playwright: {manifest.playwright_version}")
    host = manifest.host
    print(f"  host: {host.distribution} {host.version} ({host.architecture})")
    print(f"  packages: {len(manifest.packages)}")
    print(f"  engines: {', '.join(manifest.engines)}")
    return 0


def clean(paths: RuntimePaths) -> None:
    """Remove only this repository's private runtime cache, keeping shared browsers.

    The shared browser cache lives outside ``.playwright`` and is reused by other
    projects, so it is deliberately left in place.
    """
    require_regular_directory(paths.cache_root, "Playwright cache root")
    if paths.cache_root.exists():
        shutil.rmtree(paths.cache_root)
    print("Removed repository-local Playwright cache (shared browsers kept).")


def parse_args(arguments: Sequence[str]) -> argparse.Namespace:
    """Parse the small command surface exposed through Make targets."""
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    prepare_parser = subparsers.add_parser("prepare", help="prepare or reuse private libraries")
    prepare_parser.add_argument(
        "--engine",
        action="append",
        dest="engines",
        choices=ENGINES,
        required=True,
        help="browser engine to cover; repeat to request several at once",
    )
    subparsers.add_parser("status", help="show private cache status")
    run_parser = subparsers.add_parser("run", help="run a command in the private runtime")
    run_parser.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    subparsers.add_parser("probe", help="launch every prepared Playwright engine")
    subparsers.add_parser("clean", help="remove only the private cache")
    parsed = parser.parse_args(arguments)
    # argparse.REMAINDER keeps the "--" separator the Make wrapper passes before
    # the wrapped command, so drop one leading separator before it reaches exec.
    if parsed.action == "run" and parsed.command and parsed.command[0] == "--":
        parsed.command = parsed.command[1:]
    return parsed


def main(arguments: Sequence[str] | None = None) -> int:
    """Execute one action, keeping expected setup errors concise for Make users."""
    args = parse_args(sys.argv[1:] if arguments is None else arguments)
    paths = RuntimePaths.from_repo(Path(__file__).parents[2])
    try:
        if args.action == "prepare":
            prepare(paths, args.engines)
            return 0
        if args.action == "status":
            return status(paths)
        if args.action == "run":
            return run_in_runtime(paths, args.command)
        if args.action == "probe":
            return probe(paths)
        if args.action == "clean":
            clean(paths)
            return 0
    except RuntimeSetupError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    raise AssertionError(f"unhandled action: {args.action}")


if __name__ == "__main__":
    raise SystemExit(main())
