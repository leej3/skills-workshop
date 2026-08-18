from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

from scripts import workshop as workshop_cli

SCHEMA_KINDS = tuple(workshop_cli.SCHEMA_NAMES)


@pytest.fixture
def memory_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills-workshop"
    shutil.copytree(
        workshop_cli.REPOSITORY / "schemas" / "memory",
        root / "schemas" / "memory",
    )
    return root


@pytest.fixture
def invoke(memory_root: Path) -> Callable[..., int]:
    def run(*arguments: str) -> int:
        return workshop_cli.main(["--root", str(memory_root), *arguments])

    return run


def records(root: Path, kind: str) -> list[dict[str, Any]]:
    return [record for _, record in workshop_cli.load_records(root, kind)]


def remember(
    invoke: Callable[..., int],
    name: str = "example-skill",
    *extra: str,
) -> None:
    assert (
        invoke(
            "remember",
            name,
            "--summary",
            f"Summary for {name}",
            *extra,
        )
        == 0
    )


def artifact_add_arguments(
    skill: str,
    *,
    source: str | None = None,
    revision: str = "abc123",
    digest_value: str = "a" * 64,
) -> list[str]:
    arguments = [
        "artifact",
        "add",
        skill,
        "--revision",
        revision,
        "--version-label",
        "v1.0.0",
        "--digest-scheme",
        "content",
        "--digest-algorithm",
        "sha256",
        "--digest-scope",
        "skill-tree",
        "--digest-value",
        digest_value,
    ]
    if source is not None:
        arguments.extend(["--source", source])
    return arguments


def completed_evaluation(
    memory_root: Path,
    invoke: Callable[..., int],
    *,
    design: str = "controlled-paired",
    repeats: int = 1,
) -> tuple[Path, dict[str, Any]]:
    remember(
        invoke,
        "evaluated-skill",
        "--source",
        "https://github.com/example/evaluated-skill.git",
        "--source-kind",
        "git",
        "--source-role",
        "canonical",
    )
    assert invoke(*artifact_add_arguments("evaluated-skill")) == 0
    skill = records(memory_root, "skills")[0]
    artifact_id = skill["artifacts"][0]["id"]
    digest = "sha256:" + "b" * 64
    assert (
        invoke(
            "eval",
            "init",
            "evaluated-skill",
            "--design",
            design,
            "--artifact",
            artifact_id,
            "--hypothesis",
            "The skill improves provenance accuracy.",
            "--protocol",
            "docs/evaluation-protocol.md",
            "--protocol-digest",
            digest,
            "--fixture",
            "fixtures/repository",
            "--fixture-digest",
            digest,
            "--fixture-revision",
            "fixture-v1",
            "--prompt",
            "Create a correctly attributed commit.",
            "--expected",
            "Both required trailers are present.",
            "--metric",
            "Trailer correctness",
            "--agent",
            "codex",
            "--agent-version",
            "1.2.3",
            "--model",
            "gpt-test",
            "--reasoning-effort",
            "high",
            "--tool",
            "shell",
            "--permission",
            "workspace-write",
            "--token-budget",
            "4096",
            "--budget-notes",
            "The same limit applies to both conditions.",
        )
        == 0
    )
    evaluation_path, evaluation = workshop_cli.load_records(memory_root, "evaluations")[
        0
    ]
    evaluation["status"] = "complete"
    evaluation["metrics"].append(
        {
            "id": "corrections",
            "description": "Number of required corrections",
            "unit": "count",
            "direction": "lower-better",
        }
    )
    evaluation["grading"] = {
        "kind": "agent",
        "grader": {"kind": "agent", "id": "grader-test"},
        "rubric": {"uri": "docs/rubric.md", "digest": digest},
        "blinded": True,
    }
    evaluation["analysis"] = {
        "conclusion": "better",
        "summary": "Treatment satisfied the rubric more reliably.",
        "limitations": ["Synthetic fixture."],
    }
    evaluation["runs"] = []
    for condition in evaluation["conditions"]:
        for repeat in range(repeats):
            run_id = workshop_cli.new_id()
            evaluation["runs"].append(
                {
                    "id": run_id,
                    "condition_id": condition["id"],
                    "case_id": "case-1",
                    "started_at": f"2026-08-17T12:0{repeat}:00Z",
                    "outcome": "success",
                    "metrics": {"primary": 1.0, "corrections": 0.0},
                    "evidence": [
                        {
                            "uri": f"evidence/{workshop_cli.bare_id(run_id)}.json",
                            "digest": digest,
                        }
                    ],
                    "notes": "Fresh isolated run.",
                }
            )
    evaluation_path.write_text(workshop_cli.json_text(evaluation), encoding="utf-8")
    assert workshop_cli.validate_memory(memory_root) == []
    return evaluation_path, evaluation


@pytest.mark.parametrize("kind", SCHEMA_KINDS)
def test_memory_schema_is_valid_json_schema(kind: str) -> None:
    schema_path = (
        workshop_cli.REPOSITORY / "schemas" / "memory" / workshop_cli.SCHEMA_NAMES[kind]
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"] == workshop_cli.schema_uri(kind)


def test_empty_memory_validates(
    invoke: Callable[..., int], capsys: pytest.CaptureFixture[str]
) -> None:
    assert invoke("validate", "--json") == 0

    report = json.loads(capsys.readouterr().out)
    assert report == {"valid": True, "errors": []}


def test_remember_supports_source_free_and_provenanced_skills(
    memory_root: Path,
    invoke: Callable[..., int],
) -> None:
    remember(invoke, "remembered-from-use", "--alias", "old-name")
    remember(
        invoke,
        "commit-provenance",
        "--source",
        "https://github.com/example/skills.git",
        "--source-kind",
        "git",
        "--source-role",
        "canonical",
        "--subpath",
        "skills/commit-provenance",
        "--source-notes",
        "Located through gh skill.",
    )

    by_name = {record["name"]: record for record in records(memory_root, "skills")}
    source_free = by_name["remembered-from-use"]
    sourced = by_name["commit-provenance"]

    assert source_free["sources"] == []
    assert "preferred_source_id" not in source_free
    assert source_free["aliases"] == ["old-name"]
    assert sourced["preferred_source_id"] == sourced["sources"][0]["id"]
    assert sourced["sources"][0] == {
        "id": sourced["preferred_source_id"],
        "kind": "git",
        "locator": "https://github.com/example/skills.git",
        "subpath": "skills/commit-provenance",
        "role": "canonical",
        "first_seen_at": sourced["created_at"],
        "external_ids": {},
        "notes": "Located through gh skill.",
    }
    assert workshop_cli.validate_memory(memory_root) == []


def test_source_add_preserves_logical_identity_and_rejects_duplicates(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(
        invoke,
        "portable-skill",
        "--source",
        "https://github.com/upstream/skills.git",
        "--source-kind",
        "git",
        "--source-role",
        "canonical",
        "--subpath",
        "skills/portable-skill",
    )
    original = records(memory_root, "skills")[0]
    original_id = original["id"]
    original_preferred = original["preferred_source_id"]

    assert (
        invoke(
            "source",
            "add",
            "portable-skill",
            "--source",
            "https://github.com/fork/skills.git",
            "--source-kind",
            "git",
            "--source-role",
            "fork",
            "--subpath",
            "skills/portable-skill",
            "--notes",
            "Contribution fork.",
        )
        == 0
    )

    updated = records(memory_root, "skills")[0]
    assert updated["id"] == original_id
    assert updated["preferred_source_id"] == original_preferred
    assert len(updated["sources"]) == 2
    assert {source["locator"] for source in updated["sources"]} == {
        "https://github.com/upstream/skills.git",
        "https://github.com/fork/skills.git",
    }
    fork = next(
        source
        for source in updated["sources"]
        if source["locator"] == "https://github.com/fork/skills.git"
    )
    assert fork["role"] == "fork"
    assert fork["notes"] == "Contribution fork."
    capsys.readouterr()

    assert (
        invoke(
            "source",
            "add",
            "portable-skill",
            "--source",
            "https://github.com/fork/skills.git",
            "--source-kind",
            "git",
            "--source-role",
            "mirror",
            "--subpath",
            "skills/portable-skill",
        )
        == 2
    )
    assert "source already recorded" in capsys.readouterr().err
    after_duplicate = records(memory_root, "skills")[0]
    assert after_duplicate["id"] == original_id
    assert after_duplicate["sources"] == updated["sources"]
    assert workshop_cli.validate_memory(memory_root) == []


def test_artifact_add_uses_preferred_source_and_rejects_duplicates(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(
        invoke,
        "versioned-skill",
        "--source",
        "https://github.com/example/versioned-skill.git",
        "--source-kind",
        "git",
        "--source-role",
        "canonical",
    )
    original = records(memory_root, "skills")[0]
    preferred_source_id = original["preferred_source_id"]

    assert invoke(*artifact_add_arguments("versioned-skill")) == 0

    updated = records(memory_root, "skills")[0]
    assert updated["id"] == original["id"]
    assert len(updated["artifacts"]) == 1
    artifact = updated["artifacts"][0]
    assert artifact["source_id"] == preferred_source_id
    assert artifact["version_label"] == "v1.0.0"
    assert artifact["resolved_revision"] == "abc123"
    assert artifact["digests"] == [
        {
            "scheme": "content",
            "algorithm": "sha256",
            "scope": "skill-tree",
            "value": "a" * 64,
        }
    ]
    capsys.readouterr()

    assert invoke(*artifact_add_arguments("versioned-skill")) == 2
    assert "artifact already recorded" in capsys.readouterr().err
    after_duplicate = records(memory_root, "skills")[0]
    assert after_duplicate["artifacts"] == [artifact]
    assert workshop_cli.validate_memory(memory_root) == []


def test_artifact_add_requires_one_unambiguous_recorded_source(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(invoke, "source-free-skill")
    assert invoke(*artifact_add_arguments("source-free-skill")) == 2
    assert "no preferred source; specify --source" in capsys.readouterr().err
    assert records(memory_root, "skills")[0]["artifacts"] == []

    locator = "https://github.com/example/shared-location"
    remember(
        invoke,
        "ambiguous-source-skill",
        "--source",
        locator,
        "--source-kind",
        "git",
        "--source-role",
        "canonical",
    )
    assert (
        invoke(
            "source",
            "add",
            "ambiguous-source-skill",
            "--source",
            locator,
            "--source-kind",
            "http",
            "--source-role",
            "mirror",
        )
        == 0
    )
    capsys.readouterr()

    assert (
        invoke(*artifact_add_arguments("ambiguous-source-skill", source=locator)) == 2
    )
    assert (
        "--source must identify exactly one recorded source" in capsys.readouterr().err
    )
    by_name = {record["name"]: record for record in records(memory_root, "skills")}
    assert by_name["ambiguous-source-skill"]["artifacts"] == []
    assert workshop_cli.validate_memory(memory_root) == []


def test_show_human_output_includes_source_subpath_and_notes(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(
        invoke,
        "document-helper",
        "--source",
        "https://github.com/example/skills.git",
        "--source-kind",
        "git",
        "--source-role",
        "canonical",
        "--subpath",
        "skills/document-helper",
        "--source-notes",
        "Reviewed during the documentation pilot.",
    )
    skill = records(memory_root, "skills")[0]
    capsys.readouterr()

    assert invoke("show", "document-helper") == 0

    assert capsys.readouterr().out == (
        f"document-helper [{skill['id']}]\n"
        "Summary for document-helper\n"
        "Source (canonical, git): https://github.com/example/skills.git"
        " :: skills/document-helper\n"
        "  Reviewed during the documentation pilot.\n"
        "History: 0 event(s)\n"
    )


def test_project_add_records_only_portable_apm_pointers(
    memory_root: Path,
    invoke: Callable[..., int],
) -> None:
    assert (
        invoke(
            "project",
            "add",
            "analysis-project",
            "--alias",
            "analysis",
            "--repo-url",
            "https://github.com/example/analysis.git",
            "--subpath",
            "packages/pipeline",
            "--manifest",
            "config/apm.yml",
            "--lock",
            "config/apm.lock.yaml",
            "--notes",
            "Project-local APM remains authoritative.",
        )
        == 0
    )

    project = records(memory_root, "projects")[0]
    assert project["name"] == "analysis-project"
    assert project["aliases"] == ["analysis"]
    assert project["repository"] == {
        "url": "https://github.com/example/analysis.git",
        "subpath": "packages/pipeline",
    }
    assert project["managers"] == [
        {
            "kind": "apm",
            "manifest_path": "config/apm.yml",
            "lock_path": "config/apm.lock.yaml",
        }
    ]
    assert "path" not in project
    assert workshop_cli.validate_memory(memory_root) == []


def test_project_scan_records_only_known_membership_and_is_idempotent(
    memory_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(invoke, "commit-provenance")
    remember(invoke, "skills-workshop")
    assert invoke("project", "add", "workshop-project") == 0
    project = records(memory_root, "projects")[0]
    downstream = memory_root / "downstream"
    downstream.mkdir()
    (downstream / "apm.lock.yaml").write_text(
        """\
lockfile_version: '1'
apm_version: 0.28.0
dependencies:
  - name: commit-provenance
    source: local
    local_path: ./skills/commit-provenance
  - name: skills-workshop
    source: local
    local_path: ./skills/skills-workshop
  - name: unremembered-skill
    source: local
    local_path: ./skills/unremembered-skill
""",
        encoding="utf-8",
    )

    def fake_project_evidence(
        root: Path, project_record: dict[str, Any], project_path: Path
    ) -> dict[str, Any]:
        assert root == memory_root
        assert project_record["id"] == project["id"]
        assert project_path == downstream
        return {
            "project_id": project["id"],
            "repository_commit": "abc123",
            "dirty": False,
            "manifest_path": "apm.yml",
            "lock_path": "apm.lock.yaml",
            "lock_digest": "sha256:" + "b" * 64,
            "dependency_selector": None,
            "command": ["apm", "deps", "list"],
            "apm_version": "APM 0.28.0",
        }

    monkeypatch.setattr(workshop_cli, "project_evidence", fake_project_evidence)
    capsys.readouterr()

    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    first_output = capsys.readouterr().out
    assert "Recorded 2 APM membership event(s)" in first_output
    assert "Not remembered; left only in APM: unremembered-skill" in first_output

    skills = {record["name"]: record for record in records(memory_root, "skills")}
    assert set(skills) == {"commit-provenance", "skills-workshop"}
    membership = records(memory_root, "events")
    assert len(membership) == 2
    assert {event["type"] for event in membership} == {"project-membership"}
    assert {event["skill_id"] for event in membership} == {
        skills["commit-provenance"]["id"],
        skills["skills-workshop"]["id"],
    }
    assert {event["payload"]["skill_name"] for event in membership} == {
        "commit-provenance",
        "skills-workshop",
    }
    assert {
        event["project_evidence"]["dependency_selector"] for event in membership
    } == {
        "./skills/commit-provenance",
        "./skills/skills-workshop",
    }
    assert all(
        event["payload"]["state"] == "resolved"
        and event["asserted_by"]
        == {
            "kind": "tool",
            "id": "apm-lock",
            "runtime": "apm",
            "runtime_version": "APM 0.28.0",
        }
        for event in membership
    )
    first_ids = {event["id"] for event in membership}

    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    second_output = capsys.readouterr().out
    assert "Recorded 0 APM membership event(s)" in second_output
    assert "Not remembered; left only in APM: unremembered-skill" in second_output
    assert {event["id"] for event in records(memory_root, "events")} == first_ids

    assert invoke("where-used", "commit-provenance", "--json") == 0
    usage = json.loads(capsys.readouterr().out)
    commit_membership = next(
        event
        for event in membership
        if event["skill_id"] == skills["commit-provenance"]["id"]
    )
    resolution_digest = commit_membership["payload"]["resolution_digest"]
    assert resolution_digest.startswith("sha256:")
    assert len(resolution_digest) == len("sha256:") + 64
    assert usage == [
        {
            "event_id": commit_membership["id"],
            "type": "project-membership",
            "occurred_at": commit_membership["occurred_at"],
            "project_id": project["id"],
            "project_name": "workshop-project",
            "payload": {
                "state": "resolved",
                "skill_name": "commit-provenance",
                "resolution_digest": resolution_digest,
            },
        }
    ]
    assert workshop_cli.validate_memory(memory_root) == []


def test_project_scan_keys_membership_to_the_dependency_resolution(
    memory_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(invoke, "commit-provenance")
    assert invoke("project", "add", "workshop-project") == 0
    project = records(memory_root, "projects")[0]
    downstream = memory_root / "downstream"
    downstream.mkdir()
    lock_path = downstream / "apm.lock.yaml"

    def write_lock(*, generated_at: str, version: str = "0.0.0") -> None:
        lock_path.write_text(
            f"""\
lockfile_version: '1'
generated_at: {generated_at!r}
dependencies:
  - name: commit-provenance
    version: {version}
    source: local
    local_path: ./skills/commit-provenance
""",
            encoding="utf-8",
        )

    def fake_project_evidence(
        root: Path, project_record: dict[str, Any], project_path: Path
    ) -> dict[str, Any]:
        assert root == memory_root
        assert project_record["id"] == project["id"]
        lock_digest = hashlib.sha256(lock_path.read_bytes()).hexdigest()
        return {
            "project_id": project["id"],
            "repository_commit": "abc123",
            "dirty": False,
            "manifest_path": "apm.yml",
            "lock_path": "apm.lock.yaml",
            "lock_digest": f"sha256:{lock_digest}",
            "dependency_selector": None,
            "command": ["apm", "deps", "list"],
            "apm_version": "0.28.0",
        }

    monkeypatch.setattr(workshop_cli, "project_evidence", fake_project_evidence)
    write_lock(generated_at="2026-08-17T00:00:00Z")
    capsys.readouterr()

    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    assert "Recorded 1 APM membership event(s)" in capsys.readouterr().out
    first_event = records(memory_root, "events")[0]

    write_lock(generated_at="2026-08-18T00:00:00Z")
    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    assert "Recorded 0 APM membership event(s)" in capsys.readouterr().out
    assert [event["id"] for event in records(memory_root, "events")] == [
        first_event["id"]
    ]

    write_lock(generated_at="2026-08-19T00:00:00Z", version="0.1.0")
    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    assert "Recorded 1 APM membership event(s)" in capsys.readouterr().out
    events = records(memory_root, "events")
    assert len(events) == 2
    assert len({event["project_evidence"]["lock_digest"] for event in events}) == 2
    assert len({event["payload"]["resolution_digest"] for event in events}) == 2
    assert workshop_cli.validate_memory(memory_root) == []


def test_project_scan_records_root_local_apm_skills(
    memory_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(invoke, "commit-provenance")
    remember(invoke, "skills-workshop")
    assert invoke("project", "add", "workshop-project") == 0
    project = records(memory_root, "projects")[0]
    downstream = memory_root / "downstream"
    downstream.mkdir()
    lock_path = downstream / "apm.lock.yaml"

    def write_lock(workshop_hash: str = "b" * 64) -> None:
        lock_path.write_text(
            f"""\
lockfile_version: '1'
apm_version: 0.28.0
dependencies: []
deployments:
  - kind: project-relative
    value: .agents/skills/commit-provenance
    active_owner: .
    content_hash: null
  - kind: project-relative
    value: .agents/skills/skills-workshop
    active_owner: .
    content_hash: null
  - kind: project-relative
    value: .agents/skills/unremembered-skill
    active_owner: .
    content_hash: null
local_deployed_files:
  - .agents/skills/commit-provenance
  - .agents/skills/commit-provenance/SKILL.md
  - .agents/skills/skills-workshop
  - .agents/skills/skills-workshop/SKILL.md
  - .agents/skills/unremembered-skill
  - .agents/skills/unremembered-skill/SKILL.md
local_deployed_file_hashes:
  .agents/skills/commit-provenance/SKILL.md: sha256:{"a" * 64}
  .agents/skills/skills-workshop/SKILL.md: sha256:{workshop_hash}
  .agents/skills/unremembered-skill/SKILL.md: sha256:{"c" * 64}
""",
            encoding="utf-8",
        )

    def fake_project_evidence(
        root: Path, project_record: dict[str, Any], project_path: Path
    ) -> dict[str, Any]:
        assert root == memory_root
        assert project_record["id"] == project["id"]
        assert project_path == downstream
        return {
            "project_id": project["id"],
            "repository_commit": "abc123",
            "dirty": False,
            "manifest_path": "apm.yml",
            "lock_path": "apm.lock.yaml",
            "lock_digest": "sha256:"
            + hashlib.sha256(lock_path.read_bytes()).hexdigest(),
            "dependency_selector": None,
            "command": ["apm", "deps", "list"],
            "apm_version": "0.28.0",
        }

    monkeypatch.setattr(workshop_cli, "project_evidence", fake_project_evidence)
    write_lock()
    capsys.readouterr()

    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    output = capsys.readouterr().out
    assert "Recorded 2 APM membership event(s)" in output
    assert "Not remembered; left only in APM: unremembered-skill" in output
    events = records(memory_root, "events")
    assert {event["project_evidence"]["dependency_selector"] for event in events} == {
        ".apm/skills/commit-provenance",
        ".apm/skills/skills-workshop",
    }

    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    assert "Recorded 0 APM membership event(s)" in capsys.readouterr().out

    write_lock(workshop_hash="d" * 64)
    assert (
        invoke(
            "project",
            "scan",
            "workshop-project",
            "--project-path",
            str(downstream),
        )
        == 0
    )
    assert "Recorded 1 APM membership event(s)" in capsys.readouterr().out
    assert len(records(memory_root, "events")) == 3
    assert workshop_cli.validate_memory(memory_root) == []


def test_consideration_and_rated_use_are_distinct_append_only_evidence(
    memory_root: Path,
    invoke: Callable[..., int],
) -> None:
    remember(invoke)

    assert (
        invoke(
            "consider",
            "example-skill",
            "--decision",
            "adopted",
            "--reason",
            "The provenance checks fit this repository.",
            "--asserted-kind",
            "human",
            "--asserted-by",
            "john",
        )
        == 0
    )
    assert (
        invoke(
            "use",
            "example-skill",
            "--task",
            "Attribute a release commit",
            "--invocation",
            "explicit",
            "--outcome",
            "success",
            "--rating",
            "4",
            "--rationale",
            "Useful with one minor correction.",
            "--listing-state",
            "full-description",
            "--asserted-kind",
            "human",
            "--asserted-by",
            "john",
        )
        == 0
    )

    events = records(memory_root, "events")
    assert {event["type"] for event in events} == {"consideration", "use"}
    assert len({event["id"] for event in events}) == 2
    use = next(event for event in events if event["type"] == "use")
    assert use["payload"]["rating"] == 4
    assert use["payload"]["scale_id"] == "workshop-overall-v1"
    assert use["payload"]["listing_state"] == "full-description"
    assert use["asserted_by"] == {"kind": "human", "id": "john"}
    assert use["review"] == {"state": "unreviewed"}
    assert workshop_cli.validate_memory(memory_root) == []


def test_history_human_output_identifies_asserting_actor_and_review_state(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(invoke)
    assert (
        invoke(
            "consider",
            "example-skill",
            "--decision",
            "adopted",
            "--reason",
            "The checks matched the repository policy.",
            "--asserted-kind",
            "agent",
            "--asserted-by",
            "codex-test",
        )
        == 0
    )
    event = records(memory_root, "events")[0]
    capsys.readouterr()

    assert invoke("history", "example-skill") == 0

    assert capsys.readouterr().out == (
        "History for example-skill (1 event(s))\n"
        f"- {event['occurred_at']} consideration "
        "[agent:codex-test; unreviewed]: "
        "The checks matched the repository policy.\n"
    )


def test_contribution_add_round_trip_and_invalid_artifact_is_atomic(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(
        invoke,
        "contributed-skill",
        "--source",
        "https://github.com/example/contributed-skill.git",
        "--source-kind",
        "git",
        "--source-role",
        "canonical",
    )
    assert invoke(*artifact_add_arguments("contributed-skill")) == 0
    skill = records(memory_root, "skills")[0]
    artifact_id = skill["artifacts"][0]["id"]
    capsys.readouterr()

    assert (
        invoke(
            "contribution",
            "add",
            "contributed-skill",
            "--kind",
            "pull-request",
            "--direction",
            "upstream",
            "--url",
            "https://github.com/example/contributed-skill/pull/12",
            "--state",
            "open",
            "--summary",
            "Proposed a portable provenance check.",
            "--artifact",
            artifact_id,
            "--asserted-kind",
            "agent",
            "--asserted-by",
            "codex-test",
            "--model",
            "gpt-test",
            "--runtime",
            "codex",
            "--runtime-version",
            "1.2.3",
            "--reasoning-effort",
            "high",
        )
        == 0
    )
    event = records(memory_root, "events")[0]
    assert event["type"] == "contribution"
    assert event["skill_id"] == skill["id"]
    assert event["artifact_id"] == artifact_id
    assert event["payload"] == {
        "kind": "pull-request",
        "direction": "upstream",
        "url": "https://github.com/example/contributed-skill/pull/12",
        "state": "open",
        "summary": "Proposed a portable provenance check.",
    }
    assert event["asserted_by"] == {
        "kind": "agent",
        "id": "codex-test",
        "model": "gpt-test",
        "runtime": "codex",
        "runtime_version": "1.2.3",
        "reasoning_effort": "high",
    }
    assert event["review"] == {"state": "unreviewed"}
    capsys.readouterr()

    assert invoke("history", "contributed-skill") == 0
    assert capsys.readouterr().out == (
        "History for contributed-skill (1 event(s))\n"
        f"- {event['occurred_at']} contribution "
        "[agent:codex-test; unreviewed]: "
        "Proposed a portable provenance check.\n"
    )

    before = {
        path: path.read_bytes()
        for path in workshop_cli.record_paths(memory_root, "events")
    }
    assert (
        invoke(
            "contribution",
            "add",
            "contributed-skill",
            "--kind",
            "commit",
            "--direction",
            "upstream",
            "--url",
            "https://github.com/example/contributed-skill/commit/abc123",
            "--state",
            "submitted",
            "--summary",
            "This event must roll back.",
            "--artifact",
            workshop_cli.new_id(),
            "--asserted-kind",
            "agent",
            "--asserted-by",
            "codex-test",
        )
        == 2
    )
    assert "record would invalidate memory" in capsys.readouterr().err
    after = {
        path: path.read_bytes()
        for path in workshop_cli.record_paths(memory_root, "events")
    }
    assert after == before
    assert workshop_cli.validate_memory(memory_root) == []


def test_memory_find_recalls_skills_from_event_text_and_source_locator(
    invoke: Callable[..., int], capsys: pytest.CaptureFixture[str]
) -> None:
    remember(
        invoke,
        "annex-helper",
        "--source",
        "https://github.com/example/lab-data-skills.git",
        "--source-kind",
        "git",
    )
    assert (
        invoke(
            "consider",
            "annex-helper",
            "--decision",
            "adopted",
            "--reason",
            "Recovered a forgotten glacier dataset workflow.",
            "--asserted-kind",
            "human",
            "--asserted-by",
            "john",
        )
        == 0
    )
    capsys.readouterr()

    assert invoke("find", "glacier dataset", "--provider", "memory", "--json") == 0
    event_match = json.loads(capsys.readouterr().out)["memory"]
    assert [result["name"] for result in event_match] == ["annex-helper"]

    assert invoke("find", "lab data", "--provider", "memory", "--json") == 0
    source_match = json.loads(capsys.readouterr().out)["memory"]
    assert [result["name"] for result in source_match] == ["annex-helper"]


def test_where_used_resolves_project_evidence(
    memory_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(invoke)
    assert invoke("project", "add", "analysis-project") == 0
    project = records(memory_root, "projects")[0]

    def fake_project_evidence(
        root: Path, project_record: dict[str, Any], project_path: Path
    ) -> dict[str, Any]:
        assert root == memory_root
        assert project_path == memory_root / "downstream"
        return {
            "project_id": project_record["id"],
            "repository_commit": "abc123",
            "dirty": False,
            "manifest_path": "apm.yml",
            "lock_path": "apm.lock.yaml",
            "lock_digest": "sha256:" + "a" * 64,
            "dependency_selector": "example-skill",
            "command": ["apm", "deps", "list"],
            "apm_version": "APM 0.28.0",
        }

    monkeypatch.setattr(workshop_cli, "project_evidence", fake_project_evidence)
    assert (
        invoke(
            "use",
            "example-skill",
            "--task",
            "Prepare analysis",
            "--invocation",
            "automatic",
            "--outcome",
            "success",
            "--rationale",
            "The procedure was followed.",
            "--project",
            "analysis-project",
            "--project-path",
            str(memory_root / "downstream"),
            "--asserted-kind",
            "agent",
            "--asserted-by",
            "codex",
        )
        == 0
    )
    capsys.readouterr()

    assert invoke("where-used", "example-skill", "--json") == 0
    usage = json.loads(capsys.readouterr().out)
    assert len(usage) == 1
    assert usage[0]["type"] == "use"
    assert usage[0]["project_id"] == project["id"]
    assert usage[0]["project_name"] == "analysis-project"


def test_evaluation_scaffold_and_controlled_artifact_guard(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(invoke)
    capsys.readouterr()

    guarded = invoke(
        "eval",
        "init",
        "example-skill",
        "--design",
        "controlled-paired",
        "--hypothesis",
        "The skill improves provenance accuracy.",
        "--fixture",
        "fixtures/repository",
        "--prompt",
        "Create a correctly attributed commit.",
        "--expected",
        "Both required trailers are present.",
        "--metric",
        "Trailer correctness",
    )
    assert guarded == 2
    assert (
        "controlled and replicated designs require --artifact"
        in capsys.readouterr().err
    )
    assert records(memory_root, "evaluations") == []

    assert (
        invoke(
            "eval",
            "init",
            "example-skill",
            "--design",
            "exploratory",
            "--hypothesis",
            "The skill improves provenance accuracy.",
            "--fixture",
            "fixtures/repository",
            "--prompt",
            "Create a correctly attributed commit.",
            "--expected",
            "Both required trailers are present.",
            "--metric",
            "Trailer correctness",
            "--agent",
            "codex",
            "--model",
            "gpt-test",
            "--tool",
            "shell",
            "--permission",
            "workspace-write",
        )
        == 0
    )

    evaluation = records(memory_root, "evaluations")[0]
    assert evaluation["design"] == "exploratory"
    assert evaluation["status"] == "planned"
    assert [condition["skill_enabled"] for condition in evaluation["conditions"]] == [
        False,
        True,
    ]
    assert (
        evaluation["conditions"][0]["runtime"] == evaluation["conditions"][1]["runtime"]
    )
    assert evaluation["conditions"][1]["runtime"]["tools"] == ["shell"]
    assert evaluation["cases"][0]["expected"] == "Both required trailers are present."
    assert evaluation["runs"] == []
    assert workshop_cli.validate_memory(memory_root) == []


@pytest.mark.parametrize(
    ("design", "repeats"),
    [("controlled-paired", 1), ("replicated", 2)],
)
def test_semantically_complete_evaluation_validates(
    memory_root: Path,
    invoke: Callable[..., int],
    design: str,
    repeats: int,
) -> None:
    _, evaluation = completed_evaluation(
        memory_root, invoke, design=design, repeats=repeats
    )

    expected_runs = 2 * repeats
    assert len(evaluation["runs"]) == expected_runs
    assert (
        evaluation["conditions"][0]["runtime"] == evaluation["conditions"][1]["runtime"]
    )
    assert evaluation["conditions"][0]["runtime"]["budget"] == {
        "time_seconds": None,
        "token_limit": 4096,
        "turn_limit": None,
        "notes": "The same limit applies to both conditions.",
    }


def set_planned_conclusion(evaluation: dict[str, Any]) -> None:
    evaluation["analysis"]["conclusion"] = "planned"


def remove_all_runs(evaluation: dict[str, Any]) -> None:
    evaluation["runs"] = []


def remove_grader(evaluation: dict[str, Any]) -> None:
    evaluation["grading"]["kind"] = "unassigned"
    evaluation["grading"]["grader"] = None


def remove_rubric(evaluation: dict[str, Any]) -> None:
    evaluation["grading"]["rubric"] = None


def remove_treatment_artifact(evaluation: dict[str, Any]) -> None:
    treatment = next(
        condition
        for condition in evaluation["conditions"]
        if condition["skill_enabled"]
    )
    treatment["artifact_id"] = None


def make_runtime_nonconcrete(evaluation: dict[str, Any]) -> None:
    for condition in evaluation["conditions"]:
        condition["runtime"]["model"] = None


def remove_runtime_budget(evaluation: dict[str, Any]) -> None:
    for condition in evaluation["conditions"]:
        condition["runtime"]["budget"] = {
            "time_seconds": None,
            "token_limit": None,
            "turn_limit": None,
            "notes": "",
        }


def mismatch_condition_runtimes(evaluation: dict[str, Any]) -> None:
    evaluation["conditions"][1]["runtime"]["budget"]["token_limit"] = 2048


def remove_treatment_run(evaluation: dict[str, Any]) -> None:
    evaluation["runs"] = [
        run for run in evaluation["runs"] if run["condition_id"] != "with-skill"
    ]


def omit_declared_metric(evaluation: dict[str, Any]) -> None:
    evaluation["runs"][0]["metrics"].pop("corrections")


def claim_replication_without_repeats(evaluation: dict[str, Any]) -> None:
    evaluation["design"] = "replicated"


@pytest.mark.parametrize(
    ("mutate", "expected_fragments"),
    [
        (set_planned_conclusion, ("planned conclusion",)),
        (remove_all_runs, ("requires recorded runs",)),
        (remove_grader, ("requires assigned grading",)),
        (remove_rubric, ("requires assigned grading",)),
        (
            remove_treatment_artifact,
            ("treatment condition", "requires an exact revision and digest"),
        ),
        (make_runtime_nonconcrete, ("lacks concrete runtime fields", "model")),
        (remove_runtime_budget, ("lacks concrete runtime fields", "budget")),
        (mismatch_condition_runtimes, ("conditions must use identical runtimes",)),
        (
            remove_treatment_run,
            ("requires at least 1 run(s) for condition with-skill, case case-1",),
        ),
        (omit_declared_metric, ("lacks metrics", "corrections")),
        (
            claim_replication_without_repeats,
            ("requires at least 2 run(s)",),
        ),
    ],
    ids=[
        "planned-conclusion",
        "no-runs",
        "unassigned-grader",
        "missing-rubric",
        "missing-treatment-artifact",
        "nonconcrete-runtime",
        "missing-budget",
        "mismatched-runtimes",
        "incomplete-condition-case-coverage",
        "missing-declared-metric",
        "unreplicated",
    ],
)
def test_completed_evaluation_rejects_incomplete_semantics(
    memory_root: Path,
    invoke: Callable[..., int],
    mutate: Callable[[dict[str, Any]], None],
    expected_fragments: tuple[str, ...],
) -> None:
    evaluation_path, evaluation = completed_evaluation(memory_root, invoke)
    mutate(evaluation)
    evaluation_path.write_text(workshop_cli.json_text(evaluation), encoding="utf-8")

    errors = workshop_cli.validate_memory(memory_root)

    assert errors
    joined = "\n".join(errors)
    for fragment in expected_fragments:
        assert fragment in joined


def test_schema_invalid_complete_evaluation_reports_errors_without_crashing(
    memory_root: Path,
    invoke: Callable[..., int],
) -> None:
    evaluation_path, evaluation = completed_evaluation(memory_root, invoke)
    evaluation["grading"]["rubric"] = "docs/rubric.md"
    evaluation_path.write_text(workshop_cli.json_text(evaluation), encoding="utf-8")

    errors = workshop_cli.validate_memory(memory_root)

    assert errors
    assert any(
        "grading.rubric" in error
        and "not valid under any of the given schemas" in error
        for error in errors
    )


def test_validate_reports_semantic_reference_failures(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    remember(
        invoke,
        "sourced-skill",
        "--source",
        "https://github.com/example/skills.git",
        "--source-kind",
        "git",
    )
    skill_path, skill = workshop_cli.load_records(memory_root, "skills")[0]
    skill["preferred_source_id"] = workshop_cli.new_id()
    skill_path.write_text(workshop_cli.json_text(skill), encoding="utf-8")
    capsys.readouterr()

    assert invoke("validate", "--json") == 1
    report = json.loads(capsys.readouterr().out)
    assert report["valid"] is False
    assert any(
        "preferred_source_id is not one of this skill's sources" in error
        for error in report["errors"]
    )


def test_external_find_dry_run_prints_exact_pinned_commands(
    memory_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        invoke(
            "find",
            "brain imaging",
            "--provider",
            "asm",
            "--provider",
            "github",
            "--provider",
            "vercel",
            "--limit",
            "7",
            "--dry-run",
            "--json",
        )
        == 0
    )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["asm"]["executed"] is False
    assert output["github"]["executed"] is False
    assert output["vercel"]["executed"] is False
    assert output["asm"]["command"] == [
        "npx",
        "--yes",
        f"agent-skill-manager@{workshop_cli.ASM_VERSION}",
        "search",
        "brain imaging",
        "--available",
        "--machine",
    ]
    assert output["github"]["command"][-2:] == [
        "--json",
        "skillName,description,repo,path,namespace,stars",
    ]
    assert output["vercel"]["command"] == [
        "npx",
        "--yes",
        f"skills@{workshop_cli.VERCEL_SKILLS_VERSION}",
        "find",
        "brain imaging",
    ]
    assert captured.err.count("read-only search") == 3
    assert f"cwd={memory_root}" in captured.err
    assert (
        f"agent-skill-manager@{workshop_cli.ASM_VERSION} search 'brain imaging'"
        in captured.err
    )
    assert "gh skill search 'brain imaging' --limit 7" in captured.err
    assert (
        f"skills@{workshop_cli.VERCEL_SKILLS_VERSION} find 'brain imaging'"
        in captured.err
    )


def test_parse_asm_json_results_honors_limit() -> None:
    payload = json.dumps(
        {
            "success": True,
            "data": [
                {
                    "name": "first-skill",
                    "description": "First result",
                    "source": "community",
                },
                "provider progress message",
                {
                    "name": "second-skill",
                    "description": "Second result",
                    "source": "community",
                },
                {"name": "third-skill", "description": "Beyond the limit"},
            ],
        }
    )

    assert workshop_cli.parse_provider_results("asm", payload, 2) == [
        {
            "name": "first-skill",
            "description": "First result",
            "source": "community",
        },
        {
            "name": "second-skill",
            "description": "Second result",
            "source": "community",
        },
    ]


def test_parse_github_json_results_honors_limit() -> None:
    payload = json.dumps(
        [
            {
                "skillName": "first-skill",
                "description": "First result",
                "repo": "example/skills",
                "path": "skills/first-skill",
                "namespace": "example/skills/first-skill",
                "stars": 42,
            },
            {
                "skillName": "second-skill",
                "description": "Beyond the limit",
                "repo": "example/skills",
                "path": "skills/second-skill",
                "namespace": "example/skills/second-skill",
                "stars": 21,
            },
        ]
    )

    assert workshop_cli.parse_provider_results("github", payload, 1) == [
        {
            "skillName": "first-skill",
            "description": "First result",
            "repo": "example/skills",
            "path": "skills/first-skill",
            "namespace": "example/skills/first-skill",
            "stars": 42,
        }
    ]


def test_parse_ansi_vercel_results_strips_presentation_and_honors_limit() -> None:
    output = (
        "\x1b[1mexample/skills@first-skill\x1b[0m "
        "\x1b[32m1.2K installs\x1b[0m\n"
        "\x1b[2m└ https://skills.sh/example/skills/first-skill\x1b[0m\n"
        "example/skills@second-skill 98 installs\n"
        "└ https://skills.sh/example/skills/second-skill\n"
        "example/skills@third-skill 10 installs\n"
        "└ https://skills.sh/example/skills/third-skill\n"
    )

    assert workshop_cli.parse_provider_results("vercel", output, 2) == [
        {
            "candidate": "example/skills@first-skill",
            "popularity": "1.2K installs",
            "url": "https://skills.sh/example/skills/first-skill",
        },
        {
            "candidate": "example/skills@second-skill",
            "popularity": "98 installs",
            "url": "https://skills.sh/example/skills/second-skill",
        },
    ]


def test_preview_dry_run_prints_exact_non_installing_gh_command(
    memory_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        workshop_cli,
        "command_version",
        lambda command: "gh version 2.97.0",
    )
    assert (
        invoke(
            "preview",
            "con/skills",
            "scan-projects@abc123",
            "--allow-hidden-dirs",
            "--dry-run",
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        (
            "[github] runner=gh version 2.97.0; read-only candidate preview; "
            f"may use network and GitHub authentication; cwd={memory_root}"
        ),
        "$ gh skill preview con/skills scan-projects@abc123 --allow-hidden-dirs",
    ]
    assert captured.out == "Dry run; preview command not executed.\n"
    assert "install" not in captured.err


@pytest.mark.parametrize(
    ("apply", "expected_tail", "mutation_fragment"),
    [
        (False, ["--target", "agent-skills", "--dry-run"], "preview only"),
        (True, ["--target", "agent-skills"], "will update the project's apm.yml"),
    ],
)
def test_install_delegates_to_apm_with_preview_by_default(
    memory_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    apply: bool,
    expected_tail: list[str],
    mutation_fragment: str,
) -> None:
    project = memory_root / "downstream"
    project.mkdir()
    calls: list[tuple[str, list[str], Path, str, bool]] = []

    def fake_run_external(
        provider: str,
        command: list[str],
        cwd: Path,
        mutation: str,
        *,
        dry_run: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        calls.append((provider, command, cwd, mutation, dry_run))
        return subprocess.CompletedProcess(command, 0, "APM completed\n", "")

    monkeypatch.setattr(workshop_cli, "run_external", fake_run_external)
    arguments = [
        "install",
        "github.com/example/skills",
        "--project",
        str(project),
        "--skill",
        "one",
        "--skill",
        "two",
        "--target",
        "agent-skills",
    ]
    if apply:
        arguments.append("--apply")

    assert invoke(*arguments) == 0

    assert len(calls) == 1
    provider, command, cwd, mutation, wrapper_dry_run = calls[0]
    assert provider == "apm"
    assert cwd == project
    assert command[:7] == [
        "apm",
        "install",
        "github.com/example/skills",
        "--skill",
        "one",
        "--skill",
        "two",
    ]
    assert command[-len(expected_tail) :] == expected_tail
    assert mutation_fragment in mutation
    assert wrapper_dry_run is False


def test_install_warns_when_apm_preview_contradicts_itself(
    memory_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = memory_root / "downstream"
    project.mkdir()

    def contradictory_preview(
        provider: str,
        command: list[str],
        cwd: Path,
        mutation: str,
        *,
        dry_run: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        assert provider == "apm"
        assert command[-1] == "--dry-run"
        assert cwd == project
        assert "preview only" in mutation
        assert dry_run is False
        return subprocess.CompletedProcess(
            command,
            0,
            "Would add github.com/example/skills\nWould install no changes\n",
            "",
        )

    monkeypatch.setattr(workshop_cli, "run_external", contradictory_preview)

    assert (
        invoke(
            "install",
            "github.com/example/skills",
            "--project",
            str(project),
        )
        == 0
    )

    captured = capsys.readouterr()
    assert "Would add github.com/example/skills" in captured.out
    assert "Preview complete" in captured.out
    assert "WARNING: APM's preview is internally inconsistent" in captured.err
    assert "Do not treat this preview as approval to apply" in captured.err


def test_doctor_json_explains_versions_and_authority_boundaries(
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    versions = {
        "apm": "APM 0.28.0",
        "gh": "gh version 2.97.0",
        "node": "v22.0.0",
    }
    monkeypatch.setattr(
        workshop_cli,
        "command_version",
        lambda command: versions.get(command[0]),
    )

    assert invoke("doctor", "--json") == 0

    report = json.loads(capsys.readouterr().out)
    assert set(report) == {
        "apm",
        "gh-skill",
        "asm",
        "vercel-skills",
        "workshop",
        "node",
    }
    assert report["apm"]["authority"] == "project state"
    assert report["gh-skill"]["authority"] == "discovery only in this workflow"
    assert report["workshop"]["authority"] == "cross-project memory only"
    assert report["asm"]["version"].endswith(workshop_cli.ASM_VERSION)
    assert report["vercel-skills"]["version"].endswith(
        workshop_cli.VERCEL_SKILLS_VERSION
    )
    assert report["node"]["version"] == "v22.0.0"


def test_apm_version_extracts_semver_before_misleading_revision_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workshop_cli,
        "command_version",
        lambda command: "Agent Package Manager (APM) CLI version 0.28.0 (ae66f92)",
    )

    assert workshop_cli.apm_version() == "0.28.0"
