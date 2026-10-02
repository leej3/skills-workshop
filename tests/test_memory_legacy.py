import json

import pytest

from scripts.memory_legacy import recover, snapshot, working_tree
from scripts.memory_store import MemoryStore


def test_snapshot_roundtrip_and_overlay_exclusion(tmp_path):
    source = tmp_path / "source"
    (source / "skills").mkdir(parents=True)
    (source / "observations").mkdir()
    raw = b'{"name": "exact original bytes"}\n'
    (source / "skills/a.json").write_bytes(raw)
    (source / "observations/private.json").write_text('{"private": true}')
    memory = MemoryStore(tmp_path / "state")
    first = snapshot(memory, source)
    assert first["files"] == 1
    assert snapshot(memory, source)["duplicate"]
    item = first["artifact"]
    archive = (memory.store_root("shared") / "objects" / item["sha256"]).read_bytes()
    destination = tmp_path / "restored"
    assert recover(archive, destination)["files"] == 1
    assert (destination / "skills/a.json").read_bytes() == raw
    assert not (destination / "observations").exists()
    with pytest.raises(ValueError, match="must not exist"):
        recover(archive, destination)
    (source / "skills/a.json").write_text('{"updated": true}')
    assert snapshot(memory, source)["id"] != first["id"]


def test_working_tree_is_explicit_and_does_not_recreate_repository_memory(
    tmp_path, monkeypatch
):
    assert working_tree(tmp_path) == tmp_path / "memory"
    (tmp_path / "memory-storage.json").write_text(json.dumps({"backend": "annex"}))
    external = tmp_path / "external"
    monkeypatch.setenv("WORKSHOP_MEMORY_WORKTREE", str(external))
    assert working_tree(tmp_path) == external
    assert not (tmp_path / "memory").exists()


def test_recover_rejects_parent_paths_before_writing(tmp_path):
    import base64

    from scripts.memory_capture import store_archive

    memory = MemoryStore(tmp_path / "state")
    item = store_archive(
        memory,
        "shared",
        "bad.tar.gz",
        {
            "files.json": json.dumps(
                {"../escape": base64.b64encode(b"x").decode()}
            ).encode()
        },
    )
    raw = (memory.store_root("shared") / "objects" / item["sha256"]).read_bytes()
    with pytest.raises(ValueError, match="invalid curated path"):
        recover(raw, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_empty_snapshot_and_missing_source(tmp_path):
    memory = MemoryStore(tmp_path / "state")
    with pytest.raises(ValueError, match="missing"):
        snapshot(memory, tmp_path / "absent")
    source = tmp_path / "empty"
    source.mkdir()
    result = snapshot(memory, source)
    assert result["files"] == 0 and result["artifact"]


def test_bad_archive_cli_has_clean_error(tmp_path):
    import subprocess
    import sys

    bad = tmp_path / "bad.tar.gz"
    bad.write_bytes(b"bad")
    result = subprocess.run(
        [
            sys.executable,
            "scripts/memory.py",
            "--state",
            str(tmp_path / "state"),
            "restore-curated",
            str(bad),
            "--output",
            str(tmp_path / "new"),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "new").exists()
