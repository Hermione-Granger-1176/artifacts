from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import scripts.ci.app_shards as app_shards


def write_json(path: Path, payload: object) -> None:
    """Write one JSON test fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_app(apps_root: Path, slug: str, *, browser: bool = False) -> None:
    """Create one minimal artifact directory."""
    app_dir = apps_root / slug
    app_dir.mkdir(parents=True)
    (app_dir / "index.html").write_text("<html></html>\n", encoding="utf-8")
    if browser:
        (app_dir / "js").mkdir()
        (app_dir / "js" / "app.js").write_text("export {};\n", encoding="utf-8")


def base_plan(
    *, browser_scope: str = "changed", thumbnail_scope: str = "changed"
) -> dict[str, object]:
    """Return a valid small impact plan."""
    return {
        "browser_scope": browser_scope,
        "thumbnail_scope": thumbnail_scope,
        "changed_slugs": ["alpha", "beta"],
        "thumbnail_slugs": ["alpha", "gamma"],
    }


def test_browser_app_slugs_and_add_shards_are_deterministic(tmp_path: Path) -> None:
    """Test shard planning sorts and independently assigns browser and thumbnails."""
    apps_root = tmp_path / "apps"
    make_app(apps_root, "beta", browser=True)
    make_app(apps_root, "alpha", browser=True)
    make_app(apps_root, "gamma")

    assert app_shards.browser_app_slugs(apps_root) == ["alpha", "beta"]
    plan = app_shards.add_shards(base_plan(), apps_root=apps_root)

    assert plan["shards"] == [
        {
            "index": 0,
            "browser_slugs": ["alpha", "beta"],
            "thumbnail_slugs": ["alpha", "gamma"],
        }
    ]
    assert app_shards.compact_matrix(plan) == '{"include":[{"shard":0}]}'
    assert app_shards.shard_count(plan) == 1


def test_add_shards_resolves_all_and_none_scopes(tmp_path: Path) -> None:
    """Test all-app browser scope remains independent from no thumbnail scope."""
    apps_root = tmp_path / "apps"
    make_app(apps_root, "alpha", browser=True)
    make_app(apps_root, "beta")

    plan = app_shards.add_shards(
        base_plan(browser_scope="all", thumbnail_scope="none"), apps_root=apps_root
    )

    assert plan["shards"] == [{"index": 0, "browser_slugs": ["alpha"], "thumbnail_slugs": []}]
    empty = app_shards.add_shards(
        base_plan(browser_scope="none", thumbnail_scope="none"), apps_root=apps_root
    )
    assert empty["shards"] == []
    assert app_shards.compact_matrix(empty) == '{"include":[]}'


def test_add_shards_honors_memoized_browser_slug_list(tmp_path: Path) -> None:
    """Explicit browser slugs keep memoized apps out of browser shard manifests."""
    apps_root = tmp_path / "apps"
    make_app(apps_root, "alpha", browser=True)
    make_app(apps_root, "beta", browser=True)

    plan = app_shards.add_shards(
        {**base_plan(browser_scope="all", thumbnail_scope="none"), "browser_slugs": ["beta"]},
        apps_root=apps_root,
    )

    assert plan["shards"] == [{"index": 0, "browser_slugs": ["beta"], "thumbnail_slugs": []}]


def test_add_shards_obeys_size_and_matrix_limits() -> None:
    """Test thousands of synthetic app slugs fill bounded deterministic shards."""
    all_apps = [f"app-{index:04d}" for index in range(app_shards.SHARD_SIZE * 2 + 1)]
    plan = {
        "browser_scope": "none",
        "thumbnail_scope": "changed",
        "changed_slugs": [],
        "thumbnail_slugs": list(reversed(all_apps)),
    }
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_shards, "discover_app_slugs", lambda _root: all_apps)
    monkeypatch.setattr(app_shards, "browser_app_slugs", lambda _root, _slugs=None: [])
    try:
        result = app_shards.add_shards(plan)
    finally:
        monkeypatch.undo()

    shards = result["shards"]
    assert isinstance(shards, list)
    assert [len(shard["thumbnail_slugs"]) for shard in shards] == [20, 20, 1]
    assert shards[0]["thumbnail_slugs"][0] == "app-0000"

    oversized = {
        **plan,
        "thumbnail_slugs": [f"app-{index:04d}" for index in range(2561)],
    }
    monkeypatch.setattr(
        app_shards, "discover_app_slugs", lambda _root: oversized["thumbnail_slugs"]
    )
    monkeypatch.setattr(app_shards, "browser_app_slugs", lambda _root, _slugs=None: [])
    try:
        with pytest.raises(ValueError, match="shard capacity"):
            app_shards.add_shards(oversized)
    finally:
        monkeypatch.undo()


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "browser_scope"),
        (
            {
                "browser_scope": "invalid",
                "thumbnail_scope": "none",
                "changed_slugs": [],
                "thumbnail_slugs": [],
            },
            "browser_scope",
        ),
        (
            {
                "browser_scope": "none",
                "thumbnail_scope": "none",
                "changed_slugs": "alpha",
                "thumbnail_slugs": [],
            },
            "changed_slugs",
        ),
    ],
)
def test_add_shards_rejects_malformed_impact_fields(
    tmp_path: Path, payload: dict[str, object], message: str
) -> None:
    """Test planning rejects malformed impact-plan fields."""
    with pytest.raises(ValueError, match=message):
        app_shards.add_shards(payload, apps_root=tmp_path / "apps")


@pytest.mark.parametrize(
    ("shards", "message"),
    [
        ("bad", "shards"),
        (["bad"], "shard"),
        ([{"index": -1, "browser_slugs": [], "thumbnail_slugs": []}], "index"),
        ([{"index": 1, "browser_slugs": [], "thumbnail_slugs": []}], "contiguous"),
        ([{"index": 0, "browser_slugs": "bad", "thumbnail_slugs": []}], "browser_slugs"),
    ],
)
def test_compact_matrix_rejects_malformed_shards(shards: object, message: str) -> None:
    """Test compact workflow matrices validate every persisted shard shape."""
    with pytest.raises(ValueError, match=message):
        app_shards.compact_matrix({"shards": shards})


def test_compact_matrix_rejects_too_many_shards() -> None:
    """Test compact matrix output rejects GitHub Actions matrix overflow."""
    shards = [
        {"index": index, "browser_slugs": [], "thumbnail_slugs": []}
        for index in range(app_shards.MAX_SHARD_COUNT + 1)
    ]
    with pytest.raises(ValueError, match="matrix limit"):
        app_shards.compact_matrix({"shards": shards})


def test_plan_and_manifest_readers_validate_json(tmp_path: Path) -> None:
    """Test persisted plan and manifest readers reject invalid JSON shapes."""
    object_path = tmp_path / "object.json"
    write_json(object_path, [])
    with pytest.raises(ValueError, match="JSON object"):
        app_shards.read_plan(object_path)

    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, {"index": -1, "browser_slugs": [], "thumbnail_slugs": []})
    with pytest.raises(ValueError, match="index"):
        app_shards.read_shard_manifest(manifest_path)

    write_json(manifest_path, {"index": 0, "browser_slugs": [], "thumbnail_slugs": "bad"})
    with pytest.raises(ValueError, match="thumbnail_slugs"):
        app_shards.read_shard_manifest(manifest_path)

    with pytest.raises(ValueError, match="Impact plan is missing"):
        app_shards.read_plan(tmp_path / "missing.json")

    linked = tmp_path / "linked.json"
    linked.symlink_to(manifest_path)
    with pytest.raises(ValueError, match="must not be a symlink"):
        app_shards.read_plan(linked)


def test_write_and_read_shard_manifest_selects_requested_shard(tmp_path: Path) -> None:
    """Test standalone manifests carry exactly the selected plan assignment."""
    plan_path = tmp_path / "plan.json"
    write_json(
        plan_path,
        {
            "shards": [
                {"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]},
                {"index": 1, "browser_slugs": ["beta"], "thumbnail_slugs": []},
            ]
        },
    )
    manifest_path = tmp_path / "nested" / "manifest.json"
    app_shards.write_shard_manifest(plan_path, shard_index=1, output_path=manifest_path)

    assert app_shards.read_shard_manifest(manifest_path) == {
        "index": 1,
        "browser_slugs": ["beta"],
        "thumbnail_slugs": [],
    }
    with pytest.raises(ValueError, match="not present"):
        app_shards.shard_manifest(app_shards.read_plan(plan_path), shard_index=2)


def test_invalidate_package_and_merge_shard_results(tmp_path: Path) -> None:
    """Test thumbnail results are invalidated, packaged, and merged safely."""
    apps_root = tmp_path / "apps"
    make_app(apps_root, "alpha")
    thumbnail = apps_root / "alpha" / "thumbnail.webp"
    thumbnail.write_bytes(b"old")
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, {"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]})

    assert app_shards.invalidate_shard_thumbnails(manifest_path, apps_root=apps_root) == [thumbnail]
    assert not thumbnail.exists()
    assert app_shards.invalidate_shard_thumbnails(manifest_path, apps_root=apps_root) == []
    thumbnail.write_bytes(b"new")

    output_root = tmp_path / "result"
    output_root.mkdir()
    (output_root / "stale").write_text("remove\n", encoding="utf-8")
    app_shards.package_shard_result(manifest_path, output_root=output_root, apps_root=apps_root)
    assert (output_root / "manifest.json").is_file()
    assert (output_root / "apps" / "alpha" / "thumbnail.webp").read_bytes() == b"new"

    destination_root = tmp_path / "destination" / "apps"
    results_root = tmp_path / "results"
    result_dir = results_root / "app-shard-0"
    result_dir.parent.mkdir()
    result_dir.mkdir()
    for source in output_root.iterdir():
        target = result_dir / source.name
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            target.write_bytes(source.read_bytes())

    assert app_shards.merge_shard_results(results_root, apps_root=destination_root) == ["alpha"]
    assert (destination_root / "alpha" / "thumbnail.webp").read_bytes() == b"new"
    assert app_shards.merge_shard_results(tmp_path / "missing", apps_root=destination_root) == []


def test_package_and_merge_reject_invalid_results(tmp_path: Path) -> None:
    """Test transfer helpers reject missing, duplicate, and symlinked results."""
    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, {"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]})
    with pytest.raises(ValueError, match="missing after capture"):
        app_shards.package_shard_result(
            manifest_path, output_root=tmp_path / "result", apps_root=tmp_path / "missing-apps"
        )

    results_root = tmp_path / "results"
    for name in ("first", "second"):
        result = results_root / name
        write_json(
            result / "manifest.json",
            {"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]},
        )
        thumbnail = result / "apps" / "alpha" / "thumbnail.webp"
        thumbnail.parent.mkdir(parents=True)
        thumbnail.write_bytes(b"thumb")
    with pytest.raises(ValueError, match="duplicate"):
        app_shards.merge_shard_results(results_root, apps_root=tmp_path / "apps")

    symlink_root = tmp_path / "symlink-results"
    symlink_root.mkdir()
    (symlink_root / "outside").symlink_to(tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        app_shards.merge_shard_results(symlink_root, apps_root=tmp_path / "apps")

    missing_root = tmp_path / "missing-results"
    write_json(
        missing_root / "artifact" / "manifest.json",
        {"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]},
    )
    with pytest.raises(ValueError, match="missing thumbnail"):
        app_shards.merge_shard_results(missing_root, apps_root=tmp_path / "apps")


def test_write_and_package_reject_symlinked_outputs(tmp_path: Path) -> None:
    """Test manifest and result writers refuse symlinked output paths."""
    plan_path = tmp_path / "plan.json"
    write_json(
        plan_path,
        {"shards": [{"index": 0, "browser_slugs": [], "thumbnail_slugs": []}]},
    )
    real_output = tmp_path / "real-manifest.json"
    real_output.write_text("{}", encoding="utf-8")
    linked_output = tmp_path / "linked-manifest.json"
    linked_output.symlink_to(real_output)
    with pytest.raises(ValueError, match="symlink"):
        app_shards.write_shard_manifest(plan_path, shard_index=0, output_path=linked_output)

    manifest_path = tmp_path / "manifest.json"
    write_json(manifest_path, {"index": 0, "browser_slugs": [], "thumbnail_slugs": []})
    linked_root = tmp_path / "linked-result"
    linked_root.symlink_to(tmp_path / "real-result")
    with pytest.raises(ValueError, match="symlink"):
        app_shards.package_shard_result(manifest_path, output_root=linked_root, apps_root=tmp_path)


def test_shard_helpers_reject_symlinked_manifest_inputs_and_thumbnail_paths(tmp_path: Path) -> None:
    """Manifest, source, destination, and parent symlinks are rejected before I/O."""
    plan_path = tmp_path / "plan.json"
    write_json(
        plan_path,
        {"shards": [{"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]}]},
    )
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(ValueError, match="Shard manifest output"):
        app_shards.write_shard_manifest(
            plan_path, shard_index=0, output_path=linked_parent / "manifest.json"
        )

    manifest_target = tmp_path / "manifest-target.json"
    write_json(manifest_target, {"index": 0, "browser_slugs": [], "thumbnail_slugs": []})
    linked_manifest = tmp_path / "manifest.json"
    linked_manifest.symlink_to(manifest_target)
    with pytest.raises(ValueError, match="manifest input"):
        app_shards.read_shard_manifest(linked_manifest)
    with pytest.raises(ValueError, match="manifest is missing"):
        app_shards.read_shard_manifest(tmp_path / "missing.json")

    manifest_path = tmp_path / "thumbnail-manifest.json"
    write_json(manifest_path, {"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]})
    apps_root = tmp_path / "apps"
    target = tmp_path / "thumbnail.webp"
    target.write_bytes(b"thumb")
    thumbnail = apps_root / "alpha" / "thumbnail.webp"
    thumbnail.parent.mkdir(parents=True)
    thumbnail.symlink_to(target)
    with pytest.raises(ValueError, match="Shard thumbnail must not be a symlinked path"):
        app_shards.invalidate_shard_thumbnails(manifest_path, apps_root=apps_root)
    with pytest.raises(ValueError, match="symlink"):
        app_shards.package_shard_result(
            manifest_path, output_root=tmp_path / "result", apps_root=apps_root
        )

    linked_slug_root = tmp_path / "linked-slug-apps"
    linked_slug_root.mkdir()
    slug_target = tmp_path / "outside-slug"
    slug_target.mkdir()
    (slug_target / "thumbnail.webp").write_bytes(b"thumb")
    (linked_slug_root / "alpha").symlink_to(slug_target, target_is_directory=True)
    with pytest.raises(ValueError, match="Shard thumbnail must not be a symlinked path"):
        app_shards.invalidate_shard_thumbnails(manifest_path, apps_root=linked_slug_root)
    assert (slug_target / "thumbnail.webp").exists()

    results_root = tmp_path / "results"
    write_json(
        results_root / "result" / "manifest.json",
        {"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]},
    )
    source_thumbnail = results_root / "result" / "apps" / "alpha" / "thumbnail.webp"
    source_thumbnail.parent.mkdir(parents=True)
    source_thumbnail.write_bytes(b"thumb")
    destination_root = tmp_path / "destination"
    destination_root.mkdir()
    (destination_root / "alpha").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        app_shards.merge_shard_results(results_root, apps_root=destination_root)


def test_main_runs_makefile_facing_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test every Makefile-facing command dispatches to the corresponding helper."""
    monkeypatch.chdir(tmp_path)
    make_app(tmp_path / "apps", "alpha")
    (tmp_path / "apps" / "alpha" / "thumbnail.webp").write_bytes(b"thumb")
    plan_path = tmp_path / "plan.json"
    write_json(
        plan_path,
        {"shards": [{"index": 0, "browser_slugs": [], "thumbnail_slugs": ["alpha"]}]},
    )
    manifest_path = tmp_path / "manifest.json"

    assert (
        app_shards.main(
            [
                "write-manifest",
                "--plan",
                str(plan_path),
                "--shard",
                "0",
                "--output",
                str(manifest_path),
            ]
        )
        == 0
    )
    assert app_shards.main(["invalidate-thumbnails", "--manifest", str(manifest_path)]) == 0
    (tmp_path / "apps" / "alpha" / "thumbnail.webp").write_bytes(b"thumb")
    result_root = tmp_path / "result"
    assert (
        app_shards.main(
            ["package-result", "--manifest", str(manifest_path), "--output", str(result_root)]
        )
        == 0
    )
    downloads = tmp_path / "downloads" / "artifact"
    downloads.parent.mkdir()
    shutil.copytree(result_root, downloads)
    assert app_shards.main(["merge-results", "--root", str(tmp_path / "downloads")]) == 0
