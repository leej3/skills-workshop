#!/usr/bin/env python3
"""Record schema-validated skill observations with a private sensitivity overlay."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from observation_store import SCHEMA, private_root, public_root, read, write

OUTCOMES = ("success", "partial", "failure", "abandoned", "unknown")


def append(args, payload):
    sensitivity = None
    if args.private_fields or args.visibility == "private":
        if not args.sensitivity_reason or not args.sensitivity_category:
            raise ValueError(
                "private content requires --sensitivity-category and --sensitivity-reason"
            )
        sensitivity = {
            "fields": args.private_fields,
            "category": args.sensitivity_category,
            "reason": args.sensitivity_reason,
            "classifier": args.classifier,
            "confidence": args.classification_confidence,
            "policy_version": "overlay-v1",
        }
    return write(
        args.store, args.overlay, payload, args.event_id, args.visibility, sensitivity
    )


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
    payload = {
        "kind": "usage",
        "skill": args.skill,
        "task": args.task,
        "outcome": args.outcome,
        "task_outcome": args.task_outcome,
        "duration_seconds": args.duration_seconds,
        "duration_scope": args.duration_scope,
        "skill_digest": digest,
        "model": args.model,
        "measurement": args.measurement,
        "unit": "skill-task",
    }
    if args.details:
        details = json.loads(args.details.read_text())
        allowed = {
            "context",
            "execution",
            "resources",
            "quality",
            "evidence",
            "evaluation",
        }
        if not isinstance(details, dict) or set(details) - allowed:
            raise ValueError(
                "details must contain only schema-defined optional reporting groups"
            )
        payload.update(details)
    return append(args, payload)


def note(args):
    rows = read(args.store, args.overlay)
    uses = {r["id"]: r for r in rows if r["kind"] == "usage"}
    if any(r not in uses or uses[r]["skill"] != args.skill for r in args.usage_id):
        raise ValueError("usage IDs must identify observations of this skill")
    return append(
        args,
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
        metrics = {}
        for section, fields in {
            "resources": (
                "input_tokens",
                "output_tokens",
                "cached_input_tokens",
                "cost_usd",
                "peak_rss_bytes",
                "cpu_seconds",
            ),
            "execution": ("attempts", "tool_calls", "errors", "retries"),
            "quality": (
                "tests_passed",
                "tests_failed",
                "human_interventions",
                "rework_seconds",
                "rating",
            ),
        }.items():
            for field in fields:
                values = [
                    r[section][field] for r in group if field in r.get(section, {})
                ]
                if values:
                    metrics[f"{section}.{field}"] = {
                        "n": len(values),
                        "median": statistics.median(values),
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
                "metrics": metrics,
                "measurement_sources": dict(Counter(r["measurement"] for r in group)),
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
    parser.add_argument(
        "--store", type=Path, default=public_root(), help="shareable record tree"
    )
    parser.add_argument(
        "--overlay",
        type=Path,
        default=private_root(),
        help="private overlay outside Git",
    )
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
    use.add_argument(
        "--details",
        type=Path,
        help="JSON object with optional schema-defined reporting groups",
    )
    use.add_argument(
        "--measurement",
        choices=("agent-reported", "host-measured", "human-reported", "mixed"),
        default="agent-reported",
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
        "--status", choices=("open", "resolved", "deferred", "rejected"), default="open"
    )
    notes.add_argument("--usage-id", action="append", default=[])
    notes.add_argument("--event-id", type=short)
    for command in (use, notes):
        command.add_argument(
            "--visibility", choices=("shareable", "private"), default="shareable"
        )
        command.add_argument("--private-fields", nargs="+", default=[])
        command.add_argument("--sensitivity-reason", type=short)
        command.add_argument(
            "--sensitivity-category",
            choices=(
                "personal",
                "credentials",
                "confidential-project",
                "private-conversation",
                "internal-location",
                "uncertain",
                "other",
            ),
        )
        command.add_argument(
            "--classifier", choices=("agent", "human", "tool"), default="agent"
        )
        command.add_argument(
            "--classification-confidence",
            choices=("low", "medium", "high"),
            default="medium",
        )
    commands.add_parser("schema", help="print the formal JSON Schema")
    for name in ("summary", "insights", "sensitivity", "validate"):
        command = commands.add_parser(name)
        command.add_argument("--since", type=lambda s: datetime.fromisoformat(s).date())
        command.add_argument("--public-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            result = record(args)
        elif args.command == "note":
            result = note(args)
        elif args.command == "schema":
            result = SCHEMA
        else:
            rows = read(args.store, args.overlay, args.public_only)
            if args.since:
                rows = [
                    r
                    for r in rows
                    if datetime.fromisoformat(r["recorded_at"]).date() >= args.since
                ]
            if args.command == "summary":
                result = summary(rows)
            elif args.command == "insights":
                result = insights(rows)
            elif args.command == "validate":
                result = {
                    "valid": True,
                    "records": len(rows),
                    "view": "shareable" if args.public_only else "merged",
                }
            else:
                groups = defaultdict(list)
                for row in rows:
                    if row.get("sensitivity"):
                        classification = row["sensitivity"]
                        groups[
                            (
                                classification["category"],
                                tuple(classification["fields"]),
                            )
                        ].append(classification)
                result = [
                    {
                        "category": category,
                        "fields": fields,
                        "n": len(items),
                        "reasons": sorted({i["reason"] for i in items}),
                        "guidance": "Review recurring classifications; do not automatically weaken disclosure rules.",
                    }
                    for (category, fields), items in sorted(groups.items())
                ]
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except (ValueError, OSError) as error:
        parser.exit(1, f"Feedback not recorded/read: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())
