from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import migrate_metadata, validate_metadata


def test_validator_rejects_destructive_lock_fields(workshop: Path, monkeypatch) -> None:
    monkeypatch.setattr(validate_metadata, "REPOSITORY", workshop)
    path = workshop / "materializations" / "project--core.lock.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "bundle": "core",
                "project": {"id": "project", "remote": None},
                "skills": [
                    {
                        "name": "../../../victim",
                        "source": "../outside",
                        "identity": "../outside#../../../victim",
                        "source_sha256": "not-a-digest",
                        "project_sha256": "not-a-digest",
                        "status": "synced",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    errors = "\n".join(validate_metadata.validate_lock(path))

    assert "invalid skill name" in errors
    assert "invalid skill source" in errors
    assert "invalid source digest" in errors


def test_v1_migration_adds_stable_identity_and_separate_baselines() -> None:
    digest = "a" * 64
    migrated, changed = migrate_metadata.migrate_lock(
        {
            "cluster": "core",
            "project": {"id": "project", "remote": None},
            "skills": [
                {
                    "name": "alpha",
                    "source": "skills/alpha",
                    "sha256": digest,
                }
            ],
        }
    )

    assert changed
    assert migrated["schema_version"] == 3
    assert migrated["bundle"] == "core"
    assert "cluster" not in migrated
    skill = migrated["skills"][0]
    assert skill["identity"] == "skills/alpha#alpha"
    assert skill["source_sha256"] == digest
    assert skill["project_sha256"] == digest
    assert skill["status"] == "synced"


@pytest.mark.parametrize("name_field", ["cluster", "bundle"])
def test_v2_migration_renames_cluster_and_advances_schema(name_field: str) -> None:
    lock = {
        "schema_version": 2,
        name_field: "research",
        "project": {"id": "project", "remote": None},
        "skills": [],
    }

    migrated, changed = migrate_metadata.migrate_lock(lock)

    assert changed
    assert migrated == {
        "schema_version": 3,
        "bundle": "research",
        "project": {"id": "project", "remote": None},
        "skills": [],
    }


def test_v3_migration_is_a_no_op() -> None:
    lock = {
        "schema_version": 3,
        "bundle": "core",
        "project": {"id": "project", "remote": None},
        "skills": [],
    }

    migrated, changed = migrate_metadata.migrate_lock(lock)

    assert migrated is lock
    assert not changed


def test_legacy_lock_rejects_conflicting_cluster_and_bundle() -> None:
    with pytest.raises(ValueError, match="conflicting bundle and cluster"):
        migrate_metadata.migrate_lock(
            {
                "schema_version": 2,
                "cluster": "old",
                "bundle": "new",
                "skills": [],
            }
        )


def test_v3_lock_rejects_legacy_cluster_field() -> None:
    with pytest.raises(ValueError, match="schema-v3 uses 'bundle', not 'cluster'"):
        migrate_metadata.migrate_lock(
            {
                "schema_version": 3,
                "cluster": "core",
                "skills": [],
            }
        )


def test_migration_rejects_unknown_schema_version() -> None:
    with pytest.raises(ValueError, match="unsupported.*schema version: 4"):
        migrate_metadata.migrate_lock(
            {
                "schema_version": 4,
                "bundle": "core",
                "skills": [],
            }
        )


def test_validator_directs_legacy_lock_to_migration(tmp_path: Path) -> None:
    path = tmp_path / "legacy.lock.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cluster": "core",
                "project": {"id": "project", "remote": None},
                "skills": [],
            }
        ),
        encoding="utf-8",
    )

    assert validate_metadata.validate_lock(path) == [
        f"{path}: schema_version 2; run migrate-metadata --apply"
    ]


def test_migrate_file_plans_then_atomically_applies_v3(tmp_path: Path) -> None:
    path = tmp_path / "legacy.lock.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cluster": "core",
                "project": {"id": "project", "remote": None},
                "skills": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    before = path.read_bytes()

    assert migrate_metadata.migrate(path, apply=False)
    assert path.read_bytes() == before
    assert migrate_metadata.migrate(path, apply=True)

    migrated = json.loads(path.read_text(encoding="utf-8"))
    assert migrated["schema_version"] == 3
    assert migrated["bundle"] == "core"
    assert "cluster" not in migrated


def test_materialization_schema_contract_is_v3_bundle() -> None:
    schema_path = (
        Path(__file__).resolve().parents[1]
        / "schemas"
        / "materialization-lock.schema.json"
    )
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"] == {"const": 3}
    assert "bundle" in schema["required"]
    assert "cluster" not in schema["properties"]


def test_manifest_validator_rejects_source_declared_name_mismatch(
    workshop: Path, make_skill, write_bundle, monkeypatch
) -> None:
    monkeypatch.setattr(validate_metadata, "REPOSITORY", workshop)
    make_skill(workshop / "skills" / "alpha", "alpha")
    manifest = write_bundle(workshop, "wrong-name", [("beta", "skills/alpha")])

    errors = "\n".join(validate_metadata.validate_manifest(manifest))

    assert "declares 'alpha', expected 'beta'" in errors


def test_manifest_validator_rejects_nested_skill_symlinks(
    workshop: Path, make_skill, write_bundle, monkeypatch
) -> None:
    monkeypatch.setattr(validate_metadata, "REPOSITORY", workshop)
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    secret = workshop.parent / "secret.txt"
    secret.write_text("do not expose\n", encoding="utf-8")
    (source / "secret.txt").symlink_to(secret)
    manifest = write_bundle(workshop, "linked", [("alpha", "skills/alpha")])

    errors = "\n".join(validate_metadata.validate_manifest(manifest))

    assert "contains symlinks" in errors


def test_trust_registry_requires_review_evidence(workshop: Path, monkeypatch) -> None:
    monkeypatch.setattr(validate_metadata, "REPOSITORY", workshop)
    path = workshop / "policy" / "trust.toml"
    path.parent.mkdir()
    path.write_text(
        """schema_version = 1
identity_format = "<source>#<name>"

[reviews."skills/alpha#alpha"]
source = "skills/alpha"
name = "alpha"
state = "reviewed"
""",
        encoding="utf-8",
    )

    errors = "\n".join(validate_metadata.validate_trust_registry(path))

    assert "needs digest, reviewer, and date" in errors
