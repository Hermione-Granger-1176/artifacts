#!/usr/bin/env python3
"""Plan and materialize bounded app-verification shards for CI workflows."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import cast

from scripts.lib.app_discovery import artifact_base_path, discover_app_slugs, thumbnail_file
from scripts.lib.path_validation import reject_symlinks

SHARD_SIZE = 20
MAX_SHARD_COUNT = 128
SHARD_MANIFEST_FILE = "manifest.json"


def browser_app_slugs(apps_root: Path, slugs: list[str] | None = None) -> list[str]:
    """Return app slugs that have the mature app browser-test entry point."""
    candidates = discover_app_slugs(apps_root) if slugs is None else slugs
    return [slug for slug in candidates if (apps_root / slug / "js" / "app.js").is_file()]


def _string_list(payload: dict[str, object], key: str) -> list[str]:
    """Read one required list of strings from a JSON-compatible payload."""
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"Plan field {key} must be a list of strings")
    return sorted(set(cast("list[str]", value)))


def _scope(payload: dict[str, object], key: str) -> str:
    """Read one app-impact scope from a JSON-compatible payload."""
    value = payload.get(key)
    if value not in {"all", "changed", "none"}:
        raise ValueError(f"Plan field {key} must be all, changed, or none")
    return value


def _scope_slugs(scope: str, scoped_slugs: list[str], all_slugs: list[str]) -> list[str]:
    """Resolve one impact scope to its ordered concrete app slug list."""
    if scope == "all":
        return all_slugs
    if scope == "changed":
        return sorted(set(scoped_slugs) & set(all_slugs))
    return []


def _chunked(slugs: list[str]) -> list[list[str]]:
    """Split sorted app slugs into deterministic bounded chunks."""
    if len(slugs) > SHARD_SIZE * MAX_SHARD_COUNT:
        raise ValueError(
            "Affected app count exceeds the configured shard capacity "
            f"({SHARD_SIZE * MAX_SHARD_COUNT})"
        )
    return [slugs[start : start + SHARD_SIZE] for start in range(0, len(slugs), SHARD_SIZE)]


def add_shards(plan: dict[str, object], *, apps_root: Path | None = None) -> dict[str, object]:
    """Add deterministic browser and thumbnail shard assignments to one impact plan."""
    root = apps_root or Path(artifact_base_path())
    all_apps = discover_app_slugs(root)
    browser_apps = browser_app_slugs(root, all_apps)
    browser_slugs = _scope_slugs(
        _scope(plan, "browser_scope"),
        _string_list(plan, "changed_slugs"),
        browser_apps,
    )
    thumbnail_slugs = _scope_slugs(
        _scope(plan, "thumbnail_scope"),
        _string_list(plan, "thumbnail_slugs"),
        all_apps,
    )
    affected_slugs = sorted(set(browser_slugs) | set(thumbnail_slugs))

    shards: list[dict[str, object]] = []
    for index, chunk in enumerate(_chunked(affected_slugs)):
        chunk_set = set(chunk)
        shards.append(
            {
                "index": index,
                "browser_slugs": [slug for slug in browser_slugs if slug in chunk_set],
                "thumbnail_slugs": [slug for slug in thumbnail_slugs if slug in chunk_set],
            }
        )

    return {**plan, "shards": shards}


def _shards(plan: dict[str, object]) -> list[dict[str, object]]:
    """Read and validate the shard list from a plan payload."""
    value = plan.get("shards")
    if not isinstance(value, list):
        raise ValueError("Plan field shards must be a list")
    shards: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError("Every shard must be an object")
        index = item.get("index")
        if not isinstance(index, int) or index < 0:
            raise ValueError("Every shard index must be a non-negative integer")
        _string_list(item, "browser_slugs")
        _string_list(item, "thumbnail_slugs")
        shards.append(cast("dict[str, object]", item))
    if [cast("int", shard["index"]) for shard in shards] != list(range(len(shards))):
        raise ValueError("Shard indexes must be contiguous and start at zero")
    if len(shards) > MAX_SHARD_COUNT:
        raise ValueError(f"Plan exceeds the {MAX_SHARD_COUNT}-shard matrix limit")
    return shards


def compact_matrix(plan: dict[str, object]) -> str:
    """Return the compact GitHub Actions matrix containing shard indexes only."""
    return json.dumps(
        {"include": [{"shard": shard["index"]} for shard in _shards(plan)]},
        separators=(",", ":"),
    )


def shard_count(plan: dict[str, object]) -> int:
    """Return the validated number of executable shard assignments."""
    return len(_shards(plan))


def read_plan(path: Path) -> dict[str, object]:
    """Read one persisted JSON impact plan."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Impact plan must be a JSON object")
    return cast("dict[str, object]", payload)


def shard_manifest(plan: dict[str, object], *, shard_index: int) -> dict[str, object]:
    """Return a validated shard manifest selected from one persisted plan."""
    for shard in _shards(plan):
        if shard["index"] == shard_index:
            return {
                "index": shard_index,
                "browser_slugs": _string_list(shard, "browser_slugs"),
                "thumbnail_slugs": _string_list(shard, "thumbnail_slugs"),
            }
    raise ValueError(f"Shard index {shard_index} is not present in the impact plan")


def write_shard_manifest(plan_path: Path, *, shard_index: int, output_path: Path) -> None:
    """Select one plan shard and write its standalone manifest."""
    manifest = shard_manifest(read_plan(plan_path), shard_index=shard_index)
    if output_path.is_symlink():
        raise ValueError(f"Shard manifest output must not be a symlink: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def read_shard_manifest(path: Path) -> dict[str, object]:
    """Read and validate a standalone app-shard manifest."""
    payload = read_plan(path)
    index = payload.get("index")
    if not isinstance(index, int) or index < 0:
        raise ValueError("Shard manifest index must be a non-negative integer")
    return {
        "index": index,
        "browser_slugs": _string_list(payload, "browser_slugs"),
        "thumbnail_slugs": _string_list(payload, "thumbnail_slugs"),
    }


def invalidate_shard_thumbnails(
    manifest_path: Path, *, apps_root: Path | None = None
) -> list[Path]:
    """Delete prior thumbnails for the manifest's targeted thumbnail slugs."""
    root = apps_root or Path(artifact_base_path())
    removed: list[Path] = []
    for slug in cast("list[str]", read_shard_manifest(manifest_path)["thumbnail_slugs"]):
        thumbnail = root / slug / thumbnail_file()
        if thumbnail.exists():
            thumbnail.unlink()
            removed.append(thumbnail)
    return removed


def package_shard_result(
    manifest_path: Path,
    *,
    output_root: Path,
    apps_root: Path | None = None,
) -> None:
    """Package a shard manifest and its generated thumbnails for transfer."""
    manifest = read_shard_manifest(manifest_path)
    root = apps_root or Path(artifact_base_path())
    if output_root.is_symlink():
        raise ValueError(f"Shard result output must not be a symlink: {output_root}")
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    (output_root / SHARD_MANIFEST_FILE).write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )

    for slug in cast("list[str]", manifest["thumbnail_slugs"]):
        source = root / slug / thumbnail_file()
        if not source.is_file():
            raise ValueError(f"Shard thumbnail is missing after capture: {source}")
        destination = output_root / artifact_base_path() / slug / thumbnail_file()
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def merge_shard_results(results_root: Path, *, apps_root: Path | None = None) -> list[str]:
    """Validate and merge every downloaded shard thumbnail result into the checkout."""
    if not results_root.exists():
        return []
    reject_symlinks(results_root)
    destination_root = apps_root or Path(artifact_base_path())
    merged: list[str] = []
    seen_slugs: set[str] = set()
    for result_root in sorted(path for path in results_root.iterdir() if path.is_dir()):
        manifest = read_shard_manifest(result_root / SHARD_MANIFEST_FILE)
        for slug in cast("list[str]", manifest["thumbnail_slugs"]):
            if slug in seen_slugs:
                raise ValueError(f"Shard results contain duplicate thumbnail slug: {slug}")
            source = result_root / artifact_base_path() / slug / thumbnail_file()
            if not source.is_file():
                raise ValueError(f"Shard result is missing thumbnail: {source}")
            target = destination_root / slug / thumbnail_file()
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            seen_slugs.add(slug)
            merged.append(slug)
    return merged


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser used by Makefile wrappers."""
    parser = argparse.ArgumentParser(description="Manage CI app shard manifests")
    commands = parser.add_subparsers(dest="command", required=True)
    write = commands.add_parser("write-manifest")
    write.add_argument("--plan", required=True)
    write.add_argument("--shard", type=int, required=True)
    write.add_argument("--output", required=True)
    invalidate = commands.add_parser("invalidate-thumbnails")
    invalidate.add_argument("--manifest", required=True)
    package = commands.add_parser("package-result")
    package.add_argument("--manifest", required=True)
    package.add_argument("--output", required=True)
    merge = commands.add_parser("merge-results")
    merge.add_argument("--root", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one Makefile-facing app-shard command."""
    args = _parser().parse_args(argv)
    if args.command == "write-manifest":
        write_shard_manifest(Path(args.plan), shard_index=args.shard, output_path=Path(args.output))
    elif args.command == "invalidate-thumbnails":
        for thumbnail in invalidate_shard_thumbnails(Path(args.manifest)):
            print(f"Invalidating {thumbnail}")
    elif args.command == "package-result":
        package_shard_result(Path(args.manifest), output_root=Path(args.output))
    elif args.command == "merge-results":
        for slug in merge_shard_results(Path(args.root)):
            print(f"Merged thumbnail for {slug}")
    else:  # pragma: no cover - argparse constrains command values.
        raise ValueError(f"Unsupported app-shard command: {args.command}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
