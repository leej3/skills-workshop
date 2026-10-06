import io
import json
import subprocess

import pytest

from scripts.memory_annex import AnnexTransport, credential
from scripts.memory_store import digest


def configuration(tmp_path):
    config = {
        "stores": {
            "shared": {
                "metadata": {"url": "git@github.com:example/project.git"},
                "payload": {
                    "url": "https://annex.example/project.git",
                    "username": "test",
                    "token_file": str(tmp_path / "token"),
                },
            }
        }
    }
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    return config, path


def test_metadata_is_plain_git_without_annex_http_discovery(tmp_path, monkeypatch):
    config, path = configuration(tmp_path)
    transport = AnnexTransport(tmp_path, path, "shared")
    transport.repo.mkdir(parents=True)
    subprocess.run(
        ["git", "init", str(transport.repo)], check=True, capture_output=True
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **kw: pytest.fail("metadata must not request an annex endpoint"),
    )
    transport.configure_remote("origin", config["stores"]["shared"]["metadata"])
    assert transport.git("remote", "get-url", "origin") == (
        "git@github.com:example/project.git"
    )
    assert transport.git("config", "remote.origin.annex-ignore") == "true"


def test_payload_endpoint_is_required_before_cloning(tmp_path):
    config, path = configuration(tmp_path)
    del config["stores"]["shared"]["payload"]
    path.write_text(json.dumps(config))
    transport = AnnexTransport(tmp_path, path, "shared")
    with pytest.raises(ValueError, match="separate metadata and payload"):
        transport.setup()
    assert not transport.repo.exists()


def test_missing_provenance_does_not_create_or_stage_pointer(tmp_path, monkeypatch):
    _, path = configuration(tmp_path)
    transport = AnnexTransport(tmp_path, path, "shared")
    transport.config["provenance_script"] = "resolve.sh"
    calls = []

    class MissingRef:
        returncode = 1
        stdout = ""

    def git(*args, **kwargs):
        calls.append(args)
        if args[:2] == ("rev-parse", "--verify"):
            return MissingRef()
        if args[:2] == ("ls-remote", "origin"):
            return ""
        raise AssertionError(f"unexpected Git mutation before provenance: {args[0]}")

    def missing_provenance(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(transport, "git", git)
    monkeypatch.setattr(
        "scripts.memory_annex.subprocess.check_output", missing_provenance
    )

    with pytest.raises(subprocess.CalledProcessError):
        transport._put("artifact-id", b"archive", "refs/workshop/artifacts/v1/")

    assert calls == [
        ("rev-parse", "--verify", "refs/workshop/artifacts/v1/artifact-id"),
        ("ls-remote", "origin", "refs/workshop/artifacts/v1/artifact-id"),
    ]
    assert not (transport.repo / "batches" / "artifact-id.tar.gz").exists()
    assert not (transport.repo / ".git").exists()


def test_publish_batch_syncs_annex_metadata_once_after_all_refs(tmp_path, monkeypatch):
    _, path = configuration(tmp_path)
    transport = AnnexTransport(tmp_path, path, "shared")
    published = []
    synced = []

    def put(ident, raw, prefix, *, sync):
        published.append((ident, raw, prefix, sync))
        return {"sha256": ident, "ref": prefix + ident}

    def git(*args, **kwargs):
        synced.append((args, kwargs))

    monkeypatch.setattr(transport, "_put", put)
    monkeypatch.setattr(transport, "git", git)
    artifacts = [
        (
            {
                "store": "shared",
                "sha256": digest(b"one"),
                "size": 3,
            },
            b"one",
        ),
        (
            {
                "store": "shared",
                "sha256": digest(b"two"),
                "size": 3,
            },
            b"two",
        ),
    ]

    receipt = transport.publish_batch_with_artifacts(
        "batch-id", b"batch", iter(artifacts)
    )

    assert [item[3] for item in published] == [False, False, False]
    assert [(item[0], item[2]) for item in published] == [
        (digest(b"one"), "refs/workshop/artifacts/v1/"),
        (digest(b"two"), "refs/workshop/artifacts/v1/"),
        ("batch-id", "refs/workshop/memory/v2/"),
    ]
    assert receipt["sha256"] == "batch-id"
    assert synced == [(("annex", "sync", "--only-annex", "--no-content", "origin"), {})]


def test_publish_batch_failure_does_not_sync_or_return_receipt(tmp_path, monkeypatch):
    _, path = configuration(tmp_path)
    transport = AnnexTransport(tmp_path, path, "shared")
    calls = []

    def put(ident, raw, prefix, *, sync):
        calls.append((ident, sync))
        if len(calls) == 2:
            raise RuntimeError("fixture failure")
        return {"sha256": ident}

    def git(*args, **kwargs):
        calls.append((args, kwargs))

    monkeypatch.setattr(transport, "_put", put)
    monkeypatch.setattr(transport, "git", git)
    artifacts = [
        ({"store": "shared", "sha256": digest(b"1"), "size": 1}, b"1"),
        ({"store": "shared", "sha256": digest(b"2"), "size": 1}, b"2"),
    ]

    with pytest.raises(RuntimeError, match="fixture failure"):
        transport.publish_batch_with_artifacts("batch-id", b"batch", iter(artifacts))
    assert calls == [(digest(b"1"), False), (digest(b"2"), False)]


def test_credentials_are_scoped_to_endpoint_role(tmp_path, monkeypatch, capsys):
    config, _ = configuration(tmp_path)
    (tmp_path / "token").write_text("synthetic-fixture-token")
    request = "protocol=https\nhost=annex.example\npath=project.git\n"
    monkeypatch.setattr("sys.stdin", io.StringIO(request))
    monkeypatch.setenv("WORKSHOP_MEMORY_ROLE", "metadata")
    credential(config, "shared")
    assert capsys.readouterr().out == ""
    monkeypatch.setattr("sys.stdin", io.StringIO(request))
    monkeypatch.setenv("WORKSHOP_MEMORY_ROLE", "payload")
    credential(config, "shared")
    assert (
        capsys.readouterr().out == "username=test\npassword=synthetic-fixture-token\n"
    )
