"""Publish synthetic evidence, restore it, and rebuild SQLite/qmd views."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.memory import restore
from scripts.memory_annex import AnnexTransport
from scripts.memory_capture import store_archive
from scripts.memory_store import MemoryStore, digest, envelope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, required=True, help="test-only transport configuration"
    )
    parser.add_argument(
        "--resume", action="store_true", help="retry the same staged batch IDs"
    )
    args = parser.parse_args()
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=args.resume, mode=0o700)
    writer = MemoryStore(root / "writer")
    now = datetime.now(timezone.utc)
    texts = {
        "quartzrecovery": "After a lost upload acknowledgement, retry the identical batch ID and bytes.",
        "amberbatch": "Aggregate once daily per store into 1000-record batches, with at most one remainder.",
        "cedarlogs": "All collected logs are annex artifacts fetched only on demand.",
    }
    ids = {}
    # Even a one-byte log uses exactly the same artifact mechanism.
    log = store_archive(writer, "shared", "synthetic-log.tar.gz", {"stdout.log": b"x"})
    existing = list(writer.records("shared"))
    if existing:
        for row in existing:
            ids[row["payload"]["text"].split("\n", 1)[0]] = row["id"]
        assert set(ids) == set(texts)
    else:
        for term, text in texts.items():
            ident = str(uuid.uuid4())
            ids[term] = ident
            row = envelope(
                {"text": term + "\n" + text, "synthetic": True},
                ident=ident,
                kind="evidence",
                occurred_at=now.isoformat(),
                store="shared",
                producer="replaceability-fixture",
                version="1",
                source_schema="fixture-v1",
            )
            row["external_artifacts"] = [log]
            writer.append(row, "replaceability-probe")
        writer.prepare(
            "shared", now.date().isoformat(), (now + timedelta(days=1)).isoformat()
        )
    transport = AnnexTransport(writer.root, args.config, "shared")
    transport.setup()
    writer.publish("shared", transport)
    reader = MemoryStore(root / "reader")
    remote = AnnexTransport(reader.root, args.config, "shared")
    remote.setup()
    restore(reader, "shared", remote)
    restored = {r["id"]: r for r in reader.records("shared") if r["id"] in ids.values()}
    assert len(restored) == 3
    assert (
        remote.git("annex", "contentlocation", log["annex_key"], check=False).returncode
        != 0
    )
    projection = root / ("projection-" + str(uuid.uuid4()))
    projection.mkdir()
    docs = projection / "docs"
    docs.mkdir()
    db = sqlite3.connect(projection / "search.sqlite")
    db.execute("CREATE VIRTUAL TABLE evidence USING fts5(id UNINDEXED,text)")
    source_hashes = {}
    for ident, row in restored.items():
        body = row["payload"]["text"]
        (docs / (ident + ".md")).write_text(body)
        source_hashes[ident] = digest(body.encode())
        db.execute("INSERT INTO evidence VALUES(?,?)", (ident, body))
    db.commit()
    env = {
        **os.environ,
        "INDEX_PATH": str(projection / "qmd.sqlite"),
        "QMD_CONFIG_DIR": str(projection / "qmd-config"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_CONFIG_HOME": str(root / "config"),
    }
    qmd = str(ROOT / "experiments/context-pilots/node_modules/.bin/qmd")
    outputs = []

    def run(*cmd):
        p = subprocess.run(
            cmd, env=env, text=True, capture_output=True, check=False, timeout=120
        )
        outputs.append(
            {
                "command": list(cmd),
                "exit": p.returncode,
                "stdout": p.stdout,
                "stderr": p.stderr,
            }
        )
        (root / "commands.json").write_text(json.dumps(outputs, indent=2) + "\n")
        if p.returncode:
            raise RuntimeError("retrieval command failed; see commands.json")
        return p.stdout

    run(qmd, "collection", "add", str(docs), "--name", "restored")
    comparisons = []
    for term, expected in [*ids.items(), ("missingvioletterm", None)]:
        sqlids = [
            r[0]
            for r in db.execute(
                "SELECT id FROM evidence WHERE evidence MATCH ?", (term,)
            )
        ]
        raw = run(qmd, "search", term, "--json", "-n", "5")
        hits = json.loads(raw)
        qmdids = [Path(h["file"]).stem for h in hits]
        assert set(sqlids) == set(qmdids) == ({expected} if expected else set())
        comparisons.append(
            {
                "query": term,
                "sqlite_ids": sqlids,
                "qmd_ids": qmdids,
                "source_sha256": source_hashes.get(expected),
            }
        )
    db.close()
    # Verify the tiny log remains lazy even after both indexes have been queried.
    assert (
        remote.git("annex", "contentlocation", log["annex_key"], check=False).returncode
        != 0
    )
    fetched = remote.fetch_artifact(log)
    assert digest(fetched) == log["sha256"]
    result = {
        "synthetic": True,
        "checks": comparisons,
        "lazy_logs_until_explicit_fetch": True,
        "insight": {
            "text": texts["quartzrecovery"],
            "evidence_id": ids["quartzrecovery"],
            "source_sha256": source_hashes[ids["quartzrecovery"]],
            "method": "deterministic quotation of restored evidence; no model synthesis",
        },
        "sqlite_version": sqlite3.sqlite_version,
        "qmd_version": run(qmd, "--version").strip(),
    }
    (root / "results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
