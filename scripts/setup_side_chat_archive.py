"""Install the optional Codex Desktop side-chat archive hooks on this host."""

import argparse
import json
import os
import shlex
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ("UserPromptSubmit", "Stop")


def setup(root, home, python, *, apply=False):
    """Merge our hooks only; leave trust and unrelated configuration unchanged."""
    source = root.resolve() / "scripts/archive_side_chat.py"
    if not source.is_file():
        raise ValueError(f"missing hook source: {source}")
    command = shlex.join([str(python), str(source)])
    path = home / "hooks.json"
    previous = path.read_text() if path.exists() else None
    config = json.loads(previous) if previous is not None else {}
    hooks = config.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise TypeError("hooks must be an object")
    legacy = home / "hooks/archive_side_chat.py"

    for event in EVENTS:
        groups = hooks.setdefault(event, [])
        if not isinstance(groups, list):
            raise TypeError(f"{event} must be a list")
        found = False
        for group in groups:
            for handler in group.get("hooks", []):
                try:
                    parts = shlex.split(handler.get("command", ""))
                except ValueError:
                    continue
                if (
                    handler.get("type") == "command"
                    and len(parts) == 2
                    and parts[1] in {str(source), str(legacy)}
                ):
                    if group.get("matcher"):
                        raise ValueError(
                            f"remove the unsupported {event} matcher first"
                        )
                    handler["command"] = command
                    found = True
        if not found:
            groups.append(
                {"hooks": [{"type": "command", "command": command, "timeout": 3}]}
            )

    updated = json.dumps(config, indent=2) + "\n"
    changed = previous is None or json.loads(previous) != config
    if apply and changed:
        home.mkdir(parents=True, exist_ok=True)
        if previous is not None:
            backups = home / "backups"
            backups.mkdir(mode=0o700, exist_ok=True)
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            with (backups / f"hooks-before-side-chat-{stamp}.json").open("x") as backup:
                os.fchmod(backup.fileno(), 0o600)
                backup.write(previous)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=home, delete=False
            ) as output:
                temporary = Path(output.name)
                output.write(updated)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return command, changed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    home = (
        Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        .expanduser()
        .resolve()
    )
    try:
        command, changed = setup(ROOT, home, sys.executable, apply=args.apply)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        parser.exit(1, f"Setup failed: {error}\n")
    print(
        ("Updated" if args.apply else "Would update")
        if changed
        else "Already installed",
        home / "hooks.json",
    )
    print(f"UserPromptSubmit / Stop: {command}")
    print(f"Archives: {home / 'side-chat-archive'}")
    if args.apply:
        print("Review and trust both hooks in Codex CLI /hooks on this host.")
    else:
        print("Run with --apply to install.")


if __name__ == "__main__":
    main()
