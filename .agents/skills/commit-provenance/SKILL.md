---
name: commit-provenance
description: Resolve the exact active Codex Desktop and agent-runtime versions, model identifier, and reasoning effort for commit provenance. Use immediately before every Codex-authored git commit or whenever a commit trailer requires model, tool, or reasoning-effort attribution.
---

# Commit Provenance

Run `scripts/resolve.sh` immediately before creating the commit. Do not reuse a
previous result after a model or effort switch.

The script resolves the current task from `CODEX_THREAD_ID`, then reads the
latest `turn_context` in that task's local session transcript. Treat this as
authoritative for model and reasoning effort. Never infer either from prose or
use `config.toml` as the current-turn value.

## Commit trailer

Use the script's two output trailers unchanged:

```text
Co-Authored-By: Codex Desktop <desktop-version> (runtime codex-cli <runtime-version>) / <model> <codex@openai.com>
Codex-Reasoning-Effort: <effort>
```

If the script cannot identify every required value, stop and ask the user; do
not create the commit with guessed provenance. Preserve any stricter repository
commit-message requirements.
