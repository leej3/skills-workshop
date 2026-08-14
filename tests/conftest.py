from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import_skills = importlib.import_module("scripts.import_skills")
inventory = importlib.import_module("scripts.inventory")
manage_skills = importlib.import_module("scripts.manage_skills")
skill_status = importlib.import_module("scripts.skill_status")
upstream_status = importlib.import_module("scripts.upstream_status")


@pytest.fixture
def workshop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workshop"
    for directory in (
        "clusters",
        "materializations",
        "profiles",
        "skills",
        "upstreams",
    ):
        (root / directory).mkdir(parents=True)

    monkeypatch.setattr(manage_skills, "REPOSITORY", root)
    monkeypatch.setattr(manage_skills, "MATERIALIZATIONS", root / "materializations")
    monkeypatch.setattr(manage_skills, "BACKUPS", root / ".backups")
    monkeypatch.setattr(import_skills, "REPOSITORY", root)
    monkeypatch.setattr(import_skills, "MATERIALIZATIONS", root / "materializations")
    monkeypatch.setattr(import_skills, "BACKUPS", root / ".backups")
    monkeypatch.setattr(inventory, "REPOSITORY", root)
    monkeypatch.setattr(skill_status, "REPOSITORY", root)
    monkeypatch.setattr(skill_status, "MATERIALIZATIONS", root / "materializations")
    monkeypatch.setattr(upstream_status, "REPOSITORY", root)
    monkeypatch.setattr(upstream_status, "REGISTRY", root / "registry.toml")
    monkeypatch.setattr(
        upstream_status,
        "TRUST_REGISTRY",
        root / "policy" / "trust.toml",
    )
    skill_status._local_upstream_candidate.cache_clear()
    skill_status._remote_head.cache_clear()
    return root


@pytest.fixture
def make_skill():
    def make(
        path: Path,
        name: str,
        body: str = "Initial guidance.\n",
    ) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        (path / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: Test skill\n---\n\n{body}",
            encoding="utf-8",
        )
        return path

    return make


@pytest.fixture
def write_cluster():
    def write(
        root: Path,
        name: str,
        skills: list[tuple[str, str]],
        description: str = "Test cluster",
    ) -> Path:
        lines = [
            "schema_version = 1",
            f"name = {json.dumps(name)}",
            f"description = {json.dumps(description)}",
        ]
        if not skills:
            lines.append("skills = []")
        for skill_name, source in skills:
            lines.extend(
                [
                    "",
                    "[[skills]]",
                    f"name = {json.dumps(skill_name)}",
                    f"source = {json.dumps(source)}",
                ]
            )
        path = root / "clusters" / f"{name}.toml"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return write
