#!/usr/bin/env python3
"""Inventory host-installed and pinned-upstream Agent Skills."""

from __future__ import annotations

import argparse
import json
import subprocess
import tomllib
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]


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

    duplicates: dict[str, list[str]] = {}
    for item in installed:
        duplicates.setdefault(item["name"], []).append(item["path"])

    return {
        "installed": installed,
        "duplicate_installations": {
            name: paths for name, paths in duplicates.items() if len(paths) > 1
        },
        "upstreams": upstreams,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPOSITORY / "inventory" / "installed-skills.json",
    )
    args = parser.parse_args()
    inventory = build_inventory(REPOSITORY / "registry.toml")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")
    print(
        f"Found {len(inventory['installed'])} installed skills and "
        f"{sum(len(item['skills']) for item in inventory['upstreams'])} upstream skills."
    )
    print(args.output)


if __name__ == "__main__":
    main()
