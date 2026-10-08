"""Daily collection with observable progress and independent store outcomes."""

import sqlite3
import subprocess
import sys
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from scripts.memory import import_feedback, rebuild_index
from scripts.memory_annex import AnnexTransport
from scripts.memory_legacy import snapshot


def progress(message):
    print(message, file=sys.stderr, flush=True)


def collect_daily(memory, args):
    progress("daily: snapshot and feedback import")
    result = {
        "curated": snapshot(memory, args.curated),
        "imported": import_feedback(memory, args.public, args.private),
        "stores": {},
        "ok": True,
    }
    progress("daily: feedback import complete " + str(result["imported"]))
    today = datetime.now(ZoneInfo(args.timezone)).date()
    cutoff = (
        datetime.combine(today, time(), ZoneInfo(args.timezone))
        .astimezone(timezone.utc)
        .isoformat()
    )
    errors = (
        OSError,
        ValueError,
        RuntimeError,
        sqlite3.Error,
        subprocess.SubprocessError,
    )
    for store in ("shared", "sensitive"):
        state = {
            "ok": True,
            "errors": [],
            "published_batches": [],
            "withheld_batches": [],
        }
        result["stores"][store] = state
        phase = "prepare"
        before = {b["id"] for b in memory.pending(store)}
        try:
            progress(f"{store}: sealing eligible records")
            memory.prepare(store, (today - timedelta(days=1)).isoformat(), cutoff)
            before = {b["id"] for b in memory.pending(store)}
            phase = "publication"
            if before:
                progress(f"{store}: publishing {len(before)} pending batches")
                transport = None
                if memory.publishable_pending(store):
                    transport = AnnexTransport(memory.root, args.config, store)
                    transport.progress = progress
                    transport.setup()
                state.update(memory.publish(store, transport))
        except errors as error:
            # Never include raw exception text: remote diagnostics may be private.
            state["errors"].append({"phase": phase, "type": type(error).__name__})
            state["ok"] = False
            progress(
                f"{store}: {phase} failed ({type(error).__name__}); retaining source data"
            )
        state["pending_batches"] = [b["id"] for b in memory.pending(store)]
        state["published_batches"] = sorted(before - set(state["pending_batches"]))
        try:
            progress(f"{store}: rebuilding local projection")
            state.update(
                rebuild_index(
                    memory, store, memory.store_root(store) / "projection.sqlite"
                )
            )
        except errors as error:
            state["errors"].append(
                {"phase": "projection", "type": type(error).__name__}
            )
            state["ok"] = False
        result["ok"] = result["ok"] and state["ok"]
    progress("daily: complete" if result["ok"] else "daily: completed with errors")
    return result
