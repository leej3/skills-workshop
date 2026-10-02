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
