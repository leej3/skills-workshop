---
name: gwq
description: Use gwq to create, locate, and work in Git worktrees, including agent-created detached checkouts. Apply its scripting and absorbed-submodule limitations when using it unattended.
---

Use the installed `gwq` executable.
Consult its command help and [upstream documentation](https://github.com/d-kuro/gwq).

Run repository-scoped commands from the intended repository.
`gwq list --json` uses Git's registered worktrees and finds linked checkouts in other storage locations.
Global mode scans only `worktree.basedir`; it is not a complete Git worktree inventory.
Do not relocate existing worktrees to make them discoverable.

For agents, inspect the JSON listing and select one exact path or branch.
`get`, `cd`, `exec`, and `remove` use substring matching and open a picker when matches are ambiguous.
Verify uniqueness before invoking them.
Do not use `cd` or `--stay` for unattended work: these can launch a nested shell.
Use the selected directory as the execution working directory instead.

Create a branch with `gwq add -b BRANCH`, supplying an explicit destination when the repository has no hosted remote or its remote is a local filesystem path.
Inspect the listing afterward to obtain the path; creation stdout is a human message.
Skip missing paths in navigation.
Treat unexpected non-JSON output as an incomplete result rather than a valid empty listing.

Observed in v0.1.2: absorbed submodules report their primary Git metadata directory as the worktree path.
Before using a selected primary entry, resolve the checkout with `git -C PATH rev-parse --show-toplevel`.
Use that returned checkout directory, not `.git/modules/...`.
Global discovery also omits linked worktrees whose Git directory is under a submodule's `modules/` tree; inspect those repositories individually.

Removal can print an error while returning status 0.
After an authorized removal, verify both the directory and Git's worktree records.
Ordinary removal can delete ignored files; preserve them first.
Git Annex hydration and content preservation remain separate operations.
Do not infer recoverable content from a clean Git status, and do not add force or prune operations to work around a failed removal.
