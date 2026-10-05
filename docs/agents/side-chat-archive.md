# Side-chat archive

From a Workshop checkout on each Codex Desktop host:

```console
pixi install --locked
pixi run setup-side-chat-archive
pixi run setup-side-chat-archive --apply
```

Review and trust the `UserPromptSubmit` and `Stop` hooks in Codex CLI `/hooks`.
The installer preserves other hooks and uses this checkout's Python and source paths.
Rerun it after relocating the Python environment; keep the checkout at its installed path.
Hook activation is independent of Workshop skill-guidance modes.

Prompts and completed assistant replies are stored as private Markdown and JSONL files in `$CODEX_HOME/side-chat-archive` (default `~/.codex/side-chat-archive`).
Archives stay on their host, outside Git; installation does not synchronize conversations.
Main threads, tool output, and unfinished replies are excluded.

The hook checks Codex Desktop's prompt history or client bindings and excludes persisted threads because hook events lack a side-chat flag.
Unidentified non-persisted sessions and incomplete or failed backups emit an immediate Codex warning; copy the chat somewhere safe before closing it.
On each submitted prompt, the hook supplies a short model-visible archive recovery hint when the archive directory exists.
An archived side chat also receives its own ID and transcript path; no archived message content is injected into other conversations.
JSONL records include the working directory when supplied by Codex.
The hook payload has no parent-thread ID, so locate older chats by content and timestamps rather than assuming the newest archive belongs to the current thread.
Successful backups do not display warnings.
App changes can require an update to detection; a disabled hook or an app crash cannot report its own failure.
The current implementation supports macOS and Linux, using Python's POSIX file locking.
See [Codex hooks](https://learn.chatgpt.com/docs/hooks) for event and trust behavior.
