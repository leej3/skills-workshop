from __future__ import annotations

import json
from pathlib import Path

from scripts import migrate_metadata, validate_metadata


def test_validator_rejects_destructive_lock_fields(workshop: Path, monkeypatch) -> None:
    monkeypatch.setattr(validate_metadata, "REPOSITORY", workshop)
    path = workshop / "materializations" / "project--core.lock.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cluster": "core",
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
    assert migrated["schema_version"] == 2
    skill = migrated["skills"][0]
    assert skill["identity"] == "skills/alpha#alpha"
    assert skill["source_sha256"] == digest
    assert skill["project_sha256"] == digest
    assert skill["status"] == "synced"


def test_manifest_validator_rejects_source_declared_name_mismatch(
    workshop: Path, make_skill, write_cluster, monkeypatch
) -> None:
    monkeypatch.setattr(validate_metadata, "REPOSITORY", workshop)
    make_skill(workshop / "skills" / "alpha", "alpha")
    manifest = write_cluster(workshop, "wrong-name", [("beta", "skills/alpha")])

    errors = "\n".join(validate_metadata.validate_manifest(manifest))

    assert "declares 'alpha', expected 'beta'" in errors


def test_manifest_validator_rejects_nested_skill_symlinks(
    workshop: Path, make_skill, write_cluster, monkeypatch
) -> None:
    monkeypatch.setattr(validate_metadata, "REPOSITORY", workshop)
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    secret = workshop.parent / "secret.txt"
    secret.write_text("do not expose\n", encoding="utf-8")
    (source / "secret.txt").symlink_to(secret)
    manifest = write_cluster(workshop, "linked", [("alpha", "skills/alpha")])

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
