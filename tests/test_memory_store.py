import copy
import json
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest

from scripts.memory import rebuild_index, restore
from scripts.memory_store import MemoryStore, artifact, digest, envelope


def row(i, store="shared"):
    return envelope(
        {"future_native_field": i},
        ident=str(uuid.UUID(int=i + 1)),
        kind="observation",
        occurred_at="2026-10-01T00:00:00Z",
        store=store,
        producer="fixture",
        source_schema="fixture-v1",
        reason="synthetic private evidence" if store == "sensitive" else None,
        artifacts=[artifact("raw.txt", b"original\x00bytes")],
    )


def seal(memory, day="2099-01-01"):
    return memory.prepare("shared", day, "2099-01-02T00:00:00+00:00")


def test_multi_agent_batches_and_retries(tmp_path):
    memory = MemoryStore(tmp_path)

    def write(agent):
        for i in range(agent * 613, (agent + 1) * 613):
            memory.append(row(i), str(agent))

    with ThreadPoolExecutor(4) as pool:
        list(pool.map(write, range(4)))
    batches = seal(memory)
    assert sorted(len(json.loads(b["body"])["records"]) for b in batches) == [
        452,
        1000,
        1000,
    ]
    assert seal(memory) == batches
    memory.append(row(3000), "late")
    assert seal(memory) == batches
    assert len(seal(memory, "2099-01-02")) == 4


def test_cross_agent_dedup_conflicts_and_classification(tmp_path):
    memory = MemoryStore(tmp_path)
    memory.append(row(1), "a")
    memory.append(row(1), "b")
    assert len(json.loads(seal(memory)[0]["body"])["records"]) == 1
    changed = row(1)
    changed["payload"] = {"different": True}
    with pytest.raises(ValueError, match="conflicts"):
        memory.append(changed, "c")
    with pytest.raises(ValueError, match="classification"):
        memory.append(row(1, "sensitive"), "a")
    private = row(2, "sensitive")
    memory.append(private, "a")
    assert next(memory.records("shared"))["id"] != private["id"]
    invalid = copy.deepcopy(private)
    invalid["artifacts"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="digest"):
        memory.append(invalid, "a")


def test_ambiguous_publish_retry_preserves_batch_identity(tmp_path):
    memory = MemoryStore(tmp_path)
    memory.append(row(1), "a")
    batches = seal(memory)
    uploaded = {}

    def fail(ident, raw):
        uploaded[ident] = raw
        raise RuntimeError("lost acknowledgement")

    with pytest.raises(RuntimeError):
        memory.publish("shared", fail)
    assert memory.pending("shared") == batches

    def succeed(ident, raw):
        assert uploaded[ident] == raw
        return {"sha256": digest(raw)}

    memory.publish("shared", succeed)
    assert not memory.pending("shared")
    assert len(list(memory.records("shared"))) == 1


def test_restore_and_rebuild_from_remote_bytes(tmp_path):
    original = MemoryStore(tmp_path / "original")
    original.append(row(1), "a")
    batch = seal(original)[0]

    class Remote:
        def retrieve(self):
            yield (
                "refs/workshop/memory/v2/" + batch["id"],
                (batch["body"] + "\n").encode(),
            )

    recovered = MemoryStore(tmp_path / "recovered")
    restore(recovered, "shared", Remote())
    restore(recovered, "shared", Remote())
    assert list(recovered.records("shared")) == [row(1)]
    assert not recovered.pending("shared")
    assert rebuild_index(recovered, "shared", tmp_path / "index.sqlite")["records"] == 1


def test_invalid_input_leaves_no_acknowledged_record(tmp_path):
    memory = MemoryStore(tmp_path)
    bad = row(1)
    del bad["source"]
    with pytest.raises(ValueError):
        memory.append(bad, "a")
    assert seal(memory) == []


def test_restore_reserves_identity_across_stores(tmp_path):
    memory = MemoryStore(tmp_path)
    record = row(20)
    batch_id = str(uuid.uuid4())

    class Remote:
        def retrieve(self):
            yield (
                "refs/workshop/memory/v2/" + batch_id,
                json.dumps(
                    {
                        "schema_version": 1,
                        "id": batch_id,
                        "store": "shared",
                        "day": "2026-10-01",
                        "records": [record],
                    }
                ).encode(),
            )

    restore(memory, "shared", Remote())
    with pytest.raises(ValueError, match="classification"):
        memory.append(row(20, "sensitive"), "later-agent")


def test_delivery_provenance_and_cutoff_survive_aggregation(tmp_path):
    memory = MemoryStore(tmp_path)
    memory.append(row(1), "agent-a")
    memory.append(row(1), "agent-b")
    assert memory.prepare("shared", "2000-01-01", "2000-01-02T00:00:00Z") == []
    batch = json.loads(seal(memory)[0]["body"])
    assert {d["agent"] for d in batch["collection"][row(1)["id"]]} == {
        "agent-a",
        "agent-b",
    }
    assert "observation-v2" in batch["schemas"]
    assert batch["records"][0]["artifacts"] == row(1)["artifacts"]


def test_missing_private_tree_does_not_import_public(tmp_path):
    from scripts.memory import import_feedback

    memory = MemoryStore(tmp_path / "state")
    public = tmp_path / "public"
    public.mkdir()
    with pytest.raises(ValueError, match="both legacy trees"):
        import_feedback(memory, public, tmp_path / "missing")
    assert seal(memory) == []


def test_cli_rejects_invalid_envelope_without_stdout(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[1] / "scripts/memory.py"),
            "--state",
            str(tmp_path),
            "ingest",
            "-",
            "--agent",
            "test",
        ],
        input='{"secret":"do not print this value"}',
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert not result.stdout
    assert "do not print this value" not in result.stderr
    assert "Traceback" not in result.stderr


def test_native_trial_freezes_inputs_and_retains_unknowns(tmp_path):
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "experiments/context-pilots/native_trial.py"
    )
    spec = importlib.util.spec_from_file_location("native_trial", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prepared = module.prepare("tree", tmp_path)
    work = Path(prepared["workspace"])
    (work / "response.txt").write_text("Synthetic test response; not a model trial.")
    (work / "runtime.json").write_text('{"model":null,"synthetic_test":true}')
    first = module.finish(work, tmp_path)
    assert module.finish(work, tmp_path)["duplicate"]
    seal(MemoryStore(tmp_path))
    record = next(MemoryStore(tmp_path).records("shared"))
    assert record["id"] == first["id"]
    assert "model" in record["context"]["missing"]
    assert record["payload"]["grade"] is None
    (work / "fixture.json").write_text("{}")
    with pytest.raises(ValueError, match="frozen input changed"):
        module.finish(work, tmp_path)


def test_legacy_overlay_routes_entire_record_and_original_bytes(tmp_path):
    import base64

    from scripts.memory import import_feedback

    record = {
        "schema_version": 2,
        "id": str(uuid.uuid4()),
        "recorded_at": "2026-10-01T00:00:00Z",
        "kind": "usage",
        "skill": "fixture",
        "task": "test",
        "outcome": "success",
        "task_outcome": "unknown",
        "duration_seconds": None,
        "duration_scope": None,
        "skill_digest": None,
        "model": None,
        "measurement": "agent-reported",
        "unit": "skill-task",
        "visibility": "shareable",
    }
    public, private = tmp_path / "public", tmp_path / "private"
    for directory in (public, private):
        (directory / "records/2026/10").mkdir(parents=True)
    (public / "records/2026/10/record.json").write_text(json.dumps(record))
    record["sensitivity"] = {
        "fields": ["/evidence"],
        "category": "other",
        "reason": "synthetic private detail",
        "classifier": "agent",
        "confidence": "high",
    }
    raw = json.dumps(record, indent=3).encode()
    (private / "records/2026/10/record.json").write_bytes(raw)
    memory = MemoryStore(tmp_path / "memory")
    assert import_feedback(memory, public, private)["sensitive"] == 1
    assert seal(memory) == []
    memory.prepare("sensitive", "2099-01-01", "2099-01-02T00:00:00Z")
    saved = next(memory.records("sensitive"))
    assert saved["payload"] == record
    assert base64.b64decode(saved["artifacts"][0]["bytes_base64"]) == raw
