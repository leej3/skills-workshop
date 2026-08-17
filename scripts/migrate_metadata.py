#!/usr/bin/env python3
"""Plan or apply supported workshop metadata schema migrations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .materialization_metadata import (
        CURRENT_LOCK_SCHEMA_VERSION,
        lock_bundle,
        lock_schema_version,
    )
except ImportError:  # Direct execution: python scripts/migrate_metadata.py
    from materialization_metadata import (
        CURRENT_LOCK_SCHEMA_VERSION,
        lock_bundle,
        lock_schema_version,
    )

REPOSITORY = Path(__file__).resolve().parents[1]


def migrate_lock(data: dict[str, object]) -> tuple[dict[str, object], bool]:
    context = "materialization lock"
    version = lock_schema_version(data, context=context)
    bundle = lock_bundle(data, context=context)
    if version == CURRENT_LOCK_SCHEMA_VERSION:
        return data, False
    if version == 1:
        skills = data.get("skills")
        if not isinstance(skills, list):
            raise TypeError("materialization lock skills must be an array")
        for skill in skills:
            if not isinstance(skill, dict):
                raise TypeError("materialization lock skill entries must be objects")
            if not isinstance(skill.get("name"), str) or not isinstance(
                skill.get("source"), str
            ):
                raise TypeError(
                    "v1 skill entries require string name and source fields"
                )
            skill["identity"] = f"{skill['source']}#{skill['name']}"
            if "source_sha256" not in skill and "sha256" in skill:
                skill["source_sha256"] = skill.pop("sha256")
            if not isinstance(skill.get("source_sha256"), str):
                raise TypeError(
                    f"v1 skill {skill['name']!r} has no usable source digest"
                )
            skill.setdefault("project_sha256", skill.get("source_sha256"))
            skill.setdefault(
                "status",
                "synced"
                if skill.get("source_sha256") == skill.get("project_sha256")
                else "diverged",
            )
            skill.setdefault("revision", None)
            skill.setdefault("origin_url", skill.pop("url", None))
            skill.setdefault("upstream_url", None)
            skill.setdefault("source_dirty", False)
    data.pop("cluster", None)
    data["bundle"] = bundle
    data["schema_version"] = CURRENT_LOCK_SCHEMA_VERSION
    return data, True


def migrate(path: Path, apply: bool) -> bool:
    data = json.loads(path.read_text(encoding="utf-8"))
    data, changed = migrate_lock(data)
    if changed and apply:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write migrated metadata")
    args = parser.parse_args()
    paths = sorted((REPOSITORY / "materializations").glob("*.lock.json"))
    changed = [path for path in paths if migrate(path, args.apply)]
    action = "Migrated" if args.apply else "Would migrate"
    for path in changed:
        print(f"{action}: {path.relative_to(REPOSITORY)}")
    print(f"{len(changed)} of {len(paths)} locks require migration")


if __name__ == "__main__":
    main()
