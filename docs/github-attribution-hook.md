# GitHub attribution hook

The Workshop maintains `scripts/github_attribution_hook.py` and its tests.
This optional Codex `PreToolUse` hook helps an agent remember its publishing identity.
It is not an authorization system or a security boundary.

For directly inspectable GitHub messages, the hook requires this first non-empty line:

```text
**AI-generated draft — not reviewed by John**
```

It checks `gh pr` and `gh issue` bodies, file bodies, reviews, and comments attached to close/reopen commands.
It also checks common GitHub MCP body fields.
Missing attribution blocks the call with instructions to correct and retry.
An implicit or dynamic body produces a reminder; unrelated operations pass through.
It does not infer approval, rewrite messages, or inspect human edit history.
The agent remains responsible for preserving human-edited comments.

## Install

Add the following group to `hooks.PreToolUse` in `~/.codex/hooks.json`, preserving existing hooks.
Replace the Python and checkout paths with absolute paths on your machine.

```json
{
  "matcher": "Bash|.*github.*",
  "hooks": [{
    "type": "command",
    "command": "/absolute/path/to/python3 /absolute/path/to/skills-workshop/scripts/github_attribution_hook.py",
    "timeout": 5,
    "statusMessage": "Checking GitHub message attribution"
  }]
}
```

The configuration points directly to the maintained source; no deployed code copy is needed.
Keep the checkout at that path.
Review and trust the hook through Codex's `/hooks` interface before relying on it.
After source changes, run the tests and recheck activation in a new session.
Workshop activation modes govern skill guidance; they do not toggle this separately installed hook.
Remove only this group to uninstall it.

```console
pixi run pytest -q tests/test_github_attribution_hook.py
```

See the [Codex hook documentation](https://learn.chatgpt.com/docs/hooks) for trust and event behavior.
