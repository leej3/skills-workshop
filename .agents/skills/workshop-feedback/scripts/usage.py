#!/usr/bin/env python3
"""Private, append-only skill observations. Python standard library; no Git or network."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import statistics
import uuid
from collections import Counter, defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

OUTCOMES = ("success", "partial", "failure", "unknown")


def default_store():
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "skills-workshop"
        / "feedback"
    )


@contextmanager
def journal(store):
    store = store.expanduser().resolve()
    if any((p / ".git").exists() for p in (store, *store.parents)):
        raise ValueError(
            "feedback storage must be outside Git; export curated lessons separately"
        )
    store.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(store, 0o700)
    path = store / "observations.jsonl"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "r+", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        fcntl.flock(stream, fcntl.LOCK_EX)
        rows = []
        for line in stream:
            row = json.loads(line)
            if row.get("schema_version") != 1:
                raise ValueError("unsupported observation schema")
            rows.append(row)
        yield stream, rows


def append(store, payload, event_id=None):
    event_id = event_id or str(uuid.uuid4())
    with journal(store) as (stream, rows):
        for row in rows:
            if row["id"] == event_id:
                original = {
                    k: v
                    for k, v in row.items()
                    if k not in ("id", "recorded_at", "schema_version")
                }
                if original != payload:
                    raise ValueError("event ID already exists with different content")
                return {"id": event_id, "duplicate": True}
        row = {
            "schema_version": 1,
            "id": event_id,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return {"id": event_id, "duplicate": False}


def record(args):
    if args.duration_seconds is not None:
        if not math.isfinite(args.duration_seconds) or args.duration_seconds < 0:
            raise ValueError("duration must be finite and nonnegative")
        if args.duration_scope is None:
            raise ValueError("duration requires --duration-scope task or skill")
    elif args.duration_scope is not None:
        raise ValueError("duration scope requires a measured duration")
    digest = None
    if args.skill_path:
        path = args.skill_path
        if path.is_dir():
            path = path / "SKILL.md"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return append(
        args.store,
        {
            "kind": "usage",
            "skill": args.skill,
            "task": args.task,
            "outcome": args.outcome,
            "task_outcome": args.task_outcome,
            "duration_seconds": args.duration_seconds,
            "duration_scope": args.duration_scope,
            "skill_digest": digest,
            "model": args.model,
            "measurement": "agent-reported",
            "unit": "skill-task",
        },
        args.event_id,
    )


def note(args):
    with journal(args.store) as (_, rows):
        uses = {r["id"]: r for r in rows if r["kind"] == "usage"}
    if any(r not in uses or uses[r]["skill"] != args.skill for r in args.usage_id):
        raise ValueError("usage IDs must identify observations of this skill")
    return append(
        args.store,
        {
            "kind": "insight",
            "skill": args.skill,
            "group": args.group,
            "priority": args.priority,
            "confidence": args.confidence,
            "status": args.status,
            "summary": args.summary,
            "action": args.action,
            "usage_ids": sorted(set(args.usage_id)),
        },
        args.event_id,
    )


def summary(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["kind"] == "usage":
            groups[
                (row["skill"], row["task"], row["skill_digest"], row["model"])
            ].append(row)
    results = []
    for (skill, task, digest, model), group in sorted(
        groups.items(), key=lambda item: str(item[0])
    ):
        outcomes = Counter(r["outcome"] for r in group)
        known = len(group) - outcomes["unknown"]
        durations = {}
        for scope in ("task", "skill"):
            values = [
                r["duration_seconds"] for r in group if r["duration_scope"] == scope
            ]
            durations[scope] = {
                "n": len(values),
                "median_seconds": statistics.median(values) if values else None,
            }
        results.append(
            {
                "skill": skill,
                "task": task,
                "skill_digest": digest,
                "model": model,
                "n": len(group),
                "outcomes": dict(outcomes),
                "known_outcomes": known,
                "success_fraction_known": outcomes["success"] / known
                if known
                else None,
                "task_outcomes": dict(Counter(r["task_outcome"] for r in group)),
                "durations": durations,
            }
        )
    return {
        "groups": results,
        "caveat": "Reported skill-task observations; missing uses are unknown. Not causal benefit or time saved. Task durations overlap across skills; do not sum them.",
    }


def insights(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["kind"] == "insight":
            groups[(row["skill"], row["group"])].append(row)
    results = []
    for (skill, group), notes in groups.items():
        latest = notes[-1]
        if latest["status"] != "open":
            continue
        results.append(
            {
                "skill": skill,
                "group": group,
                "priority": latest["priority"],
                "confidence": latest["confidence"],
                "observations": len(notes),
                "linked_uses": len({u for n in notes for u in n["usage_ids"]}),
                "summary": latest["summary"],
                "action": latest["action"],
                "latest_id": latest["id"],
            }
        )
    return sorted(
        results,
        key=lambda r: (r["priority"], -r["linked_uses"], r["skill"], r["group"]),
    )


def short(value):
    if not value.strip() or len(value) > 240 or any(ord(c) < 32 for c in value):
        raise argparse.ArgumentTypeError(
            "use 1–240 characters without control characters"
        )
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=default_store())
    commands = parser.add_subparsers(dest="command", required=True)
    use = commands.add_parser(
        "record", help="one outcome per skill/task; no narrative required"
    )
    use.add_argument("skill", type=short)
    use.add_argument(
        "--task",
        required=True,
        type=short,
        help="stable category, e.g. build-validation",
    )
    use.add_argument(
        "--outcome",
        required=True,
        choices=OUTCOMES,
        help="did the skill perform its intended role?",
    )
    use.add_argument("--task-outcome", choices=OUTCOMES, default="unknown")
    use.add_argument("--duration-seconds", type=float)
    use.add_argument("--duration-scope", choices=("task", "skill"))
    use.add_argument(
        "--skill-path",
        type=Path,
        help="hash SKILL.md without storing its path or content",
    )
    use.add_argument(
        "--model", type=short, help="only if known; omitted values remain null"
    )
    use.add_argument(
        "--event-id",
        type=short,
        help="reuse a random ID when retrying the same observation",
    )
    notes = commands.add_parser(
        "note", help="exceptional lesson; append again to update a group"
    )
    notes.add_argument("skill", type=short)
    notes.add_argument("--group", required=True, type=short)
    notes.add_argument("--summary", required=True, type=short)
    notes.add_argument("--action", required=True, type=short)
    notes.add_argument("--priority", type=int, choices=range(4), default=2)
    notes.add_argument("--confidence", choices=("low", "medium", "high"), default="low")
    notes.add_argument(
        "--status", choices=("open", "resolved", "deferred"), default="open"
    )
    notes.add_argument("--usage-id", action="append", default=[])
    notes.add_argument("--event-id", type=short)
    for name in ("summary", "insights"):
        read = commands.add_parser(name)
        read.add_argument("--since", type=lambda s: datetime.fromisoformat(s).date())
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            result = record(args)
        elif args.command == "note":
            result = note(args)
        else:
            with journal(args.store) as (_, rows):
                # Insight state must include resolution notes; filter groups by recent activity below.
                if args.since and args.command == "summary":
                    rows = [
                        r
                        for r in rows
                        if datetime.fromisoformat(r["recorded_at"]).date() >= args.since
                    ]
                result = summary(rows) if args.command == "summary" else insights(rows)
                if args.since and args.command == "insights":
                    recent = {
                        r["id"]
                        for r in rows
                        if datetime.fromisoformat(r["recorded_at"]).date() >= args.since
                    }
                    result = [r for r in result if r["latest_id"] in recent]
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(1, f"Feedback not recorded/read: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
