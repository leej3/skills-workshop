#!/usr/bin/env python3
"""Link the global core profile or copy a skill cluster into a project."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import tomllib

REPOSITORY = Path(__file__).resolve().parents[1]
CORE_STATE = ".skills-workshop-core.json"
MATERIALIZATIONS = REPOSITORY / "materializations"
BACKUPS = REPOSITORY / ".backups"
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def safe_name(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not SAFE_NAME.fullmatch(value):
        raise ValueError(f"unsafe {context} {value!r}")
    return value


def declared_skill_name(skill_file: Path) -> str | None:
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("'\"") or None
    return None


def repository_source(
    value: object,
    *,
    require_skill: bool = True,
    expected_name: str | None = None,
) -> Path:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"invalid skill source: {value!r}")
    relative = Path(value)
    if (
        relative.is_absolute()
        or relative.as_posix() != value
        or any(part in {".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"invalid skill source: {value}")
    repository = REPOSITORY.resolve()
    source = repository / relative
    current = repository
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"invalid skill source: {value}")
    resolved = source.resolve()
    if resolved == repository or repository not in resolved.parents:
        raise ValueError(f"invalid skill source: {value}")
    if require_skill:
        validate_skill_tree(
            source,
            context=f"skill source {value!r}",
            expected_name=expected_name,
        )
    return source


def validate_skill_tree(
    path: Path, *, context: str, expected_name: str | None = None
) -> None:
    if not path.is_dir() or path.is_symlink() or not (path / "SKILL.md").is_file():
        raise ValueError(f"{context} is not a real skill directory: {path}")
    links = [item for item in path.rglob("*") if item.is_symlink()]
    if links:
        shown = ", ".join(str(item.relative_to(path)) for item in links[:3])
        extra = f" (+{len(links) - 3} more)" if len(links) > 3 else ""
        raise ValueError(
            f"{context} contains symlinks, which materialization refuses: "
            f"{shown}{extra}"
        )
    declared_name = declared_skill_name(path / "SKILL.md")
    if not isinstance(declared_name, str) or not SAFE_NAME.fullmatch(declared_name):
        raise ValueError(f"{context} has no valid declared name: {path / 'SKILL.md'}")
    if expected_name is not None and declared_name != expected_name:
        raise ValueError(
            f"{context} declares {declared_name!r}, expected {expected_name!r}"
        )


def validate_project_skills_root(project: Path) -> Path:
    agents = project / ".agents"
    root = agents / "skills"
    for path in (agents, root):
        if (path.exists() or path.is_symlink()) and (
            not path.is_dir() or path.is_symlink()
        ):
            raise ValueError(f"project skill path is not a real directory: {path}")
    return root


def load_manifest(path: Path) -> dict[str, object]:
    with path.open("rb") as stream:
        manifest = tomllib.load(stream)
    if manifest.get("schema_version") != 1:
        raise ValueError(f"unsupported schema_version in {path}")
    manifest_name = safe_name(manifest.get("name"), context=f"manifest name in {path}")
    if path.stem != manifest_name:
        raise ValueError(
            f"manifest filename/name mismatch: {path.stem!r} != {manifest_name!r}"
        )
    entries = manifest.get("skills", [])
    if not isinstance(entries, list):
        raise TypeError(f"skills must be an array in {path}")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise TypeError(f"each skill must be a table in {path}")
        name = entry.get("name")
        source = entry.get("source")
        if not name or not source:
            raise ValueError(f"each skill needs name and source in {path}")
        safe_name(name, context=f"skill name in {path}")
        if name in seen:
            raise ValueError(f"duplicate skill {name!r} in {path}")
        seen.add(name)
        if not isinstance(source, str):
            raise TypeError(f"skill source must be a string in {path}")
    for entry in entries:
        name = entry["name"]
        source = entry["source"]
        repository_source(source, expected_name=name)
    return manifest


def load_previous_lock(
    path: Path, *, cluster: str, project_id: str
) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(
            f"cannot read previous coordination lock {path}: {error}"
        ) from error
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise TypeError(f"invalid previous coordination lock: {path}")
    if data.get("schema_version", 1) not in {1, 2}:
        raise ValueError(f"unsupported coordination lock schema: {path}")
    if data.get("cluster") != cluster:
        raise ValueError(
            f"coordination lock cluster does not match {cluster!r}: {path}"
        )
    project = data.get("project")
    if not isinstance(project, dict) or project.get("id") != project_id:
        raise ValueError(
            f"coordination lock project does not match {project_id!r}: {path}"
        )
    seen: set[str] = set()
    for item in data["skills"]:
        if not isinstance(item, dict):
            raise TypeError(f"invalid skill entry in coordination lock: {path}")
        name = safe_name(item.get("name"), context=f"locked skill name in {path}")
        if name in seen:
            raise ValueError(f"duplicate locked skill {name!r} in {path}")
        seen.add(name)
        repository_source(item.get("source"), require_skill=False)
        baseline = item.get("project_sha256", item.get("sha256"))
        if baseline is not None and not isinstance(baseline, str):
            raise ValueError(f"invalid project digest for {name!r} in {path}")
    return data


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
        if "://" in remote:
            candidate = urlsplit(remote).path.lstrip("/")
        else:
            scp = re.match(r"^(?:[^@/]+@)?[^:/]+:(.+)$", remote)
            candidate = scp.group(1) if scp else remote.strip("/")
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
    if not isinstance(old_state, dict) or not isinstance(old_state.get("links"), dict):
        raise TypeError(f"invalid core profile state: {state_path}")
    desired: dict[str, str] = {}

    for entry in manifest["skills"]:
        source = repository_source(entry["source"], expected_name=entry["name"])
        destination = target / entry["name"]
        desired[entry["name"]] = str(source)
        if destination.is_symlink() and destination.resolve() == source:
            continue
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"refusing to replace unmanaged path: {destination}")
        destination.symlink_to(source, target_is_directory=True)

    for name, source in old_state.get("links", {}).items():
        safe_name(name, context=f"managed core link in {state_path}")
        if not isinstance(source, str):
            raise TypeError(f"invalid managed core source in {state_path}: {source!r}")
        if name in desired:
            continue
        destination = target / name
        if destination.is_symlink() and str(destination.resolve()) == source:
            destination.unlink()

    temporary = state_path.with_suffix(state_path.suffix + ".tmp")
    temporary.write_text(json.dumps({"links": desired}, indent=2) + "\n")
    temporary.replace(state_path)
    print(f"Core profile: {len(desired)} linked skills in {target}")


def replace_tree(source: Path, destination: Path) -> None:
    if not source.is_dir() or source.is_symlink():
        raise ValueError(f"replacement source is not a real directory: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}.skills-workshop-", dir=destination.parent
    ) as temporary:
        staged = Path(temporary) / "tree"
        shutil.copytree(source, staged, symlinks=False)
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        elif destination.exists() or destination.is_symlink():
            raise FileExistsError(
                f"refusing to replace a non-directory skill path: {destination}"
            )
        staged.replace(destination)


def skill_identity(name: str, source: str) -> str:
    return f"{source}#{name}"


def backup_tree(
    path: Path, project_id: str, cluster: str, side: str, name: str
) -> Path | None:
    if not path.is_dir() or path.is_symlink():
        return None
    digest = digest_tree(path)
    destination = BACKUPS / f"{project_id}--{cluster}" / side / name / digest
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(path, destination, symlinks=False)
    return destination


def tree_diff(source: Path, project: Path) -> str:
    source_files = {
        item.relative_to(source).as_posix(): item
        for item in source.rglob("*")
        if item.is_file()
    }
    project_files = (
        {
            item.relative_to(project).as_posix(): item
            for item in project.rglob("*")
            if item.is_file()
        }
        if project.is_dir() and not project.is_symlink()
        else {}
    )
    output: list[str] = []
    for relative in sorted(source_files.keys() | project_files.keys()):
        left = source_files.get(relative)
        right = project_files.get(relative)
        try:
            left_lines = left.read_text(encoding="utf-8").splitlines() if left else []
            right_lines = (
                right.read_text(encoding="utf-8").splitlines() if right else []
            )
        except UnicodeDecodeError:
            if not left or not right or left.read_bytes() != right.read_bytes():
                output.append(f"Binary files differ: {relative}")
            continue
        output.extend(
            difflib.unified_diff(
                left_lines,
                right_lines,
                fromfile=f"workshop/{relative}",
                tofile=f"project/{relative}",
                lineterm="",
            )
        )
    return "\n".join(output)


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
    dry_run: bool = False,
    prune: bool = False,
    show_diff: bool = False,
) -> None:
    safe_name(name, context="cluster name")
    manifest_path = REPOSITORY / "clusters" / f"{name}.toml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"unknown cluster: {name}")
    manifest = load_manifest(manifest_path)
    if manifest["name"] != name:
        raise ValueError(
            f"cluster filename/name mismatch: requested {name!r}, "
            f"manifest declares {manifest['name']!r}"
        )
    project = project.resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"project does not exist: {project}")
    project_id, project_remote = project_identity(project, requested_project_id)
    destination_root = validate_project_skills_root(project)
    lock_path = MATERIALIZATIONS / f"{project_id}--{manifest['name']}.lock.json"
    previous_lock = load_previous_lock(
        lock_path, cluster=manifest["name"], project_id=project_id
    )
    previous_by_name = {item["name"]: item for item in previous_lock.get("skills", [])}
    planned: list[dict[str, object]] = []

    for entry in manifest["skills"]:
        source = repository_source(entry["source"], expected_name=entry["name"])
        destination = destination_root / entry["name"]
        source_digest = digest_tree(source)
        present = destination.exists() or destination.is_symlink()
        real_directory = destination.is_dir() and not destination.is_symlink()
        if real_directory:
            validate_skill_tree(
                destination,
                context=f"project skill {entry['name']!r}",
                expected_name=entry["name"],
            )
        project_digest = digest_tree(destination) if real_directory else None
        planned.append(
            {
                "entry": entry,
                "source": source,
                "destination": destination,
                "source_digest": source_digest,
                "project_digest": project_digest,
                "present": present,
                "unsafe_type": present and not real_directory,
                "conflicting": present and project_digest != source_digest,
            }
        )

    unsafe_targets = [item for item in planned if item["unsafe_type"]]
    if unsafe_targets:
        paths = ", ".join(str(item["destination"]) for item in unsafe_targets)
        raise FileExistsError(
            "refusing non-directory or symlink project skill paths: " + paths
        )

    manifest_names = {item["entry"]["name"] for item in planned}
    prune_items: list[dict[str, object]] = []
    for old_name, old in previous_by_name.items():
        safe_name(old_name, context=f"locked skill name in {lock_path}")
        if old_name in manifest_names:
            continue
        destination = destination_root / old_name
        present = destination.exists() or destination.is_symlink()
        real_directory = destination.is_dir() and not destination.is_symlink()
        symlinked_tree = real_directory and any(
            item.is_symlink() for item in destination.rglob("*")
        )
        current_digest = (
            digest_tree(destination) if real_directory and not symlinked_tree else None
        )
        prune_items.append(
            {
                "name": old_name,
                "destination": destination,
                "current_digest": current_digest,
                "baseline_digest": old.get("project_sha256") or old.get("sha256"),
                "unsafe_type": (present and not real_directory) or symlinked_tree,
            }
        )

    unsafe_prunes = [
        item
        for item in prune_items
        if item["unsafe_type"]
        or (
            item["current_digest"] is not None
            and item["current_digest"] != item["baseline_digest"]
        )
    ]
    if prune and unsafe_prunes:
        names = ", ".join(item["name"] for item in unsafe_prunes)
        raise SystemExit(f"refusing to prune locally changed skills: {names}")

    conflicts = [item for item in planned if item["conflicting"]]
    if conflicts:
        if dry_run and not conflict:
            conflict = "abort"
        else:
            conflict = choose_conflict_policy(conflicts, conflict)
    if conflicts and conflict == "abort" and not dry_run:
        raise SystemExit("No changes made.")

    if show_diff or dry_run:
        for item in conflicts:
            print(f"\n--- {item['entry']['name']} ---")
            print(tree_diff(item["source"], item["destination"]) or "No text diff.")

    additions = [item for item in planned if not item["present"]]
    print(
        f"Plan: {len(additions)} add, {len(conflicts)} conflict, "
        f"{len(prune_items) if prune else 0} prune; policy={conflict or 'none'}"
    )
    if prune_items and not prune:
        names = ", ".join(item["name"] for item in prune_items)
        print(f"Unselected managed skills retained (use --prune): {names}")
    if dry_run:
        print("Dry run: no files or locks changed.")
        return

    destination_root.mkdir(parents=True, exist_ok=True)
    validate_project_skills_root(project)

    locked: list[dict[str, object]] = []
    for item in planned:
        entry = item["entry"]
        source = item["source"]
        destination = item["destination"]
        current_present = destination.exists() or destination.is_symlink()
        current_real_directory = destination.is_dir() and not destination.is_symlink()
        if current_present and not current_real_directory:
            raise RuntimeError(
                f"project skill path changed during apply: {destination}"
            )
        if not item["present"]:
            if current_present:
                raise RuntimeError(
                    f"project skill appeared during apply: {destination}"
                )
            shutil.copytree(source, destination, symlinks=False)
        elif item["conflicting"] and conflict == "back-propagate":
            if digest_tree(source) != item["source_digest"] or (
                not current_real_directory
                or digest_tree(destination) != item["project_digest"]
            ):
                raise RuntimeError(f"skill changed during apply: {entry['name']}")
            backup_tree(source, project_id, manifest["name"], "workshop", entry["name"])
            replace_tree(destination, source)
        elif item["conflicting"] and conflict == "overwrite":
            if digest_tree(source) != item["source_digest"] or (
                not current_real_directory
                or digest_tree(destination) != item["project_digest"]
            ):
                raise RuntimeError(f"skill changed during apply: {entry['name']}")
            backup_tree(
                destination, project_id, manifest["name"], "project", entry["name"]
            )
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
                "identity": skill_identity(entry["name"], entry["source"]),
                "source_sha256": source_digest,
                "project_sha256": project_digest,
                "status": "synced" if source_digest == project_digest else "diverged",
                **upstream_metadata(source),
            }
        )

    if prune:
        for item in prune_items:
            destination = item["destination"]
            if destination.exists() or destination.is_symlink():
                if (
                    not destination.is_dir()
                    or destination.is_symlink()
                    or digest_tree(destination) != item["current_digest"]
                ):
                    raise RuntimeError(
                        f"managed skill changed during prune: {item['name']}"
                    )
                backup_tree(
                    destination,
                    project_id,
                    manifest["name"],
                    "project-pruned",
                    item["name"],
                )
                shutil.rmtree(destination)

    lock = {
        "schema_version": 2,
        "cluster": manifest["name"],
        "project": {"id": project_id, "remote": project_remote},
        "skills": locked,
    }
    MATERIALIZATIONS.mkdir(parents=True, exist_ok=True)
    temporary = lock_path.with_suffix(lock_path.suffix + ".tmp")
    temporary.write_text(json.dumps(lock, indent=2) + "\n")
    temporary.replace(lock_path)
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
        "--target",
        type=Path,
        default=Path("~/.agents/skills").expanduser(),
        help="user skill directory (default: ~/.agents/skills)",
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
        "--dry-run", action="store_true", help="show the plan and diffs without changes"
    )
    cluster.add_argument(
        "--show-diff", action="store_true", help="show file-level conflict diffs"
    )
    cluster.add_argument(
        "--prune",
        action="store_true",
        help="remove previously managed skills no longer present in the cluster",
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
        apply_cluster(
            args.name,
            args.project,
            args.conflict,
            args.project_id,
            args.dry_run,
            args.prune,
            args.show_diff,
        )
    else:
        configure_upstreams()


if __name__ == "__main__":
    main()
