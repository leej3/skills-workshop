"""Safely create and reuse content-addressed skill recovery backups."""

from __future__ import annotations

import hashlib
import os
import re
import secrets
import shutil
import stat
from pathlib import Path

SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


def _declared_skill_name(contents: str) -> str | None:
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


def inspect_snapshot(path: Path, *, expected_name: str) -> str:
    """Validate a real skill snapshot and return its content digest."""
    if not SAFE_NAME.fullmatch(expected_name):
        raise ValueError(f"unsafe backup skill name: {expected_name!r}")
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"backup snapshot is not a real directory: {path}")
    try:
        items = sorted(path.rglob("*"))
    except OSError as error:
        raise ValueError(f"cannot inspect backup snapshot: {path}") from error
    links = [item for item in items if item.is_symlink()]
    if links:
        raise ValueError(f"backup snapshot contains symlinks: {path}")
    special = [item for item in items if not item.is_dir() and not item.is_file()]
    if special:
        raise ValueError(f"backup snapshot contains a special file: {path}")

    skill_file = path / "SKILL.md"
    if not skill_file.is_file() or skill_file.is_symlink():
        raise ValueError(f"backup snapshot has no real SKILL.md: {path}")
    try:
        declared_name = _declared_skill_name(skill_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as error:
        raise ValueError(f"cannot read backup SKILL.md: {skill_file}") from error
    if declared_name != expected_name:
        raise ValueError(
            f"backup snapshot declares {declared_name!r}, expected {expected_name!r}"
        )

    digest = hashlib.sha256()
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    for item in (candidate for candidate in items if candidate.is_file()):
        relative = item.relative_to(path).as_posix()
        try:
            descriptor = os.open(item, os.O_RDONLY | no_follow)
        except OSError as error:
            raise ValueError(f"cannot read backup file: {item}") from error
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError(f"backup file is not regular: {item}")
            digest.update(relative.encode())
            digest.update(b"\0")
            while chunk := os.read(descriptor, 1024 * 1024):
                digest.update(chunk)
            digest.update(b"\0")
        finally:
            os.close(descriptor)
    return digest.hexdigest()


def verify_snapshot(
    path: Path,
    *,
    expected_name: str,
    expected_digest: str,
) -> None:
    actual = inspect_snapshot(path, expected_name=expected_name)
    if actual != expected_digest:
        raise ValueError(
            f"backup content digest mismatch at {path}: "
            f"expected {expected_digest}, found {actual}"
        )


def _directory_flags() -> int:
    no_follow = getattr(os, "O_NOFOLLOW", 0)
    directory_only = getattr(os, "O_DIRECTORY", 0)
    if not no_follow or not directory_only or not shutil.rmtree.avoids_symlink_attacks:
        raise RuntimeError("safe descriptor-based backup storage is unavailable")
    return os.O_RDONLY | no_follow | directory_only


def _inode(result: os.stat_result) -> tuple[int, int]:
    return result.st_dev, result.st_ino


def _open_real_directory(
    parent: int,
    name: str,
    expected: os.stat_result,
) -> int:
    if not stat.S_ISDIR(expected.st_mode):
        raise ValueError(f"backup path component is not a real directory: {name}")
    try:
        descriptor = os.open(name, _directory_flags(), dir_fd=parent)
    except OSError as error:
        raise ValueError(
            f"backup path component is not a real directory: {name}"
        ) from error
    if _inode(os.fstat(descriptor)) != _inode(expected):
        os.close(descriptor)
        raise RuntimeError(f"backup path changed during storage: {name}")
    return descriptor


def _ensure_real_directory(parent: int, name: str) -> tuple[int, tuple[int, int]]:
    try:
        os.mkdir(name, dir_fd=parent)
    except FileExistsError:
        pass
    try:
        result = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except OSError as error:
        raise ValueError(f"cannot create backup directory: {name}") from error
    descriptor = _open_real_directory(parent, name, result)
    return descriptor, _inode(result)


def _descriptor_entries(descriptor: int) -> list[tuple[str, os.stat_result]]:
    try:
        with os.scandir(descriptor) as entries:
            return sorted(
                ((entry.name, entry.stat(follow_symlinks=False)) for entry in entries),
                key=lambda item: item[0],
            )
    except OSError as error:
        raise ValueError("cannot inspect descriptor-anchored backup") from error


def _read_file(
    parent: int,
    name: str,
    expected: os.stat_result,
) -> bytes:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=parent,
        )
    except OSError as error:
        raise ValueError(f"cannot read backup file: {name}") from error
    try:
        current = os.fstat(descriptor)
        if _inode(current) != _inode(expected) or not stat.S_ISREG(current.st_mode):
            raise ValueError(f"backup file changed during inspection: {name}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _read_tree(
    descriptor: int,
    relative: tuple[str, ...] = (),
) -> list[tuple[str, bytes]]:
    files: list[tuple[str, bytes]] = []
    for name, entry_stat in _descriptor_entries(descriptor):
        path = (*relative, name)
        if stat.S_ISDIR(entry_stat.st_mode):
            child = _open_real_directory(descriptor, name, entry_stat)
            try:
                files.extend(_read_tree(child, path))
            finally:
                os.close(child)
        elif stat.S_ISREG(entry_stat.st_mode):
            files.append(("/".join(path), _read_file(descriptor, name, entry_stat)))
        else:
            raise ValueError("backup snapshot contains a symlink or special file")
    return files


def _inspect_descriptor(descriptor: int, *, expected_name: str) -> str:
    files = _read_tree(descriptor)
    skill_files = [contents for path, contents in files if path == "SKILL.md"]
    if len(skill_files) != 1:
        raise ValueError("backup snapshot has no real SKILL.md")
    try:
        declared_name = _declared_skill_name(skill_files[0].decode("utf-8"))
    except UnicodeDecodeError as error:
        raise ValueError("cannot read backup SKILL.md") from error
    if declared_name != expected_name:
        raise ValueError(
            f"backup snapshot declares {declared_name!r}, expected {expected_name!r}"
        )
    digest = hashlib.sha256()
    for relative, contents in sorted(files):
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(contents)
        digest.update(b"\0")
    return digest.hexdigest()


def _verify_descriptor(
    descriptor: int,
    *,
    expected_name: str,
    expected_digest: str,
) -> None:
    actual = _inspect_descriptor(descriptor, expected_name=expected_name)
    if actual != expected_digest:
        raise ValueError(
            f"backup content digest mismatch: expected {expected_digest}, "
            f"found {actual}"
        )


def _copy_tree(source: int, destination: int) -> None:
    for name, entry_stat in _descriptor_entries(source):
        if stat.S_ISDIR(entry_stat.st_mode):
            os.mkdir(name, dir_fd=destination)
            source_child = _open_real_directory(source, name, entry_stat)
            destination_stat = os.stat(
                name,
                dir_fd=destination,
                follow_symlinks=False,
            )
            destination_child = _open_real_directory(
                destination,
                name,
                destination_stat,
            )
            try:
                _copy_tree(source_child, destination_child)
                os.fchmod(destination_child, stat.S_IMODE(entry_stat.st_mode))
            finally:
                os.close(destination_child)
                os.close(source_child)
        elif stat.S_ISREG(entry_stat.st_mode):
            source_file = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=source,
            )
            try:
                if _inode(os.fstat(source_file)) != _inode(entry_stat):
                    raise RuntimeError(f"skill changed while creating backup: {name}")
                destination_file = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    stat.S_IMODE(entry_stat.st_mode),
                    dir_fd=destination,
                )
                try:
                    while chunk := os.read(source_file, 1024 * 1024):
                        view = memoryview(chunk)
                        while view:
                            written = os.write(destination_file, view)
                            view = view[written:]
                    os.fchmod(destination_file, stat.S_IMODE(entry_stat.st_mode))
                finally:
                    os.close(destination_file)
            finally:
                os.close(source_file)
        else:
            raise ValueError("skill changed to a symlink or special file during backup")


def _open_existing_snapshot(parent: int, digest: str) -> int | None:
    try:
        result = os.stat(digest, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    return _open_real_directory(parent, digest, result)


def _assert_root(root: Path, root_descriptor: int) -> None:
    try:
        current = os.stat(root, follow_symlinks=False)
    except OSError as error:
        raise RuntimeError("backup root changed during storage") from error
    if _inode(current) != _inode(os.fstat(root_descriptor)) or not stat.S_ISDIR(
        current.st_mode
    ):
        raise RuntimeError("backup root changed during storage")


def _assert_component_chain(
    root_descriptor: int,
    components: tuple[str, ...],
    identities: tuple[tuple[int, int], ...],
) -> None:
    descriptors = [os.dup(root_descriptor)]
    try:
        parent = descriptors[0]
        for name, expected_inode in zip(components, identities, strict=True):
            try:
                result = os.stat(name, dir_fd=parent, follow_symlinks=False)
            except OSError as error:
                raise RuntimeError("backup path changed during storage") from error
            child = _open_real_directory(parent, name, result)
            descriptors.append(child)
            if _inode(os.fstat(child)) != expected_inode:
                raise RuntimeError("backup path changed during storage")
            parent = child
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def _safe_component(value: str) -> bool:
    return bool(value and value not in {".", ".."} and Path(value).name == value)


def store_snapshot(
    source: Path,
    root: Path,
    components: tuple[str, ...],
    *,
    expected_name: str,
) -> Path:
    """Stage, verify, publish, and retain a descriptor-anchored skill backup."""
    if not components or any(not _safe_component(item) for item in components):
        raise ValueError(f"unsafe backup layout components: {components!r}")
    expected_digest = inspect_snapshot(source, expected_name=expected_name)
    try:
        os.mkdir(root)
    except FileExistsError:
        pass
    try:
        root_descriptor = os.open(root, _directory_flags())
    except OSError as error:
        raise ValueError(f"backup root is not a real directory: {root}") from error

    descriptors: list[int] = [root_descriptor]
    identities: list[tuple[int, int]] = []
    staged: str | None = None
    destination_descriptor: int | None = None
    try:
        _assert_root(root, root_descriptor)
        parent = root_descriptor
        for component in components:
            child, identity = _ensure_real_directory(parent, component)
            descriptors.append(child)
            identities.append(identity)
            parent = child

        destination_descriptor = _open_existing_snapshot(parent, expected_digest)
        if destination_descriptor is None:
            staged = f".skills-workshop-backup-{secrets.token_hex(8)}"
            os.mkdir(staged, dir_fd=parent)
            staged_stat = os.stat(staged, dir_fd=parent, follow_symlinks=False)
            staged_descriptor = _open_real_directory(parent, staged, staged_stat)
            try:
                source_stat = os.stat(source, follow_symlinks=False)
                source_descriptor = os.open(source, _directory_flags())
                try:
                    if _inode(os.fstat(source_descriptor)) != _inode(source_stat):
                        raise RuntimeError(
                            f"skill changed while creating backup: {source}"
                        )
                    _copy_tree(source_descriptor, staged_descriptor)
                    os.fchmod(staged_descriptor, stat.S_IMODE(source_stat.st_mode))
                finally:
                    os.close(source_descriptor)
                _verify_descriptor(
                    staged_descriptor,
                    expected_name=expected_name,
                    expected_digest=expected_digest,
                )
            finally:
                os.close(staged_descriptor)
            if inspect_snapshot(source, expected_name=expected_name) != expected_digest:
                raise RuntimeError(f"skill changed while creating backup: {source}")
            try:
                os.rename(
                    staged,
                    expected_digest,
                    src_dir_fd=parent,
                    dst_dir_fd=parent,
                )
                staged = None
            except OSError:
                destination_descriptor = _open_existing_snapshot(
                    parent,
                    expected_digest,
                )
                if destination_descriptor is None:
                    raise
            if destination_descriptor is None:
                destination_descriptor = _open_existing_snapshot(
                    parent,
                    expected_digest,
                )
                if destination_descriptor is None:
                    raise RuntimeError("published backup disappeared during storage")

        _verify_descriptor(
            destination_descriptor,
            expected_name=expected_name,
            expected_digest=expected_digest,
        )
        if inspect_snapshot(source, expected_name=expected_name) != expected_digest:
            raise RuntimeError(f"skill changed while creating backup: {source}")
        _assert_root(root, root_descriptor)
        _assert_component_chain(
            root_descriptor,
            components,
            tuple(identities),
        )
        destination_stat = os.stat(
            expected_digest,
            dir_fd=parent,
            follow_symlinks=False,
        )
        if _inode(destination_stat) != _inode(os.fstat(destination_descriptor)):
            raise RuntimeError("backup destination changed during storage")
        os.utime(destination_descriptor, None)
        _assert_root(root, root_descriptor)
        _assert_component_chain(
            root_descriptor,
            components,
            tuple(identities),
        )
        return root.joinpath(*components, expected_digest)
    finally:
        if destination_descriptor is not None:
            os.close(destination_descriptor)
        if staged is not None:
            try:
                shutil.rmtree(staged, dir_fd=descriptors[-1])
            except FileNotFoundError:
                pass
        for descriptor in reversed(descriptors):
            os.close(descriptor)
