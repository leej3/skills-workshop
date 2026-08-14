from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from textual.widgets import Input, SelectionList, TextArea

from scripts import import_skills


def test_scan_project_maps_known_sources_and_cluster_memberships(
    workshop: Path, make_skill, write_cluster
) -> None:
    project = workshop.parent / "project"
    skill = make_skill(project / ".agents" / "skills" / "alpha", "alpha")
    write_cluster(
        workshop,
        "research",
        [("alpha", "upstreams/example/alpha")],
    )
    (workshop / "materializations" / "project--research.lock.json").write_text(
        json.dumps(
            {
                "project": {"id": "project"},
                "skills": [
                    {
                        "name": "alpha",
                        "source": "upstreams/example/alpha",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    mappings = import_skills.scan_project(project)

    assert mappings == [
        import_skills.SkillMapping(
            name="alpha",
            project_path=skill,
            source="upstreams/example/alpha",
            clusters={"research"},
        )
    ]


def test_scan_project_rejects_duplicate_declared_names(
    workshop: Path, make_skill
) -> None:
    project = workshop.parent / "project"
    root = project / ".agents" / "skills"
    make_skill(root / "one", "same")
    make_skill(root / "two", "same")

    with pytest.raises(ValueError, match="duplicate skill name"):
        import_skills.scan_project(project)


@pytest.mark.parametrize("source", ["../outside", "/tmp/outside", "."])
def test_validate_source_rejects_paths_outside_workshop(
    workshop: Path, source: str
) -> None:
    with pytest.raises(ValueError, match="source must stay inside"):
        import_skills.validate_source(source)


def test_import_model_updates_selected_and_preserves_other_identity(
    workshop: Path, make_skill, write_cluster
) -> None:
    project_skill = make_skill(
        workshop.parent / "project" / ".agents" / "skills" / "alpha",
        "alpha",
    )
    write_cluster(workshop, "selected", [])
    write_cluster(workshop, "unselected", [("alpha", "skills/old-alpha")])
    mapping = import_skills.SkillMapping(
        name="alpha",
        project_path=project_skill,
        source="skills/alpha",
        clusters={"selected"},
    )

    copied, changed = import_skills.import_mappings([mapping])

    assert (copied, changed) == (1, 1)
    assert import_skills.digest_tree(workshop / "skills" / "alpha") == (
        import_skills.digest_tree(project_skill)
    )
    selected = import_skills.load_clusters()["selected"]
    unselected = import_skills.load_clusters()["unselected"]
    assert selected["skills"] == [{"name": "alpha", "source": "skills/alpha"}]
    assert unselected["skills"] == [{"name": "alpha", "source": "skills/old-alpha"}]


def test_import_removes_only_the_original_unselected_identity(
    workshop: Path, make_skill, write_cluster
) -> None:
    project_skill = make_skill(
        workshop.parent / "project" / ".agents" / "skills" / "alpha",
        "alpha",
    )
    write_cluster(workshop, "old", [("alpha", "skills/old-alpha")])
    write_cluster(workshop, "other", [("alpha", "skills/other-alpha")])
    mapping = import_skills.SkillMapping(
        name="alpha",
        project_path=project_skill,
        source="skills/new-alpha",
        original_source="skills/old-alpha",
    )

    _, changed = import_skills.import_mappings([mapping])

    clusters = import_skills.load_clusters()
    assert changed == 1
    assert clusters["old"]["skills"] == []
    assert clusters["other"]["skills"] == [
        {"name": "alpha", "source": "skills/other-alpha"}
    ]


def test_import_rejects_symlinks_inside_project_skill(
    workshop: Path, make_skill, write_cluster
) -> None:
    project_skill = make_skill(
        workshop.parent / "project" / ".agents" / "skills" / "alpha",
        "alpha",
    )
    secret = workshop.parent / "secret.txt"
    secret.write_text("do not import\n", encoding="utf-8")
    (project_skill / "secret.txt").symlink_to(secret)
    write_cluster(workshop, "selected", [])
    mapping = import_skills.SkillMapping(
        name="alpha",
        project_path=project_skill,
        source="skills/alpha",
        clusters={"selected"},
    )

    with pytest.raises(ValueError, match="contains symlinks"):
        import_skills.import_mappings([mapping])

    assert not (workshop / "skills" / "alpha").exists()


@pytest.mark.parametrize("second_source", ["skills/shared", "skills/shared/nested"])
def test_import_preflights_non_overlapping_workshop_sources(
    workshop: Path, make_skill, second_source: str
) -> None:
    project = workshop.parent / "project"
    alpha = make_skill(project / ".agents" / "skills" / "alpha", "alpha")
    beta = make_skill(project / ".agents" / "skills" / "beta", "beta")
    mappings = [
        import_skills.SkillMapping(alpha.name, alpha, "skills/shared"),
        import_skills.SkillMapping(beta.name, beta, second_source),
    ]

    with pytest.raises(ValueError, match="unique and non-overlapping"):
        import_skills.import_mappings(mappings, project=project)

    assert not (workshop / "skills" / "shared").exists()


def test_import_rejects_workshop_source_declared_name_mismatch(
    workshop: Path, make_skill
) -> None:
    project = workshop.parent / "project"
    beta = make_skill(project / ".agents" / "skills" / "beta", "beta")
    source = make_skill(workshop / "skills" / "shared", "alpha")
    before = source.joinpath("SKILL.md").read_bytes()
    mapping = import_skills.SkillMapping("beta", beta, "skills/shared")

    with pytest.raises(ValueError, match="declares 'alpha', expected 'beta'"):
        import_skills.import_mappings([mapping], project=project)

    assert source.joinpath("SKILL.md").read_bytes() == before


def test_import_preflights_existing_locks_before_copying(
    workshop: Path, make_skill, write_cluster
) -> None:
    project = workshop.parent / "project"
    project_skill = make_skill(
        project / ".agents" / "skills" / "alpha",
        "alpha",
    )
    cluster_path = write_cluster(workshop, "selected", [])
    before_cluster = cluster_path.read_bytes()
    (workshop / "materializations" / "project--selected.lock.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cluster": "selected",
                "project": {"id": "project", "remote": None},
                "skills": [
                    {
                        "name": "old",
                        "source": "skills/old",
                        "identity": "skills/old#old",
                        "source_sha256": "invalid",
                        "project_sha256": "invalid",
                        "status": "synced",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    mapping = import_skills.SkillMapping(
        name="alpha",
        project_path=project_skill,
        source="skills/alpha",
        clusters={"selected"},
    )

    with pytest.raises(ValueError, match="source digest"):
        import_skills.import_mappings([mapping], project=project)

    assert not (workshop / "skills" / "alpha").exists()
    assert cluster_path.read_bytes() == before_cluster


def test_import_writes_v2_workshop_coordination_lock(
    workshop: Path, make_skill, write_cluster
) -> None:
    project = workshop.parent / "project"
    project_skill = make_skill(
        project / ".agents" / "skills" / "alpha",
        "alpha",
    )
    write_cluster(workshop, "selected", [])
    mapping = import_skills.SkillMapping(
        name="alpha",
        project_path=project_skill,
        source="skills/alpha",
        clusters={"selected"},
    )

    import_skills.import_mappings([mapping], project=project)

    lock = json.loads(
        (workshop / "materializations" / "project--selected.lock.json").read_text(
            encoding="utf-8"
        )
    )
    assert lock["schema_version"] == 2
    assert lock["project"] == {"id": "project", "remote": None}
    assert lock["skills"][0]["identity"] == "skills/alpha#alpha"
    assert lock["skills"][0]["status"] == "synced"


def test_ssh_remote_project_identity_matches_workshop_convention(
    workshop: Path, tmp_path: Path
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "remote",
            "add",
            "origin",
            "ssh://git@github.com/example/research.git",
        ],
        check=True,
    )

    identity, remote = import_skills.project_identity(project)

    assert identity == "example--research"
    assert remote == "ssh://git@github.com/example/research.git"


@pytest.mark.asyncio
async def test_import_tui_mounts_with_preview_and_mapping_controls(
    workshop: Path, make_skill, write_cluster
) -> None:
    project = workshop.parent / "project"
    make_skill(
        project / ".agents" / "skills" / "alpha",
        "alpha",
        "Preview content.\n",
    )
    write_cluster(workshop, "research", [("alpha", "skills/alpha")])
    app = import_skills.ImportSkillsApp(project)

    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.pause()
        assert app.query_one("#source", Input).value == "skills/alpha"
        assert app.query_one("#cluster-list", SelectionList).selected == ["research"]
        assert "Preview content." in app.query_one("#preview", TextArea).text
