"""Collect, aggregate, publish and project portable Workshop evidence.

JSON results go to stdout; errors go to stderr. No command deletes source data.
"""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tarfile
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.memory_store import (
    MemoryStore,
    artifact,
    atomic_bytes,
    canonical,
    envelope,
    validate,
)


def import_feedback(memory, public, private):
    # Merge before routing: a private overlay makes the complete record sensitive.
    rows = {}
    for tree in (public, private):
        for path in sorted(tree.glob("records/*/*/*.json")):
            raw = path.read_bytes()
            row = json.loads(raw)
            from jsonschema import Draft202012Validator, FormatChecker

            schema = json.loads(
                (
                    Path(__file__).resolve().parents[1]
                    / "controls/skills/workshop-feedback/schemas/observation-v2.schema.json"
                ).read_text()
            )
            if list(
                Draft202012Validator(
                    schema, format_checker=FormatChecker()
                ).iter_errors(row)
            ):
                raise ValueError("invalid legacy observation")
            rows[row["id"]] = (row, raw, tree == private)
    if not public.is_dir() or not private.is_dir():
        raise ValueError(
            "both legacy trees must exist; missing private tree is not evidence of absence"
        )
    result = {"shared": 0, "sensitive": 0, "duplicates": 0}
    for row, raw, private_row in rows.values():
        sensitive = (
            private_row
            or row.get("visibility") == "private"
            or bool(row.get("sensitivity"))
        )
        store = "sensitive" if sensitive else "shared"
        reason = (
            (row.get("sensitivity", {}).get("reason") or "private source tree")
            if sensitive
            else None
        )
        ctx = {
            "conditions": {
                "collection": "legacy-feedback-import",
                "execution": row.get("execution"),
                "evaluation": row.get("evaluation"),
            },
            "model": {"id": row["model"]} if row.get("model") else None,
            "skill": {
                "name": row.get("skill"),
                "entrypoint_digest": row.get("skill_digest"),
            },
        }
        packet = envelope(
            row,
            ident=row["id"],
            kind="observation",
            occurred_at=row["recorded_at"],
            store=store,
            producer="workshop-feedback",
            source_schema="observation-v2",
            reason=reason,
            context=ctx,
            artifacts=[artifact("original-record.json", raw, "application/json")],
        )
        outcome = memory.append(packet, "legacy-feedback-import")
        result[store] += 1
        result["duplicates"] += outcome["duplicate"]
    return result


def rebuild_index(memory, store, output):
    # One independent index per classification. Never merge sensitive rows into shared views.
    temporary = output.with_name(output.name + ".tmp")
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary.unlink(missing_ok=True)
    db = sqlite3.connect(temporary)
    os.chmod(temporary, 0o600)
    try:
        db.execute(
            "CREATE TABLE records(id TEXT PRIMARY KEY,kind TEXT,source TEXT,body TEXT)"
        )
        db.execute("CREATE VIRTUAL TABLE search USING fts5(id UNINDEXED,text)")
        count = 0
        for row in memory.records(store):
            body = canonical(row)
            db.execute(
                "INSERT INTO records VALUES(?,?,?,?)",
                (row["id"], row["kind"], row["source"]["producer"], body),
            )
            db.execute(
                "INSERT INTO search VALUES(?,?)", (row["id"], canonical(row["payload"]))
            )
            count += 1
        db.commit()
    finally:
        db.close()
    os.replace(temporary, output)
    return {"store": store, "records": count, "index": str(output)}


def restore(memory, store, transport):
    restored = 0
    for ref, raw in transport.retrieve():
        batch = json.loads(raw)
        if (
            batch.get("schema_version") != 1
            or batch.get("store") != store
            or ref.split("/")[-1] != batch.get("id")
        ):
            raise ValueError("invalid batch metadata")
        for row in batch["records"]:
            validate(row)
            if row["classification"]["store"] != store:
                raise ValueError("restored classification mismatch")
            memory.reserve(row)
        # Record original batch IDs/receipts, never reaggregate recovery data.
        with memory.lock(store), memory.ledger(store) as db:
            from scripts.memory_store import digest

            body = canonical(batch)
            previous = db.execute(
                "SELECT body FROM batches WHERE id=?", (batch["id"],)
            ).fetchone()
            if previous and previous[0] != body:
                raise ValueError("restored batch conflicts with local history")
            for row in batch["records"]:
                sha = digest(canonical(row).encode())
                prior = db.execute(
                    "SELECT digest,batch_id FROM records WHERE id=?", (row["id"],)
                ).fetchone()
                if prior and prior != (sha, batch["id"]):
                    raise ValueError("restored record conflicts with local history")
                db.execute(
                    "INSERT OR IGNORE INTO records VALUES(?,?,?)",
                    (row["id"], sha, batch["id"]),
                )
            db.execute(
                "INSERT OR IGNORE INTO batches VALUES(?,?,?,'published',?)",
                (
                    batch["id"],
                    batch["day"],
                    body,
                    canonical({"ref": ref, "sha256": digest(raw)}),
                ),
            )
            db.execute("INSERT OR IGNORE INTO days VALUES(?)", (batch["day"],))
            db.commit()
            restored += 1
    return {"restored_batches": restored}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path.home() / ".local/state/skills-workshop/memory",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    ingest = commands.add_parser(
        "ingest", help="validate and append one JSON envelope; '-' reads stdin"
    )
    ingest.add_argument("input")
    ingest.add_argument("--agent", required=True)
    imp = commands.add_parser(
        "import-feedback",
        help="losslessly import legacy public/private trees without deleting them",
    )
    imp.add_argument("--public", type=Path, required=True)
    imp.add_argument("--private", type=Path, required=True)
    capture = commands.add_parser(
        "capture-duct", help="stage a finished run; optional immediate annex upload"
    )
    capture.add_argument("directory", type=Path)
    capture.add_argument("--store", choices=("shared", "sensitive"), required=True)
    capture.add_argument("--agent", required=True)
    capture.add_argument("--reason")
    capture.add_argument("--related")
    capture.add_argument(
        "--config",
        type=Path,
        help="upload artifact now; its assessment still joins the daily batch",
    )
    fetch = commands.add_parser(
        "fetch-artifact", help="explicitly download one referenced artifact"
    )
    fetch.add_argument("reference", type=Path, help="artifact descriptor JSON")
    fetch.add_argument("--config", type=Path, required=True)
    fetch.add_argument("--output", type=Path, required=True)
    daily = commands.add_parser(
        "daily", help="import, seal yesterday, retry uploads and rebuild projections"
    )
    from scripts.memory_legacy import working_tree

    legacy = working_tree(Path(__file__).resolve().parents[1])
    daily.add_argument("--public", type=Path, default=legacy / "observations")
    daily.add_argument("--curated", type=Path, default=legacy)
    daily.add_argument(
        "--private",
        type=Path,
        default=Path.home() / ".local/state/skills-workshop/feedback-overlay",
    )
    daily.add_argument("--config", type=Path, required=True)
    daily.add_argument("--timezone", default="America/New_York")
    curated = commands.add_parser(
        "snapshot-curated", help="stage a lossless curated working-tree snapshot"
    )
    curated.add_argument("directory", type=Path)
    recovery = commands.add_parser(
        "restore-curated", help="recover a fetched curated archive into a new directory"
    )
    recovery.add_argument("archive", type=Path)
    recovery.add_argument("--output", type=Path, required=True)
    for name in ("flush", "publish", "restore", "status", "index", "export"):
        sub = commands.add_parser(name)
        sub.add_argument("--store", choices=("shared", "sensitive"), required=True)
        if name in ("publish", "restore"):
            sub.add_argument("--config", type=Path, required=True)
        if name == "flush":
            sub.add_argument(
                "--timezone",
                default="America/New_York",
                help="seal the previous local calendar day; retry does not reseal",
            )
        if name in ("index", "export"):
            sub.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        memory = MemoryStore(args.state)
        if args.command == "snapshot-curated":
            from scripts.memory_legacy import snapshot

            result = snapshot(memory, args.directory)
        elif args.command == "restore-curated":
            from scripts.memory_legacy import recover

            result = recover(args.archive.read_bytes(), args.output)
        elif args.command == "capture-duct":
            from scripts.memory_capture import capture_duct

            result = capture_duct(
                memory,
                args.directory,
                args.store,
                args.agent,
                args.reason,
                args.related,
            )
            if args.config:
                from scripts.memory_annex import AnnexTransport

                transport = AnnexTransport(memory.root, args.config, args.store)
                item = result["artifact"]
                with memory.lock(args.store):
                    transport.setup()
                    result["receipt"] = transport.publish_artifact(
                        item,
                        (
                            memory.store_root(args.store) / "objects" / item["sha256"]
                        ).read_bytes(),
                    )
        elif args.command == "fetch-artifact":
            from scripts.memory_annex import AnnexTransport

            item = json.loads(args.reference.read_text())
            transport = AnnexTransport(memory.root, args.config, item["store"])
            transport.setup()
            atomic_bytes(args.output, transport.fetch_artifact(item))
            result = {"output": str(args.output), "sha256": item["sha256"]}
        elif args.command == "daily":
            from scripts.memory_annex import AnnexTransport
            from scripts.memory_legacy import snapshot

            result = {
                "curated": snapshot(memory, args.curated),
                "imported": import_feedback(memory, args.public, args.private),
                "stores": {},
            }
            today = datetime.now(ZoneInfo(args.timezone)).date()
            cutoff = (
                datetime.combine(today, time(), ZoneInfo(args.timezone))
                .astimezone(timezone.utc)
                .isoformat()
            )
            for store in ("shared", "sensitive"):
                memory.prepare(store, (today - timedelta(days=1)).isoformat(), cutoff)
                if memory.pending(store):
                    transport = AnnexTransport(memory.root, args.config, store)
                    transport.setup()
                    memory.publish(store, transport)
                result["stores"][store] = rebuild_index(
                    memory, store, memory.store_root(store) / "projection.sqlite"
                )
        elif args.command == "ingest":
            data = (
                sys.stdin.read() if args.input == "-" else Path(args.input).read_text()
            )
            result = memory.append(json.loads(data), args.agent)
        elif args.command == "import-feedback":
            result = import_feedback(memory, args.public, args.private)
        elif args.command == "flush":
            today = datetime.now(ZoneInfo(args.timezone)).date()
            cutoff = (
                datetime.combine(today, time(), ZoneInfo(args.timezone))
                .astimezone(timezone.utc)
                .isoformat()
            )
            batches = memory.prepare(
                args.store, (today - timedelta(days=1)).isoformat(), cutoff
            )
            result = {"store": args.store, "pending_batches": len(batches)}
        elif args.command in ("publish", "restore"):
            from scripts.memory_annex import AnnexTransport

            transport = AnnexTransport(memory.root, args.config, args.store)
            transport.setup()
            if args.command == "restore":
                result = restore(memory, args.store, transport)
            else:
                memory.publish(args.store, transport)
                result = memory.status(args.store)
        elif args.command == "status":
            result = memory.status(args.store)
        elif args.command == "index":
            result = rebuild_index(memory, args.store, args.output)
        else:
            raw = "".join(
                canonical(r) + "\n" for r in memory.records(args.store)
            ).encode()
            atomic_bytes(args.output, raw)
            result = {"store": args.store, "output": str(args.output)}
        print(json.dumps(result))
    except (
        OSError,
        tarfile.TarError,
        TypeError,
        ValueError,
        RuntimeError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ):
        parser.exit(
            1,
            "Memory operation failed; source data retained. Check configuration and validated inputs.\n",
        )


if __name__ == "__main__":
    main()
