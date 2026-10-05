import fcntl
import io
import json
import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from scripts.archive_side_chat import BackupError, handle, main, save


@contextmanager
def database(path):
    connection = sqlite3.connect(path)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        with database(self.home / "state_5.sqlite") as db:
            db.execute("CREATE TABLE threads (id TEXT)")
        self.session = "00000000-0000-4000-8000-000000000001"
        self.event = {
            "session_id": self.session,
            "turn_id": "turn-1",
            "transcript_path": None,
            "hook_event_name": "Stop",
            "last_assistant_message": "Actual **reply** — intact.",
        }
        (self.home / ".codex-global-state.json").write_text("{}")

    def mark_side_chat(self):
        self.atoms = {
            f"thread-client-id-v1:local%3A{self.session}": "client-new-thread:test",
            "client-thread-bindings-v1": {"client-new-thread:test": self.session},
            "prompt-history": {self.session: ["Side question"]},
        }
        (self.home / ".codex-global-state.json").write_text(
            json.dumps({"electron-persisted-atom-state": self.atoms})
        )

    def test_saves_prompt_and_reply_without_duplicates(self):
        self.mark_side_chat()
        prompt = dict(
            self.event, hook_event_name="UserPromptSubmit", prompt="My question"
        )
        self.assertTrue(save(prompt, self.home))
        self.assertTrue(save(self.event, self.home))
        self.assertTrue(save(self.event, self.home))
        folder = self.home / "side-chat-archive"
        rows = [
            json.loads(line)
            for line in (folder / f"{self.session}.jsonl").read_text().splitlines()
        ]
        self.assertEqual([r["role"] for r in rows], ["user", "assistant"])
        self.assertEqual(rows[-1]["content"], self.event["last_assistant_message"])
        self.assertIn(
            self.event["last_assistant_message"],
            (folder / f"{self.session}.md").read_text(),
        )
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        self.assertEqual(
            (folder / f"{self.session}.jsonl").stat().st_mode & 0o777, 0o600
        )

    def test_persisted_main_thread_is_not_saved_even_without_transcript(self):
        self.mark_side_chat()
        with database(self.home / "state_5.sqlite") as db:
            db.execute("INSERT INTO threads VALUES (?)", (self.session,))
        self.assertFalse(save(self.event, self.home))
        self.assertFalse((self.home / "side-chat-archive").exists())

    def test_first_prompt_is_recovered_from_desktop_history_at_stop(self):
        self.mark_side_chat()
        self.atoms["prompt-history"] = {
            self.session: ["First prompt"],
            "unrelated": ["Do not copy"],
        }
        (self.home / ".codex-global-state.json").write_text(
            json.dumps({"electron-persisted-atom-state": self.atoms})
        )
        save(self.event, self.home)
        rows = [
            json.loads(line)
            for line in (self.home / "side-chat-archive" / f"{self.session}.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertEqual(
            [r["content"] for r in rows],
            ["First prompt", self.event["last_assistant_message"]],
        )

    def test_transcript_thread_is_not_saved(self):
        self.mark_side_chat()
        self.assertFalse(
            save(dict(self.event, transcript_path="/a/transcript.jsonl"), self.home)
        )

    def test_desktop_fork_without_client_binding_is_saved_but_main_is_not(self):
        # Real Desktop forks have prompt history without client-new-thread state.
        atoms = {"prompt-history": {self.session: ["Side question"]}}
        (self.home / ".codex-global-state.json").write_text(
            json.dumps({"electron-persisted-atom-state": atoms})
        )
        self.assertTrue(save(self.event, self.home))
        archive = self.home / "side-chat-archive" / f"{self.session}.jsonl"
        rows = [json.loads(line) for line in archive.read_text().splitlines()]
        self.assertEqual(
            [r["content"] for r in rows],
            ["Side question", self.event["last_assistant_message"]],
        )
        # Saving a normal thread always excludes it, even with Desktop history.
        with database(self.home / "state_5.sqlite") as db:
            db.execute("INSERT INTO threads VALUES (?)", (self.session,))
        before = archive.read_bytes()
        self.assertFalse(save(dict(self.event, turn_id="turn-2"), self.home))
        self.assertEqual(archive.read_bytes(), before)

    def test_another_chats_prompt_history_does_not_qualify_this_session(self):
        atoms = {"prompt-history": {"another-session": ["Unrelated prompt"]}}
        (self.home / ".codex-global-state.json").write_text(
            json.dumps({"electron-persisted-atom-state": atoms})
        )
        with self.assertRaises(BackupError):
            save(self.event, self.home)

    def test_unknown_ephemeral_thread_is_not_saved(self):
        result = handle(self.event, self.home)
        self.assertIn("Cannot identify", result["systemMessage"])
        self.assertFalse((self.home / "side-chat-archive").exists())

    def test_inconsistent_binding_is_not_saved(self):
        self.mark_side_chat()
        self.atoms.pop("prompt-history")
        self.atoms["client-thread-bindings-v1"]["client-new-thread:test"] = (
            "different-session"
        )
        (self.home / ".codex-global-state.json").write_text(
            json.dumps({"electron-persisted-atom-state": self.atoms})
        )
        with self.assertRaises(BackupError):
            save(self.event, self.home)

    def test_empty_or_other_hook_does_not_create_archive(self):
        self.mark_side_chat()
        result = handle(dict(self.event, last_assistant_message=None), self.home)
        self.assertIn("no assistant text", result["systemMessage"])
        self.assertFalse(
            save(dict(self.event, hook_event_name="PreToolUse"), self.home)
        )

    def test_missing_prompt_warns_after_saving_reply(self):
        self.mark_side_chat()
        self.atoms.pop("prompt-history")
        (self.home / ".codex-global-state.json").write_text(
            json.dumps({"electron-persisted-atom-state": self.atoms})
        )
        result = handle(self.event, self.home)
        self.assertIn("reply was saved", result["systemMessage"])
        path = self.home / "side-chat-archive" / f"{self.session}.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertEqual(rows[0]["content"], self.event["last_assistant_message"])

    def test_write_failure_warns_without_exposing_content(self):
        self.mark_side_chat()
        (self.home / "side-chat-archive").write_text("Obstruct directory creation")
        result = handle(self.event, self.home)
        self.assertIn("WARNING", result["systemMessage"])
        self.assertIn("Copy this chat", result["systemMessage"])
        self.assertNotIn(self.event["last_assistant_message"], json.dumps(result))
        self.assertNotIn("continue", result)

    def test_lock_contention_warns_immediately(self):
        self.mark_side_chat()
        save(self.event, self.home)
        path = self.home / "side-chat-archive" / f"{self.session}.jsonl"
        with path.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = handle(self.event, self.home)
        self.assertIn("Archive access failed", result["systemMessage"])

    def test_corrupt_database_or_archive_warns(self):
        self.mark_side_chat()
        save(self.event, self.home)
        path = self.home / "side-chat-archive" / f"{self.session}.jsonl"
        path.write_text("broken JSON with private text")
        result = handle(self.event, self.home)
        self.assertIn("JSONDecodeError", result["systemMessage"])
        self.assertNotIn("private text", result["systemMessage"])
        (self.home / "state_5.sqlite").unlink()
        self.assertIn("systemMessage", handle(self.event, self.home))

    def test_main_threads_and_successful_side_chats_are_quiet(self):
        self.mark_side_chat()
        self.assertEqual(handle(self.event, self.home), {})
        with database(self.home / "state_5.sqlite") as db:
            db.execute("INSERT INTO threads VALUES (?)", (self.session,))
        self.assertEqual(handle(self.event, self.home), {})

    def test_malformed_hook_input_still_emits_warning_json(self):
        output = io.StringIO()
        with (
            patch.dict(os.environ, {"CODEX_HOME": str(self.home)}),
            patch("sys.stdin", io.StringIO("private malformed payload")),
            patch("sys.stdout", output),
        ):
            main()
        result = json.loads(output.getvalue())
        self.assertIn("JSONDecodeError", result["systemMessage"])
        self.assertNotIn("private malformed payload", result["systemMessage"])

    def test_side_chat_receives_its_archive_location(self):
        self.mark_side_chat()
        result = handle(
            dict(self.event, hook_event_name="UserPromptSubmit", prompt="Question"),
            self.home,
        )
        context = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn(f"{self.session}.md", context)
        self.assertNotIn("systemMessage", result)

    def test_main_thread_can_discover_archives_without_copying_their_content(self):
        self.mark_side_chat()
        save(dict(self.event, cwd="/work/project"), self.home)
        with database(self.home / "state_5.sqlite") as db:
            db.execute("INSERT INTO threads VALUES (?)", (self.session,))
        archive = self.home / "side-chat-archive" / f"{self.session}.jsonl"
        before = archive.read_bytes()
        result = handle(
            dict(self.event, hook_event_name="UserPromptSubmit", prompt="Recover it"),
            self.home,
        )
        context = result["hookSpecificOutput"]["additionalContext"]
        self.assertIn(str(archive.parent), context)
        self.assertNotIn("This side chat's archive ID", context)
        self.assertNotIn(self.event["last_assistant_message"], context)
        self.assertEqual(archive.read_bytes(), before)
        self.assertEqual(json.loads(before.splitlines()[-1])["cwd"], "/work/project")

    def test_no_discovery_hint_when_archive_does_not_exist(self):
        with database(self.home / "state_5.sqlite") as db:
            db.execute("INSERT INTO threads VALUES (?)", (self.session,))
        self.assertEqual(
            handle(dict(self.event, hook_event_name="UserPromptSubmit"), self.home),
            {},
        )


if __name__ == "__main__":
    unittest.main()
