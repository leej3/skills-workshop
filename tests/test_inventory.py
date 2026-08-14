from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import inventory


def test_inventory_json_and_tsv_relationship_join(
    workshop: Path, make_skill, write_cluster
) -> None:
    workshop_skill = make_skill(workshop / "skills" / "alpha", "alpha")
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
    write_cluster(workshop, "research", [("alpha", "skills/alpha")])
    (workshop / "materializations" / "example--research.lock.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "cluster": "research",
                "project": {"id": "example", "remote": None},
                "skills": [
                    {
                        "name": "alpha",
                        "source": "skills/alpha",
                        "status": "diverged",
                    }
                ],
            }
        ),
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
            "source": "workshop",
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
    assert alpha["source"] == "skills/alpha"
    assert alpha["clusters"] == "research"
    assert alpha["projects"] == "example"
    assert alpha["status"] == "diverged"
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
