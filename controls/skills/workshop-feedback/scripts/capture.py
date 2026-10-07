"""Bridge the portable recorder to its configured Workshop evidence collector."""

import json
import os
import subprocess
import sys
from pathlib import Path


def capture_record(args, result):
    root = os.environ.get("SKILLS_WORKSHOP_ROOT")
    if not root:
        try:
            root = json.loads(
                (Path.home() / ".config/skills-workshop/config.json").read_text()
            )["workshop_root"]
        except (OSError, ValueError, KeyError) as error:
            raise ValueError("capture requires configured workshop_root") from error
    script = Path(root).expanduser() / "scripts/memory.py"
    if not script.is_file():
        raise ValueError("configured Workshop has no memory collector")
    tree = (
        args.overlay
        if result["overlay"] or args.visibility == "private"
        else args.store
    )
    paths = list(tree.glob(f"records/*/*/{result['id']}.json"))
    if len(paths) != 1:
        raise ValueError("cannot locate recorded observation for capture")
    command = [sys.executable, str(script)]
    if args.capture_state:
        command += ["--state", str(args.capture_state)]
    command += [
        "capture-feedback",
        str(paths[0]),
        "--manifest",
        str(args.capture),
        "--store",
        args.capture_store,
        "--agent",
        "workshop-feedback",
    ]
    reason = args.capture_reason or args.sensitivity_reason
    if reason:
        command += ["--reason", reason]
    if args.capture_config:
        command += ["--config", str(args.capture_config)]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        # Do not echo subprocess diagnostics that may include source contents.
        raise ValueError(
            f"observation {result['id']} was saved; evidence capture/upload failed. "
            "Retry with the same --event-id; source data and any staged capture remain intact."
        )
    return json.loads(completed.stdout)
