from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from scripts import skill_status


def lock_entry(
    name: str,
    source: str,
    digest: str,
    lock_path: Path,
    bundle: str = "core",
) -> skill_status.LockEntry:
    return skill_status.LockEntry(
        name=name,
        source=source,
        identity=f"{source}#{name}",
        source_sha256=digest,
        project_sha256=digest,
        bundle=bundle,
        lock_path=lock_path,
    )


@pytest.mark.parametrize(
    ("workshop_body", "project_body", "expected"),
    [
        ("Baseline.\n", "Baseline.\n", "synced"),
        ("Workshop changed.\n", "Baseline.\n", "workshop-changed"),
        ("Baseline.\n", "Project changed.\n", "project-changed"),
        ("Workshop changed.\n", "Project changed.\n", "both-changed"),
    ],
)
def test_classifies_two_sided_changes(
    workshop: Path,
    make_skill,
    workshop_body: str,
    project_body: str,
    expected: str,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha", "Baseline.\n")
    baseline = skill_status.digest_tree(source)
    project = workshop.parent / "project"
    destination = make_skill(
        project / ".agents" / "skills" / "alpha",
        "alpha",
        "Baseline.\n",
    )
    make_skill(source, "alpha", workshop_body)
    make_skill(destination, "alpha", project_body)
    entry = lock_entry(
        "alpha",
        "skills/alpha",
        baseline,
        workshop / "materializations" / "project--core.lock.json",
    )

    result = skill_status.classify_skill([entry], project, workshop)

    assert result.state == expected
    assert result.classifications == [expected]


def test_classification_reports_missing_sides(workshop: Path, make_skill) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    baseline = skill_status.digest_tree(source)
    project = workshop.parent / "project"
    project.mkdir()
    entry = lock_entry(
        "alpha",
        "skills/alpha",
        baseline,
        workshop / "materializations" / "project--core.lock.json",
    )

    assert skill_status.classify_skill([entry], project, workshop).state == (
        "missing-project"
    )
    shutil.rmtree(source)
    make_skill(project / ".agents" / "skills" / "alpha", "alpha")
    assert skill_status.classify_skill([entry], project, workshop).state == (
        "missing-workshop"
    )


def test_diff_trees_lists_file_changes_and_text_patches(
    workshop: Path, make_skill
) -> None:
    source = make_skill(
        workshop / "skills" / "alpha",
        "alpha",
        "Workshop text.\n",
    )
    project = make_skill(
        workshop.parent / "project-skill",
        "alpha",
        "Project text.\n",
    )
    (source / "workshop-only.txt").write_text("source", encoding="utf-8")
    (project / "project-only.txt").write_text("project", encoding="utf-8")

    differences = skill_status.diff_trees(source, project, include_patches=True)
    by_path = {difference.path: difference for difference in differences}

    assert by_path["SKILL.md"].status == "modified"
    assert "-Workshop text." in by_path["SKILL.md"].patch
    assert "+Project text." in by_path["SKILL.md"].patch
    assert by_path["workshop-only.txt"].status == "only-in-workshop"
    assert by_path["project-only.txt"].status == "only-in-project"


def test_diff_trees_reports_symlink_target_without_reading_it(
    workshop: Path, make_skill
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    project = make_skill(workshop.parent / "project-skill", "alpha")
    (source / "data.txt").write_text("public\n", encoding="utf-8")
    secret = workshop.parent / "secret.txt"
    secret.write_text("private payload\n", encoding="utf-8")
    (project / "data.txt").symlink_to(secret)

    differences = skill_status.diff_trees(source, project, include_patches=True)
    difference = next(item for item in differences if item.path == "data.txt")

    assert difference.status == "symlink-modified"
    assert "private payload" not in (difference.detail or "")


def test_v1_lock_without_explicit_schema_uses_legacy_digest(
    workshop: Path, make_skill
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    digest = skill_status.digest_tree(source)
    lock_path = workshop / "materializations" / "project--core.lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "bundle": "core",
                "project": {"id": "project", "remote": None},
                "skills": [
                    {
                        "name": "alpha",
                        "source": "skills/alpha",
                        "sha256": digest,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    _, entries = skill_status.load_lock(lock_path)

    assert entries[0].source_sha256 == digest
    assert entries[0].project_sha256 == digest


def test_inspection_builds_read_only_reconciliation_and_prune_plan(
    workshop: Path, make_skill, write_bundle
) -> None:
    project = workshop.parent / "project"
    alpha_source = make_skill(
        workshop / "skills" / "alpha",
        "alpha",
        "Baseline.\n",
    )
    old_source = make_skill(
        workshop / "skills" / "old",
        "old",
        "Old baseline.\n",
    )
    alpha_project = make_skill(
        project / ".agents" / "skills" / "alpha",
        "alpha",
        "Project changed.\n",
    )
    old_project = make_skill(
        project / ".agents" / "skills" / "old",
        "old",
        "Old baseline.\n",
    )
    alpha_baseline_copy = workshop.parent / "alpha-baseline"
    make_skill(alpha_baseline_copy, "alpha", "Baseline.\n")
    alpha_baseline = skill_status.digest_tree(alpha_baseline_copy)
    old_baseline = skill_status.digest_tree(old_source)
    write_bundle(workshop, "core", [("alpha", "skills/alpha")])
    lock_path = workshop / "materializations" / "project--core.lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "bundle": "core",
                "project": {"id": "project", "remote": None},
                "skills": [
                    {
                        "name": "alpha",
                        "source": "skills/alpha",
                        "identity": "skills/alpha#alpha",
                        "source_sha256": alpha_baseline,
                        "project_sha256": alpha_baseline,
                    },
                    {
                        "name": "old",
                        "source": "skills/old",
                        "identity": "skills/old#old",
                        "source_sha256": old_baseline,
                        "project_sha256": old_baseline,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    before = {
        "alpha_source": skill_status.digest_tree(alpha_source),
        "alpha_project": skill_status.digest_tree(alpha_project),
        "old_source": skill_status.digest_tree(old_source),
        "old_project": skill_status.digest_tree(old_project),
        "lock": lock_path.read_bytes(),
    }

    report = skill_status.inspect_project(
        project,
        repository=workshop,
        materializations=workshop / "materializations",
        plan_policy="overwrite",
        prune=True,
    )

    states = {status.name: status for status in report.skills}
    assert states["alpha"].state == "project-changed"
    assert not states["alpha"].obsolete
    assert states["old"].state == "synced"
    assert states["old"].obsolete
    assert report.plan is not None
    assert report.plan.dry_run
    assert not report.plan.halted
    assert {(action.skill, action.action) for action in report.plan.actions} == {
        ("alpha", "replace-project-skill"),
        ("old", "remove-project-skill"),
    }
    assert skill_status.digest_tree(alpha_source) == before["alpha_source"]
    assert skill_status.digest_tree(alpha_project) == before["alpha_project"]
    assert skill_status.digest_tree(old_source) == before["old_source"]
    assert skill_status.digest_tree(old_project) == before["old_project"]
    assert lock_path.read_bytes() == before["lock"]


def test_prune_plan_blocks_locally_changed_obsolete_skill(
    workshop: Path, make_skill
) -> None:
    source = make_skill(workshop / "skills" / "old", "old", "Baseline.\n")
    baseline = skill_status.digest_tree(source)
    project = workshop.parent / "project"
    make_skill(
        project / ".agents" / "skills" / "old",
        "old",
        "Locally changed.\n",
    )
    status = skill_status.classify_skill(
        [
            lock_entry(
                "old",
                "skills/old",
                baseline,
                workshop / "materializations" / "project--core.lock.json",
            )
        ],
        project,
        workshop,
    )
    status.obsolete = True

    plan = skill_status.build_plan([status], prune=True)

    assert plan.halted
    assert [(action.action, action.blocked) for action in plan.actions] == [
        ("blocked-prune", True)
    ]
