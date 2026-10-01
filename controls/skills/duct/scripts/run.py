#!/usr/bin/env python3
"""Allocate a private project run directory and exec con/duct."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def git(cwd, *args):
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--project-id", default=os.environ.get("DUCT_PROJECT_ID"))
    parser.add_argument("--store", type=Path, default=os.environ.get("DUCT_STORE_ROOT"))
    parser.add_argument("--message", default="")
    parser.add_argument(
        "--capture", choices=["all", "none", "stdout", "stderr"], default="all"
    )
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("supply a command after --")
    if args.project_id and not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", args.project_id
    ):
        parser.error(
            "project ID must be 1-128 letters, digits, dots, underscores or hyphens, starting with a letter or digit"
        )

    duct = shutil.which("duct")
    if not duct:
        candidate = Path.home() / ".local/bin/duct"
        if candidate.is_file() and os.access(candidate, os.X_OK):
            duct = str(candidate)
    if not duct:
        parser.error(
            "duct unavailable; install con-duct in a project environment or with uv tool install con-duct"
        )

    cwd = Path.cwd().resolve()
    project = (
        (args.project or Path(git(cwd, "rev-parse", "--show-toplevel") or cwd))
        .expanduser()
        .resolve()
    )
    if not project.is_dir():
        parser.error("project must be an existing directory")
    try:
        cwd.relative_to(project)
    except ValueError:
        parser.error("working directory must be inside the project")
    label = re.sub(r"[^A-Za-z0-9._-]+", "-", project.name).strip(".-") or "project"
    key = (
        args.project_id
        or f"{label[:60]}-{hashlib.sha256(os.fsencode(project)).hexdigest()[:16]}"
    )
    state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state")))
    store = (args.store or state / "con-duct/projects").expanduser().resolve()
    started = datetime.now(timezone.utc)
    run = store / key / (started.strftime("%Y%m%dT%H%M%S.%fZ-") + uuid.uuid4().hex)
    # Restrict only directories created here; restore the command's original mask.
    old_mask = os.umask(0o077)
    try:
        run.mkdir(parents=True, exist_ok=False, mode=0o700)
        status = git(project, "status", "--porcelain")
        context = {
            "schema_version": 1,
            "project_id": key,
            "project_root": str(project),
            "working_directory": str(cwd),
            "started_at": started.isoformat(),
            "git_commit": git(project, "rev-parse", "HEAD"),
            "git_dirty": bool(status) if status is not None else None,
            "duct_executable": duct,
        }
        (run / "context.json").write_text(json.dumps(context, indent=2) + "\n")
    finally:
        os.umask(old_mask)
    print(f"duct run directory: {run}", file=sys.stderr, flush=True)
    # Escape literal braces because duct treats the prefix as a format string.
    prefix = str(run / "run_").replace("{", "{{").replace("}", "}}")
    os.execv(
        duct,
        [
            duct,
            "--output-prefix",
            prefix,
            "--fail-time",
            "0",
            "--capture-outputs",
            args.capture,
            "--outputs",
            "all",
            "--message",
            args.message,
            "--",
            *command,
        ],
    )


if __name__ == "__main__":
    main()
