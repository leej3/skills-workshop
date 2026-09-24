"""Behavioral checks for the private completion hook and aggregate semantics."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = (
    Path(__file__).resolve().parents[1]
    / ".agents/skills/workshop-feedback/scripts/usage.py"
)
spec = importlib.util.spec_from_file_location("local_feedback", HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)


def call(store, *args):
    return subprocess.run(
        [sys.executable, str(HOOK), "--store", str(store), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def record(store, *args):
    return call(
        store,
        "record",
        "duct",
        "--task",
        "build-validation",
        "--outcome",
        "success",
        *args,
    )


def test_minimal_record_private_and_deduplicated(tmp_path, monkeypatch):
    store = tmp_path / "state"
    monkeypatch.setenv("CODEX_THREAD_ID", "private-conversation")
    assert record(store, "--event-id", "retry-one").returncode == 0
    retry = record(store, "--event-id", "retry-one")
    assert json.loads(retry.stdout)["duplicate"] is True
    path = store / "observations.jsonl"
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["duration_seconds"] is None
    assert "private-conversation" not in path.read_text()
    assert str(tmp_path) not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o600
    assert store.stat().st_mode & 0o777 == 0o700
    conflict = record(store, "--event-id", "retry-one", "--outcome", "failure")
    assert conflict.returncode == 1
    assert len(path.read_text().splitlines()) == 1


@pytest.mark.parametrize(
    "args",
    [
        ("--duration-seconds", "-1", "--duration-scope", "task"),
        ("--duration-seconds", "nan", "--duration-scope", "task"),
        ("--duration-seconds", "inf", "--duration-scope", "skill"),
        ("--duration-seconds", "3"),
        ("--duration-scope", "skill"),
    ],
)
def test_invalid_durations_do_not_write(tmp_path, args):
    assert record(tmp_path, *args).returncode == 1
    assert not (tmp_path / "observations.jsonl").exists()


def test_parallel_writers_preserve_all_records(tmp_path):
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(HOOK),
                "--store",
                str(tmp_path),
                "record",
                "duct",
                "--task",
                "build-validation",
                "--outcome",
                "success",
                "--event-id",
                str(i),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for i in range(16)
    ]
    for process in processes:
        process.communicate()
        assert process.returncode == 0
    rows = [
        json.loads(s)
        for s in (tmp_path / "observations.jsonl").read_text().splitlines()
    ]
    assert len({r["id"] for r in rows}) == 16


def test_statistics_keep_unknowns_and_duration_scopes_separate(tmp_path):
    record(
        tmp_path,
        "--duration-seconds",
        "20",
        "--duration-scope",
        "task",
        "--task-outcome",
        "failure",
    )
    record(
        tmp_path,
        "--outcome",
        "failure",
        "--duration-seconds",
        "4",
        "--duration-scope",
        "skill",
    )
    record(tmp_path, "--outcome", "unknown")
    group = json.loads(call(tmp_path, "summary").stdout)["groups"][0]
    assert group["n"] == 3
    assert group["known_outcomes"] == 2
    assert group["success_fraction_known"] == 0.5
    assert group["durations"]["task"] == {"n": 1, "median_seconds": 20}
    assert group["durations"]["skill"] == {"n": 1, "median_seconds": 4}
    assert group["task_outcomes"]["failure"] == 1


def test_digest_separates_revisions_without_path(tmp_path):
    entry = tmp_path / "SKILL.md"
    entry.write_text("first")
    store = tmp_path / "state"
    record(store, "--skill-path", str(entry))
    entry.write_text("second")
    record(store, "--skill-path", str(entry))
    assert len(json.loads(call(store, "summary").stdout)["groups"]) == 2
    assert str(entry) not in (store / "observations.jsonl").read_text()


def test_notes_group_prioritize_and_resolve(tmp_path):
    usage = json.loads(record(tmp_path).stdout)["id"]

    def note(group, priority, *args):
        result = call(
            tmp_path,
            "note",
            "duct",
            "--group",
            group,
            "--priority",
            str(priority),
            "--summary",
            "Sampling issue",
            "--action",
            "Check runtime",
            *args,
        )
        assert result.returncode == 0, result.stderr

    note("minor", 3)
    note("blocking", 1, "--usage-id", usage)
    note("blocking", 1, "--usage-id", usage)
    rows = json.loads(call(tmp_path, "insights").stdout)
    assert rows[0]["group"] == "blocking"
    assert rows[0]["observations"] == 2
    assert rows[0]["linked_uses"] == 1
    note("blocking", 1, "--status", "resolved")
    assert [r["group"] for r in json.loads(call(tmp_path, "insights").stdout)] == [
        "minor"
    ]
    assert (
        call(
            tmp_path,
            "note",
            "other",
            "--group",
            "bad",
            "--summary",
            "bad",
            "--action",
            "bad",
            "--usage-id",
            usage,
        ).returncode
        == 1
    )


def test_rejects_git_store_and_corrupt_history(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").write_text("gitdir: elsewhere")
    assert record(repo / "state").returncode == 1
    store = tmp_path / "state"
    store.mkdir()
    path = store / "observations.jsonl"
    path.write_text('{"partial":')
    assert record(store).returncode == 1
    assert path.read_text() == '{"partial":'


def test_no_automatic_environment_capture(tmp_path, monkeypatch):
    monkeypatch.setenv("SECRET_TOKEN", "never-record-this")
    assert record(tmp_path).returncode == 0
    assert "never-record-this" not in (tmp_path / "observations.jsonl").read_text()
    assert (
        json.loads(call(tmp_path, "summary", "--since", "2999-01-01").stdout)["groups"]
        == []
    )
