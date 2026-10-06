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
    for item in row.get("external_artifacts", []):
        if item["store"] != row["classification"]["store"]:
            raise ValueError("artifact classification mismatch")
        if item["annex_key"] != f"SHA256-s{item['size']}--{item['sha256']}":
            raise ValueError("artifact key mismatch")
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

    def publication_holds(self, store):
        """Read the local, fail-closed list of batches withheld from upload."""
        path = self.store_root(store) / "publication-holds.json"
        if path.is_symlink():
            raise ValueError("publication hold file must not be a symlink")
        try:
            document = json.loads(path.read_text())
        except FileNotFoundError:
            return set()
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("cannot read publication hold file") from exc
        if (
            not isinstance(document, dict)
            or set(document) != {"schema_version", "held_batch_ids"}
            or document["schema_version"] != 1
            or not isinstance(document["held_batch_ids"], list)
        ):
            raise ValueError("invalid publication hold file")
        held = document["held_batch_ids"]
        if any(not isinstance(ident, str) for ident in held):
            raise ValueError("invalid publication hold file")
        try:
            canonical_ids = [str(uuid.UUID(ident)) for ident in held]
        except ValueError as exc:
            raise ValueError("invalid publication hold file") from exc
        if canonical_ids != held or len(set(held)) != len(held):
            raise ValueError("invalid publication hold file")
        return set(held)

    def batch_supersessions(self, store):
        """Load append-only decisions that retire a batch from active views."""
        path = self.store_root(store) / "batch-supersessions.jsonl"
        if path.is_symlink():
            raise ValueError("batch supersession journal must not be a symlink")
        try:
            lines = path.read_text().splitlines()
        except FileNotFoundError:
            return {}
        except OSError as exc:
            raise ValueError("cannot read batch supersession journal") from exc
        resolutions = {}
        amendment_ids = set()
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError("invalid batch supersession journal") from exc
            schema = event.get("schema") if isinstance(event, dict) else None
            if schema == "memory-batch-supersession-amendment-v1":
                required = {
                    "schema",
                    "amendment_id",
                    "resolution_id",
                    "source_batch_id",
                    "added_replacement_batches",
                    "promoted_source_record_ids",
                    "evidence",
                    "reason",
                    "recorded_at",
                }
                try:
                    if set(event) != required:
                        raise ValueError
                    source_id = str(uuid.UUID(event["source_batch_id"]))
                    amendment_id = str(uuid.UUID(event["amendment_id"]))
                    if amendment_id != event["amendment_id"]:
                        raise ValueError
                    base = resolutions.get(source_id)
                    if (
                        not base
                        or event["resolution_id"] != base["resolution_id"]
                        or amendment_id in amendment_ids
                    ):
                        raise ValueError
                    promoted = event["promoted_source_record_ids"]
                    if not isinstance(promoted, list) or not promoted:
                        raise ValueError
                    if promoted != sorted(set(promoted)):
                        raise ValueError
                    for ident in promoted:
                        if str(uuid.UUID(ident)) != ident:
                            raise ValueError
                    local_only = set(base["retained_local_only_source_record_ids"])
                    if not set(promoted) <= local_only:
                        raise ValueError
                    added = event["added_replacement_batches"]
                    if not isinstance(added, list) or not added:
                        raise ValueError
                    existing_ids = {
                        replacement["id"] for replacement in base["replacement_batches"]
                    }
                    for prior_event in lines:
                        if prior_event == line:
                            break
                        try:
                            prior = json.loads(prior_event)
                        except json.JSONDecodeError:
                            continue
                        if (
                            prior.get("schema")
                            == "memory-batch-supersession-amendment-v1"
                            and prior.get("source_batch_id") == source_id
                        ):
                            existing_ids.update(
                                item["id"]
                                for item in prior["added_replacement_batches"]
                            )
                    for replacement in added:
                        if set(replacement) != {
                            "id",
                            "store",
                            "sha256",
                            "ref",
                            "commit",
                            "record_count",
                            "artifact_keys",
                        }:
                            raise ValueError
                        rid = str(uuid.UUID(replacement["id"]))
                        if (
                            rid != replacement["id"]
                            or rid in existing_ids
                            or replacement["store"] not in STORES
                            or replacement["ref"] != "refs/workshop/memory/v2/" + rid
                            or len(replacement["sha256"]) != 64
                            or any(
                                ch not in "0123456789abcdef"
                                for ch in replacement["sha256"]
                            )
                            or not isinstance(replacement["commit"], str)
                            or len(replacement["commit"]) != 40
                            or not isinstance(replacement["record_count"], int)
                            or replacement["record_count"] < 1
                            or not isinstance(replacement["artifact_keys"], int)
                            or replacement["artifact_keys"] < 0
                        ):
                            raise ValueError
                        existing_ids.add(rid)
                    evidence = event["evidence"]
                    if (
                        not isinstance(evidence, dict)
                        or not evidence
                        or any(
                            not isinstance(k, str)
                            or not k
                            or not isinstance(v, str)
                            or len(v) != 64
                            or any(ch not in "0123456789abcdef" for ch in v)
                            for k, v in evidence.items()
                        )
                    ):
                        raise ValueError
                    if (
                        not isinstance(event["reason"], str)
                        or not event["reason"].strip()
                    ):
                        raise ValueError
                    datetime.fromisoformat(event["recorded_at"])
                except (KeyError, TypeError, ValueError) as exc:
                    raise ValueError("invalid batch supersession amendment") from exc
                if canonical(event) != line:
                    raise ValueError("noncanonical batch supersession amendment")
                base["replacement_batches"].extend(added)
                base["retained_local_only_source_record_ids"] = sorted(
                    local_only - set(promoted)
                )
                amendment_ids.add(amendment_id)
                continue

            required = {
                "schema",
                "resolution_id",
                "source_batch_id",
                "source_batch_sha256",
                "source_record_ids_sha256",
                "source_record_count",
                "replacement_batches",
                "retained_local_only_source_record_ids",
                "evidence",
                "reason",
                "recorded_at",
            }
            try:
                if (
                    set(event) != required
                    or event["schema"] != "memory-batch-supersession-v1"
                ):
                    raise ValueError
                source_id = str(uuid.UUID(event["source_batch_id"]))
                if source_id != event["source_batch_id"]:
                    raise ValueError
                if event["resolution_id"] != str(
                    uuid.uuid5(uuid.UUID(source_id), "memory-batch-supersession-v1")
                ):
                    raise ValueError
                if any(
                    not isinstance(event[field], str)
                    or len(event[field]) != 64
                    or any(ch not in "0123456789abcdef" for ch in event[field])
                    for field in ("source_batch_sha256", "source_record_ids_sha256")
                ):
                    raise ValueError
                if (
                    not isinstance(event["source_record_count"], int)
                    or event["source_record_count"] < 1
                ):
                    raise ValueError
                if (
                    not isinstance(event["replacement_batches"], list)
                    or not event["replacement_batches"]
                ):
                    raise ValueError
                replacement_ids = []
                for replacement in event["replacement_batches"]:
                    if set(replacement) != {
                        "id",
                        "store",
                        "sha256",
                        "ref",
                        "commit",
                        "record_count",
                        "artifact_keys",
                    }:
                        raise ValueError
                    rid = str(uuid.UUID(replacement["id"]))
                    if rid != replacement["id"] or replacement["store"] not in STORES:
                        raise ValueError
                    if replacement["ref"] != "refs/workshop/memory/v2/" + rid:
                        raise ValueError
                    for field in ("sha256",):
                        if len(replacement[field]) != 64 or any(
                            ch not in "0123456789abcdef" for ch in replacement[field]
                        ):
                            raise ValueError
                    if (
                        not isinstance(replacement["commit"], str)
                        or len(replacement["commit"]) != 40
                    ):
                        raise ValueError
                    if (
                        not isinstance(replacement["record_count"], int)
                        or replacement["record_count"] < 1
                    ):
                        raise ValueError
                    if (
                        not isinstance(replacement["artifact_keys"], int)
                        or replacement["artifact_keys"] < 0
                    ):
                        raise ValueError
                    replacement_ids.append(rid)
                if (
                    len(set(replacement_ids)) != len(replacement_ids)
                    or source_id in replacement_ids
                ):
                    raise ValueError
                local_only = event["retained_local_only_source_record_ids"]
                if not isinstance(local_only, list) or len(local_only) != len(
                    set(local_only)
                ):
                    raise ValueError
                for ident in local_only:
                    if str(uuid.UUID(ident)) != ident:
                        raise ValueError
                if not isinstance(event["evidence"], dict) or not event["evidence"]:
                    raise ValueError
                if any(
                    not isinstance(key, str)
                    or not key
                    or not isinstance(value, str)
                    or len(value) != 64
                    or any(ch not in "0123456789abcdef" for ch in value)
                    for key, value in event["evidence"].items()
                ):
                    raise ValueError
                if not isinstance(event["reason"], str) or not event["reason"].strip():
                    raise ValueError
                datetime.fromisoformat(event["recorded_at"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("invalid batch supersession journal") from exc
            if source_id in resolutions or canonical(event) != line:
                raise ValueError("duplicate or noncanonical batch supersession event")
            resolutions[source_id] = event
        return resolutions

    def append_batch_supersession(
        self,
        store,
        source_batch_id,
        replacement_batches,
        retained_local_only_source_record_ids,
        evidence,
        reason,
    ):
        """Append a verified resolution while retaining the immutable source batch."""
        source_batch_id = str(uuid.UUID(source_batch_id))
        path = self.store_root(store) / "batch-supersessions.jsonl"
        if path.is_symlink():
            raise ValueError("batch supersession journal must not be a symlink")
        with self.lock(store), self.ledger(store) as db:
            existing = self.batch_supersessions(store)
            if source_batch_id in existing:
                raise ValueError("source batch already has an append-only supersession")
            source = db.execute(
                "SELECT body,state,receipt FROM batches WHERE id=?", (source_batch_id,)
            ).fetchone()
            if not source or source[1] != "pending" or source[2] is not None:
                raise ValueError("source batch must be pending without a receipt")
            if source_batch_id not in self.publication_holds(store):
                raise ValueError("source batch must remain held during supersession")
            source_batch = json.loads(source[0])
            source_raw = (source[0] + "\n").encode()
            source_ids = {row["id"] for row in source_batch["records"]}
            source_ids_by_replacement = {}
            verified_replacements = []
            for target in replacement_batches:
                target_store = target["store"]
                state_root = Path(target["state_path"]).expanduser().resolve()
                replacement_id = str(uuid.UUID(target["id"]))
                replacement_path = state_root / target_store / "ledger.sqlite"
                if (
                    target_store not in STORES
                    or replacement_id == source_batch_id
                    or not replacement_path.is_file()
                ):
                    raise ValueError(
                        "replacement batch must identify a distinct published batch"
                    )
                replacement_db = sqlite3.connect(
                    f"file:{replacement_path}?mode=ro",
                    uri=True,
                    factory=ClosingConnection,
                )
                try:
                    found = replacement_db.execute(
                        "SELECT body,state,receipt FROM batches WHERE id=?",
                        (replacement_id,),
                    ).fetchone()
                finally:
                    replacement_db.close()
                if not found or found[1] != "published" or not found[2]:
                    raise ValueError("replacement batch is not durably published")
                batch = json.loads(found[0])
                receipt = json.loads(found[2])
                raw = (found[0] + "\n").encode()
                sha = digest(raw)
                ref = "refs/workshop/memory/v2/" + replacement_id
                if (
                    batch.get("id") != replacement_id
                    or batch.get("store") != target_store
                    or receipt.get("sha256") != sha
                    or receipt.get("ref") != ref
                    or not isinstance(receipt.get("commit"), str)
                    or len(receipt["commit"]) != 40
                ):
                    raise ValueError("replacement receipt does not match its batch")
                record_rows = batch.get("records", [])
                for row in record_rows:
                    validate(row)
                    if row["classification"]["store"] != target_store:
                        raise ValueError("replacement record/store mismatch")
                    mapped = set()
                    ancillary_decision = False
                    if row["id"] in source_ids:
                        mapped.add(row["id"])
                    for relation in row.get("relations", []):
                        if (
                            relation.get("relation") == "reclassified-from"
                            and relation.get("id") in source_ids
                        ):
                            mapped.add(relation["id"])
                        elif (
                            relation.get("relation") == "routes-shareable-subset-of"
                            and relation.get("id") == source_batch_id
                            and row["kind"] == "decision"
                            and row.get("payload", {}).get("measurement_contribution")
                            is False
                        ) or (
                            relation.get("relation") == "corrects-classification-of"
                            and relation.get("id") in source_ids
                            and row["kind"] == "decision"
                            and row.get("payload", {}).get("measurement_scope")
                            == "none; classification-only"
                        ):
                            ancillary_decision = True
                    if len(mapped) > 1:
                        raise ValueError("replacement ambiguously maps source records")
                    if mapped:
                        source_id = mapped.pop()
                        if source_id in source_ids_by_replacement:
                            raise ValueError(
                                "source record is represented more than once"
                            )
                        source_ids_by_replacement[source_id] = replacement_id
                    elif row["id"] not in source_ids and not ancillary_decision:
                        raise ValueError(
                            "replacement record is not linked to the source decision"
                        )
                artifact_keys = {
                    item["sha256"]
                    for row in record_rows
                    for item in row.get("external_artifacts", [])
                }
                verified_replacements.append(
                    {
                        "id": replacement_id,
                        "store": target_store,
                        "sha256": sha,
                        "ref": ref,
                        "commit": receipt["commit"],
                        "record_count": len(record_rows),
                        "artifact_keys": len(artifact_keys),
                    }
                )
            local_only = sorted(set(retained_local_only_source_record_ids))
            if any(str(uuid.UUID(ident)) != ident for ident in local_only):
                raise ValueError("invalid local-only source record ID")
            if set(source_ids_by_replacement) | set(local_only) != source_ids:
                raise ValueError(
                    "supersession does not account for every source record"
                )
            if set(source_ids_by_replacement) & set(local_only):
                raise ValueError("source record is both replaced and retained locally")
            if (
                not isinstance(evidence, dict)
                or not evidence
                or any(
                    not isinstance(key, str)
                    or not key
                    or not isinstance(value, str)
                    or len(value) != 64
                    or any(ch not in "0123456789abcdef" for ch in value)
                    for key, value in evidence.items()
                )
            ):
                raise ValueError("supersession evidence is required")
            if not isinstance(reason, str) or not reason.strip():
                raise ValueError("supersession reason is required")
            event = {
                "schema": "memory-batch-supersession-v1",
                "resolution_id": str(
                    uuid.uuid5(
                        uuid.UUID(source_batch_id), "memory-batch-supersession-v1"
                    )
                ),
                "source_batch_id": source_batch_id,
                "source_batch_sha256": digest(source_raw),
                "source_record_ids_sha256": digest(
                    canonical(sorted(source_ids)).encode()
                ),
                "source_record_count": len(source_ids),
                "replacement_batches": verified_replacements,
                "retained_local_only_source_record_ids": local_only,
                "evidence": evidence,
                "reason": reason.strip(),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            raw_event = (canonical(event) + "\n").encode()
            descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                if os.write(descriptor, raw_event) != len(raw_event):
                    raise OSError("short append to supersession journal")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return event

    def append_batch_supersession_amendment(
        self,
        store,
        source_batch_id,
        replacement_batches,
        promoted_source_record_ids,
        evidence,
        reason,
    ):
        """Append a lineage amendment for previously local-only source records."""
        source_batch_id = str(uuid.UUID(source_batch_id))
        promoted = sorted(set(promoted_source_record_ids))
        if not promoted or any(str(uuid.UUID(ident)) != ident for ident in promoted):
            raise ValueError("amendment must identify canonical source record IDs")
        if (
            not isinstance(evidence, dict)
            or not evidence
            or any(
                not isinstance(key, str)
                or not key
                or not isinstance(value, str)
                or len(value) != 64
                or any(ch not in "0123456789abcdef" for ch in value)
                for key, value in evidence.items()
            )
        ):
            raise ValueError("amendment evidence is required")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("amendment reason is required")
        if not replacement_batches:
            raise ValueError("amendment requires a published replacement batch")
        path = self.store_root(store) / "batch-supersessions.jsonl"
        if path.is_symlink():
            raise ValueError("batch supersession journal must not be a symlink")
        with self.lock(store), self.ledger(store) as db:
            resolutions = self.batch_supersessions(store)
            base = resolutions.get(source_batch_id)
            if not base:
                raise ValueError("source batch has no supersession to amend")
            if not set(promoted) <= set(base["retained_local_only_source_record_ids"]):
                raise ValueError("amendment must promote only local-only records")
            source = db.execute(
                "SELECT body,state,receipt FROM batches WHERE id=?", (source_batch_id,)
            ).fetchone()
            if not source or source[1] != "pending" or source[2] is not None:
                raise ValueError("historical source batch integrity changed")
            source_batch = json.loads(source[0])
            source_raw = (source[0] + "\n").encode()
            source_rows = {row["id"]: row for row in source_batch["records"]}
            if digest(source_raw) != base["source_batch_sha256"] or not set(
                promoted
            ) <= set(source_rows):
                raise ValueError("amendment source lineage does not match")

            known_replacement_ids = {item["id"] for item in base["replacement_batches"]}
            if len(replacement_batches) != 1:
                raise ValueError("one replacement batch is required per amendment")
            for target in replacement_batches:
                target_store = target["store"]
                if target_store not in STORES:
                    raise ValueError("unknown amendment replacement store")
                replacement_id = str(uuid.UUID(target["id"]))
                replacement_db_path = (
                    Path(target["state_path"]).expanduser().resolve()
                    / target_store
                    / "ledger.sqlite"
                )
                if (
                    target_store not in STORES
                    or replacement_id in known_replacement_ids
                    or not replacement_db_path.is_file()
                ):
                    raise ValueError("amendment replacement must be a new batch")
                with sqlite3.connect(
                    f"file:{replacement_db_path}?mode=ro", uri=True
                ) as replacement_db:
                    found = replacement_db.execute(
                        "SELECT body,state,receipt FROM batches WHERE id=?",
                        (replacement_id,),
                    ).fetchone()
                if not found or found[1] != "published" or not found[2]:
                    raise ValueError("amendment replacement is not durably published")
                body, _, receipt_raw = found
                batch = json.loads(body)
                receipt = json.loads(receipt_raw)
                batch_sha = digest((body + "\n").encode())
                expected_ref = "refs/workshop/memory/v2/" + replacement_id
                if (
                    batch.get("id") != replacement_id
                    or batch.get("store") != target_store
                    or receipt.get("sha256") != batch_sha
                    or receipt.get("ref") != expected_ref
                    or not isinstance(receipt.get("commit"), str)
                    or len(receipt["commit"]) != 40
                ):
                    raise ValueError("amendment replacement receipt mismatch")
                seen = set()
                for row in batch["records"]:
                    validate(row)
                    if row["classification"]["store"] != target_store:
                        raise ValueError("amendment replacement store mismatch")
                    links = [
                        relation["id"]
                        for relation in row.get("relations", [])
                        if relation.get("relation") == "reclassified-from"
                        and relation.get("id") in promoted
                    ]
                    if row["id"] in promoted:
                        links.append(row["id"])
                    if len(set(links)) != 1 or links[0] in seen:
                        raise ValueError(
                            "amendment replacement does not map promoted source exactly once"
                        )
                    seen.add(links[0])
                if seen != set(promoted):
                    raise ValueError("amendment replacement omits promoted source")
                keys = {
                    item["sha256"]
                    for row in batch["records"]
                    for item in row.get("external_artifacts", [])
                }
                base["replacement_batches"].append(
                    {
                        "id": replacement_id,
                        "store": target_store,
                        "sha256": batch_sha,
                        "ref": expected_ref,
                        "commit": receipt["commit"],
                        "record_count": len(batch["records"]),
                        "artifact_keys": len(keys),
                    }
                )
                known_replacement_ids.add(replacement_id)
            amendment_id = str(uuid.uuid4())
            event = {
                "schema": "memory-batch-supersession-amendment-v1",
                "amendment_id": amendment_id,
                "resolution_id": base["resolution_id"],
                "source_batch_id": source_batch_id,
                "added_replacement_batches": base["replacement_batches"][
                    -len(replacement_batches) :
                ],
                "promoted_source_record_ids": promoted,
                "evidence": evidence,
                "reason": reason.strip(),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            }
            raw_event = (canonical(event) + "\n").encode()
            descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                if os.write(descriptor, raw_event) != len(raw_event):
                    raise OSError("short append to supersession amendment journal")
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            return event

    def publishable_pending(self, store):
        held = self.publication_holds(store)
        return [batch for batch in self.pending(store) if batch["id"] not in held]

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
            historical = set(self.batch_supersessions(store))
            return [
                {"id": ident, "body": body, "state": state}
                for ident, body, state in db.execute(
                    "SELECT id,body,state FROM batches WHERE state!='published' ORDER BY day,id"
                )
                if ident not in historical
            ]
        finally:
            if owned:
                db.close()

    def _artifact_stream(self, store, records):
        for row in records:
            for item in row.get("external_artifacts", []):
                content = (
                    self.store_root(store) / "objects" / item["sha256"]
                ).read_bytes()
                if digest(content) != item["sha256"] or len(content) != item["size"]:
                    raise ValueError("external artifact content mismatch")
                yield item, content

    def publish(self, store, transport):
        # Keep staging and all outbox payloads, even after successful publication.
        with self.lock(store), self.ledger(store) as db:
            held = self.publication_holds(store)
            published_batches = []
            withheld_batches = []
            for batch in self.pending(store, db):
                if batch["id"] in held:
                    withheld_batches.append(batch["id"])
                    continue
                raw = (batch["body"] + "\n").encode()
                records = json.loads(batch["body"])["records"]
                artifacts = self._artifact_stream(store, records)

                publish_batch = getattr(transport, "publish_batch_with_artifacts", None)
                if publish_batch:
                    receipt = publish_batch(batch["id"], raw, artifacts)
                else:
                    for item, content in artifacts:
                        transport.publish_artifact(item, content)
                    receipt = transport(batch["id"], raw)
                if receipt.get("sha256") != digest(raw):
                    raise ValueError("transport receipt digest mismatch")
                db.execute(
                    "UPDATE batches SET state='published',receipt=? WHERE id=?",
                    (canonical(receipt), batch["id"]),
                )
                db.commit()
                published_batches.append(batch["id"])
            return {
                "published_batches": published_batches,
                "withheld_batches": withheld_batches,
            }

    def records(self, store):
        historical = set(self.batch_supersessions(store))
        with self.ledger(store) as db:
            for ident, body in db.execute(
                "SELECT id,body FROM batches ORDER BY day,id"
            ):
                if ident in historical:
                    continue
                for row in json.loads(body)["records"]:
                    yield validate(row)

    def status(self, store):
        with self.ledger(store) as db:
            historical = self.batch_supersessions(store)
            pending = {
                ident
                for (ident,) in db.execute(
                    "SELECT id FROM batches WHERE state!='published'"
                )
            }
            counts = dict(
                db.execute("SELECT state,count(*) FROM batches GROUP BY state")
            )
            historical_pending = sum(
                1
                for ident in historical
                if db.execute(
                    "SELECT 1 FROM batches WHERE id=? AND state!='published'", (ident,)
                ).fetchone()
            )
            if historical_pending:
                counts["pending"] = counts.get("pending", 0) - historical_pending
                if not counts["pending"]:
                    del counts["pending"]
            active_records = 0
            for ident, body in db.execute("SELECT id,body FROM batches"):
                if ident not in historical:
                    active_records += len(json.loads(body)["records"])
            return {
                "store": store,
                "records_sealed": db.execute("SELECT count(*) FROM records").fetchone()[
                    0
                ],
                "records_active": active_records,
                "batches": counts,
                "historical_batches": sorted(historical),
                "withheld_batches": sorted(
                    self.publication_holds(store) & pending - set(historical)
                ),
            }
