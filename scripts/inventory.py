#!/usr/bin/env python3
"""Inventory host-installed and pinned-upstream Agent Skills."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path

import tomllib
import yaml

REPOSITORY = Path(__file__).resolve().parents[1]
try:
    from .storage import state_home
except ImportError:  # Direct execution: python scripts/inventory.py
    from storage import state_home


def canonical_skill_collections(repository: Path) -> list[dict[str, object]]:
    """Find published sources and native skills, excluding APM deployments."""
    collections = []
    manifest = repository / "apm.yml"
    if manifest.is_file():
        package = yaml.safe_load(manifest.read_text()) or {}
        skills: set[Path] = set()
        for entry in package.get("includes", []):
            source = (repository / entry).resolve()
            if not source.is_relative_to(repository.resolve()):
                raise ValueError(
                    f"{manifest}: included source escapes package: {entry}"
                )
            skills.update(path.parent for path in source.rglob("SKILL.md"))
        collections.append(
            {"name": "reusable", "root": repository, "skills": sorted(skills)}
        )

    generated: set[Path] = set()
    lock_path = repository / "apm.lock.yaml"
    if lock_path.is_file():
        lock = yaml.safe_load(lock_path.read_text()) or {}
        deployed = list(lock.get("local_deployed_files", []))
        deployed.extend(
            item["value"]
            for item in lock.get("deployments", [])
            if item.get("kind") == "project-relative"
            and isinstance(item.get("value"), str)
        )
        for dependency in lock.get("dependencies", []):
            deployed.extend(dependency.get("deployed_files", []))
        for entry in deployed:
            path = Path(entry)
            if path.parts[:2] == (".agents", "skills") and len(path.parts) >= 3:
                generated.add(repository / Path(*path.parts[:3]))

    native = repository / ".agents/skills"
    skills = [
        path.parent
        for path in sorted(native.rglob("SKILL.md"))
        if not any(path.is_relative_to(root) for root in generated)
    ]
    if skills:
        collections.append({"name": "native", "root": native, "skills": skills})
    return collections


def skill_name(skill_file: Path) -> str:
    """Return the frontmatter name, falling back to the directory name."""
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return skill_file.parent.name
    if not lines or lines[0].strip() != "---":
        return skill_file.parent.name
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("'\"") or skill_file.parent.name
    return skill_file.parent.name


def git_revision(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    relative_path = path.relative_to(REPOSITORY)
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY), "ls-files", "--stage", str(relative_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    fields = result.stdout.split()
    return fields[1] if result.returncode == 0 and len(fields) >= 2 else None


def collect(root: Path, source: str) -> list[dict[str, str]]:
    if not root.is_dir():
        return []
    return [
        {
            "name": skill_name(skill_file),
            "path": str(skill_file.parent.resolve()),
            "source": source,
        }
        for skill_file in sorted(root.rglob("SKILL.md"))
    ]


def build_inventory(config_path: Path) -> dict[str, object]:
    with config_path.open("rb") as stream:
        config = tomllib.load(stream)

    installed: list[dict[str, str]] = []
    for root in config.get("skill_roots", []):
        path = Path(root["path"]).expanduser()
        installed.extend(collect(path, root["name"]))

    upstreams: list[dict[str, object]] = []
    for upstream in config.get("upstreams", []):
        path = REPOSITORY / upstream["path"]
        skills = collect(path, upstream["name"])
        upstreams.append(
            {
                **upstream,
                "revision": git_revision(path),
                "initialized": bool(skills),
                "skills": skills,
            }
        )

    workshop = [
        {
            "name": skill_name(path / "SKILL.md"),
            "path": str(path.resolve()),
            "source": collection["name"],
        }
        for collection in canonical_skill_collections(REPOSITORY)
        for path in collection["skills"]
    ]

    duplicates: dict[str, list[str]] = {}
    for item in installed:
        duplicates.setdefault(item["name"], []).append(item["path"])

    return {
        "installed": installed,
        "workshop": workshop,
        "duplicate_installations": {
            name: paths for name, paths in duplicates.items() if len(paths) > 1
        },
        "upstreams": upstreams,
    }


def relative_workshop_path(path: str) -> str | None:
    try:
        return Path(path).resolve().relative_to(REPOSITORY).as_posix()
    except ValueError:
        return None


def tabular_rows(inventory: dict[str, object]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def append(
        item: dict[str, str],
        scope: str,
        collection: str,
        upstream_url: str = "",
        revision: str = "",
    ) -> None:
        workshop_path = relative_workshop_path(item["path"])
        relation_key = workshop_path or ""
        rows.append(
            {
                "skill": item["name"],
                "scope": scope,
                "collection": collection,
                "source": relation_key,
                "path": item["path"],
                "upstream": upstream_url,
                "revision": revision,
            }
        )

    for item in inventory["workshop"]:
        append(item, "workshop", item["source"])
    for upstream in inventory["upstreams"]:
        for item in upstream["skills"]:
            append(
                item,
                "upstream",
                upstream["name"],
                upstream["url"],
                upstream["revision"] or "",
            )
    for item in inventory["installed"]:
        append(item, "installed", item["source"])
    return sorted(rows, key=lambda row: (row["skill"], row["scope"], row["path"]))


def write_tsv(inventory: dict[str, object], output: Path) -> None:
    columns = [
        "skill",
        "scope",
        "collection",
        "source",
        "path",
        "upstream",
        "revision",
    ]
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(tabular_rows(inventory))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
    )
    parser.add_argument("--format", choices=("json", "tsv"), default="json")
    parser.add_argument(
        "--view", action="store_true", help="open the generated table in VisiData"
    )
    args = parser.parse_args()
    inventory = build_inventory(REPOSITORY / "registry.toml")
    output = args.output or state_home() / "inventory" / (
        "skills.tsv" if args.format == "tsv" else "installed-skills.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "tsv":
        write_tsv(inventory, output)
    else:
        output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(
        f"Found {len(inventory['installed'])} installed skills and "
        f"{sum(len(item['skills']) for item in inventory['upstreams'])} upstream skills."
    )
    print(output)
    if args.view:
        subprocess.run(["vd", str(output)], check=True)


if __name__ == "__main__":
    main()
