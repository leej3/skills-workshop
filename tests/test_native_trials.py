import importlib.util
import json
from pathlib import Path

import pytest

from scripts.memory_store import MemoryStore

PATH = (
    Path(__file__).resolve().parents[1] / "experiments/context-pilots/native_trial.py"
)
spec = importlib.util.spec_from_file_location("native_trial", PATH)
trial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trial)


def records(state):
    memory = MemoryStore(state)
    memory.prepare("shared", "2099-01-01", "2099-01-02T00:00:00Z")
    return list(memory.records("shared"))


def _write_grade_receipt(state, recovery):
    """Make a small, packet-matched grade record for control-plane tests."""
    recovery_id = recovery["id"]
    packet_dir = Path(state) / "native-recoveries" / f"{recovery_id}-grader"
    out = trial.grading_packet(Path(recovery["recovery"]), packet_dir)
    packet_path = Path(out["grader_input"])
    packet_raw = packet_path.read_bytes()
    packet = json.loads(packet_raw)
    grade = {
        "method": {
            "input_sha256": trial.digest(packet_raw),
            "assessment": "static review",
        },
        "responses": [
            {
                "label": response["label"],
                "items": [
                    {"rubric_item": item, "score": 2, "rationale": "supported"}
                    for item in packet["rubric"]
                ],
            }
            for response in packet["responses"]
        ],
        "evaluation_scope": "one exploratory anonymous pair",
    }
    grade_path = Path(state) / f"{recovery_id}-grade.json"
    grade_path.write_text(json.dumps(grade))
    return trial.ingest_grade(recovery["recovery"], state, grade_path, packet_path)


def test_attempt_is_retained_without_response_and_failure_can_close_it(tmp_path):
    work = Path(trial.prepare("tree", tmp_path)["workspace"])
    assert len(trial.pending(tmp_path)["unresolved"]) == 1
    assert (
        json.loads((work / "attempt-event.json").read_text())["payload"]["status"]
        == "attempted"
    )
    result = trial.finish(work, tmp_path, "interrupted", "executor stopped")
    assert trial.finish(work, tmp_path, "interrupted", "executor stopped")["duplicate"]
    assert not trial.pending(tmp_path)["unresolved"]
    rows = records(tmp_path)
    assert {r["payload"]["status"] for r in rows} == {"attempted", "interrupted"}
    outcome = next(r for r in rows if r["id"] == result["id"])
    assert outcome["context"]["runtime"] is None
    assert "runtime" in outcome["context"]["missing"]
    assert all(r["external_artifacts"] and not r["artifacts"] for r in rows)
    with pytest.raises(ValueError, match="already frozen"):
        trial.finish(work, tmp_path, "failed", "different outcome")


def test_crash_after_event_before_append_replays_exactly(tmp_path, monkeypatch):
    original = MemoryStore.append

    def fail(*args, **kwargs):
        raise OSError("simulated crash")

    monkeypatch.setattr(MemoryStore, "append", fail)
    with pytest.raises(OSError):
        trial.prepare("cli", tmp_path)
    monkeypatch.setattr(MemoryStore, "append", original)
    assert len(trial.pending(tmp_path)["unresolved"]) == 1
    assert len(records(tmp_path)) == 1


def test_failed_invalid_runtime_and_partial_response_are_preserved(tmp_path):
    work = Path(trial.prepare("cli", tmp_path)["workspace"])
    (work / "runtime.json").write_text("broken json")
    (work / "response.txt").write_text("partial answer")
    trial.finish(work, tmp_path, "failed", "invalid executor output")
    row = next(r for r in records(tmp_path) if r["payload"]["status"] == "failed")
    assert "runtime.json" in row["payload"]["files"]
    assert "response.txt" in row["payload"]["files"]


def test_pair_freezes_same_inputs_and_grading_hides_assignment(tmp_path):
    pair = trial.prepare_pair(tmp_path)
    assert set(pair["order"]) == {"ambient-baseline", "explicit-skill"}
    inputs = []
    for index, path in enumerate(pair["workspaces"]):
        work = Path(path)
        inputs.append(json.loads((work / "agent-input.json").read_text()))
        (work / "runtime.json").write_text('{"model":null}')
        (work / "response.txt").write_text(f"Synthetic answer {index}")
        trial.finish(work, tmp_path)
    assert inputs[0]["prompt"] == inputs[1]["prompt"]
    assert sum("skill" in i for i in inputs) == 1
    assert all("rubric" not in i for i in inputs)
    out = trial.grading_packet(Path(pair["pair"]), tmp_path / "grading")
    graded = json.loads(Path(out["grader_input"]).read_text())
    assert len(graded["rubric"]) > 5
    assert set(graded) == {"prompt", "rubric", "responses"}
    assert all(set(r) == {"label", "response"} for r in graded["responses"])
    (Path(pair["workspaces"][0]) / "response.txt").write_text("tampered")
    with pytest.raises(ValueError, match="response changed"):
        trial.grading_packet(Path(pair["pair"]), tmp_path / "grading2")


def test_legacy_completion_is_not_reopened_by_pending(tmp_path):
    work = Path(trial.prepare("tree", tmp_path)["workspace"])
    (work / "attempt-event.json").unlink()
    (work / "receipt.json").write_text('{"kind":"tree"}')
    assert not trial.pending(tmp_path)["unresolved"]


def test_unresolved_pair_blocks_routine_pair_preparation(tmp_path):
    pair = trial.prepare_pair(tmp_path)
    original = {
        path: (Path(path) / "manifest.json").read_bytes() for path in pair["workspaces"]
    }
    with pytest.raises(ValueError, match="unresolved trial attempts"):
        trial.prepare_pair(tmp_path)
    assert all(
        (Path(path) / "manifest.json").read_bytes() == original[path]
        for path in pair["workspaces"]
    )


def test_operator_recovery_preserves_originals_and_links_alternatives(tmp_path):
    pair = trial.prepare_pair(tmp_path)
    original_snapshots = {
        path: {
            name: (Path(path) / name).read_bytes()
            for name in (
                "manifest.json",
                "attempt-event.json",
                "agent-input.json",
                "fixture.json",
                "treatment-skill.md",
                "protocol.md",
                "collector.py",
            )
        }
        for path in pair["workspaces"]
    }
    with pytest.raises(ValueError, match="authorization"):
        trial.prepare_recovery(pair["pair"], tmp_path)
    recovered = trial.prepare_recovery(pair["pair"], tmp_path, True)
    plan = json.loads(Path(recovered["recovery"]).read_text())
    assert plan["pair_id"] == pair["id"]
    assert plan["recovery_of_pair"] == pair["id"]
    assert plan["analysis_rule"].startswith("alternative executions")
    assert set(plan["original_trial_ids"]) == {
        json.loads((Path(path) / "manifest.json").read_text())["id"]
        for path in pair["workspaces"]
    }
    by_treatment = {}
    for original, recovery in zip(pair["workspaces"], plan["workspaces"]):
        old_manifest = json.loads((Path(original) / "manifest.json").read_text())
        new_manifest = json.loads((Path(recovery) / "manifest.json").read_text())
        assert new_manifest["id"] != old_manifest["id"]
        assert new_manifest["pair_id"] == pair["id"]
        assert new_manifest["recovery_of"] == old_manifest["id"]
        assert new_manifest["recovery_id"] == plan["id"]
        assert (
            new_manifest["recovery_role"] == "operator-authorized-alternative-execution"
        )
        assert new_manifest["files"] == old_manifest["files"]
        for name in old_manifest["files"]:
            assert (Path(recovery) / name).read_bytes() == original_snapshots[original][
                name
            ]
        for name, data in original_snapshots[original].items():
            assert (Path(original) / name).read_bytes() == data
        by_treatment[old_manifest["treatment"]] = json.loads(
            (Path(recovery) / "attempt-event.json").read_text()
        )
    assert {
        row["context"]["conditions"]["recovery_of"] for row in by_treatment.values()
    } == set(plan["original_trial_ids"])
    assert len(trial.pending(tmp_path)["unresolved"]) == 4


def test_graded_recovery_unblocks_next_pair_and_reports_originals_as_historical(
    tmp_path,
):
    original = trial.prepare_pair(tmp_path)
    recovery = trial.prepare_recovery(original["pair"], tmp_path, True)
    for index, workspace in enumerate(recovery["workspaces"]):
        work = Path(workspace)
        (work / "response.txt").write_text(f"Recovered response {index}")
        (work / "runtime.json").write_text('{"model":"gpt-6-luna"}')
        trial.finish(work, tmp_path)
    _write_grade_receipt(tmp_path, recovery)

    next_pair = trial.prepare_pair(tmp_path)
    assert next_pair["id"] != original["id"]
    status = trial.pending(tmp_path)
    assert len(status["unresolved"]) == 2
    assert {row["trial_id"] for row in status["historical_admission_unknown"]} == {
        Path(path).name for path in original["workspaces"]
    }
    assert not status["reconciliation_required"]
    resolution = json.loads(
        (
            tmp_path / "native-recoveries" / f"{recovery['id']}.supersession.json"
        ).read_text()
    )
    assert resolution["original_admission_status"] == "unknown, unchanged"
    assert set(resolution["accepted_recovery_trial_ids"]) == {
        Path(path).name for path in recovery["workspaces"]
    }


def test_late_original_outcomes_are_reconciliation_only_and_do_not_block_next_pair(
    tmp_path,
):
    original = trial.prepare_pair(tmp_path)
    recovery = trial.prepare_recovery(original["pair"], tmp_path, True)
    for index, workspace in enumerate(recovery["workspaces"]):
        work = Path(workspace)
        (work / "response.txt").write_text(f"Recovered response {index}")
        (work / "runtime.json").write_text('{"model":"gpt-6-luna"}')
        trial.finish(work, tmp_path)
    _write_grade_receipt(tmp_path, recovery)
    trial.pending(tmp_path)  # Append the immutable supersession record first.

    for index, workspace in enumerate(original["workspaces"]):
        work = Path(workspace)
        (work / "response.txt").write_text(f"Late original response {index}")
        (work / "runtime.json").write_text('{"model":"gpt-6-luna"}')
        trial.finish(work, tmp_path)
    status = trial.pending(tmp_path)
    assert not status["unresolved"]
    assert {row["trial_id"] for row in status["reconciliation_required"]} == {
        Path(path).name for path in original["workspaces"]
    }
    next_pair = trial.prepare_pair(tmp_path)
    assert next_pair["id"] != original["id"]
    audited = records(tmp_path)
    import importlib.util

    audit_path = (
        Path(__file__).resolve().parents[1] / "experiments/context-pilots/audit_data.py"
    )
    audit_spec = importlib.util.spec_from_file_location(
        "late_original_audit", audit_path
    )
    audit = importlib.util.module_from_spec(audit_spec)
    audit_spec.loader.exec_module(audit)
    report = audit.audit_records(audited, tmp_path)
    assert report["valid"]
    assert report["counts"].get("superseded-original-late-alternative") == 2
    assert report["eligible_for_descriptive_analysis"] == 0


def test_transport_correction_records_source_and_delivered_input_hashes(tmp_path):
    pair = trial.prepare_pair(tmp_path)
    wrapper = "Return one complete answer in the final response only."
    recovered = trial.prepare_recovery(
        pair["pair"], tmp_path, True, wrapper, "final-only-v1"
    )
    for source, delivered in zip(pair["workspaces"], recovered["workspaces"]):
        source_work = Path(source)
        work = Path(delivered)
        original_input = (source_work / "agent-input.json").read_bytes()
        manifest = json.loads((work / "manifest.json").read_text())
        inputs = json.loads((work / "agent-input.json").read_text())
        source_manifest = json.loads((source_work / "manifest.json").read_text())
        assert (work / "source-agent-input.json").read_bytes() == original_input
        assert manifest["transport"]["revision"] == "final-only-v1"
        assert (
            manifest["transport"]["source_agent_input_sha256"]
            == source_manifest["files"]["agent-input.json"]
        )
        assert manifest["transport"]["delivered_agent_input_sha256"] == trial.digest(
            (work / "agent-input.json").read_bytes()
        )
        assert manifest["transport"]["wrapper_sha256"] == trial.digest(wrapper.encode())
        assert (work / "transport-wrapper.txt").read_text() == wrapper
        assert inputs["prompt"].startswith(wrapper + "\n\n")
        assert inputs["prompt"].endswith(json.loads(original_input)["prompt"])


def test_crash_before_outcome_append_replays_completion(tmp_path, monkeypatch):
    work = Path(trial.prepare("tree", tmp_path)["workspace"])
    (work / "response.txt").write_text("Synthetic response")
    (work / "runtime.json").write_text("{}")
    original = MemoryStore.append

    def fail(*args, **kwargs):
        raise OSError("simulated crash")

    monkeypatch.setattr(MemoryStore, "append", fail)
    with pytest.raises(OSError):
        trial.finish(work, tmp_path)
    monkeypatch.setattr(MemoryStore, "append", original)
    assert not trial.pending(tmp_path)["unresolved"]
    assert {r["payload"]["status"] for r in records(tmp_path)} == {
        "attempted",
        "completed",
    }
