#!/usr/bin/env bash
# Run inside a disposable, freshly cloned checkout with Pixi on PATH.
set -euo pipefail
cd "$(dirname "$0")/.."

pixi install --locked
pixi run configure-upstreams
pixi run setup-agent
# This check deliberately requires an empty user configuration.
test ! -e "$HOME/.agents"
test ! -e "$HOME/.codex"
test ! -e "$HOME/.config/skills-workshop"
pixi run setup-agent --apply
pixi run python - <<'PY'
import hashlib
import json
import subprocess
from pathlib import Path

root = Path.cwd()
home = Path.home()
for name in ("skills-workshop", "workshop-feedback"):
    link = home / ".agents/skills" / name
    assert link.is_symlink()
    assert link.resolve() == root / ".agents/skills" / name
config = home / ".config/skills-workshop/config.json"
assert json.loads(config.read_text())["workshop_root"] == str(root)
instructions = home / ".codex/AGENTS.md"
assert instructions.read_text().count("<!-- skills-workshop:start -->") == 1
before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (config, instructions)}
subprocess.run(["pixi", "run", "setup-agent", "--apply"], check=True)
assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before}
print("PASS: preview, skill links, configuration, instruction block, repeat setup")
PY
pixi run workshop doctor
pixi run workshop validate
pixi run workshop find "release review" --offline --limit 3
# Run from outside the checkout, without relying on system Python.
workshop_manifest="$PWD/pixi.toml"
(
    cd /tmp
    pixi run --manifest-path "$workshop_manifest" python \
        "$HOME/.agents/skills/workshop-feedback/scripts/feedback.py" --help
    pixi run --manifest-path "$workshop_manifest" python \
        "$HOME/.agents/skills/workshop-feedback/scripts/usage.py" --help
)
pixi run validate
# No tracked files should change during installation or validation.
test -z "$(git status --porcelain --untracked-files=no)"
printf '%s\n' 'PASS: clean installation and validation'
