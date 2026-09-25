"""Manage user-level Workshop activation independently of tooling and memory."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START = "<!-- skills-workshop:start -->"
END = "<!-- skills-workshop:end -->"
NAMES = ("skills-workshop", "workshop-feedback")
MODES = ("on", "manual", "off")


def store_path(home: Path) -> Path:
    # Deliberately separate from APM's shared global install and from memory.
    return home / ".local/share/skills-workshop/control-install"


def command(root: Path, action: str) -> str:
    return f"pixi run --manifest-path {shlex.quote(str(root / 'pixi.toml'))} workshop {action}"


def instruction_block(root: Path, mode: str = "on") -> str:
    policy = {
        "on": "Use $skills-workshop for skill discovery, selection, installation, and recall.\nAfter material skill use, follow $workshop-feedback for one minimal baseline record.\nSkip reads, installations, recorder use, and bookkeeping; collection failures must not block work.\nBefore completing each task, inspect, validate, and commit its shareable records in the Workshop checkout, even for work in other projects. Batch within the task, never defer commits to a later task; report Git blockers.\nPush under user publication authorization; keep sensitive details in the private overlay.",
        "manual": "Use Workshop discovery and feedback only when the user explicitly requests them.\nDo not invoke either control automatically, including routine feedback collection.\nSkill availability alone is not a request to invoke it.",
        "off": "Do not invoke Workshop discovery or feedback. Its control entrypoints are hidden.\nTooling, memory, and project-installed skills remain available and unchanged.",
    }[mode]
    return f"""{START}
## Skills Workshop

Workshop mode: {mode}. This mode governs Workshop lifecycle guidance elsewhere in user instructions.
Workshop checkout: {root}.
{policy}
These controls are user-level; do not install them into projects automatically.
If the user requests a mode change, use the corresponding command:
- On: `{command(root, "enable")}`
- Manual: `{command(root, "manual")}`
- Off: `{command(root, "disable")}`
- Status: `{command(root, "status")}`
If controls need restoration, run `pixi run --manifest-path {shlex.quote(str(root / "pixi.toml"))} setup-agent --apply`.
Mode changes require a new agent task or client reload; already loaded instructions cannot be unloaded.
{END}"""


def read_config(home: Path) -> dict:
    path = home / ".config/skills-workshop/config.json"
    values = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(values, dict):
        raise TypeError(f"expected a JSON object in {path}")
    return values


def restore_controls(root: Path, home: Path, source: str | None = None) -> None:
    store = store_path(home)
    manifest = store / "apm.yml"
    if source is None and not manifest.exists():
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
        source = f"leej3/skills-workshop/controls#{revision}"
    if source and not re.fullmatch(r"[^\s#]+#[0-9a-f]{40}", source):
        raise ValueError("control source must be an APM package#full-commit-SHA")
    store.mkdir(parents=True, exist_ok=True)
    if not manifest.exists():
        manifest.write_text(
            "name: workshop-user\nversion: 0.1.0\ntargets:\n  - agent-skills\n"
        )
    cmd = ["apm", "install"]
    if source:
        cmd += [
            source,
            "--skill",
            NAMES[0],
            "--skill",
            NAMES[1],
            "--target",
            "agent-skills",
        ]
    else:
        cmd += ["--frozen"]
    subprocess.run(cmd, cwd=store, check=True)
    subprocess.run(["apm", "audit", "--ci"], cwd=store, check=True)


def setup(
    root: Path,
    home: Path,
    codex_home: Path,
    *,
    apply: bool = False,
    mode: str | None = None,
    restore: bool = False,
    source: str | None = None,
) -> list[str]:
    """Preflight all managed surfaces; never unlink foreign files or symlinks."""
    root = root.resolve()
    values = read_config(home)
    configured = values.get("workshop_root")
    if configured is not None and (
        not isinstance(configured, str)
        or Path(configured).expanduser().resolve() != root
    ):
        raise ValueError("another checkout is configured; reconcile it before setup")
    mode = mode or values.get("mode", "on")
    if mode not in MODES:
        raise ValueError(f"invalid Workshop mode: {mode}")
    links, removals, actions = [], [], []
    for name in NAMES:
        deployed = store_path(home) / ".agents/skills" / name
        owned = {
            deployed,
            root / ".agents/skills" / name,
            root / "controls/skills" / name,
        }
        destinations = (home / ".agents/skills" / name, codex_home / "skills" / name)
        existing = []
        for target in dict.fromkeys(destinations):
            if not (target.exists() or target.is_symlink()):
                continue
            if not target.is_symlink() or target.resolve() not in owned:
                raise ValueError(
                    f"existing skill at {target}; reconcile it before setup"
                )
            existing.append(target)
        if mode == "off":
            removals.extend(existing)
        else:
            if not restore and not (deployed / "SKILL.md").is_file():
                raise ValueError(
                    "missing installed controls; run setup-agent --apply first"
                )
            target = existing[0] if existing else destinations[0]
            removals.extend(
                p for p in existing if p != target or p.resolve() != deployed
            )
            if not target.is_symlink() or target.resolve() != deployed:
                links.append((target, deployed))
    instructions = codex_home / "AGENTS.md"
    previous = instructions.read_text() if instructions.exists() else ""
    block = instruction_block(root, mode)
    if START in previous or END in previous:
        if (
            previous.count(START) != 1
            or previous.count(END) != 1
            or previous.index(START) > previous.index(END)
        ):
            raise ValueError(
                f"invalid Workshop markers in {instructions}; repair them before setup"
            )
        updated = (
            previous[: previous.index(START)]
            + block
            + previous[previous.index(END) + len(END) :]
        )
    else:
        updated = previous + ("\n\n" if previous else "") + block + "\n"
    values.update(workshop_root=str(root), mode=mode)
    config = home / ".config/skills-workshop/config.json"
    writes = [(config, json.dumps(values, indent=2) + "\n"), (instructions, updated)]
    writes = [(p, s) for p, s in writes if not p.exists() or p.read_text() != s]
    if restore:
        actions.append("Restore and audit controls in " + str(store_path(home)))
    actions += [f"Unlink: {p}" for p in removals]
    actions += [f"Link: {p} -> {s}" for p, s in links]
    actions += [f"Update: {p}" for p, _ in writes]
    if apply:
        if restore:
            restore_controls(root, home, source)
        if mode != "off":
            for name in NAMES:
                if not (
                    store_path(home) / ".agents/skills" / name / "SKILL.md"
                ).is_file():
                    raise ValueError(f"restoration did not provide {name}")
        for p in removals:
            p.unlink()
        for p, s in links:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.symlink_to(s, target_is_directory=True)
        for p, s in writes:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(s)
    return actions


def status(root: Path, home: Path, codex_home: Path) -> dict:
    values = read_config(home)
    links = {}
    for name in NAMES:
        for base in (home / ".agents/skills", codex_home / "skills"):
            p = base / name
            if p.exists() or p.is_symlink():
                links[str(p)] = (
                    str(p.resolve()) if p.is_symlink() else "unmanaged directory"
                )
    return {
        "mode": values.get("mode", "on" if links else "off"),
        "workshop_root": values.get("workshop_root", str(root)),
        "apm_directory": str(store_path(home)),
        "entrypoints": links,
        "reload_required_after_changes": True,
    }


def mode_command(action: str, root: Path = ROOT) -> int:
    home = Path.home()
    codex_home = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    try:
        if action == "status":
            print(json.dumps(status(root, home, codex_home), indent=2))
        else:
            mode = {"enable": "on", "manual": "manual", "disable": "off"}[action]
            for item in setup(root, home, codex_home, apply=True, mode=mode):
                print(item)
            print(f"Workshop mode: {mode}. Start a new task or reload your client.")
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Workshop activation failed: {error}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument(
        "--source", help="APM control package#full-SHA; omit to restore existing lock"
    )
    args = parser.parse_args()
    try:
        actions = setup(
            ROOT,
            Path.home(),
            Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")),
            apply=args.apply,
            mode=args.mode,
            restore=True,
            source=args.source,
        )
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Setup failed: {error}")
        return 1
    print("Applied user setup:" if args.apply else "Preview (no files changed):")
    for action in actions:
        print(f"- {action}")
    print(
        "Tooling and memory stay installed in every mode. Start a new task after activation changes."
    )
    if not args.apply:
        print("Run pixi run setup-agent --apply to install.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
