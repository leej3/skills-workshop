"""Annex retention and explicit recovery for the curated v0 working tree.

This adapter preserves original files without making them the interchange format
for new assessments. Observations are routed separately with their private overlay.
"""

import base64
import io
import json
import os
import tarfile
import uuid
from pathlib import Path

from scripts.memory_capture import store_archive
from scripts.memory_store import atomic_bytes, canonical, envelope


def working_tree(root):
    root = Path(root)
    if not (root / "memory-storage.json").is_file():
        return root / "memory"
    return Path(
        os.environ.get(
            "WORKSHOP_MEMORY_WORKTREE",
            Path.home() / ".local/state/skills-workshop/memory/legacy",
        )
    ).expanduser()


def snapshot(memory, directory):
    """Retain curated families; feedback must go through overlay-aware import."""
    if not directory.is_dir():
        raise ValueError("curated working tree is missing")
    files = {}
    for path in sorted(directory.rglob("*.json")):
        relative = path.relative_to(directory)
        if relative.parts[0] == "observations":
            continue
        if relative.parts[0] not in {
            "skills",
            "projects",
            "events",
            "evaluations",
            "tags",
            "bundles",
        }:
            raise ValueError("unsupported curated family")
        if path.is_symlink() or not path.is_file():
            raise ValueError("legacy snapshots require regular files")
        files[relative.as_posix()] = base64.b64encode(path.read_bytes()).decode()
    item = store_archive(
        memory,
        "shared",
        "curated-memory.tar.gz",
        {"files.json": canonical(files).encode()},
    )
    # Content identity is independent of file mtimes and archive/recovery location.
    row = envelope(
        {
            "format": "curated-files-v1",
            "files": len(files),
            "time_basis": "unknown; epoch sentinel",
            "sha256": item["sha256"],
        },
        ident=str(uuid.uuid5(uuid.NAMESPACE_URL, "workshop:curated:" + item["sha256"])),
        kind="evidence",
        occurred_at="1970-01-01T00:00:00Z",
        store="shared",
        producer="workshop-curated",
        source_schema="curated-files-v1",
    )
    row["external_artifacts"] = [item]
    return {
        **memory.append(row, "curated-snapshot"),
        "files": len(files),
        "artifact": item,
    }


def recover(raw, destination):
    """Restore into a new directory only, checking all paths before writing."""
    if destination.exists():
        raise ValueError("restore destination must not exist")
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        if (
            len(members) != 1
            or members[0].name != "files.json"
            or not members[0].isfile()
        ):
            raise ValueError("invalid curated archive")
        files = json.load(archive.extractfile(members[0]))
    if not isinstance(files, dict):
        raise TypeError("invalid curated file map")
    decoded = {}
    for name, data in files.items():
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not path.parts
            or path.parts[0] == "observations"
        ):
            raise ValueError("invalid curated path")
        decoded[path] = base64.b64decode(data, validate=True)
    destination.mkdir(parents=True, mode=0o700)
    for path, content in decoded.items():
        atomic_bytes(destination / path, content)
    return {"files": len(decoded), "directory": str(destination)}
