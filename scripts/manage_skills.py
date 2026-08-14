#!/usr/bin/env python3
"""Link the global core profile or copy a skill cluster into a project."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import tomllib

REPOSITORY = Path(__file__).resolve().parents[1]
CORE_STATE = ".skills-workshop-core.json"
MATERIALIZATIONS = REPOSITORY / "materializations"


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


def upstream_metadata(source: Path) -> dict[str, str | bool | None]:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-superproject-working-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    superproject = result.stdout.strip()
    if not superproject:
        return {
            "revision": None,
            "origin_url": None,
            "upstream_url": None,
            "source_dirty": False,
        }
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    revision = result.stdout.strip()
    remotes: dict[str, str | None] = {}
    for remote in ("origin", "upstream"):
        result = subprocess.run(
            ["git", "-C", str(source), "remote", "get-url", remote],
            check=False,
            capture_output=True,
            text=True,
        )
        remotes[f"{remote}_url"] = result.stdout.strip() or None
    result = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain", "--", "."],
        check=True,
        capture_output=True,
        text=True,
    )
    return {"revision": revision, **remotes, "source_dirty": bool(result.stdout)}


def project_identity(project: Path, requested: str | None) -> tuple[str, str | None]:
    result = subprocess.run(
        ["git", "-C", str(project), "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
    )
    remote = result.stdout.strip() or None
    candidate = requested
    if not candidate and remote:
        candidate = re.sub(r"^git@[^:]+:|^https?://[^/]+/", "", remote)
        candidate = re.sub(r"\.git$", "", candidate).replace("/", "--")
    if not candidate:
        candidate = project.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", candidate):
        raise ValueError(
            "project identifier must contain only letters, digits, dots, underscores, "
            "and hyphens"
        )
    return candidate, remote


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


def replace_tree(source: Path, destination: Path) -> None:
    if destination.is_dir() and not destination.is_symlink():
        shutil.rmtree(destination)
    elif destination.exists() or destination.is_symlink():
        destination.unlink()
    shutil.copytree(source, destination, symlinks=False)


def choose_conflict_policy(
    conflicts: list[dict[str, object]], requested: str | None
) -> str:
    if requested:
        return requested
    names = ", ".join(item["entry"]["name"] for item in conflicts)
    if not sys.stdin.isatty():
        raise SystemExit(
            f"project skills differ: {names}; rerun with --conflict abort, record, "
            "back-propagate, or overwrite"
        )

    print(f"\nProject skills differ from the workshop: {names}\n")
    print("1. Do not proceed")
    print("2. Update workshop metadata and preserve both versions")
    print("3. Back-propagate project changes into the workshop")
    print("4. Force-update the project from the workshop")
    choices = {
        "1": "abort",
        "2": "record",
        "3": "back-propagate",
        "4": "overwrite",
    }
    while True:
        answer = input("Choose 1-4 [1]: ").strip() or "1"
        if answer in choices:
            return choices[answer]
        print("Enter 1, 2, 3, or 4.")


def apply_cluster(
    name: str,
    project: Path,
    conflict: str | None,
    requested_project_id: str | None,
) -> None:
    manifest_path = REPOSITORY / "clusters" / f"{name}.toml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"unknown cluster: {name}")
    manifest = load_manifest(manifest_path)
    project = project.resolve()
    project_id, project_remote = project_identity(project, requested_project_id)
    destination_root = project / ".agents" / "skills"
    destination_root.mkdir(parents=True, exist_ok=True)
    planned: list[dict[str, object]] = []

    for entry in manifest["skills"]:
        source = (REPOSITORY / entry["source"]).resolve()
        destination = destination_root / entry["name"]
        source_digest = digest_tree(source)
        project_digest = (
            digest_tree(destination)
            if destination.is_dir() and not destination.is_symlink()
            else None
        )
        planned.append(
            {
                "entry": entry,
                "source": source,
                "destination": destination,
                "source_digest": source_digest,
                "project_digest": project_digest,
                "conflicting": (destination.exists() or destination.is_symlink())
                and project_digest != source_digest,
            }
        )

    conflicts = [item for item in planned if item["conflicting"]]
    if conflicts:
        conflict = choose_conflict_policy(conflicts, conflict)
    if conflicts and conflict == "abort":
        raise SystemExit("No changes made.")

    locked: list[dict[str, object]] = []
    for item in planned:
        entry = item["entry"]
        source = item["source"]
        destination = item["destination"]
        if not destination.exists() and not destination.is_symlink():
            shutil.copytree(source, destination, symlinks=False)
        elif item["conflicting"] and conflict == "back-propagate":
            replace_tree(destination, source)
        elif item["conflicting"] and conflict == "overwrite":
            replace_tree(source, destination)

        source_digest = digest_tree(source)
        project_digest = (
            digest_tree(destination)
            if destination.is_dir() and not destination.is_symlink()
            else None
        )
        locked.append(
            {
                "name": entry["name"],
                "source": entry["source"],
                "source_sha256": source_digest,
                "project_sha256": project_digest,
                "status": "synced" if source_digest == project_digest else "diverged",
                **upstream_metadata(source),
            }
        )

    lock = {
        "schema_version": 1,
        "cluster": manifest["name"],
        "project": {"id": project_id, "remote": project_remote},
        "skills": locked,
    }
    MATERIALIZATIONS.mkdir(parents=True, exist_ok=True)
    lock_path = MATERIALIZATIONS / f"{project_id}--{manifest['name']}.lock.json"
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print(f"Cluster {name}: {len(locked)} copied skills into {destination_root}")
    print(f"Coordination record: {lock_path}")


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
    cluster.add_argument(
        "--conflict",
        choices=("abort", "record", "back-propagate", "overwrite"),
        help="conflict policy; omit to choose from a menu in an interactive terminal",
    )
    cluster.add_argument(
        "--project-id",
        help="stable lock name; defaults to the project's origin remote or directory name",
    )
    commands.add_parser(
        "configure-upstreams",
        help="configure fork origins and canonical upstream remotes",
    )
    args = parser.parse_args()

    if args.command == "link-core":
        link_core(args.target)
    elif args.command == "apply-cluster":
        apply_cluster(args.name, args.project, args.conflict, args.project_id)
    else:
        configure_upstreams()


if __name__ == "__main__":
    main()
