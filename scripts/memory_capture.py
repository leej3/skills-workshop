"""Retain finished duct runs as separately retrievable annex artifacts."""

import gzip
import io
import json
import tarfile
import uuid
from pathlib import Path

from scripts.memory_store import atomic_bytes, digest, envelope, validate


def store_archive(memory, store, name, files):
    """Stage exact named bytes as an on-demand artifact, irrespective of size."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for filename, data in sorted(files.items()):
            if Path(filename).name != filename or filename in (".", ".."):
                raise ValueError("archive names must be plain filenames")
            member = tarfile.TarInfo(filename)
            member.size = len(data)
            member.mode = 0o600
            archive.addfile(member, io.BytesIO(data))
    raw = gzip.compress(buffer.getvalue(), mtime=0)
    sha = digest(raw)
    item = {
        "name": name,
        "sha256": sha,
        "size": len(raw),
        "store": store,
        "annex_key": f"SHA256-s{len(raw)}--{sha}",
    }
    target = memory.store_root(store) / "objects" / sha
    if target.exists() and target.read_bytes() != raw:
        raise ValueError("local artifact conflicts with capture")
    atomic_bytes(target, raw)
    return item


def capture_duct(memory, directory, store, agent, reason=None, related=None):
    directory = Path(directory).resolve()
    info = json.loads((directory / "run_info.json").read_bytes())
    context = json.loads((directory / "context.json").read_bytes())
    summary = info.get("execution_summary")
    if (
        not isinstance(summary, dict)
        or summary.get("exit_code") is None
        or summary.get("end_time") is None
    ):
        raise ValueError("duct run has not finished")
    files = {}
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise ValueError("capture must contain regular files only")
        files[path.name] = path.read_bytes()
    item = store_archive(memory, store, "duct-capture.tar.gz", files)
    sha = item["sha256"]
    row = envelope(
        {
            "capture_id": directory.name,
            "project_id": context.get("project_id"),
            "command": info.get("command"),
            "execution_summary": summary,
            "measurement_scope": "local process tree; remote compute and cost unknown",
        },
        ident=str(uuid.uuid5(uuid.NAMESPACE_URL, "workshop:duct:" + store + ":" + sha)),
        kind="evidence",
        occurred_at=context["started_at"],
        store=store,
        producer="con-duct",
        version=info.get("duct_version"),
        source_schema=info.get("schema_version", "unknown"),
        reason=reason,
        context={
            "agent_id": agent,
            "conditions": {
                "capture": "complete-finished-run",
                "git_commit": context.get("git_commit"),
                "git_dirty": context.get("git_dirty"),
            },
        },
        relations=[{"relation": "supports", "id": related}] if related else [],
    )
    row["external_artifacts"] = [item]
    validate(row)
    result = memory.append(row, agent)
    return {**result, "artifact": item}
