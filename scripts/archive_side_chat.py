"""Archive completed local Desktop side-chat turns; ignore persisted threads.

Installed as UserPromptSubmit and Stop hooks. The public hook payload has no
side-chat flag. Eligibility therefore requires all three current-runtime facts:
no transcript path, no persisted thread, and a local Desktop client binding.
Unknown sessions are skipped. No network requests or app database writes.
"""

import fcntl
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID


@contextmanager
def read_database(path):
    connection = sqlite3.connect(
        path.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.5
    )
    try:
        yield connection
    finally:
        connection.close()


def eligible(event, home):
    if event.get("transcript_path"):
        return False
    session = event["session_id"]
    # Paginated ordinary threads can also have no transcript file.
    with read_database(home / "state_5.sqlite") as connection:
        if connection.execute(
            "SELECT 1 FROM threads WHERE id=?", (session,)
        ).fetchone():
            return False
    # Interactive Desktop side chats have a client binding but no persisted
    # thread. CLI ephemeral runs and background sessions lack this binding.
    state = json.loads((home / ".codex-global-state.json").read_text())
    atoms = state.get("electron-persisted-atom-state", {})
    client = atoms.get(f"thread-client-id-v1:local%3A{session}")
    return (
        isinstance(client, str)
        and client.startswith("client-new-thread:")
        and atoms.get("client-thread-bindings-v1", {}).get(client) == session
    )


def save(event, home):
    kind = event.get("hook_event_name")
    if kind not in {"UserPromptSubmit", "Stop"}:
        return False
    session = event.get("session_id")
    if not isinstance(session, str) or str(UUID(session)) != session:
        raise ValueError("Invalid session identifier")
    role = "user" if kind == "UserPromptSubmit" else "assistant"
    content = event.get("prompt" if role == "user" else "last_assistant_message")
    if not isinstance(content, str) or not content:
        return False
    if not eligible(event, home):
        return False

    directory = home / "side-chat-archive"
    directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(directory, 0o700)
    filename = directory / f"{session}.jsonl"
    flags = os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW
    descriptor = os.open(filename, flags, 0o600)
    with os.fdopen(descriptor, "a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        os.fchmod(stream.fileno(), 0o600)
        stream.seek(0)
        messages = [json.loads(line) for line in stream if line.strip()]
        item = {
            "session_id": session,
            "turn_id": event.get("turn_id"),
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "role": role,
            "content": content,
        }
        # Recover the first prompt at Stop if the UI had not persisted its
        # client binding when the prompt hook ran. Only read this chat's history.
        if role == "assistant" and not any(
            m["role"] == "user" and m.get("turn_id") == item["turn_id"]
            for m in messages
        ):
            state_path = home / ".codex-global-state.json"
            try:
                state = json.loads(state_path.read_text())
            except (OSError, ValueError):
                state = {}  # An unavailable prompt cache must not lose the reply.
            prompts = (
                state.get("electron-persisted-atom-state", {})
                .get("prompt-history", {})
                .get(session, [])
            )
            if prompts and isinstance(prompts[-1], str):
                prompt = dict(item, role="user", content=prompts[-1])
                stream.write(json.dumps(prompt, ensure_ascii=False) + "\n")
                messages.append(prompt)
        if not any(
            all(old.get(key) == item[key] for key in ("turn_id", "role", "content"))
            for old in messages
        ):
            stream.write(json.dumps(item, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            messages.append(item)
        markdown = "# Side conversation\n\n" + f"Session: `{session}`\n\n"
        markdown += (
            "\n\n".join(f"## {m['role'].title()}\n\n{m['content']}" for m in messages)
            + "\n"
        )
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=directory,
                prefix=f".{session}-",
                delete=False,
            ) as output:
                temporary = Path(output.name)
                output.write(markdown)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, directory / f"{session}.md")
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return True


def main():
    try:
        event = json.load(sys.stdin)
        save(event, Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))))
        result = {}
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        # Advisory: never continue or block a turn, and do not log its contents.
        result = {
            "systemMessage": f"Side-chat backup unavailable: {type(error).__name__}."
        }
    print(json.dumps(result))


if __name__ == "__main__":
    main()
