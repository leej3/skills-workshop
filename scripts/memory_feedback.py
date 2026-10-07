"""Capture and recover one skill assessment with exact conversation and run bytes."""

import io
import json
import os
import sqlite3
import tarfile
import uuid
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from scripts.memory_capture import safe_name, store_archive
from scripts.memory_store import (
    ROOT,
    atomic_bytes,
    canonical,
    digest,
    envelope,
    validate,
)

SCHEMAS = ROOT / "controls/skills/workshop-feedback/schemas"


def validate_input(value, name):
    schema = json.loads((SCHEMAS / name).read_text())
    if list(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(value)
    ):
        raise ValueError("invalid capture input (values suppressed)")
    canonical(value)


def snapshot(path):
    """Read through the current file size; later appends belong to a later capture."""
    path = Path(path).expanduser()
    if path.is_symlink() or not path.is_file():
        raise ValueError("capture input must be a regular file")
    with path.open("rb") as stream:
        size = os.fstat(stream.fileno()).st_size
        data = stream.read(size)
        if len(data) != size:
            raise ValueError("capture input shrank during snapshot")
    return data


def capture_feedback(memory, observation, request_path, store, agent, reason=None):
    raw = snapshot(observation)
    report = json.loads(raw)
    validate_input(report, "observation-v2.schema.json")
    if report["kind"] != "usage" or "assessment" not in report:
        raise ValueError("capture requires a usage observation with an assessment")
    request_raw = snapshot(request_path)
    request = json.loads(request_raw)
    version = request.get("schema_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("unsupported capture request version")
    request_schema = f"capture-request-v{version}.schema.json"
    validate_input(request, request_schema)
    reference = request.get("skill_reference")
    if reference and reference["skill"] != report["skill"]:
        raise ValueError("APM reference does not match assessed skill")
    if store == "shared" and (
        report.get("sensitivity") or report["visibility"] == "private"
    ):
        raise ValueError("private observations cannot enter a shared capture")
    if (store == "sensitive" and not reason) or (store == "shared" and reason):
        raise ValueError(
            "classification reason is required only for sensitive captures"
        )
    # Fixed identity and snapshot boundary per observation, including after upload failure.
    signature = digest(
        canonical(
            {"report": digest(raw), "request": request, "reason": reason}
        ).encode()
    )
    saved = memory.store_root(store) / "captures" / (report["id"] + ".json")
    with memory.lock(store):
        if saved.exists():
            receipt = json.loads(saved.read_text())
            if receipt["request_sha256"] != signature:
                raise ValueError("capture inputs changed; use a new observation ID")
            row = validate(receipt["record"])
        else:
            if request.get("skill_path"):
                raise ValueError("skill embedding retired; use a v2 APM reference")
            files = {
                "observation.json": raw,
                "capture-request.json": request_raw,
                "schemas/observation-v2.schema.json": (
                    SCHEMAS / "observation-v2.schema.json"
                ).read_bytes(),
                f"schemas/{request_schema}": (SCHEMAS / request_schema).read_bytes(),
            }
            base = Path(request_path).resolve().parent

            def source(value):
                path = Path(value).expanduser()
                return path if path.is_absolute() else base / path

            conversation = request["conversation"]
            data = snapshot(source(conversation["path"]))
            session_id = conversation.get("session_id")
            if conversation["format"] == "codex-jsonl":
                first = json.loads(data.splitlines()[0]) if data else {}
                actual = (
                    first.get("payload", {}).get("id")
                    if first.get("type") == "session_meta"
                    else None
                )
                if not actual or (session_id and actual != session_id):
                    raise ValueError(
                        "Codex transcript does not match its session identity"
                    )
                session_id = actual
            files["conversation/transcript"] = data
            runs = []
            for index, directory in enumerate(request["duct_runs"]):
                directory = source(directory)
                if directory.is_symlink() or not directory.is_dir():
                    raise ValueError("duct input must be a directory")
                entries = {p.name: snapshot(p) for p in sorted(directory.iterdir())}
                if not {"run_info.json", "context.json"} <= entries.keys():
                    raise ValueError("duct input lacks context or execution metadata")
                info = json.loads(entries["run_info.json"])
                context = json.loads(entries["context.json"])
                if (
                    session_id
                    and context.get("session_id")
                    and context["session_id"] != session_id
                ):
                    raise ValueError("duct run belongs to a different session")
                summary = info.get("execution_summary", {})
                if summary.get("end_time") is None or summary.get("exit_code") is None:
                    raise ValueError("duct run has not finished")
                prefix = f"duct/{index:04d}/"
                files.update({prefix + name: value for name, value in entries.items()})
                runs.append(
                    {
                        "path": prefix,
                        "run_id": directory.name,
                        "context": context,
                        "command": info.get("command"),
                        "execution_summary": summary,
                    }
                )
            manifest = {
                "schema_version": 1,
                "observation_id": report["id"],
                "conversation": {
                    "path": "conversation/transcript",
                    "format": conversation["format"],
                    "session_id": session_id,
                    "turn_id": conversation.get("turn_id"),
                    "scope": "whole supplied transcript through snapshot byte boundary",
                    "bytes": len(data),
                    "ends_with_newline": data.endswith(b"\n"),
                },
                "duct_runs": runs,
                "missing_evidence": request.get("missing_evidence", []),
                "files": [
                    {"path": name, "sha256": digest(value), "size": len(value)}
                    for name, value in sorted(files.items())
                ],
            }
            if reference:
                manifest["skill_reference"] = reference
            files["manifest.json"] = (canonical(manifest) + "\n").encode()
            item = store_archive(memory, store, "skill-use-capture.tar.gz", files)
            ident = str(
                uuid.uuid5(uuid.NAMESPACE_URL, "workshop:skill-use:" + report["id"])
            )
            row = envelope(
                {"observation": report, "manifest": manifest},
                ident=ident,
                kind="evidence",
                occurred_at=report["recorded_at"],
                store=store,
                producer="workshop-feedback-capture",
                source_schema="skill-use-capture-v1",
                reason=reason,
                context={
                    "agent_id": agent,
                    "task_id": report.get("context", {}).get("task_id"),
                    "skill": {
                        "name": report["skill"],
                        "entrypoint_digest": report["skill_digest"],
                    },
                    "model": {"id": report["model"]} if report.get("model") else None,
                    "conditions": {
                        "session_id": session_id,
                        "assessment": "agent-self-assessment",
                    },
                },
                relations=[{"relation": "supports", "id": report["id"]}],
            )
            row["external_artifacts"] = [item]
            validate(row)
            atomic_bytes(
                saved,
                (
                    canonical({"request_sha256": signature, "record": row}) + "\n"
                ).encode(),
            )
        result = memory.append(row, agent)
    return {
        **result,
        "observation_id": report["id"],
        "artifact": row["external_artifacts"][0],
        "record": str(saved),
        "snapshot_reused": result["duplicate"],
    }


def capture_records(memory, store):
    """Include journaled captures before the daily batch cutoff, without resealing."""
    rows = {
        r["id"]: r
        for r in memory.records(store)
        if r["source"]["producer"] == "workshop-feedback-capture"
    }
    for path in sorted((memory.store_root(store) / "agents").glob("*.sqlite")):
        db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            for (body,) in db.execute("SELECT body FROM records"):
                row = json.loads(body)
                if row["source"]["producer"] == "workshop-feedback-capture":
                    row = validate(row)
                    if row["classification"]["store"] != store:
                        raise ValueError("capture store mismatch")
                    if row["id"] in rows and canonical(rows[row["id"]]) != canonical(
                        row
                    ):
                        raise ValueError("conflicting capture identity")
                    rows[row["id"]] = row
        finally:
            db.close()
    return sorted(rows.values(), key=lambda row: (row["occurred_at"], row["id"]))


def find_capture(memory, store, ident):
    for row in capture_records(memory, store):
        if ident in (row["id"], row["payload"]["observation"]["id"]):
            return row
    raise ValueError("capture not found in selected store")


def recover_capture(row, raw, output):
    """Verify the entire artifact before writing into a new directory."""
    validate(row)
    item = row["external_artifacts"][0]
    if len(raw) != item["size"] or digest(raw) != item["sha256"]:
        raise ValueError("capture archive integrity failure")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        for member in archive:
            if (
                not member.isfile()
                or member.name in files
                or not safe_name(member.name)
            ):
                raise ValueError("invalid archive member")
            files[member.name] = archive.extractfile(member).read()
    manifest = row["payload"]["manifest"]
    if json.loads(files["manifest.json"]) != manifest:
        raise ValueError("capture manifest mismatch")
    expected = {entry["path"]: entry for entry in manifest["files"]}
    if set(files) != set(expected) | {"manifest.json"}:
        raise ValueError("capture file set mismatch")
    for name, entry in expected.items():
        if len(files[name]) != entry["size"] or digest(files[name]) != entry["sha256"]:
            raise ValueError("capture member integrity failure")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for name, data in files.items():
        atomic_bytes(output / name, data)
    atomic_bytes(output / "envelope.json", (canonical(row) + "\n").encode())
    return {"id": row["id"], "output": str(output), "files": len(files)}


def catalog(memory, store, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    rows = capture_records(memory, store)
    entries = []
    for row in rows:
        name = f"captures/{row['id'][:2]}/{row['id']}/metadata.json"
        atomic_bytes(output / name, (canonical(row) + "\n").encode())
        entries.append(
            {
                "id": row["id"],
                "observation_id": row["payload"]["observation"]["id"],
                "path": name,
            }
        )
    atomic_bytes(
        output / "index.json",
        (
            canonical(
                {
                    "schema_version": 1,
                    "store": store,
                    "format": "workshop-capture-catalog-v1",
                    "entries": entries,
                }
            )
            + "\n"
        ).encode(),
    )
    return {"store": store, "captures": len(rows), "output": str(output)}


def import_catalog(memory, directory, agent):
    directory = Path(directory)
    index = json.loads((directory / "index.json").read_text())
    if (
        index.get("format") != "workshop-capture-catalog-v1"
        or index.get("schema_version") != 1
    ):
        raise ValueError("unknown capture catalog")
    rows = []
    for entry in index["entries"]:
        if not safe_name(entry["path"]):
            raise ValueError("unsafe catalog path")
        path = directory / entry["path"]
        if not path.resolve().is_relative_to(directory.resolve()):
            raise ValueError("catalog path escapes directory")
        row = validate(json.loads(snapshot(path)))
        if row["classification"]["store"] != index["store"] or row["id"] != entry["id"]:
            raise ValueError("catalog identity or classification mismatch")
        if row["source"]["producer"] != "workshop-feedback-capture":
            raise ValueError("catalog entry is not a capture")
        if row["payload"]["observation"]["id"] != entry["observation_id"]:
            raise ValueError("catalog observation mismatch")
        rows.append(row)
    results = [memory.append(row, agent) for row in rows]
    return {
        "store": index["store"],
        "captures": len(results),
        "duplicates": sum(r["duplicate"] for r in results),
    }
