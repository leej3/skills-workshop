"""Read fresh, thread-scoped turn metadata when no rollout transcript exists."""

import json
import argparse
from pathlib import Path
import re
import sqlite3
import sys
import time
import uuid


def resolve(database, thread_id, now=None):
    now = time.time() if now is None else now
    pattern = re.compile(
        r"turn\{[^{}]*thread\.id="
        + re.escape(thread_id)
        + r" turn\.id=([^\s}]+) model=([^\s}]+) "
        r"codex\.turn\.reasoning_effort=([^\s}]+)"
    )
    uri = Path(database).resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute(
            "SELECT ts, feedback_log_body FROM logs WHERE thread_id = ? "
            "ORDER BY id DESC LIMIT 200",
            (thread_id,),
        )
        for timestamp, body in rows:
            match = pattern.search(body or "")
            if not match:
                continue
            if not 0 <= now - timestamp <= 300:
                raise ValueError(
                    "runtime turn evidence is not fresh (five-minute limit)"
                )
            turn, model, effort = match.groups()
            if effort not in {
                "none",
                "minimal",
                "low",
                "medium",
                "high",
                "xhigh",
                "max",
                "ultra",
            }:
                raise ValueError("unrecognized runtime reasoning effort")
            return {"turn_id": turn, "model": model, "reasoning_effort": effort}
    raise ValueError("no matching runtime turn metadata for this thread")


def resolve_task_service_context(path, expected_thread_id):
    """Validate user-supplied task-service IDs when runtime identity is absent.

    Task-service context is intentionally partial: it can establish a verified
    task/turn reference, but cannot assert a model or reasoning effort.
    """
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("task-service context must be a regular file")
    try:
        document = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("invalid task-service context JSON") from error
    required = {
        "schema_version",
        "evidence_source",
        "evidence_reference",
        "thread_id",
        "turn_id",
        "model",
        "reasoning_effort",
    }
    if not isinstance(document, dict) or set(document) != required:
        raise ValueError("invalid task-service context fields")
    if document["schema_version"] != 1:
        raise ValueError("unsupported task-service context schema")
    if document["evidence_source"] != "task-service-verified-delegation-transcript":
        raise ValueError("unrecognized task-service evidence source")

    def canonical_uuid(value, field):
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a UUID string")
        try:
            canonical = str(uuid.UUID(value))
        except ValueError as error:
            raise ValueError(f"{field} must be a UUID string") from error
        if canonical != value:
            raise ValueError(f"{field} must be a canonical UUID")
        return canonical

    thread_id = canonical_uuid(document["thread_id"], "thread_id")
    turn_id = canonical_uuid(document["turn_id"], "turn_id")
    expected = canonical_uuid(expected_thread_id, "expected thread_id")
    if thread_id != expected:
        raise ValueError("task-service thread does not match CODEX_THREAD_ID")
    evidence_reference = canonical_uuid(
        document["evidence_reference"], "evidence_reference"
    )

    def unavailable(value, field):
        if not isinstance(value, dict) or set(value) != {"status", "value", "reason"}:
            raise ValueError(f"{field} must explicitly record unavailable status")
        reason = value["reason"]
        if (
            value["status"] != "unavailable"
            or value["value"] is not None
            or not isinstance(reason, str)
            or not reason.strip()
            or "\n" in reason
            or "\r" in reason
        ):
            raise ValueError(
                f"{field} must have a truthful single-line unavailable reason"
            )
        return reason.strip()

    return {
        "provenance_mode": "task-service-partial",
        "thread_id": thread_id,
        "turn_id": turn_id,
        "evidence_source": document["evidence_source"],
        "evidence_reference": evidence_reference,
        "model": None,
        "model_unavailable_reason": unavailable(document["model"], "model"),
        "reasoning_effort": None,
        "reasoning_effort_unavailable_reason": unavailable(
            document["reasoning_effort"], "reasoning_effort"
        ),
    }


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument("arg1")
        parser.add_argument("arg2", nargs="?")
        parser.add_argument("--task-service-context")
        args = parser.parse_args()
        if args.task_service_context:
            if args.arg2 is not None:
                raise ValueError(
                    "task-service mode accepts only the expected thread ID"
                )
            result = resolve_task_service_context(args.task_service_context, args.arg1)
        else:
            if args.arg2 is None:
                raise ValueError("database and thread ID are required")
            result = resolve(args.arg1, args.arg2)
        print(json.dumps(result))
    except (sqlite3.Error, ValueError, OSError) as error:
        sys.exit(f"commit-provenance: {error}")
