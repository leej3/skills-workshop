import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from runtime_context import resolve, resolve_task_service_context


class RuntimeContextTests(unittest.TestCase):
    def test_newest_turn_and_thread_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "logs.sqlite"
            with sqlite3.connect(database) as connection:
                connection.execute(
                    "CREATE TABLE logs (id INTEGER PRIMARY KEY, ts INTEGER, thread_id TEXT, feedback_log_body TEXT)"
                )
                for thread, turn, effort in [
                    ("side", "old", "low"),
                    ("side", "new", "medium"),
                    ("parent", "other", "high"),
                ]:
                    body = f"turn{{thread.id={thread} turn.id={turn} model=gpt-6-astra codex.turn.reasoning_effort={effort}}}"
                    connection.execute(
                        "INSERT INTO logs (ts,thread_id,feedback_log_body) VALUES (?,?,?)",
                        (1000, thread, body),
                    )
            self.assertEqual(
                resolve(database, "side", now=1001),
                {
                    "turn_id": "new",
                    "model": "gpt-6-astra",
                    "reasoning_effort": "medium",
                },
            )
            with self.assertRaisesRegex(ValueError, "not fresh"):
                resolve(database, "side", now=1400)
            with self.assertRaisesRegex(ValueError, "no matching"):
                resolve(database, "missing", now=1001)

    def test_missing_database_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "missing.sqlite"
            with self.assertRaises(sqlite3.Error):
                resolve(database, "side")
            self.assertFalse(database.exists())

    def task_service_document(self):
        return {
            "schema_version": 1,
            "evidence_source": "task-service-verified-delegation-transcript",
            "evidence_reference": "01a0f366-073b-7231-a8d6-b4188e1450d7",
            "thread_id": "01a10eed-811f-701a-943f-5f9b8d9680db",
            "turn_id": "01a112d4-959b-7435-ba7d-25cbfd29f3c9",
            "model": {
                "status": "unavailable",
                "value": None,
                "reason": "Task service did not provide runtime model identity.",
            },
            "reasoning_effort": {
                "status": "unavailable",
                "value": None,
                "reason": "Task service did not expose runtime reasoning effort.",
            },
        }

    def test_valid_task_service_partial_context(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            path.write_text(json.dumps(self.task_service_document()))
            resolved = resolve_task_service_context(
                path, "01a10eed-811f-701a-943f-5f9b8d9680db"
            )
        self.assertEqual(resolved["provenance_mode"], "task-service-partial")
        self.assertEqual(resolved["thread_id"], "01a10eed-811f-701a-943f-5f9b8d9680db")
        self.assertEqual(resolved["turn_id"], "01a112d4-959b-7435-ba7d-25cbfd29f3c9")
        self.assertEqual(
            resolved["evidence_source"], "task-service-verified-delegation-transcript"
        )
        self.assertEqual(
            resolved["evidence_reference"], "01a0f366-073b-7231-a8d6-b4188e1450d7"
        )
        self.assertIsNone(resolved["model"])
        self.assertIsNone(resolved["reasoning_effort"])
        self.assertTrue(resolved["model_unavailable_reason"])
        self.assertTrue(resolved["reasoning_effort_unavailable_reason"])

    def test_task_service_context_rejects_missing_or_invalid_ids(self):
        for field, value in (
            ("thread_id", None),
            ("turn_id", "not-a-uuid"),
            ("evidence_reference", "not-a-uuid"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                document = self.task_service_document()
                if value is None:
                    del document[field]
                else:
                    document[field] = value
                path = Path(directory) / "context.json"
                path.write_text(json.dumps(document))
                with self.assertRaises(ValueError):
                    resolve_task_service_context(
                        path, "01a10eed-811f-701a-943f-5f9b8d9680db"
                    )

    def test_task_service_context_rejects_cross_thread_and_claimed_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            document = self.task_service_document()
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "does not match"):
                resolve_task_service_context(
                    path, "01a0f366-073b-7231-a8d6-b4188e1450d7"
                )
            document["model"]["value"] = "gpt-6"
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(ValueError, "unavailable reason"):
                resolve_task_service_context(
                    path, "01a10eed-811f-701a-943f-5f9b8d9680db"
                )

    def test_task_service_context_rejects_unrecognized_evidence_source(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "context.json"
            document = self.task_service_document()
            document["evidence_source"] = "config.toml"
            path.write_text(json.dumps(document))
            with self.assertRaisesRegex(
                ValueError, "unrecognized task-service evidence"
            ):
                resolve_task_service_context(
                    path, "01a10eed-811f-701a-943f-5f9b8d9680db"
                )


if __name__ == "__main__":
    unittest.main()
