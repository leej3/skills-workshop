#!/usr/bin/env python3
"""Link the global core profile or copy a skill cluster into a project."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import tomllib

REPOSITORY = Path(__file__).resolve().parents[1]
CORE_STATE = ".skills-workshop-core.json"
PROJECT_LOCK = "skills.lock.json"


def load_manifest(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        manifest = tomllib.load(stream)
    entries = manifest.get("skills", [])
    if not isinstance(entries, list):
        raise TypeError(f"skills must be an array in {path}")
    seen: set[str] = set()
    for entry in entries:
        name = entry.get("name")
        source = entry.get("source")
        if not name or not source:
            raise ValueError(f"each skill needs name and source in {path}")
        if name in seen:
            raise ValueError(f"duplicate skill {name!r} in {path}")
        seen.add(name)
        source_path = (REPOSITORY / source).resolve()
        if (
            REPOSITORY not in source_path.parents
            or not (source_path / "SKILL.md").is_file()
        ):
            raise ValueError(f"invalid skill source: {source}")
    return manifest


def digest_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(file for file in path.rglob("*") if file.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def upstream_metadata(source: Path) -> dict[str, str | None]:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-superproject-working-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    superproject = result.stdout.strip()
    if not superproject:
        return {"revision": None, "url": None}
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = result.stdout.strip()
    result = subprocess.run(
        ["git", "-C", str(source), "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
    )
    return {"revision": revision, "url": result.stdout.strip() or None}


def link_core(target: Path) -> None:
    manifest = load_manifest(REPOSITORY / "profiles" / "core.toml")
    target.mkdir(parents=True, exist_ok=True)
    state_path = target / CORE_STATE
    old_state = (
        json.loads(state_path.read_text()) if state_path.exists() else {"links": {}}
    )
    desired: dict[str, str] = {}

    for entry in manifest["skills"]:
        source = (REPOSITORY / entry["source"]).resolve()
        destination = target / entry["name"]
        desired[entry["name"]] = str(source)
        if destination.is_symlink() and destination.resolve() == source:
            continue
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"refusing to replace unmanaged path: {destination}")
        destination.symlink_to(source, target_is_directory=True)

    for name, source in old_state.get("links", {}).items():
        if name in desired:
            continue
        destination = target / name
        if destination.is_symlink() and str(destination.resolve()) == source:
            destination.unlink()

    state_path.write_text(json.dumps({"links": desired}, indent=2) + "\n")
    print(f"Core profile: {len(desired)} linked skills in {target}")


def apply_cluster(name: str, project: Path, replace: bool) -> None:
    manifest_path = REPOSITORY / "clusters" / f"{name}.toml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"unknown cluster: {name}")
    manifest = load_manifest(manifest_path)
    project = project.resolve()
    destination_root = project / ".agents" / "skills"
    destination_root.mkdir(parents=True, exist_ok=True)
    locked: list[dict[str, object]] = []

    for entry in manifest["skills"]:
        source = (REPOSITORY / entry["source"]).resolve()
        destination = destination_root / entry["name"]
        source_digest = digest_tree(source)
        if destination.exists() or destination.is_symlink():
            if (
                destination.is_dir()
                and not destination.is_symlink()
                and digest_tree(destination) == source_digest
            ):
                pass
            elif not replace:
                raise FileExistsError(
                    f"skill differs; use --replace to update: {destination}"
                )
            else:
                if destination.is_dir() and not destination.is_symlink():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
                shutil.copytree(source, destination, symlinks=False)
        else:
            shutil.copytree(source, destination, symlinks=False)
        locked.append(
            {
                "name": entry["name"],
                "source": entry["source"],
                "sha256": source_digest,
                **upstream_metadata(source),
            }
        )

    lock = {
        "schema_version": 1,
        "cluster": manifest["name"],
        "skills": locked,
    }
    lock_path = project / ".agents" / PROJECT_LOCK
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Cluster {name}: {len(locked)} copied skills into {destination_root}")


def configure_upstreams() -> None:
    with (REPOSITORY / "registry.toml").open("rb") as stream:
        registry = tomllib.load(stream)
    for entry in registry.get("upstreams", []):
        path = REPOSITORY / entry["path"]
        if not (path / ".git").exists():
            raise FileNotFoundError(
                f"submodule is not initialized: {path}; run git submodule update --init"
            )
        subprocess.run(
            ["git", "-C", str(path), "remote", "set-url", "origin", entry["fork_url"]],
            check=True,
        )
        result = subprocess.run(
            ["git", "-C", str(path), "remote", "get-url", "upstream"],
            check=False,
            capture_output=True,
        )
        action = "set-url" if result.returncode == 0 else "add"
        subprocess.run(
            ["git", "-C", str(path), "remote", action, "upstream", entry["url"]],
            check=True,
        )
        print(f"{entry['name']}: origin={entry['fork_url']} upstream={entry['url']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    core = commands.add_parser("link-core", help="reconcile the global core profile")
    core.add_argument(
        "--target", type=Path, default=Path("~/.agents/skills").expanduser()
    )
    cluster = commands.add_parser("apply-cluster", help="copy a cluster into a project")
    cluster.add_argument("name")
    cluster.add_argument("project", type=Path)
    cluster.add_argument("--replace", action="store_true")
    commands.add_parser(
        "configure-upstreams",
        help="configure fork origins and canonical upstream remotes",
    )
    args = parser.parse_args()

    if args.command == "link-core":
        link_core(args.target)
    elif args.command == "apply-cluster":
        apply_cluster(args.name, args.project, args.replace)
    else:
        configure_upstreams()


if __name__ == "__main__":
    main()
