import io
import json
import subprocess

import pytest

from scripts.memory_annex import AnnexTransport, credential


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
