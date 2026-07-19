from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import scripts.ci.app_hashes as app_hashes


def write_json(path: Path, payload: object) -> None:
    """Write one JSON fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_app(root: Path, slug: str) -> None:
    """Create one browser-tested app fixture."""
    app_dir = root / "apps" / slug / "js"
    app_dir.mkdir(parents=True)
    (app_dir.parent / "index.html").write_text("<html></html>\n", encoding="utf-8")
    (app_dir / "app.js").write_text("export {};\n", encoding="utf-8")


def make_repo(root: Path) -> None:
    """Create common app-hash inputs."""
    (root / "css").mkdir()
    (root / "css" / "style.css").write_text("body {}\n", encoding="utf-8")
    modules = root / "js" / "modules"
    modules.mkdir(parents=True)
    (modules / "app-shell.js").write_text("export {};\n", encoding="utf-8")
    for path in app_hashes.SHARED_APP_BROWSER_TEST_PATHS:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("pass\n", encoding="utf-8")
    (root / "uv.lock").write_text("lock\n", encoding="utf-8")
    (root / "package-lock.json").write_text("{}\n", encoding="utf-8")


def git_records(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
    """Return deterministic fake index records for requested pathspecs."""
    records: list[str] = []
    for path in command[4:]:
        filename = path.rstrip("/")
        if filename.startswith("apps/"):
            records.append(f"100644 {filename.replace('/', '')[:8]:0<8} 0\t{filename}/js/app.js")
        else:
            records.append(f"100644 {filename.replace('/', '')[:8]:0<8} 0\t{filename}")
    return subprocess.CompletedProcess([], 0, stdout="\n".join(records))


def test_app_input_hashes_include_sorted_common_and_app_records(tmp_path: Path) -> None:
    """Input hashes are stable per app and change with a tracked blob record."""
    make_repo(tmp_path)
    make_app(tmp_path, "alpha")
    make_app(tmp_path, "beta")

    hashes = app_hashes.app_input_hashes(
        ["beta", "alpha", "alpha"], repo_root=tmp_path, run_git_fn=git_records
    )

    assert sorted(hashes) == ["alpha", "beta"]
    assert len(hashes["alpha"]) == 64
    assert hashes["alpha"] != hashes["beta"]


def test_ledger_reader_and_writer_validate_paths_and_shape(tmp_path: Path) -> None:
    """Ledger I/O gives clear errors and writes deterministic supported payloads."""
    ledger = tmp_path / "ledger.json"
    with pytest.raises(ValueError, match="Verification ledger is missing"):
        app_hashes.read_ledger(ledger)

    app_hashes._write_ledger(ledger, {"beta": "b", "alpha": "a"})
    assert app_hashes.read_ledger(ledger) == {"alpha": "a", "beta": "b"}

    write_json(ledger, {"version": 99, "hashes": {}})
    with pytest.raises(ValueError, match="unsupported version"):
        app_hashes.read_ledger(ledger)

    write_json(ledger, {"version": app_hashes.LEDGER_VERSION, "hashes": []})
    with pytest.raises(ValueError, match="map strings"):
        app_hashes.read_ledger(ledger)


def test_apply_memoization_removes_only_matching_browser_apps(tmp_path: Path) -> None:
    """Matching main-green app inputs disappear from browser shard assignments."""
    make_repo(tmp_path)
    make_app(tmp_path, "alpha")
    make_app(tmp_path, "beta")
    ledger = tmp_path / "ledger.json"
    app_hashes._write_ledger(ledger, {"alpha": "green", "beta": "stale"})
    plan = {"browser_scope": "all", "changed_slugs": []}

    result = app_hashes.apply_memoization(
        plan,
        ledger_path=ledger,
        repo_root=tmp_path,
        hash_inputs_fn=lambda _slugs, **_kwargs: {"alpha": "green", "beta": "new"},
    )

    assert result["verified_browser_slugs"] == ["alpha", "beta"]
    assert result["browser_slugs"] == ["beta"]
    assert result["memoized_browser_slugs"] == ["alpha"]
    assert result["memoization_available"] is True


def test_apply_memoization_fails_open_without_ledger_or_hashes(tmp_path: Path) -> None:
    """Missing ledgers and failed hash calculation retain every browser app."""
    make_repo(tmp_path)
    make_app(tmp_path, "alpha")
    plan = {"browser_scope": "all", "changed_slugs": []}

    missing = app_hashes.apply_memoization(
        plan, ledger_path=tmp_path / "missing.json", repo_root=tmp_path
    )
    failed = app_hashes.apply_memoization(
        plan,
        ledger_path=tmp_path / "missing.json",
        repo_root=tmp_path,
        hash_inputs_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("hash failed")),
    )

    assert missing["memoization_available"] is False
    assert "browser_slugs" not in missing
    assert failed["verified_browser_slugs"] == ["alpha"]


def test_update_ledger_merges_verified_hashes_and_allows_first_write(tmp_path: Path) -> None:
    """Only verified plan slugs are hashed and merged into a new ledger."""
    ledger = tmp_path / "nested" / "ledger.json"
    result = app_hashes.update_ledger(
        {"verified_browser_slugs": ["beta", "alpha"]},
        ledger_path=ledger,
        repo_root=tmp_path,
        hash_inputs_fn=lambda slugs, **_kwargs: {slug: f"{slug}-hash" for slug in slugs},
    )

    assert result == {"alpha": "alpha-hash", "beta": "beta-hash"}
    assert app_hashes.read_ledger(ledger) == result


def test_hash_helpers_reject_invalid_git_records_and_symlinks(tmp_path: Path) -> None:
    """Git parser and filesystem guards reject unsafe inputs before hashing."""
    with pytest.raises(ValueError, match="invalid staged-file"):
        app_hashes._parse_ls_files("bad")
    with pytest.raises(ValueError, match="symlinked tracked"):
        app_hashes._parse_ls_files("120000 deadbeef 0\tapps/alpha")
    with pytest.raises(ValueError, match="non-stage-zero"):
        app_hashes._parse_ls_files("100644 deadbeef 1\tapps/alpha")

    target = tmp_path / "target.json"
    target.write_text("{}", encoding="utf-8")
    linked = tmp_path / "ledger.json"
    linked.symlink_to(target)
    with pytest.raises(ValueError, match="must not be a symlink"):
        app_hashes.read_ledger(linked)


def test_hash_helpers_reject_invalid_plans_and_symlinked_parents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Plan validation and every hash writer reject malformed and unsafe paths."""
    object_path = tmp_path / "object.json"
    write_json(object_path, [])
    with pytest.raises(ValueError, match="Impact plan must be a JSON object"):
        app_hashes.read_plan(object_path)
    with pytest.raises(ValueError, match="browser_scope"):
        app_hashes.apply_memoization(
            {"browser_scope": "bad", "changed_slugs": []}, ledger_path=tmp_path / "ledger"
        )
    with pytest.raises(ValueError, match="changed_slugs"):
        app_hashes.apply_memoization(
            {"browser_scope": "changed", "changed_slugs": "alpha"},
            ledger_path=tmp_path / "ledger",
        )

    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ValueError, match="Verification ledger output"):
        app_hashes._write_ledger(linked_parent / "ledger.json", {})
    with pytest.raises(ValueError, match="Impact plan output"):
        app_hashes._write_plan(linked_parent / "plan.json", {})

    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ValueError, match="Repository root"):
        app_hashes.git_blob_hashes([], repo_root=linked_root)
    with pytest.raises(ValueError, match="Repository root"):
        app_hashes.app_input_hashes([], repo_root=linked_root)

    make_repo(tmp_path)
    make_app(tmp_path, "alpha")
    app_dir = tmp_path / "apps" / "linked-app"
    app_dir.symlink_to(tmp_path / "apps" / "alpha", target_is_directory=True)
    monkeypatch.setattr(app_hashes, "reject_symlinks", lambda _path: None)
    with pytest.raises(ValueError, match="App input directory"):
        app_hashes.app_input_hashes(["linked-app"], repo_root=tmp_path, run_git_fn=git_records)

    linked_apps_root = tmp_path / "linked-apps-root"
    linked_apps_root.symlink_to(tmp_path / "apps", target_is_directory=True)
    second_root = tmp_path / "second-root"
    second_root.mkdir()
    (second_root / "apps").symlink_to(linked_apps_root, target_is_directory=True)
    with pytest.raises(ValueError, match="App root"):
        app_hashes.app_input_hashes([], repo_root=second_root)

    empty_root = tmp_path / "empty-root"
    empty_root.mkdir()
    assert app_hashes.app_input_hashes([], repo_root=empty_root) == {}


def test_update_ledger_reraises_invalid_ledger_errors(tmp_path: Path) -> None:
    """Only a missing ledger is fail-open for a main ledger update."""
    ledger = tmp_path / "ledger.json"
    write_json(ledger, {"version": 99, "hashes": {}})
    with pytest.raises(ValueError, match="unsupported version"):
        app_hashes.update_ledger(
            {"verified_browser_slugs": []}, ledger_path=ledger, repo_root=tmp_path
        )


def test_main_dispatches_makefile_facing_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CLI commands apply and write ledgers through validated plan files."""
    make_repo(tmp_path)
    make_app(tmp_path, "alpha")
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, {"browser_scope": "none", "changed_slugs": []})
    ledger = tmp_path / "ledger.json"
    output = tmp_path / "output.json"
    monkeypatch.chdir(tmp_path)

    assert (
        app_hashes.main(
            [
                "apply-ledger",
                "--plan",
                str(plan_path),
                "--ledger",
                str(ledger),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    write_json(output, {"verified_browser_slugs": []})
    assert app_hashes.main(["update-ledger", "--plan", str(output), "--ledger", str(ledger)]) == 0
