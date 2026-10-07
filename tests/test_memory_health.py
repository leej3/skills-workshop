"""Isolated health-report checks; these inputs never enter production memory."""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.memory_feedback import capture_feedback
from scripts.memory_health import health, remote_checker
from scripts.memory_store import MemoryStore, canonical
from tests.test_memory_feedback import inputs

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def setup(tmp_path):
    report, request, _ = inputs(tmp_path)
    public, private = tmp_path / "public", tmp_path / "private"
    private.mkdir()
    target = public / "records/2026/10"
    target.mkdir(parents=True)
    row = json.loads(report.read_text())
    source = target / (row["id"] + ".json")
    source.write_bytes(report.read_bytes())
    return MemoryStore(tmp_path / "memory"), public, private, report, request, source


def test_unqueued_use_limit_and_inspection(tmp_path):
    memory, public, private, report, _, _ = setup(tmp_path)
    result = health(memory, "shared", public, private, now=NOW)
    assert result["matching_uses"] == 1
    use = result["uses"][0]
    assert use["storage"]["record"] == "not_queued"
    assert use["missing"] == ["conversation", "duct_logs", "pinned_skill_reference"]
    assert "health --id" in use["inspect_command"]
    ident = json.loads(report.read_text())["id"]
    detail = health(memory, "shared", public, private, now=NOW, observation_id=ident)
    assert detail["uses"][0]["observation"] == json.loads(report.read_text())
    assert not (memory.root / "shared/ledger.sqlite").exists()
    with pytest.raises(ValueError, match="positive"):
        health(memory, "shared", public, private, limit=0, now=NOW)


def test_overlay_never_leaks_into_shared_report(tmp_path):
    memory, public, private, _, _, source = setup(tmp_path)
    overlay = private / source.relative_to(public)
    overlay.parent.mkdir(parents=True)
    row = json.loads(source.read_text())
    row["visibility"] = "private"
    overlay.write_text(json.dumps(row))
    assert health(memory, "shared", public, private, now=NOW)["uses"] == []
    assert len(health(memory, "sensitive", public, private, now=NOW)["uses"]) == 1
    with pytest.raises(ValueError, match="both observation trees"):
        health(memory, "shared", public, private / "missing", now=NOW)


def test_capture_receipts_corruption_and_publication(tmp_path):
    memory, public, private, report, request, _ = setup(tmp_path)
    spec = json.loads(request.read_text())
    spec.update(
        schema_version=2,
        skill_reference={
            "manager": "apm",
            "package": "owner/repo",
            "resolved_commit": "a" * 40,
            "skill": "duct",
        },
    )
    request.write_text(json.dumps(spec))
    result = capture_feedback(memory, report, request, "shared", "unit-test")

    def get():
        return health(memory, "shared", public, private, now=NOW)["uses"][0]

    assert get()["missing"] == []
    assert get()["storage"]["record"] == "journaled"
    assert get()["storage"]["upload"] == "unknown"
    item = result["artifact"]
    receipt = memory.root / "shared/artifact-receipts" / (item["sha256"] + ".json")
    receipt.parent.mkdir()
    receipt.write_text(json.dumps({"sha256": item["sha256"], "key": item["annex_key"]}))
    assert get()["storage"]["upload"] == "receipt_recorded"
    memory.prepare("shared", "2026-10-07", "2099-01-01T00:00:00+00:00")
    assert get()["storage"]["record"] == "pending"
    with memory.ledger("shared") as db:
        db.execute(
            "update batches set state='published',receipt=?",
            (canonical({"commit": "b" * 40}),),
        )
    assert get()["storage"]["upload"] == "confirmed_at_batch_publication"
    (memory.root / "shared/objects" / item["sha256"]).write_bytes(b"corrupt")
    assert "local_payload_corrupt" in get()["issues"]


def test_remote_presence_is_separate_from_publication_and_failure():
    class Transport:
        code = 0

        def git(self, *args, **kwargs):
            if args[0] == "ls-remote":
                return "abc refs/workshop/memory/v2/batch"
            return SimpleNamespace(returncode=self.code)

    transport = Transport()
    check = remote_checker(transport)
    capture = {"external_artifacts": [{"annex_key": "key"}]}
    assert check(capture, {}) == {
        "metadata": "absent",
        "payload": "present",
        "retrievable": False,
    }
    assert check(capture, {"batch_id": "batch"})["retrievable"] is True
    transport.code = 100
    assert check(capture, {"batch_id": "batch"})["payload"] == "unknown"
    transport.code = 1
    assert check(capture, {"batch_id": "batch"})["payload"] == "absent"
    assert (
        check(capture, {"batch_id": "batch", "receipt": {"commit": "changed"}})[
            "metadata"
        ]
        == "mismatch"
    )


def test_cli_json_and_bad_limit(tmp_path):
    memory, public, private, _, _, _ = setup(tmp_path)
    command = [
        sys.executable,
        str(Path(__file__).resolve().parents[1] / "scripts/memory.py"),
        "--state",
        str(memory.root),
        "health",
        "--store",
        "shared",
        "--public",
        str(public),
        "--private",
        str(private),
        "--days",
        "100000",
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0 and json.loads(result.stdout)["matching_uses"] == 1
    result = subprocess.run(
        command + ["--limit", "0"], capture_output=True, text=True, check=False
    )
    assert (
        result.returncode == 1
        and not result.stdout
        and "Traceback" not in result.stderr
    )
