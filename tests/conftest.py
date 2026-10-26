from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
inventory = importlib.import_module("scripts.inventory")
upstream_status = importlib.import_module("scripts.upstream_status")


@pytest.fixture
def workshop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "workshop"
    (root / "upstreams").mkdir(parents=True)
    monkeypatch.setattr(inventory, "REPOSITORY", root)
    monkeypatch.setattr(upstream_status, "REPOSITORY", root)
    monkeypatch.setattr(upstream_status, "REGISTRY", root / "registry.toml")
    monkeypatch.setattr(
        upstream_status,
        "TRUST_REGISTRY",
        tmp_path / "state" / "trust.toml",
    )
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
