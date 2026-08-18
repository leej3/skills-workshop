#!/usr/bin/env python3
"""Link the global core profile or copy a skill bundle into a project."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import secrets
import shutil
import stat as stat_module
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import tomllib

try:
    from .backup_store import store_snapshot
except ImportError:  # Direct execution: python scripts/manage_skills.py
    from backup_store import store_snapshot

REPOSITORY = Path(__file__).resolve().parents[1]
CORE_STATE = ".skills-workshop-core.json"
MATERIALIZATIONS = REPOSITORY / "materializations"
BACKUPS = REPOSITORY / ".backups"
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
SAFE_PROJECT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
BACKUP_DIGEST = re.compile(r"[0-9a-f]{64}")
BACKUP_SIDES = frozenset({"project", "project-pruned", "workshop"})
DEFAULT_BACKUP_RETENTION_DAYS = 30


def safe_name(value: object, *, context: str) -> str:
    if not isinstance(value, str) or not SAFE_NAME.fullmatch(value):
        raise ValueError(f"unsafe {context} {value!r}")
    return value


def _declared_skill_name_text(contents: str) -> str | None:
    lines = contents.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("'\"") or None
    return None


def declared_skill_name(skill_file: Path) -> str | None:
    return _declared_skill_name_text(skill_file.read_text(encoding="utf-8"))


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
    path: Path, *, bundle: str, project_id: str
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
    if data.get("bundle") != bundle:
        raise ValueError(f"coordination lock bundle does not match {bundle!r}: {path}")
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
    path: Path, project_id: str, bundle: str, side: str, name: str
) -> Path | None:
    if not path.is_dir() or path.is_symlink():
        return None
    return store_snapshot(
        path,
        BACKUPS,
        (f"{project_id}--{bundle}", side, name),
        expected_name=name,
    )


def _directory_flags() -> int:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    directory_only = getattr(os, "O_DIRECTORY", 0)
    if not no_follow or not directory_only or not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError("safe descriptor-based backup cleanup is unavailable")
    return os.O_RDONLY | no_follow | directory_only


def _inode(stat: os.stat_result) -> tuple[int, int]:
    return stat.st_dev, stat.st_ino


def _snapshot(stat: os.stat_result) -> tuple[int, int, int]:
    return stat.st_dev, stat.st_ino, stat.st_mtime_ns


def _open_real_directory(
    parent: int,
    name: str,
    expected: os.stat_result,
) -> int:
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent)
    except OSError as error:
        raise RuntimeError(f"backup path changed during cleanup: {name}") from error
    if _inode(os.fstat(descriptor)) != _inode(expected):
        os.close(descriptor)
        raise RuntimeError(f"backup path changed during cleanup: {name}")
    return descriptor


def _entries(descriptor: int) -> list[tuple[str, os.stat_result]]:
    try:
        with os.scandir(descriptor) as entries:
            return sorted(
                ((entry.name, entry.stat(follow_symlinks=False)) for entry in entries),
                key=lambda item: item[0],
            )
    except OSError as error:
        raise RuntimeError("backup directory changed during cleanup") from error


def _read_regular_file(
    parent: int,
    name: str,
    expected: os.stat_result,
) -> bytes | None:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, os.O_RDONLY | no_follow, dir_fd=parent)
    except OSError:
        return None
    try:
        current = os.fstat(descriptor)
        if _inode(current) != _inode(expected) or not stat_module.S_ISREG(
            current.st_mode
        ):
            return None
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_skill_tree(
    descriptor: int,
    relative: tuple[str, ...] = (),
) -> list[tuple[str, bytes]] | None:
    files: list[tuple[str, bytes]] = []
    for name, entry_stat in _entries(descriptor):
        path = (*relative, name)
        if stat_module.S_ISLNK(entry_stat.st_mode):
            return None
        if stat_module.S_ISDIR(entry_stat.st_mode):
            try:
                child = _open_real_directory(descriptor, name, entry_stat)
            except RuntimeError:
                return None
            try:
                nested = _read_skill_tree(child, path)
            finally:
                os.close(child)
            if nested is None:
                return None
            files.extend(nested)
        elif stat_module.S_ISREG(entry_stat.st_mode):
            contents = _read_regular_file(descriptor, name, entry_stat)
            if contents is None:
                return None
            files.append(("/".join(path), contents))
        else:
            return None
    return files


def _inspect_backup_tree(
    descriptor: int,
    *,
    expected_name: str,
    expected_digest: str,
) -> tuple[int, int, int] | None:
    before = os.fstat(descriptor)
    files = _read_skill_tree(descriptor)
    after = os.fstat(descriptor)
    if files is None or _snapshot(after) != _snapshot(before):
        return None
    skill_files = [contents for path, contents in files if path == "SKILL.md"]
    if len(skill_files) != 1:
        return None
    try:
        declared_name = _declared_skill_name_text(skill_files[0].decode("utf-8"))
    except UnicodeDecodeError:
        return None
    if declared_name != expected_name:
        return None

    digest = hashlib.sha256()
    for relative, contents in sorted(files):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(contents)
        digest.update(b"\0")
    if digest.hexdigest() != expected_digest:
        return None
    return _snapshot(after)


def _scan_backup_layout(
    descriptor: int,
    prefix: Path,
    validators: tuple[Callable[[str], bool], ...],
    candidates: list[tuple[Path, tuple[int, int, int]]],
    unsafe: list[Path],
    level: int = 0,
) -> None:
    for name, entry_stat in _entries(descriptor):
        relative = prefix / name
        if not stat_module.S_ISDIR(entry_stat.st_mode) or not validators[level](name):
            unsafe.append(relative)
            continue
        try:
            child = _open_real_directory(descriptor, name, entry_stat)
        except RuntimeError:
            unsafe.append(relative)
            continue
        try:
            if level + 1 < len(validators):
                _scan_backup_layout(
                    child,
                    relative,
                    validators,
                    candidates,
                    unsafe,
                    level + 1,
                )
                continue
            snapshot = _inspect_backup_tree(
                child,
                expected_name=relative.parts[-2],
                expected_digest=name,
            )
            if snapshot is None:
                unsafe.append(relative)
            else:
                candidates.append((relative, snapshot))
        finally:
            os.close(child)


def _materialization_collection(name: str) -> bool:
    project_id, separator, bundle = name.rpartition("--")
    return bool(
        separator
        and SAFE_PROJECT_ID.fullmatch(project_id)
        and SAFE_NAME.fullmatch(bundle)
    )


def _backup_candidates(
    root_descriptor: int,
) -> tuple[list[tuple[Path, tuple[int, int, int]]], list[Path]]:
    """Find only valid skill snapshots in recognized workshop backup layouts."""
    candidates: list[tuple[Path, tuple[int, int, int]]] = []
    unsafe: list[Path] = []
    for name, entry_stat in _entries(root_descriptor):
        relative = Path(name)
        if not stat_module.S_ISDIR(entry_stat.st_mode):
            unsafe.append(relative)
            continue
        if name == "project-import":
            validators: tuple[Callable[[str], bool], ...] = (
                lambda value: bool(SAFE_NAME.fullmatch(value)),
                lambda value: bool(BACKUP_DIGEST.fullmatch(value)),
            )
        elif _materialization_collection(name):
            validators = (
                lambda value: value in BACKUP_SIDES,
                lambda value: bool(SAFE_NAME.fullmatch(value)),
                lambda value: bool(BACKUP_DIGEST.fullmatch(value)),
            )
        else:
            unsafe.append(relative)
            continue
        try:
            collection = _open_real_directory(root_descriptor, name, entry_stat)
        except RuntimeError:
            unsafe.append(relative)
            continue
        try:
            _scan_backup_layout(
                collection,
                relative,
                validators,
                candidates,
                unsafe,
            )
        finally:
            os.close(collection)
    return sorted(candidates), sorted(set(unsafe))


def _assert_root_identity(
    root: Path,
    expected: tuple[int, int],
) -> None:
    try:
        current = os.stat(root, follow_symlinks=False)
    except OSError as error:
        raise RuntimeError("backup root changed during cleanup") from error
    if _inode(current) != expected or not stat_module.S_ISDIR(current.st_mode):
        raise RuntimeError("backup root changed during cleanup")


def _remove_backup_tree(
    root_descriptor: int,
    candidate: Path,
    snapshot: tuple[int, int, int],
) -> None:
    """Remove a verified backup through descriptors anchored at BACKUPS."""
    descriptors: list[int] = []
    try:
        parent = os.dup(root_descriptor)
        descriptors.append(parent)
        for part in candidate.parts[:-1]:
            entry_stat = os.stat(part, dir_fd=parent, follow_symlinks=False)
            parent = _open_real_directory(parent, part, entry_stat)
            descriptors.append(parent)

        current_stat = os.stat(
            candidate.name,
            dir_fd=parent,
            follow_symlinks=False,
        )
        if _snapshot(current_stat) != snapshot or not stat_module.S_ISDIR(
            current_stat.st_mode
        ):
            raise RuntimeError(f"backup changed during cleanup: {candidate}")

        quarantine = f".skills-workshop-delete-{candidate.name}-{secrets.token_hex(8)}"
        os.rename(
            candidate.name,
            quarantine,
            src_dir_fd=parent,
            dst_dir_fd=parent,
        )
        try:
            quarantine_stat = os.stat(
                quarantine,
                dir_fd=parent,
                follow_symlinks=False,
            )
            quarantine_descriptor = _open_real_directory(
                parent,
                quarantine,
                quarantine_stat,
            )
            try:
                valid = _inspect_backup_tree(
                    quarantine_descriptor,
                    expected_name=candidate.parts[-2],
                    expected_digest=candidate.name,
                )
            finally:
                os.close(quarantine_descriptor)
            if valid != snapshot:
                raise RuntimeError(f"backup changed during cleanup: {candidate}")
            shutil.rmtree(quarantine, dir_fd=parent)
        except Exception:
            os.rename(
                quarantine,
                candidate.name,
                src_dir_fd=parent,
                dst_dir_fd=parent,
            )
            raise
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def cleanup_backups(
    root: Path,
    *,
    retention_days: int = DEFAULT_BACKUP_RETENTION_DAYS,
    apply: bool = False,
    now: float | None = None,
) -> dict[str, tuple[str, ...]]:
    """Preview or remove real backup trees at least ``retention_days`` old."""
    if retention_days < 1:
        raise ValueError("backup retention must be at least one day")
    try:
        root_descriptor = os.open(root, _directory_flags())
    except FileNotFoundError:
        return {"expired": (), "retained": (), "unsafe": (), "removed": ()}
    except OSError as error:
        raise ValueError(f"backup root is not a real directory: {root}") from error

    try:
        root_identity = _inode(os.fstat(root_descriptor))
        _assert_root_identity(root, root_identity)
        candidates, unsafe = _backup_candidates(root_descriptor)
        _assert_root_identity(root, root_identity)
        current_time = time.time() if now is None else now
        cutoff = current_time - retention_days * 24 * 60 * 60
        expired: list[Path] = []
        retained: list[Path] = []
        snapshots: dict[Path, tuple[int, int, int]] = {}
        for candidate, snapshot in candidates:
            snapshots[candidate] = snapshot
            modified = snapshot[2] / 1_000_000_000
            (expired if modified <= cutoff else retained).append(candidate)

        removed: list[Path] = []
        if apply:
            for candidate in expired:
                _assert_root_identity(root, root_identity)
                _remove_backup_tree(
                    root_descriptor,
                    candidate,
                    snapshots[candidate],
                )
                removed.append(candidate)
            _assert_root_identity(root, root_identity)

        def relative(paths: list[Path]) -> tuple[str, ...]:
            return tuple(path.as_posix() for path in sorted(set(paths)))

        return {
            "expired": relative(expired),
            "retained": relative(retained),
            "unsafe": relative(unsafe),
            "removed": relative(removed),
        }
    finally:
        os.close(root_descriptor)


def report_backup_cleanup(
    *,
    retention_days: int = DEFAULT_BACKUP_RETENTION_DAYS,
    apply: bool = False,
) -> None:
    result = cleanup_backups(
        BACKUPS,
        retention_days=retention_days,
        apply=apply,
    )
    action = "Removed" if apply else "Would remove"
    print(
        f"{action} {len(result['removed'] if apply else result['expired'])} "
        f"backup(s) at least {retention_days} days old."
    )
    for path in result["removed"] if apply else result["expired"]:
        print(f"  {path}")
    if result["unsafe"]:
        print(
            f"Skipped {len(result['unsafe'])} unrecognized, corrupt, or unsafe path(s):"
        )
        for path in result["unsafe"]:
            print(f"  {path}")
    if not apply:
        print("Dry run: rerun with --apply to delete expired backups.")


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


def apply_bundle(
    name: str,
    project: Path,
    conflict: str | None,
    requested_project_id: str | None,
    dry_run: bool = False,
    prune: bool = False,
    show_diff: bool = False,
) -> None:
    safe_name(name, context="bundle name")
    manifest_path = REPOSITORY / "bundles" / f"{name}.toml"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"unknown bundle: {name}")
    manifest = load_manifest(manifest_path)
    if manifest["name"] != name:
        raise ValueError(
            f"bundle filename/name mismatch: requested {name!r}, "
            f"manifest declares {manifest['name']!r}"
        )
    project = project.resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"project does not exist: {project}")
    project_id, project_remote = project_identity(project, requested_project_id)
    destination_root = validate_project_skills_root(project)
    lock_path = MATERIALIZATIONS / f"{project_id}--{manifest['name']}.lock.json"
    previous_lock = load_previous_lock(
        lock_path, bundle=manifest["name"], project_id=project_id
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
        "bundle": manifest["name"],
        "project": {"id": project_id, "remote": project_remote},
        "skills": locked,
    }
    MATERIALIZATIONS.mkdir(parents=True, exist_ok=True)
    temporary = lock_path.with_suffix(lock_path.suffix + ".tmp")
    temporary.write_text(json.dumps(lock, indent=2) + "\n")
    temporary.replace(lock_path)
    print(f"Bundle {name}: {len(locked)} copied skills into {destination_root}")
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
    bundle = commands.add_parser("apply-bundle", help="copy a bundle into a project")
    bundle.add_argument("name")
    bundle.add_argument("project", type=Path)
    bundle.add_argument(
        "--conflict",
        choices=("abort", "record", "back-propagate", "overwrite"),
        help="conflict policy; omit to choose from a menu in an interactive terminal",
    )
    bundle.add_argument(
        "--dry-run", action="store_true", help="show the plan and diffs without changes"
    )
    bundle.add_argument(
        "--show-diff", action="store_true", help="show file-level conflict diffs"
    )
    bundle.add_argument(
        "--prune",
        action="store_true",
        help="remove previously managed skills no longer present in the bundle",
    )
    bundle.add_argument(
        "--project-id",
        help="stable lock name; defaults to the project's origin remote or directory name",
    )
    commands.add_parser(
        "configure-upstreams",
        help="configure fork origins and canonical upstream remotes",
    )
    cleanup = commands.add_parser(
        "cleanup-backups",
        help="preview or remove expired local recovery backups",
    )
    cleanup.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_BACKUP_RETENTION_DAYS,
        help=f"expire backups after this many days (default: {DEFAULT_BACKUP_RETENTION_DAYS})",
    )
    cleanup.add_argument(
        "--apply",
        action="store_true",
        help="delete expired backups; without this flag the command is a dry run",
    )
    args = parser.parse_args()

    if args.command == "link-core":
        link_core(args.target)
    elif args.command == "apply-bundle":
        apply_bundle(
            args.name,
            args.project,
            args.conflict,
            args.project_id,
            args.dry_run,
            args.prune,
            args.show_diff,
        )
    elif args.command == "cleanup-backups":
        report_backup_cleanup(
            retention_days=args.retention_days,
            apply=args.apply,
        )
    else:
        configure_upstreams()


if __name__ == "__main__":
    main()
