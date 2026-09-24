"""Install the Workshop's two control skills and a bounded Codex instruction block."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- skills-workshop:start -->"
END = "<!-- skills-workshop:end -->"


def instruction_block(root: Path) -> str:
    return f"""{START}
## Skills Workshop

Workshop checkout: {root}.
Use $skills-workshop for skill discovery, selection, installation, and recall.
For a named installation, proceed with that choice after compatibility checks;
offer fresh alternatives without blocking or substituting the requested skill.
Keep working skills project-local; these two Workshop controls are user-level.
After material use, follow $workshop-feedback for one minimal local baseline
record per skill/task. Its policy owns exemptions and exceptional notes.
Routine successes require no narrative or per-record Git commit.
Batch shareable records; keep sensitive fields in the private overlay.
Review the shareable batch before publishing under user authorization.
Do not record reads, installations, the recorder itself, or bookkeeping.
Collection failures must not block the main task.
{END}"""


def setup(
    root: Path, home: Path, codex_home: Path, *, apply: bool = False
) -> list[str]:
    """Preflight destinations before writing; preserve unrelated user settings."""
    root = root.resolve()
    links = []
    actions = []
    for name in ("skills-workshop", "workshop-feedback"):
        source = root / ".agents" / "skills" / name
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"missing control skill: {source}")
        target = home / ".agents" / "skills" / name
        legacy = codex_home / "skills" / name
        if legacy.exists() or legacy.is_symlink():
            if legacy.resolve() != source:
                raise ValueError(
                    f"existing skill at {legacy}; reconcile it before setup"
                )
            if not target.exists() and not target.is_symlink():
                target = legacy
        if target.exists() or target.is_symlink():
            if not target.is_symlink() or target.resolve() != source:
                raise ValueError(
                    f"existing skill at {target}; reconcile it before setup"
                )
            actions.append(f"Already linked: {target}")
        else:
            links.append((target, source))
            actions.append(f"Link: {target} -> {source}")

    config = home / ".config" / "skills-workshop" / "config.json"
    values = json.loads(config.read_text()) if config.exists() else {}
    if not isinstance(values, dict):
        raise TypeError(f"expected a JSON object in {config}")
    configured = values.get("workshop_root")
    if configured is not None and (
        not isinstance(configured, str)
        or Path(configured).expanduser().resolve() != root
    ):
        raise ValueError(
            f"another checkout is configured in {config}; reconcile it before setup"
        )
    values["workshop_root"] = str(root)
    config_text = json.dumps(values, indent=2) + "\n"

    instructions = codex_home / "AGENTS.md"
    previous = instructions.read_text() if instructions.exists() else ""
    block = instruction_block(root)
    if START in previous or END in previous:
        if (
            previous.count(START) != 1
            or previous.count(END) != 1
            or previous.index(START) > previous.index(END)
        ):
            raise ValueError(
                f"invalid Workshop markers in {instructions}; repair them before setup"
            )
        start = previous.index(START)
        end = previous.index(END) + len(END)
        updated = previous[:start] + block + previous[end:]
    else:
        updated = previous + ("\n\n" if previous else "") + block + "\n"
    writes = [(config, config_text), (instructions, updated)]
    writes = [
        (path, content)
        for path, content in writes
        if not path.exists() or path.read_text() != content
    ]
    actions.extend(f"Update: {path}" for path, _ in writes)
    if apply:
        for target, source in links:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(source, target_is_directory=True)
        for path, content in writes:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    return actions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="install after inspecting the default preview",
    )
    args = parser.parse_args()
    try:
        actions = setup(
            ROOT,
            Path.home(),
            Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
            apply=args.apply,
        )
    except (OSError, ValueError, TypeError) as error:
        print(f"Setup failed: {error}")
        return 1
    print("Applied Codex setup:" if args.apply else "Preview (no files changed):")
    for action in actions:
        print(f"- {action}")
    print(
        "Installs discovery + feedback controls and instructions; no runtime hooks or working skills."
    )
    if not args.apply:
        print("\nManaged instruction block:\n" + instruction_block(ROOT.resolve()))
        print("Run pixi run setup-agent --apply to install.")
    else:
        print(
            "Start a new Codex task and ask: Use $skills-workshop to find a skill for my project."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
