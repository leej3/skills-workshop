"""Rich recorder: exact evidence, retry boundaries, classification and recovery."""

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from scripts.memory import restore
from scripts.memory_feedback import (
    capture_feedback,
    catalog,
    find_capture,
    recover_capture,
)
from scripts.memory_store import MemoryStore, digest
from tests.test_memory_capture import duct_run

ROOT = Path(__file__).resolve().parents[1]
ASSESSMENT = {
    "usefulness": "useful",
    "efficiency": "unknown",
    "confidence": "low",
    "basis": "agent-self-assessment",
    "rationale": "Preserved failed command output; no measured comparison.\nUnicode: café.",
    "improvements": ["Link logs automatically."],
}


def inputs(tmp_path):
    transcript = tmp_path / "session.jsonl"
    session = str(uuid.uuid4())
    transcript.write_text(
        json.dumps({"type": "session_meta", "payload": {"id": session}})
        + '\n{"type":"message","text":"original"}\n'
    )
    run = duct_run(tmp_path / "run")
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "id": str(uuid.uuid4()),
                "recorded_at": "2026-10-07T00:00:00Z",
                "kind": "usage",
                "skill": "duct",
                "task": "testing",
                "outcome": "success",
                "task_outcome": "unknown",
                "duration_seconds": None,
                "duration_scope": None,
                "skill_digest": None,
                "model": None,
                "measurement": "agent-reported",
                "unit": "skill-task",
                "visibility": "shareable",
                "assessment": ASSESSMENT,
            }
        )
    )
    request = tmp_path / "capture.json"
    request.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "conversation": {
                    "path": str(transcript),
                    "format": "codex-jsonl",
                    "session_id": session,
                },
                "duct_runs": [str(run)],
            }
        )
    )
    return report, request, transcript


def test_exact_capture_retry_after_transcript_grows_and_fresh_restore(tmp_path):
    report, request, transcript = inputs(tmp_path)
    original = transcript.read_bytes()
    writer = MemoryStore(tmp_path / "writer")
    result = capture_feedback(writer, report, request, "shared", "test")
    with transcript.open("a") as stream:
        stream.write('{"later":"not part of original capture"}\n')
    retried = capture_feedback(writer, report, request, "shared", "test")
    assert retried["duplicate"] and retried["artifact"] == result["artifact"]
    row = find_capture(writer, "shared", json.loads(report.read_text())["id"])
    raw = (
        writer.store_root("shared") / "objects" / result["artifact"]["sha256"]
    ).read_bytes()
    batches = []
    writer.prepare("shared", "2099-01-01", "2099-01-02T00:00:00Z")

    class Remote:
        def publish_batch_with_artifacts(self, ident, content, artifacts):
            assert list(artifacts) == [(result["artifact"], raw)]
            batches.append((ident, content))
            return {"sha256": digest(content)}

        def retrieve(self):
            for ident, content in batches:
                yield "refs/workshop/memory/v2/" + ident, content

    remote = Remote()
    writer.publish("shared", remote)
    reader = MemoryStore(tmp_path / "reader")
    restore(reader, "shared", remote)
    recovered = find_capture(reader, "shared", result["id"])
    assert recovered == row
    output = tmp_path / "recovered"
    recover_capture(recovered, raw, output)
    assert (output / "observation.json").read_bytes() == report.read_bytes()
    assert json.loads((output / "schemas/observation-v2.schema.json").read_text())[
        "oneOf"
    ]
    assert (output / "conversation/transcript").read_bytes() == original
    assert (output / "duct/0000/run_stdout").read_bytes() == b"original\x00bytes\n"
    with pytest.raises(FileExistsError):
        recover_capture(recovered, raw, output)
    with pytest.raises(ValueError, match="integrity"):
        recover_capture(recovered, raw + b"tampered", tmp_path / "bad")
    assert not (tmp_path / "bad").exists()


def test_classification_missing_assessment_and_mismatched_session(tmp_path):
    report, request, _ = inputs(tmp_path)
    memory = MemoryStore(tmp_path / "memory")
    with pytest.raises(ValueError, match="classification"):
        capture_feedback(memory, report, request, "sensitive", "test")
    spec = json.loads(request.read_text())
    spec["conversation"]["session_id"] = "wrong"
    request.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="session identity"):
        capture_feedback(memory, report, request, "shared", "test")
    spec["conversation"].pop("session_id")
    request.write_text(json.dumps(spec))
    value = json.loads(report.read_text())
    value["visibility"] = "private"
    report.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="private observations"):
        capture_feedback(memory, report, request, "shared", "test")
    result = capture_feedback(
        memory, report, request, "sensitive", "test", "private conversation"
    )
    assert (
        find_capture(memory, "sensitive", result["id"])["classification"]["store"]
        == "sensitive"
    )
    assert catalog(memory, "shared", tmp_path / "public-catalog")["captures"] == 0
    value.pop("assessment")
    report.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="assessment"):
        capture_feedback(
            memory, report, request, "sensitive", "test", "private conversation"
        )


def test_changed_request_and_unfinished_log_fail_without_new_capture(tmp_path):
    report, request, _ = inputs(tmp_path)
    memory = MemoryStore(tmp_path / "memory")
    info = tmp_path / "run/run_info.json"
    saved = info.read_bytes()
    info.write_text('{"execution_summary":{}}')
    with pytest.raises(ValueError, match="not finished"):
        capture_feedback(memory, report, request, "shared", "test")
    info.write_bytes(saved)
    capture_feedback(memory, report, request, "shared", "test")
    spec = json.loads(request.read_text())
    spec["duct_runs"] = []
    request.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="inputs changed"):
        capture_feedback(memory, report, request, "shared", "test")


def test_real_recorder_cli_and_full_capture_cli(tmp_path):
    _, request, _ = inputs(tmp_path)
    details = tmp_path / "details.json"
    details.write_text(json.dumps({"assessment": ASSESSMENT}))
    state = tmp_path / "state"
    command = [
        sys.executable,
        str(ROOT / "controls/skills/workshop-feedback/scripts/usage.py"),
        "--store",
        str(tmp_path / "public"),
        "--overlay",
        str(tmp_path / "private"),
        "record",
        "duct",
        "--task",
        "testing",
        "--outcome",
        "success",
        "--details",
        str(details),
        "--capture",
        str(request),
        "--capture-store",
        "shared",
        "--capture-state",
        str(state),
    ]
    p = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        env={**os.environ, "SKILLS_WORKSHOP_ROOT": str(ROOT)},
    )
    assert p.returncode == 0, p.stderr
    result = json.loads(p.stdout)
    out = tmp_path / "opened"
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/memory.py"),
            "--state",
            str(state),
            "show-capture",
            result["id"],
            "--store",
            "shared",
            "--output",
            str(out),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    assert json.loads(p.stdout)["files"] >= 6
    assert (
        json.loads((out / "observation.json").read_text())["assessment"] == ASSESSMENT
    )


def test_catalog_recovers_into_fresh_store_without_copying_payloads(tmp_path):
    from scripts.memory_feedback import import_catalog

    report, request, _ = inputs(tmp_path)
    writer = MemoryStore(tmp_path / "writer")
    result = capture_feedback(writer, report, request, "shared", "test")
    directory = tmp_path / "catalog"
    assert catalog(writer, "shared", directory)["captures"] == 1
    reader = MemoryStore(tmp_path / "reader")
    assert import_catalog(reader, directory, "test")["captures"] == 1
    assert import_catalog(reader, directory, "test")["duplicates"] == 1
    assert find_capture(reader, "shared", result["id"]) == find_capture(
        writer, "shared", result["id"]
    )
    assert not (reader.store_root("shared") / "objects").exists()


def test_unsafe_files_and_other_session_logs_are_rejected(tmp_path):
    report, request, _ = inputs(tmp_path)
    memory = MemoryStore(tmp_path / "memory")
    context = tmp_path / "run/context.json"
    row = json.loads(context.read_text())
    row["session_id"] = "different-session"
    context.write_text(json.dumps(row))
    with pytest.raises(ValueError, match="different session"):
        capture_feedback(memory, report, request, "shared", "test")
    row.pop("session_id")
    context.write_text(json.dumps(row))
    (tmp_path / "run/linked-secret").symlink_to(report)
    with pytest.raises(ValueError, match="regular file"):
        capture_feedback(memory, report, request, "shared", "test")


def test_apm_reference_roundtrip_and_reject_embedding(tmp_path):
    report, request, _ = inputs(tmp_path)
    spec = json.loads(request.read_text())
    spec["schema_version"] = 2
    reference = {
        "manager": "apm",
        "package": "leej3/skills-workshop/controls",
        "resolved_commit": "38c9df6cfee8241f1bce9bb2f65d1c083a574757",
        "skill": "duct",
    }
    spec["skill_reference"] = reference
    request.write_text(json.dumps(spec))
    memory = MemoryStore(tmp_path / "memory")
    result = capture_feedback(memory, report, request, "shared", "test")
    row = find_capture(memory, "shared", result["id"])
    raw = (
        memory.store_root("shared") / "objects" / result["artifact"]["sha256"]
    ).read_bytes()
    output = tmp_path / "recovered"
    recover_capture(row, raw, output)
    assert (
        json.loads((output / "manifest.json").read_text())["skill_reference"]
        == reference
    )
    assert not (output / "skill").exists()
    assert (output / "schemas/capture-request-v2.schema.json").exists()
    reference["resolved_commit"] = "main"
    request.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="invalid capture input"):
        capture_feedback(memory, report, request, "shared", "test")
    reference["resolved_commit"] = "a" * 40
    reference["skill"] = "another-skill"
    request.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="does not match"):
        capture_feedback(memory, report, request, "shared", "test")
    spec.pop("skill_reference")
    spec["skill_path"] = "/unused/SKILL.md"
    request.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="invalid capture input"):
        capture_feedback(memory, report, request, "shared", "test")
    spec["schema_version"] = 1
    request.write_text(json.dumps(spec))
    with pytest.raises(ValueError, match="embedding retired"):
        capture_feedback(
            MemoryStore(tmp_path / "fresh"), report, request, "shared", "test"
        )
