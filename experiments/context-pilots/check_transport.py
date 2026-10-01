"""Opt-in live annex roundtrip; writes a synthetic immutable ref to a test store."""

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.memory import restore
from scripts.memory_annex import AnnexTransport
from scripts.memory_store import MemoryStore, envelope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="test-only config, shared entry points to a private test repository",
    )
    parser.add_argument(
        "--workspace", type=Path, required=True, help="new directory outside Git"
    )
    args = parser.parse_args()
    args.workspace.mkdir(parents=True, exist_ok=False, mode=0o700)
    now = datetime.now(timezone.utc)
    writer = MemoryStore(args.workspace / "writer")
    row = envelope(
        {"synthetic": True},
        ident=str(uuid.uuid4()),
        kind="evidence",
        occurred_at=now.isoformat(),
        store="shared",
        producer="transport-roundtrip",
        version="1",
        source_schema="fixture-v1",
    )
    writer.append(row, "roundtrip")
    writer.prepare(
        "shared", now.date().isoformat(), (now + timedelta(days=1)).isoformat()
    )
    transport = AnnexTransport(writer.root, args.config, "shared")
    transport.setup()
    writer.publish("shared", transport)
    reader = MemoryStore(args.workspace / "reader")
    remote = AnnexTransport(reader.root, args.config, "shared")
    remote.setup()
    restore(reader, "shared", remote)
    assert row in list(reader.records("shared"))
    assert not writer.pending("shared")
    print(json.dumps({"exact_roundtrip": True, "record": row["id"]}))


if __name__ == "__main__":
    main()
