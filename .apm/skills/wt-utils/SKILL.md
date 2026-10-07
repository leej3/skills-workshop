---
name: wt-utils
description: Use the installed wt CLI to create, find, move, remove, or transfer Git worktrees.
---

If the tool is missing, follow the [wt-utils installation instructions](https://github.com/leej3/wt-utils#install).
Use `wt` for worktree operations.
Consult `wt --help` and subcommand help.
Pass `--no-interactive` for agent use and `--repo PATH` to select the repository.
For example: `wt new codex/my-task --repo PATH --no-interactive`.
The tool reuses existing branch worktrees and creates new ones in XDG user data storage.
Use `wt list --no-interactive --json` to discover their paths.
