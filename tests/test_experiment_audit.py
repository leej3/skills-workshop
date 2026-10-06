import hashlib
import importlib.util
import io
import json
import tarfile
import uuid
from pathlib import Path

from scripts.memory_store import artifact, envelope

PATH = Path(__file__).resolve().parents[1] / "experiments/context-pilots/audit_data.py"
spec = importlib.util.spec_from_file_location("experiment_audit", PATH)
audit_data = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_data)


def _id():
    return str(uuid.uuid4())


def _corpus():
    frozen = b'{"documents": []}'
    record = envelope(
        {"fixture_sha256": hashlib.sha256(frozen).hexdigest()},
        ident=_id(),
        kind="evidence",
        occurred_at="2026-10-06T00:00:00Z",
        store="shared",
        producer="workshop-retrieval-pilot",
        source_schema="corpus-v1",
        context={"task_id": "corpus", "conditions": {}},
        artifacts=[artifact("frozen-inputs.json", frozen, "application/json")],
    )
    return record


def _mock():
    return envelope(
        {"config": {"engine_type": "mock"}},
        ident=_id(),
        kind="evaluation",
        occurred_at="2026-10-06T00:00:00Z",
        store="shared",
        producer="waza",
        source_schema="waza-result-v1",
        context={
            "agent_id": "test",
            "conditions": {"executor": "mock", "model_calls": False},
        },
    )


def _pending(recovery_of=None):
    return envelope(
        {"status": "attempted", "trial": {"id": "trial-1"}, "files": {}},
        ident=_id(),
        kind="evaluation",
        occurred_at="2026-10-06T00:00:00Z",
        store="shared",
        producer="native-luna-pilot",
        source_schema="native-trial-v2",
        context={
            "task_id": "trial-1",
            "conditions": {"pair_id": "pair", "recovery_of": recovery_of},
        },
    )


def _native_output(response_hash=None):
    frozen = b"frozen agent input"
    response = b"captured model output"
    runtime = b'{"model":"gpt-6-luna"}'
    files = {
        "agent-input.json": frozen,
        "response.txt": response,
        "runtime.json": runtime,
    }
    ident = _id()
    return envelope(
        {
            "trial": {
                "id": ident,
                "kind": "cli",
                "files": {"agent-input.json": hashlib.sha256(frozen).hexdigest()},
            },
            "files": {
                name: hashlib.sha256(data).hexdigest() for name, data in files.items()
            },
            "response_sha256": response_hash or hashlib.sha256(response).hexdigest(),
            "grade": None,
        },
        ident=ident,
        kind="evaluation",
        occurred_at="2026-10-06T00:00:00Z",
        store="shared",
        producer="native-luna-pilot",
        source_schema="native-trial-v2",
        context={
            "task_id": ident,
            "model": {"id": "gpt-6-luna"},
            "runtime": {"model": "gpt-6-luna"},
            "conditions": {"host_context_isolation": False},
        },
        artifacts=[artifact(name, data) for name, data in files.items()],
    )


def _retrieval(corpus, local_artifact=None):
    external = []
    if local_artifact is not None:
        digest = hashlib.sha256(local_artifact).hexdigest()
        external = [
            {
                "name": "query-log.tar.gz",
                "sha256": digest,
                "size": len(local_artifact),
                "store": "shared",
                "annex_key": f"SHA256-s{len(local_artifact)}--{digest}",
            }
        ]
    row = envelope(
        {
            "provider": "sqlite",
            "paths": ["guide.md"],
            "expected_source_hit_at_5": True,
            "exit": 0,
        },
        ident=_id(),
        kind="retrieval",
        occurred_at="2026-10-06T00:00:00Z",
        store="shared",
        producer="sqlite",
        source_schema="native-query-result",
        context={
            "task_id": "run-1",
            "conditions": {
                "query": {"id": "q1", "query": "guide", "expected": "guide.md"},
                "fixture_sha256": corpus["payload"]["fixture_sha256"],
            },
        },
        relations=[{"relation": "corpus", "id": corpus["id"]}],
    )
    row["external_artifacts"] = external
    return row


def _query_archive():
    payload = json.dumps({"exit": 0, "stdout": '[{"file":"guide.md"}]'}).encode()
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        info = tarfile.TarInfo("native-output.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def test_mock_and_pending_are_excluded_from_model_effectiveness(tmp_path):
    report = audit_data.audit_records([_mock(), _pending()], tmp_path)
    assert report["valid"]
    assert report["effectiveness_claim_status"] == "not-established"
    assert report["counts"] == {"mock-plumbing": 1, "pending": 1}
    assert report["eligible_for_descriptive_analysis"] == 0


def test_recovery_attempt_is_labeled_as_alternative_not_independent(tmp_path):
    report = audit_data.audit_records([_pending("original-trial")], tmp_path)
    assert report["valid"]
    assert report["counts"] == {"recovery-alternative-pending": 1}
    assert report["eligible_for_descriptive_analysis"] == 0


def test_attempt_record_with_terminal_recovery_is_history_not_actionable_pending(
    tmp_path,
):
    outcome = _native_output()
    outcome["payload"]["status"] = "completed"
    outcome["context"]["conditions"].update(
        {"pair_id": "pair", "recovery_of": "original-trial"}
    )
    attempt = _pending("original-trial")
    attempt["context"]["task_id"] = outcome["context"]["task_id"]
    attempt["payload"]["trial"]["id"] = outcome["context"]["task_id"]
    attempt["context"]["conditions"]["pair_id"] = "pair"
    report = audit_data.audit_records([attempt, outcome], tmp_path)
    assert report["valid"]
    assert report["counts"] == {
        "recovery-alternative-attempt-history:completed": 1,
        "recovery-alternative-model-ungraded": 1,
    }
    assert report["eligible_for_descriptive_analysis"] == 0


def test_transport_degraded_recovery_is_explicitly_ineligible(tmp_path):
    row = _native_output()
    runtime = b'{"model":"gpt-6-luna","transport_degraded":true}'
    row["artifacts"] = [
        item for item in row["artifacts"] if item["name"] != "runtime.json"
    ] + [artifact("runtime.json", runtime)]
    row["payload"]["files"]["runtime.json"] = hashlib.sha256(runtime).hexdigest()
    row["context"]["conditions"]["recovery_of"] = "original-trial"
    report = audit_data.audit_records([row], tmp_path)
    assert report["valid"]
    assert report["counts"] == {"transport-degraded-alternative": 1}
    assert report["eligible_for_descriptive_analysis"] == 0


def test_invalid_schema_is_reported(tmp_path):
    row = _mock()
    del row["classification"]
    report = audit_data.audit_records([row], tmp_path)
    assert not report["valid"]
    assert "invalid envelope" in report["errors"][0]


def test_response_hash_mismatch_is_reported_and_ungraded(tmp_path):
    report = audit_data.audit_records([_native_output("0" * 64)], tmp_path)
    assert any(
        "response hash missing or inconsistent" in error for error in report["errors"]
    )
    assert report["counts"] == {"observed-model-ungraded": 1}


def test_legacy_response_hash_uses_retained_file_digest(tmp_path):
    row = _native_output()
    row["payload"].pop("response_sha256")
    report = audit_data.audit_records([row], tmp_path)
    assert report["integrity_valid"]
    assert report["counts"] == {"observed-model-ungraded": 1}


def test_duplicate_ids_are_reported(tmp_path):
    row = _mock()
    report = audit_data.audit_records([row, dict(row)], tmp_path)
    assert any("duplicate record ID" in error for error in report["errors"])


def test_missing_referenced_artifact_is_reported(tmp_path):
    corpus = _corpus()
    report = audit_data.audit_records(
        [corpus, _retrieval(corpus, b"archive")], tmp_path
    )
    assert any(
        "referenced local artifact missing" in error for error in report["errors"]
    )


def test_local_retrieval_artifact_is_verified(tmp_path):
    corpus = _corpus()
    raw = _query_archive()
    digest = hashlib.sha256(raw).hexdigest()
    (tmp_path / "shared/objects").mkdir(parents=True)
    (tmp_path / "shared/objects" / digest).write_bytes(raw)
    report = audit_data.audit_records([corpus, _retrieval(corpus, raw)], tmp_path)
    assert report["valid"]
    assert report["counts"] == {"descriptive-retrieval": 1}


def test_quality_failures_remain_visible_on_integrity_success(tmp_path):
    corpus = _corpus()
    row = _retrieval(corpus)
    row["context"]["conditions"]["query"]["expected"] = None
    row["payload"].update(
        {
            "paths": ["README.md", "README.md"],
            "expected_source_hit_at_5": False,
            "query_id": "no-evidence",
        }
    )
    report = audit_data.audit_records([corpus, row], tmp_path)
    assert report["integrity_valid"]
    assert len(report["quality_findings"]["failed_expected_source_checks"]) == 1
    assert len(report["quality_findings"]["absent_term_false_positives"]) == 1
    assert len(report["quality_findings"]["duplicate_path_results"]) == 1


def test_frozen_input_hash_mismatch_is_reported(tmp_path):
    row = _pending()
    row["payload"]["status"] = "completed"
    row["payload"]["trial"]["files"] = {"agent-input.json": "0" * 64}
    row["payload"]["files"] = {"agent-input.json": "0" * 64}
    row["artifacts"] = [artifact("agent-input.json", b"real input", "application/json")]
    report = audit_data.audit_records([row], tmp_path)
    assert any("hash mismatch" in error for error in report["errors"])
