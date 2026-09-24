"""Behavioral checks for validated records, overlays, and measurement semantics."""

import json
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

SKILL = Path(__file__).resolve().parents[1] / ".agents/skills/workshop-feedback"
HOOK = SKILL / "scripts/usage.py"
SCHEMA = json.loads((SKILL / "schemas/observation-v2.schema.json").read_text())


def call(store, *args):
    return subprocess.run(
        [
            sys.executable,
            str(HOOK),
            "--store",
            str(store / "public"),
            "--overlay",
            str(store / "overlay"),
            *args,
        ],
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


def rows(store, tree="public"):
    return [
        json.loads(p.read_text()) for p in (store / tree).glob("records/*/*/*.json")
    ]


def test_minimal_record_validated_and_deduplicated(tmp_path, monkeypatch):
    Draft202012Validator.check_schema(SCHEMA)
    monkeypatch.setenv("CODEX_THREAD_ID", "private-conversation")
    event_id = str(uuid.uuid4())
    assert record(tmp_path, "--event-id", event_id).returncode == 0
    retry = record(tmp_path, "--event-id", event_id)
    assert json.loads(retry.stdout)["duplicate"] is True
    data = rows(tmp_path)
    assert len(data) == 1
    Draft202012Validator(SCHEMA, format_checker=FormatChecker()).validate(data[0])
    assert data[0]["duration_seconds"] is None
    assert "private-conversation" not in json.dumps(data)
    assert str(tmp_path) not in json.dumps(data)
    conflict = record(tmp_path, "--event-id", event_id, "--outcome", "failure")
    assert conflict.returncode == 1
    assert len(rows(tmp_path)) == 1


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
    assert not rows(tmp_path)


def test_parallel_writers_preserve_records(tmp_path):
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                str(HOOK),
                "--store",
                str(tmp_path / "public"),
                "--overlay",
                str(tmp_path / "overlay"),
                "record",
                "duct",
                "--task",
                "build-validation",
                "--outcome",
                "success",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(8)
    ]
    for process in processes:
        process.communicate()
        assert process.returncode == 0
    assert len({r["id"] for r in rows(tmp_path)}) == 8


def test_statistics_keep_unknowns_and_scopes_separate(tmp_path):
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


def test_digest_separates_revisions(tmp_path):
    entry = tmp_path / "SKILL.md"
    entry.write_text("first")
    record(tmp_path, "--skill-path", str(entry))
    entry.write_text("second")
    record(tmp_path, "--skill-path", str(entry))
    assert len(json.loads(call(tmp_path, "summary").stdout)["groups"]) == 2


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
    data = json.loads(call(tmp_path, "insights").stdout)
    assert data[0]["group"] == "blocking"
    assert data[0]["observations"] == 2
    assert data[0]["linked_uses"] == 1
    note("blocking", 1, "--status", "resolved")
    assert [r["group"] for r in json.loads(call(tmp_path, "insights").stdout)] == [
        "minor"
    ]


def details(tmp_path, data):
    path = tmp_path / "details.json"
    path.write_text(json.dumps(data))
    return str(path)


def test_overlay_removes_sensitive_fields_and_merges_once(tmp_path):
    source = details(
        tmp_path,
        {
            "context": {
                "session_id": "sensitive-session",
                "task_summary": "Validation",
            },
            "resources": {"input_tokens": 123, "cost_usd": 0.01},
        },
    )
    event_id = str(uuid.uuid4())
    args = (
        "--details",
        source,
        "--private-fields",
        "/context/session_id",
        "--sensitivity-category",
        "private-conversation",
        "--sensitivity-reason",
        "Internal conversation reference",
        "--event-id",
        event_id,
    )
    result = record(tmp_path, *args)
    assert result.returncode == 0, result.stderr
    assert "sensitive-session" not in json.dumps(rows(tmp_path))
    assert "sensitivity" not in rows(tmp_path)[0]
    assert rows(tmp_path, "overlay")[0]["context"]["session_id"] == "sensitive-session"
    assert (tmp_path / "overlay").stat().st_mode & 0o777 == 0o700
    overlay_file = next((tmp_path / "overlay").glob("records/*/*/*.json"))
    assert overlay_file.stat().st_mode & 0o777 == 0o600
    group = json.loads(call(tmp_path, "summary").stdout)["groups"][0]
    assert group["n"] == 1
    assert group["metrics"]["resources.input_tokens"] == {"n": 1, "median": 123}
    assert json.loads(call(tmp_path, "sensitivity").stdout)[0]["n"] == 1
    assert json.loads(call(tmp_path, "sensitivity", "--public-only").stdout) == []
    # A retry repairs a missing projection after an interrupted two-tree write.
    next((tmp_path / "public").glob("records/*/*/*.json")).unlink()
    assert record(tmp_path, *args).returncode == 0
    assert len(rows(tmp_path)) == 1
    assert json.loads(call(tmp_path, "summary").stdout)["groups"][0]["n"] == 1


def test_wholly_private_record_and_required_field_redaction(tmp_path):
    args = (
        "--sensitivity-category",
        "confidential-project",
        "--sensitivity-reason",
        "Task identity is confidential",
    )
    assert record(tmp_path, "--private-fields", "/task", *args).returncode == 1
    assert not rows(tmp_path)
    assert record(tmp_path, "--visibility", "private", *args).returncode == 0
    assert not rows(tmp_path)
    assert len(rows(tmp_path, "overlay")) == 1
    assert json.loads(call(tmp_path, "summary", "--public-only").stdout)["groups"] == []


@pytest.mark.parametrize(
    "data",
    [
        {"resources": {"input_tokens": -1}},
        {"resources": {"input_tokens": "many"}},
        {"context": {"undeclared": "x"}},
        {"unexpected": 1},
        {"execution": {"started_at": "not-a-date"}},
        {
            "execution": {
                "started_at": "2026-01-02T00:00:00Z",
                "ended_at": "2026-01-01T00:00:00Z",
            }
        },
    ],
)
def test_schema_rejects_invalid_optional_fields(tmp_path, data):
    result = record(tmp_path, "--details", details(tmp_path, data))
    assert result.returncode == 1
    assert not rows(tmp_path)


def test_shareable_git_tree_allowed_private_git_overlay_rejected(tmp_path):
    (tmp_path / "public").mkdir()
    (tmp_path / "public/.git").write_text("gitdir: elsewhere")
    assert record(tmp_path).returncode == 0
    (tmp_path / "overlay/.git").write_text("gitdir: elsewhere")
    assert record(tmp_path).returncode == 1


def test_corrupt_history_not_overwritten(tmp_path):
    record(tmp_path)
    path = next((tmp_path / "public").glob("records/*/*/*.json"))
    path.write_text('{"partial":')
    assert record(tmp_path).returncode == 1
    assert path.read_text() == '{"partial":'


def test_sensitive_classification_requires_reason(tmp_path):
    assert record(tmp_path, "--visibility", "private").returncode == 1
    assert not rows(tmp_path)
