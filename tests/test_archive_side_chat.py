import json
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path

from scripts.archive_side_chat import save


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

    def test_unknown_ephemeral_thread_is_not_saved(self):
        self.assertFalse(save(self.event, self.home))

    def test_inconsistent_binding_is_not_saved(self):
        self.mark_side_chat()
        self.atoms["client-thread-bindings-v1"]["client-new-thread:test"] = (
            "different-session"
        )
        (self.home / ".codex-global-state.json").write_text(
            json.dumps({"electron-persisted-atom-state": self.atoms})
        )
        self.assertFalse(save(self.event, self.home))

    def test_empty_or_other_hook_does_not_create_archive(self):
        self.mark_side_chat()
        self.assertFalse(save(dict(self.event, last_assistant_message=None), self.home))
        self.assertFalse(
            save(dict(self.event, hook_event_name="PreToolUse"), self.home)
        )


if __name__ == "__main__":
    unittest.main()
