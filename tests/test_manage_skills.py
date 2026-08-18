from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts import manage_skills


def skill_text(path: Path) -> str:
    return (path / "SKILL.md").read_text(encoding="utf-8")


def test_manifest_rejects_duplicate_skill_names(
    workshop: Path, make_skill, write_bundle
) -> None:
    make_skill(workshop / "skills" / "one", "one")
    make_skill(workshop / "skills" / "two", "two")
    manifest = write_bundle(
        workshop,
        "duplicates",
        [("same", "skills/one"), ("same", "skills/two")],
    )

    with pytest.raises(ValueError, match="duplicate skill"):
        manage_skills.load_manifest(manifest)


@pytest.mark.parametrize("name", ["../escape", "nested/name", "/absolute"])
def test_manifest_rejects_unsafe_destination_names(
    workshop: Path, make_skill, write_bundle, name: str
) -> None:
    make_skill(workshop / "skills" / "safe", "safe")
    manifest = write_bundle(workshop, "unsafe", [(name, "skills/safe")])

    with pytest.raises(ValueError, match="skill name"):
        manage_skills.load_manifest(manifest)


def test_manifest_rejects_source_path_traversal(
    workshop: Path, make_skill, write_bundle
) -> None:
    make_skill(workshop.parent / "outside", "outside")
    manifest = write_bundle(
        workshop,
        "traversal",
        [("outside", "../outside")],
    )

    with pytest.raises(ValueError, match="invalid skill source"):
        manage_skills.load_manifest(manifest)


def test_manifest_rejects_symlinks_inside_skill(
    workshop: Path, make_skill, write_bundle
) -> None:
    source = make_skill(workshop / "skills" / "linked", "linked")
    secret = workshop.parent / "secret.txt"
    secret.write_text("do not import\n", encoding="utf-8")
    (source / "secret.txt").symlink_to(secret)
    manifest = write_bundle(workshop, "linked", [("linked", "skills/linked")])

    with pytest.raises(ValueError, match="contains symlinks"):
        manage_skills.load_manifest(manifest)


def test_manifest_rejects_source_declared_name_mismatch(
    workshop: Path, make_skill, write_bundle
) -> None:
    make_skill(workshop / "skills" / "alpha", "alpha")
    manifest = write_bundle(workshop, "wrong-name", [("beta", "skills/alpha")])

    with pytest.raises(ValueError, match="declares 'alpha', expected 'beta'"):
        manage_skills.load_manifest(manifest)


def test_bundle_name_cannot_escape_manifest_directory(workshop: Path) -> None:
    project = workshop.parent / "project"
    project.mkdir()

    with pytest.raises(ValueError, match="bundle name"):
        manage_skills.apply_bundle("../outside", project, None, None)


def test_apply_bundle_copies_skills_and_writes_workshop_lock(
    workshop: Path, make_skill, write_bundle
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    write_bundle(workshop, "core", [("alpha", "skills/alpha")])
    project = workshop.parent / "project"
    project.mkdir()

    manage_skills.apply_bundle("core", project, None, None)

    destination = project / ".agents" / "skills" / "alpha"
    assert skill_text(destination) == skill_text(source)
    lock_path = workshop / "materializations" / "project--core.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    assert lock["bundle"] == "core"
    assert lock["project"] == {"id": "project", "remote": None}
    assert lock["skills"][0]["status"] == "synced"
    assert lock["skills"][0]["source_sha256"] == lock["skills"][0]["project_sha256"]


def test_abort_preflight_is_atomic(workshop: Path, make_skill, write_bundle) -> None:
    make_skill(workshop / "skills" / "new", "new")
    source = make_skill(workshop / "skills" / "changed", "changed", "Workshop.\n")
    write_bundle(
        workshop,
        "core",
        [("new", "skills/new"), ("changed", "skills/changed")],
    )
    project = workshop.parent / "project"
    skills_root = project / ".agents" / "skills"
    skills_root.mkdir(parents=True)
    destination = make_skill(skills_root / "changed", "changed", "Project.\n")
    before_source = skill_text(source)
    before_project = skill_text(destination)

    with pytest.raises(SystemExit, match="No changes made"):
        manage_skills.apply_bundle("core", project, "abort", None)

    assert not (skills_root / "new").exists()
    assert skill_text(source) == before_source
    assert skill_text(destination) == before_project
    assert not list((workshop / "materializations").glob("*.lock.json"))


def test_apply_bundle_dry_run_changes_no_project_or_lock(
    workshop: Path, make_skill, write_bundle, capsys: pytest.CaptureFixture[str]
) -> None:
    make_skill(workshop / "skills" / "alpha", "alpha")
    write_bundle(workshop, "core", [("alpha", "skills/alpha")])
    project = workshop.parent / "project"
    project.mkdir()

    manage_skills.apply_bundle("core", project, None, None, dry_run=True)

    assert not (project / ".agents").exists()
    assert not list((workshop / "materializations").glob("*.lock.json"))
    assert "Dry run: no files or locks changed." in capsys.readouterr().out


def test_prune_removes_only_previously_managed_unchanged_skill(
    workshop: Path, make_skill, write_bundle
) -> None:
    make_skill(workshop / "skills" / "alpha", "alpha")
    make_skill(workshop / "skills" / "old", "old")
    write_bundle(
        workshop,
        "core",
        [("alpha", "skills/alpha"), ("old", "skills/old")],
    )
    project = workshop.parent / "project"
    project.mkdir()
    manage_skills.apply_bundle("core", project, None, None)
    old_project = project / ".agents" / "skills" / "old"
    old_digest = manage_skills.digest_tree(old_project)
    write_bundle(workshop, "core", [("alpha", "skills/alpha")])

    manage_skills.apply_bundle("core", project, None, None, prune=True)

    assert not old_project.exists()
    backup = (
        workshop / ".backups" / "project--core" / "project-pruned" / "old" / old_digest
    )
    assert (backup / "SKILL.md").is_file()
    lock = json.loads(
        (workshop / "materializations" / "project--core.lock.json").read_text(
            encoding="utf-8"
        )
    )
    assert [item["name"] for item in lock["skills"]] == ["alpha"]


def test_prune_refuses_changed_skill_before_copying_additions(
    workshop: Path, make_skill, write_bundle
) -> None:
    make_skill(workshop / "skills" / "old", "old", "Baseline.\n")
    write_bundle(workshop, "core", [("old", "skills/old")])
    project = workshop.parent / "project"
    project.mkdir()
    manage_skills.apply_bundle("core", project, None, None)
    old_project = project / ".agents" / "skills" / "old"
    make_skill(old_project, "old", "Locally changed.\n")
    make_skill(workshop / "skills" / "new", "new")
    write_bundle(workshop, "core", [("new", "skills/new")])

    with pytest.raises(SystemExit, match="refusing to prune locally changed"):
        manage_skills.apply_bundle("core", project, None, None, prune=True)

    assert skill_text(old_project).endswith("Locally changed.\n")
    assert not (project / ".agents" / "skills" / "new").exists()


def test_prune_rejects_traversal_from_tampered_lock(
    workshop: Path, make_skill, write_bundle
) -> None:
    make_skill(workshop / "skills" / "alpha", "alpha")
    write_bundle(workshop, "core", [("alpha", "skills/alpha")])
    project = workshop.parent / "project"
    project.mkdir()
    victim = make_skill(project / "victim", "victim")
    lock_path = workshop / "materializations" / "project--core.lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "bundle": "core",
                "project": {"id": "project", "remote": None},
                "skills": [
                    {
                        "name": "../../../victim",
                        "source": "skills/old",
                        "identity": "skills/old#../../../victim",
                        "source_sha256": "a" * 64,
                        "project_sha256": "a" * 64,
                        "status": "synced",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="locked skill name"):
        manage_skills.apply_bundle("core", project, "overwrite", None, prune=True)

    assert (victim / "SKILL.md").is_file()


@pytest.mark.parametrize("replacement", ["file", "symlink"])
def test_prune_refuses_non_directory_managed_path(
    workshop: Path, make_skill, write_bundle, replacement: str
) -> None:
    make_skill(workshop / "skills" / "old", "old")
    manifest = write_bundle(workshop, "core", [("old", "skills/old")])
    project = workshop.parent / "project"
    project.mkdir()
    manage_skills.apply_bundle("core", project, None, None)
    managed = project / ".agents" / "skills" / "old"
    shutil.rmtree(managed)
    if replacement == "file":
        managed.write_text("local data\n", encoding="utf-8")
    else:
        target = project / "local-target"
        target.write_text("local data\n", encoding="utf-8")
        managed.symlink_to(target)
    manifest.write_text(
        'schema_version = 1\nname = "core"\ndescription = "Test bundle"\nskills = []\n',
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="refusing to prune locally changed skills"):
        manage_skills.apply_bundle("core", project, None, None, prune=True)

    assert managed.exists() or managed.is_symlink()


@pytest.mark.parametrize(
    ("policy", "expected_source", "expected_project", "status"),
    [
        ("record", "Workshop.\n", "Project.\n", "diverged"),
        ("back-propagate", "Project.\n", "Project.\n", "synced"),
        ("overwrite", "Workshop.\n", "Workshop.\n", "synced"),
    ],
)
def test_explicit_conflict_policies(
    workshop: Path,
    make_skill,
    write_bundle,
    policy: str,
    expected_source: str,
    expected_project: str,
    status: str,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha", "Workshop.\n")
    write_bundle(workshop, "core", [("alpha", "skills/alpha")])
    project = workshop.parent / "project"
    destination = make_skill(
        project / ".agents" / "skills" / "alpha",
        "alpha",
        "Project.\n",
    )

    manage_skills.apply_bundle("core", project, policy, None)

    assert skill_text(source).endswith(expected_source)
    assert skill_text(destination).endswith(expected_project)
    lock = json.loads(
        (workshop / "materializations" / "project--core.lock.json").read_text(
            encoding="utf-8"
        )
    )
    assert lock["skills"][0]["status"] == status
    if status == "synced":
        assert lock["skills"][0]["source_sha256"] == lock["skills"][0]["project_sha256"]
    else:
        assert lock["skills"][0]["source_sha256"] != lock["skills"][0]["project_sha256"]
