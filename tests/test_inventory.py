from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

from scripts import inventory


def test_inventory_cli_preserves_external_output_and_optional_view(
    workshop: Path, monkeypatch
) -> None:
    (workshop / "registry.toml").write_text("schema_version = 1\n")
    state = workshop.parent / "state"
    monkeypatch.setenv("SKILLS_MANAGER_STATE_HOME", str(state))
    monkeypatch.setattr(sys, "argv", ["inventory", "--format", "tsv", "--view"])
    viewed = []
    monkeypatch.setattr(
        inventory.subprocess,
        "run",
        lambda command, **kwargs: viewed.append(command),
    )

    inventory.main()

    output = state / "inventory" / "skills.tsv"
    assert output.is_file()
    assert viewed == [["vd", str(output)]]
    assert not (workshop / "inventory").exists()


def test_canonical_collections_follow_manifests_and_exclude_deployments(
    workshop: Path, make_skill
) -> None:
    make_skill(workshop / ".apm/skills/published", "published")
    make_skill(workshop / ".apm/skills/old-source", "old-source")
    make_skill(workshop / ".agents/skills/native", "native")
    for name in ("published", "external", "old-format"):
        make_skill(workshop / ".agents/skills" / name, name)
    (workshop / "apm.yml").write_text("includes:\n  - .apm/skills/published\n")
    (workshop / "apm.lock.yaml").write_text(
        "local_deployed_files:\n  - .agents/skills/published/SKILL.md\n"
        "deployments:\n  - kind: project-relative\n"
        "    value: .agents/skills/external\n"
        "dependencies:\n  - deployed_files:\n"
        "      - .agents/skills/old-format/SKILL.md\n"
    )

    collections = inventory.canonical_skill_collections(workshop)

    assert {
        item["name"]: [path.name for path in item["skills"]] for item in collections
    } == {"reusable": ["published"], "native": ["native"]}


def test_inventory_json_and_tsv_sources(workshop: Path, make_skill) -> None:
    workshop_skill = make_skill(workshop / ".agents/skills" / "alpha", "alpha")
    upstream_skill = make_skill(
        workshop / "upstreams" / "collection" / "beta",
        "beta",
    )
    installed_root = workshop.parent / "installed"
    make_skill(installed_root / "gamma", "gamma")
    config = workshop / "registry.toml"
    config.write_text(
        "\n".join(
            [
                "schema_version = 1",
                "",
                "[[skill_roots]]",
                'name = "personal"',
                f"path = {json.dumps(str(installed_root))}",
                "",
                "[[upstreams]]",
                'name = "collection"',
                'url = "https://example.test/collection.git"',
                'fork_url = "https://example.test/fork.git"',
                'path = "upstreams/collection"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    data = inventory.build_inventory(config)

    assert data["installed"] == [
        {
            "name": "gamma",
            "path": str((installed_root / "gamma").resolve()),
            "source": "personal",
        }
    ]
    assert data["workshop"] == [
        {
            "name": "alpha",
            "path": str(workshop_skill.resolve()),
            "source": "native",
        }
    ]
    assert data["upstreams"][0]["skills"] == [
        {
            "name": "beta",
            "path": str(upstream_skill.resolve()),
            "source": "collection",
        }
    ]
    json.dumps(data)

    output = workshop / "inventory" / "skills.tsv"
    output.parent.mkdir()
    inventory.write_tsv(data, output)
    with output.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream, delimiter="\t"))

    alpha = next(row for row in rows if row["skill"] == "alpha")
    assert alpha["scope"] == "workshop"
    assert alpha["source"] == ".agents/skills/alpha"
    assert alpha["collection"] == "native"
    beta = next(row for row in rows if row["skill"] == "beta")
    assert beta["scope"] == "upstream"
    assert beta["upstream"] == "https://example.test/collection.git"
    gamma = next(row for row in rows if row["skill"] == "gamma")
    assert gamma["scope"] == "installed"
    assert gamma["collection"] == "personal"


def test_inventory_reports_duplicate_installed_names(
    workshop: Path, make_skill
) -> None:
    first = workshop.parent / "first"
    second = workshop.parent / "second"
    make_skill(first / "same", "same")
    make_skill(second / "different-directory", "same")
    config = workshop / "registry.toml"
    config.write_text(
        "\n".join(
            [
                "[[skill_roots]]",
                'name = "first"',
                f"path = {json.dumps(str(first))}",
                "",
                "[[skill_roots]]",
                'name = "second"',
                f"path = {json.dumps(str(second))}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    data = inventory.build_inventory(config)

    assert data["duplicate_installations"] == {
        "same": [
            str((first / "same").resolve()),
            str((second / "different-directory").resolve()),
        ]
    }
