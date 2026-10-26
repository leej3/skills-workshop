"""Separate code resources from explicitly selected external state."""

import os
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]


def external_path(value):
    if not isinstance(value, str) or not Path(value).expanduser().is_absolute():
        raise ValueError("external storage requires an absolute path")
    path = Path(value).expanduser().resolve()
    if path == CODE_ROOT or CODE_ROOT in path.parents:
        raise ValueError("state must be outside the code checkout")
    return path


def state_home():
    return external_path(
        os.environ.get(
            "SKILLS_MANAGER_STATE_HOME",
            str(
                Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
                / "skills-manager"
            ),
        )
    )
