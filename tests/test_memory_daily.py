"""Isolated daily orchestration tests; no production memory or transport."""

from types import SimpleNamespace

import pytest

from scripts.memory import import_feedback
from scripts.memory_daily import collect_daily
from scripts.memory_store import MemoryStore
from tests.test_memory_store import row


def test_wrong_feedback_level_is_rejected(tmp_path):
    public = tmp_path / "observations/records/2026/10"
    public.mkdir(parents=True)
    (public / "record.json").write_text("{}")
    private = tmp_path / "private"
    private.mkdir()
    with pytest.raises(ValueError, match="parent of records"):
        import_feedback(MemoryStore(tmp_path / "state"), public.parent.parent, private)


def test_failed_publication_still_indexes_and_processes_other_store(
    tmp_path, monkeypatch, capsys
):
    from scripts import memory_daily

    memory = MemoryStore(tmp_path / "state")
    memory.append(row(1), "unit-test")
    memory.prepare("shared", "2000-01-01", "2099-01-01T00:00:00Z")
    monkeypatch.setattr(memory_daily, "snapshot", lambda *a: {"duplicate": True})
    monkeypatch.setattr(
        memory_daily,
        "import_feedback",
        lambda *a: {"shared": 1, "sensitive": 0, "duplicates": 1},
    )

    class FailedTransport:
        def __init__(self, *args):
            pass

        def setup(self):
            raise RuntimeError("private server diagnostic")

    monkeypatch.setattr(memory_daily, "AnnexTransport", FailedTransport)
    args = SimpleNamespace(
        curated=tmp_path,
        public=tmp_path,
        private=tmp_path,
        config=tmp_path,
        timezone="America/New_York",
    )
    result = collect_daily(memory, args)
    assert not result["ok"]
    assert result["stores"]["shared"]["pending_batches"]
    assert result["stores"]["shared"]["errors"] == [
        {"phase": "publication", "type": "RuntimeError"}
    ]
    assert result["stores"]["sensitive"]["ok"]
    assert (memory.root / "shared/projection.sqlite").exists()
    assert (memory.root / "sensitive/projection.sqlite").exists()
    output = capsys.readouterr()
    assert not output.out
    assert "private server diagnostic" not in output.err
    assert "rebuilding local projection" in output.err


def test_cli_partial_failure_keeps_json_and_nonzero_exit(tmp_path, monkeypatch, capsys):
    import json

    from scripts import memory, memory_daily

    expected = {
        "ok": False,
        "stores": {"shared": {"errors": [{"phase": "publication"}]}},
    }
    monkeypatch.setattr(memory_daily, "collect_daily", lambda *args: expected)
    monkeypatch.setattr(
        "sys.argv",
        [
            "memory",
            "--state",
            str(tmp_path),
            "daily",
            "--config",
            str(tmp_path / "config"),
        ],
    )
    with pytest.raises(SystemExit) as error:
        memory.main()
    assert error.value.code == 1
    output = capsys.readouterr()
    assert json.loads(output.out) == expected
    assert "Daily collection incomplete" in output.err
