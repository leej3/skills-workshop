"""Isolated regression checks for code/data separation; no real state is read."""

import os
import subprocess
import sys

import pytest

from scripts import storage


@pytest.mark.parametrize(
    "target", ["relative", str(storage.CODE_ROOT), str(storage.CODE_ROOT / "state")]
)
def test_invalid_external_selection_fails_closed(monkeypatch, target):
    monkeypatch.setenv("SKILLS_MANAGER_STATE_HOME", target)
    with pytest.raises(ValueError):
        storage.state_home()


def test_linked_code_location_is_rejected(tmp_path, monkeypatch):
    link = tmp_path / "state"
    link.symlink_to(storage.CODE_ROOT, target_is_directory=True)
    monkeypatch.setenv("SKILLS_MANAGER_STATE_HOME", str(link))
    with pytest.raises(ValueError, match="outside the code checkout"):
        storage.state_home()


def test_existing_discovery_state_location_is_preserved(tmp_path, monkeypatch):
    monkeypatch.delenv("SKILLS_MANAGER_STATE_HOME", raising=False)
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    expected = tmp_path / "skills-manager"
    assert storage.state_home() == expected
    assert not expected.exists()


def test_discovery_state_stays_outside_code(tmp_path):
    state = tmp_path / "external-state"
    code = """
import sys
from pathlib import Path
from scripts import inventory, upstream_status
expected = Path(sys.argv[1])
assert inventory.state_home() == expected
assert upstream_status.TRUST_REGISTRY == expected / "trust.toml"
assert not expected.exists()
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(state)],
        cwd=storage.CODE_ROOT,
        env={**os.environ, "SKILLS_MANAGER_STATE_HOME": str(state)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
