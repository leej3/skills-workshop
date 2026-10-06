import gzip
import io
import json
import tarfile

import pytest

from scripts.memory import restore
from scripts.memory_capture import capture_duct
from scripts.memory_store import MemoryStore, digest


def duct_run(path):
    path.mkdir()
    (path / "context.json").write_text(
        json.dumps({"started_at": "2026-10-01T00:00:00Z", "project_id": "fixture"})
    )
    (path / "run_info.json").write_text(
        json.dumps(
            {
                "command": "synthetic test",
                "duct_version": "0.22.0",
                "schema_version": "0.2.3",
                "execution_summary": {
                    "exit_code": 1,
                    "end_time": 10,
                    "wall_clock_time": 0.5,
                },
            }
        )
    )
    (path / "run_stdout").write_bytes(b"original\x00bytes\n")
    return path


def test_capture_is_separate_deterministic_and_restore_does_not_fetch_logs(tmp_path):
    memory = MemoryStore(tmp_path / "writer")
    source = duct_run(tmp_path / "run")
    result = capture_duct(memory, source, "shared", "test")
    assert capture_duct(memory, source, "shared", "test")["duplicate"]
    item = result["artifact"]
    raw = (memory.store_root("shared") / "objects" / item["sha256"]).read_bytes()
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(raw))) as archive:
        assert archive.extractfile("run_stdout").read() == b"original\x00bytes\n"
    memory.prepare("shared", "2099-01-01", "2099-01-02T00:00:00Z")
    uploads = []
    batches = []

    class Remote:
        def publish_batch_with_artifacts(self, ident, batch_content, artifacts):
            uploads.append("bulk-start")
            for reference, artifact_content in artifacts:
                self.publish_artifact(reference, artifact_content)
            uploads.append("annex-sync")
            return self.__call__(ident, batch_content)

        def publish_artifact(self, reference, content):
            assert reference == item and content == raw
            uploads.append("artifact")

        def __call__(self, ident, content):
            assert uploads == ["bulk-start", "artifact", "annex-sync"]
            batches.append((ident, content))
            return {"sha256": digest(content)}

        def retrieve(self):
            for ident, content in batches:
                yield "refs/workshop/memory/v2/" + ident, content

    remote = Remote()
    memory.publish("shared", remote)
    assert uploads == ["bulk-start", "artifact", "annex-sync"]
    recovered = MemoryStore(tmp_path / "reader")
    restore(recovered, "shared", remote)
    row = next(recovered.records("shared"))
    assert row["external_artifacts"] == [item]
    assert not row["artifacts"]
    assert not (recovered.store_root("shared") / "objects").exists()


def test_incomplete_or_symlink_capture_is_not_accepted(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    source = duct_run(tmp_path / "run")
    original = (source / "run_info.json").read_bytes()
    (source / "run_info.json").write_text('{"execution_summary": {}}')
    with pytest.raises(ValueError, match="not finished"):
        capture_duct(memory, source, "shared", "test")
    (source / "run_info.json").write_bytes(original)
    (source / "outside").symlink_to(tmp_path / "secret")
    with pytest.raises(ValueError, match="regular files"):
        capture_duct(memory, source, "shared", "test")


def test_capture_routing_uses_explicit_store_for_path_and_secret_fixture(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    cross_project = duct_run(tmp_path / "cross-project")
    context = json.loads((cross_project / "context.json").read_text())
    context["project_id"] = "synthetic-other-project"
    context["working_directory"] = "/tmp/synthetic-other-project"
    (cross_project / "context.json").write_text(json.dumps(context))
    cross_result = capture_duct(memory, cross_project, "shared", "test-agent")

    secret_fixture = duct_run(tmp_path / "synthetic-sensitive")
    canary = b"Authorization: Bearer SYNTHETIC_ONLY_NOT_A_REAL_CREDENTIAL"
    (secret_fixture / "run_stderr").write_bytes(canary)
    sensitive_result = capture_duct(
        memory,
        secret_fixture,
        "sensitive",
        "test-agent",
        reason="Synthetic credential-like routing fixture; no real credential",
    )

    memory.prepare("shared", "2099-01-01", "2099-01-02T00:00:00Z")
    memory.prepare("sensitive", "2099-01-01", "2099-01-02T00:00:00Z")
    shared_row = next(memory.records("shared"))
    sensitive_row = next(memory.records("sensitive"))

    assert cross_result["artifact"]["store"] == "shared"
    assert shared_row["classification"]["store"] == "shared"
    assert sensitive_result["artifact"]["store"] == "sensitive"
    assert sensitive_row["classification"]["store"] == "sensitive"
    assert sensitive_row["classification"]["reason"].startswith("Synthetic")
    assert [row["id"] for row in memory.records("shared")] == [shared_row["id"]]
    archive = (
        memory.store_root("sensitive")
        / "objects"
        / sensitive_result["artifact"]["sha256"]
    ).read_bytes()
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(archive))) as saved:
        assert saved.extractfile("run_stderr").read() == canary


def test_missing_artifact_prevents_batch_publication(tmp_path):
    memory = MemoryStore(tmp_path / "memory")
    result = capture_duct(
        memory,
        duct_run(tmp_path / "run"),
        "sensitive",
        "test",
        reason="synthetic private output",
    )
    memory.prepare("sensitive", "2099-01-01", "2099-01-02T00:00:00Z")
    (memory.store_root("sensitive") / "objects" / result["artifact"]["sha256"]).unlink()
    with pytest.raises(FileNotFoundError):
        memory.publish("sensitive", lambda *args: pytest.fail("must not publish batch"))
    assert len(memory.pending("sensitive")) == 1
