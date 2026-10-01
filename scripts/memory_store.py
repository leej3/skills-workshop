"""Durable per-agent evidence journals and a recoverable daily batch outbox.

Only a designated aggregator on one host should publish a given store.
SQLite journals are staging, not the interchange format: batches contain full
versioned JSON envelopes and embedded original artifact bytes.
"""

import base64
import fcntl
import hashlib
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "schemas/memory-envelope-v1.schema.json").read_text())
VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FormatChecker())
STORES = ("shared", "sensitive")
BATCH_SIZE = 1000


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(row):
    if list(VALIDATOR.iter_errors(row)):
        raise ValueError("invalid memory envelope (values suppressed)")
    if (
        row["classification"]["store"] == "shared"
        and row["classification"]["reason"] is not None
    ):
        raise ValueError("classification reasons belong only in sensitive records")
    if (
        row["classification"]["store"] == "sensitive"
        and not row["classification"]["reason"]
    ):
        raise ValueError("sensitive records require a classification reason")
    canonical(row)
    names = set()
    for item in row["artifacts"]:
        raw = base64.b64decode(item["bytes_base64"], validate=True)
        if digest(raw) != item["sha256"] or item["name"] in names:
            raise ValueError("artifact digest mismatch or duplicate name")
        names.add(item["name"])
    return row


def artifact(name, data, media_type="application/octet-stream"):
    return {
        "name": name,
        "media_type": media_type,
        "sha256": digest(data),
        "bytes_base64": base64.b64encode(data).decode("ascii"),
    }


def envelope(
    payload,
    *,
    ident,
    kind,
    occurred_at,
    store,
    producer,
    source_schema,
    version=None,
    reason=None,
    context=None,
    artifacts=None,
    relations=None,
):
    ctx = {
        "task_id": None,
        "agent_id": None,
        "runtime": None,
        "model": None,
        "skill": None,
        "conditions": {},
        "missing": [],
    }
    ctx.update(context or {})
    ctx["missing"] = sorted(
        set(ctx["missing"])
        | {
            key
            for key in ("task_id", "agent_id", "runtime", "model", "skill")
            if ctx[key] is None
        }
    )
    return validate(
        {
            "schema_version": 1,
            "id": ident,
            "kind": kind,
            "occurred_at": occurred_at,
            "classification": {
                "store": store,
                "policy": "whole-record-v1",
                "reason": reason,
            },
            "source": {
                "producer": producer,
                "version": version,
                "schema": source_schema,
            },
            "context": ctx,
            "payload": payload,
            "artifacts": artifacts or [],
            "relations": relations or [],
        }
    )


def atomic_bytes(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = path.with_name(path.name + "." + str(uuid.uuid4()) + ".tmp")
    try:
        with tmp.open("xb") as stream:
            os.chmod(tmp, 0o600)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        tmp.unlink(missing_ok=True)


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect(path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    db = sqlite3.connect(path, timeout=30, factory=ClosingConnection)
    os.chmod(path, 0o600)
    db.execute("PRAGMA synchronous=FULL")
    return db


class MemoryStore:
    def __init__(self, root):
        self.root = Path(root).expanduser().resolve()
        if any((p / ".git").exists() for p in (self.root, *self.root.parents)):
            raise ValueError("memory state must be outside a Git checkout")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)

    def store_root(self, store):
        if store not in STORES:
            raise ValueError("unknown store")
        path = self.root / store
        path.mkdir(exist_ok=True, mode=0o700)
        return path

    @contextmanager
    def lock(self, store):
        with (self.store_root(store) / "aggregate.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            yield

    def append(self, row, agent):
        validate(row)
        # Hash the label: neither path traversal nor agent naming collisions.
        path = (
            self.store_root(row["classification"]["store"])
            / "agents"
            / (digest(agent.encode()) + ".sqlite")
        )
        body = canonical(row)
        self.reserve(row)
        with connect(path) as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, body TEXT NOT NULL, received_at TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)"
            )
            db.execute("INSERT OR IGNORE INTO metadata VALUES('agent',?)", (agent,))
            existing = db.execute(
                "SELECT body FROM records WHERE id=?", (row["id"],)
            ).fetchone()
            if existing and existing[0] != body:
                raise ValueError("record ID conflicts with existing content")
            if not existing:
                db.execute(
                    "INSERT INTO records VALUES(?,?,?)",
                    (row["id"], body, datetime.now(timezone.utc).isoformat()),
                )
        db.close()
        return {
            "id": row["id"],
            "store": row["classification"]["store"],
            "duplicate": bool(existing),
        }

    def reserve(self, row):
        """Reserve immutable identity for ingestion or recovery; safe to retry."""
        body = canonical(row)
        # Reject silent reclassification or changed content even across agents.
        # A retry after registry reservation but before journaling is safe.
        with connect(self.root / "identities.sqlite") as identities:
            identities.execute(
                "CREATE TABLE IF NOT EXISTS identities(id TEXT PRIMARY KEY, store TEXT, digest TEXT)"
            )
            identities.execute("BEGIN IMMEDIATE")
            prior = identities.execute(
                "SELECT store,digest FROM identities WHERE id=?", (row["id"],)
            ).fetchone()
            identity = (row["classification"]["store"], digest(body.encode()))
            if prior and prior != identity:
                raise ValueError(
                    "record identity conflicts with earlier content or classification"
                )
            identities.execute(
                "INSERT OR IGNORE INTO identities VALUES(?,?,?)", (row["id"], *identity)
            )
        identities.close()

    def ledger(self, store):
        db = connect(self.store_root(store) / "ledger.sqlite")
        db.executescript("""
          CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, digest TEXT NOT NULL, batch_id TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS batches(id TEXT PRIMARY KEY, day TEXT NOT NULL, body TEXT NOT NULL, state TEXT NOT NULL, receipt TEXT);
          CREATE TABLE IF NOT EXISTS days(day TEXT PRIMARY KEY);
        """)
        return db

    def prepare(self, store, day, cutoff):
        """Seal at most once for a day; late arrivals wait until the next day.

        The receive-time cutoff avoids retroactively including late imports in
        already sealed days. Source timestamps remain unchanged in envelopes.
        """
        date.fromisoformat(day)
        boundary = datetime.fromisoformat(cutoff)
        if boundary.tzinfo is None:
            raise ValueError("cutoff must include a timezone")
        with self.lock(store), self.ledger(store) as db:
            if db.execute("SELECT 1 FROM days WHERE day=?", (day,)).fetchone():
                return self.pending(store, db)
            candidates = {}
            deliveries = {}
            for path in sorted((self.store_root(store) / "agents").glob("*.sqlite")):
                with sqlite3.connect(
                    f"file:{path}?mode=ro", uri=True, factory=ClosingConnection
                ) as source:
                    agent_row = (
                        source.execute(
                            "SELECT value FROM metadata WHERE key='agent'"
                        ).fetchone()
                        if source.execute(
                            "SELECT 1 FROM sqlite_master WHERE name='metadata'"
                        ).fetchone()
                        else None
                    )
                    agent_label = agent_row[0] if agent_row else None
                    for ident, body, received in source.execute(
                        "SELECT id,body,received_at FROM records ORDER BY received_at,id"
                    ):
                        if datetime.fromisoformat(received) >= boundary:
                            continue
                        row = validate(json.loads(body))
                        if (
                            row["classification"]["store"] != store
                            or row["id"] != ident
                        ):
                            raise ValueError("journal routing/identity mismatch")
                        sha = digest(body.encode())
                        existing = db.execute(
                            "SELECT digest FROM records WHERE id=?", (ident,)
                        ).fetchone()
                        if existing:
                            if existing[0] != sha:
                                raise ValueError(
                                    "record ID conflicts with sealed history"
                                )
                            continue
                        if ident in candidates and candidates[ident][0] != body:
                            raise ValueError("record ID conflicts across agents")
                        deliveries.setdefault(ident, []).append(
                            {"received_at": received, "agent": agent_label}
                        )
                        if ident not in candidates or received < candidates[ident][1]:
                            candidates[ident] = (body, received)
            ordered = sorted(
                candidates, key=lambda ident: (candidates[ident][1], ident)
            )
            for offset in range(0, len(ordered), BATCH_SIZE):
                ids = ordered[offset : offset + BATCH_SIZE]
                batch_id = str(uuid.uuid4())
                body = canonical(
                    {
                        "schema_version": 1,
                        "id": batch_id,
                        "store": store,
                        "day": day,
                        "collection": {i: deliveries[i] for i in ids},
                        "schemas": {
                            "envelope-v1": SCHEMA,
                            "observation-v2": json.loads(
                                (
                                    ROOT
                                    / "controls/skills/workshop-feedback/schemas/observation-v2.schema.json"
                                ).read_text()
                            ),
                        },
                        "records": [json.loads(candidates[i][0]) for i in ids],
                    }
                )
                db.execute(
                    "INSERT INTO batches VALUES(?,?,?,'pending',NULL)",
                    (batch_id, day, body),
                )
                db.executemany(
                    "INSERT INTO records VALUES(?,?,?)",
                    [(i, digest(candidates[i][0].encode()), batch_id) for i in ids],
                )
            db.execute("INSERT INTO days VALUES(?)", (day,))
            db.commit()
            return self.pending(store, db)

    def pending(self, store, db=None):
        owned = db is None
        db = db or self.ledger(store)
        try:
            return [
                {"id": ident, "body": body, "state": state}
                for ident, body, state in db.execute(
                    "SELECT id,body,state FROM batches WHERE state!='published' ORDER BY day,id"
                )
            ]
        finally:
            if owned:
                db.close()

    def publish(self, store, transport):
        # Keep staging and all outbox payloads, even after successful publication.
        with self.lock(store), self.ledger(store) as db:
            for batch in self.pending(store, db):
                raw = (batch["body"] + "\n").encode()
                receipt = transport(batch["id"], raw)
                if receipt.get("sha256") != digest(raw):
                    raise ValueError("transport receipt digest mismatch")
                db.execute(
                    "UPDATE batches SET state='published',receipt=? WHERE id=?",
                    (canonical(receipt), batch["id"]),
                )
                db.commit()

    def records(self, store):
        with self.ledger(store) as db:
            for (body,) in db.execute("SELECT body FROM batches ORDER BY day,id"):
                for row in json.loads(body)["records"]:
                    yield validate(row)

    def status(self, store):
        with self.ledger(store) as db:
            return {
                "store": store,
                "records_sealed": db.execute("SELECT count(*) FROM records").fetchone()[
                    0
                ],
                "batches": dict(
                    db.execute("SELECT state,count(*) FROM batches GROUP BY state")
                ),
            }
