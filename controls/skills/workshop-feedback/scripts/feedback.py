#!/usr/bin/env python3
"""Run Workshop feedback from any project without guessing a checkout path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    configured = os.environ.get("SKILLS_WORKSHOP_ROOT")
    if not configured:
        config = Path.home() / ".config" / "skills-workshop" / "config.json"
        try:
            configured = json.loads(config.read_text())["workshop_root"]
        except (OSError, ValueError, KeyError, TypeError):
            print(
                "Configure SKILLS_WORKSHOP_ROOT or ~/.config/skills-workshop/config.json before recording feedback.",
                file=sys.stderr,
            )
            return 1
    if not isinstance(configured, str):
        print("workshop_root must be an absolute directory path", file=sys.stderr)
        return 1
    root = Path(configured).expanduser()
    if (
        not root.is_absolute()
        or not (root / "scripts" / "workshop.py").is_file()
        or not (root / "pixi.toml").is_file()
    ):
        print("Configured Skills Workshop checkout is unavailable.", file=sys.stderr)
        return 1
    arguments = sys.argv[1:]
    try:
        return subprocess.run(
            [
                "pixi",
                "run",
                "--manifest-path",
                str(root / "pixi.toml"),
                "workshop",
                "feedback",
                *arguments,
            ],
            cwd=root,
            check=False,
        ).returncode
    except FileNotFoundError:
        print("Pixi is unavailable; feedback was not recorded.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
