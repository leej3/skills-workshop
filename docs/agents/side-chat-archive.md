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
Unknown sessions are skipped; app changes can require an update to this detection.
The current implementation supports macOS and Linux, using Python's POSIX file locking.
See [Codex hooks](https://learn.chatgpt.com/docs/hooks) for event and trust behavior.
