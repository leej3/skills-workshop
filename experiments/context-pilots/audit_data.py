"""Read-only quality and eligibility audit for retained Workshop pilots."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import sqlite3
import tarfile
import zlib
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT))
from scripts.memory_store import validate

PILOT_PRODUCERS = {"native-luna-pilot", "waza", "sqlite", "qmd", "brain"}
NATIVE_STATUSES = {
    "attempted",
    "completed",
    "failed",
    "interrupted",
    "blocked",
    "abandoned",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_records(ledger: Path) -> list[dict[str, Any]]:
    """Read staged/published records without opening the ledger for writes."""
    uri = f"file:{ledger.resolve()}?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        rows = connection.execute("SELECT body FROM batches ORDER BY day,id")
        records = []
        for (body,) in rows:
            records.extend(json.loads(body).get("records", []))
    existing = {}
    for record in records:
        existing.setdefault(record.get("id"), []).append(record)
    # Daily batches may not yet include recent immutable attempt/outcome events.
    for event_path in sorted(ledger.parent.parent.glob("native-trials/*/*event.json")):
        event = json.loads(event_path.read_text())
        same_id = existing.get(event.get("id"), [])
        if not same_id or any(previous != event for previous in same_id):
            records.append(event)
        existing.setdefault(event.get("id"), []).append(event)
    return records


def _artifact_bytes(
    record: dict[str, Any], state: Path, errors: list[str]
) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for item in record.get("artifacts", []):
        try:
            data = base64.b64decode(item["bytes_base64"], validate=True)
        except (KeyError, ValueError, TypeError):
            errors.append(
                f"{record.get('id')}: invalid embedded artifact {item.get('name')}"
            )
            continue
        if sha256(data) != item.get("sha256"):
            errors.append(
                f"{record.get('id')}: embedded artifact hash mismatch: {item.get('name')}"
            )
            continue
        if item["name"] in found:
            errors.append(
                f"{record.get('id')}: duplicate embedded artifact name: {item['name']}"
            )
        found[item["name"]] = data
    for item in record.get("external_artifacts", []):
        local = state / item.get("store", "") / "objects" / item.get("sha256", "")
        if not local.is_file():
            continue
        try:
            raw = local.read_bytes()
            packed = gzip.decompress(raw)
            with tarfile.open(fileobj=io.BytesIO(packed), mode="r:") as archive:
                for member in archive.getmembers():
                    if not member.isfile() or Path(member.name).name != member.name:
                        errors.append(
                            f"{record.get('id')}: unsafe member in local artifact archive"
                        )
                        continue
                    stream = archive.extractfile(member)
                    if stream is None:
                        errors.append(
                            f"{record.get('id')}: unreadable local artifact member"
                        )
                        continue
                    data = stream.read()
                    if member.name in found:
                        errors.append(
                            f"{record.get('id')}: duplicate artifact filename: {member.name}"
                        )
                    found[member.name] = data
        except (OSError, EOFError, tarfile.TarError, zlib.error) as exc:
            errors.append(
                f"{record.get('id')}: invalid local artifact archive ({type(exc).__name__})"
            )
    return found


def _accepted_recovery_originals(state: Path, errors: list[str]):
    """Index originals superseded operationally by a verified recovery grade."""
    found = {}
    root = state / "native-recoveries"
    for path in sorted(root.glob("*.supersession.json")):
        try:
            resolution = json.loads(path.read_text())
            recovery_id = resolution["recovery_id"]
            receipt_path = root / f"{recovery_id}.grade-receipt.json"
            record_path = root / f"{recovery_id}.grade-record.json"
            grade_path = root / f"{recovery_id}.grade.json"
            receipt = json.loads(receipt_path.read_text())
            record_raw = record_path.read_bytes()
            record = validate(json.loads(record_raw))
            grade_raw = grade_path.read_bytes()
            packet_path = Path(receipt["packet_path"])
            packet_raw = packet_path.read_bytes()
            grade = json.loads(grade_raw)
            packet = json.loads(packet_raw)
            captured = receipt.get("captured_responses", [])
            for item in captured:
                if sha256(Path(item["path"]).read_bytes()) != item.get("sha256"):
                    raise ValueError("graded response capture changed")
            if (
                resolution.get("schema") != "native-recovery-supersession-v1"
                or resolution.get("acceptance_scope")
                != "operational admission supersession only; no effectiveness claim"
                or resolution.get("original_admission_status") != "unknown, unchanged"
                or resolution.get("grade_record_id") != record.get("id")
                or resolution.get("grade_record_sha256") != sha256(record_raw)
                or receipt.get("grade_record_id") != record.get("id")
                or receipt.get("grade_record_sha256") != sha256(record_raw)
                or receipt.get("grade_sha256") != sha256(grade_raw)
                or receipt.get("packet_sha256") != sha256(packet_raw)
                or grade.get("method", {}).get("input_sha256") != sha256(packet_raw)
                or {sha256(row["response"].encode()) for row in packet["responses"]}
                != {item.get("sha256") for item in captured}
                or resolution.get("grade_sha256") != sha256(grade_raw)
                or resolution.get("packet_sha256") != sha256(packet_raw)
                or record.get("source", {}).get("producer")
                != "native-blinded-grader-ingest"
                or record.get("payload", {}).get("pair_id") != resolution.get("pair_id")
                or record.get("payload", {}).get("recovery_id") != recovery_id
                or record.get("payload", {}).get("grade_sha256") != sha256(grade_raw)
                or record.get("payload", {}).get("packet_sha256") != sha256(packet_raw)
            ):
                raise ValueError("supersession does not match its grade receipt")
            original_ids = resolution.get("original_trial_ids", [])
            outcomes = resolution.get("accepted_outcomes", [])
            accepted_ids = resolution.get("accepted_recovery_trial_ids", [])
            if (
                len(original_ids) != 2
                or len(set(original_ids)) != 2
                or len(outcomes) != 2
                or len(set(accepted_ids)) != 2
                or set(accepted_ids) != {item.get("trial_id") for item in outcomes}
            ):
                raise ValueError(
                    "supersession does not name exactly one completed pair"
                )
            for ident in original_ids:
                if ident in found:
                    raise ValueError(
                        "original admission appears in multiple supersessions"
                    )
                found[ident] = resolution
        except (OSError, ValueError, TypeError, KeyError) as exc:
            errors.append(
                f"{path.name}: invalid recovery supersession metadata ({type(exc).__name__})"
            )
    return found


def audit_records(records: Iterable[dict[str, Any]], state: Path) -> dict[str, Any]:
    """Validate schema, lineage, local artifact bytes, and analysis eligibility."""
    errors: list[str] = []
    warnings: list[str] = []
    all_records = list(records)
    selected = [
        r for r in all_records if r.get("source", {}).get("producer") in PILOT_PRODUCERS
    ]
    counts: Counter[str] = Counter()
    seen: dict[str, int] = Counter()
    failed_checks: list[dict[str, str]] = []
    false_positives: list[dict[str, str]] = []
    duplicate_path_results: list[dict[str, str]] = []
    by_id = {r.get("id"): r for r in all_records if isinstance(r.get("id"), str)}
    superseded_originals = _accepted_recovery_originals(state, errors)
    terminal_statuses: dict[str, set[str]] = {}
    for row in all_records:
        if row.get("source", {}).get("producer") != "native-luna-pilot":
            continue
        ident = row.get("context", {}).get("task_id")
        status = row.get("payload", {}).get("status")
        if ident and status in NATIVE_STATUSES - {"attempted"}:
            terminal_statuses.setdefault(ident, set()).add(status)
    conflicting_terminal = {
        ident: statuses
        for ident, statuses in terminal_statuses.items()
        if len(statuses) > 1
    }
    for ident in conflicting_terminal:
        errors.append(f"{ident}: conflicting terminal native trial outcomes")

    for record in selected:
        ident = record.get("id", "<missing-id>")
        seen[ident] += 1
        try:
            validate(record)
        except (ValueError, TypeError, KeyError) as exc:
            errors.append(
                f"{ident}: invalid envelope or embedded hash ({type(exc).__name__})"
            )
            counts["invalid-envelope"] += 1
            continue
        artifacts = _artifact_bytes(record, state, errors)
        producer = record.get("source", {}).get("producer")
        payload = record.get("payload", {})
        context = record.get("context", {})
        if not isinstance(payload, dict):
            errors.append(f"{ident}: payload is not an object")
            counts["invalid-payload"] += 1
            continue

        for item in record.get("external_artifacts", []):
            local = state / item.get("store", "") / "objects" / item.get("sha256", "")
            if not local.is_file():
                errors.append(
                    f"{ident}: referenced local artifact missing: {item.get('name')}"
                )
            else:
                data = local.read_bytes()
                if len(data) != item.get("size") or sha256(data) != item.get("sha256"):
                    errors.append(
                        f"{ident}: referenced local artifact checksum/size mismatch: {item.get('name')}"
                    )

        if producer == "native-luna-pilot":
            status = payload.get("status")
            trial = payload.get("trial", {})
            supersession = superseded_originals.get(context.get("task_id"))
            if supersession:
                if status == "attempted":
                    counts["superseded-admission-unknown"] += 1
                else:
                    counts["superseded-original-late-alternative"] += 1
                    warnings.append(
                        f"{ident}: late original result needs reconciliation with recovery "
                        f"{supersession['recovery_id']} and is excluded from analysis"
                    )
                continue
            terminal = terminal_statuses.get(context.get("task_id"), set())
            if status == "attempted" and len(terminal) == 1:
                history = (
                    "recovery-alternative-attempt-history"
                    if context.get("conditions", {}).get("recovery_of")
                    else "attempt-history"
                )
                counts[f"{history}:{next(iter(terminal))}"] += 1
                continue
            if not isinstance(trial, dict):
                errors.append(f"{ident}: trial lineage is not an object")
                counts["invalid-payload"] += 1
                continue
            trial_files = trial.get("files", {})
            payload_files = payload.get("files", {})
            if not isinstance(trial_files, dict) or not isinstance(payload_files, dict):
                errors.append(f"{ident}: file lineage is not an object")
                counts["invalid-payload"] += 1
                continue
            expected_files = {**trial_files, **payload_files}
            for name, expected in expected_files.items():
                content = artifacts.get(name)
                if content is None:
                    errors.append(
                        f"{ident}: frozen/output file missing from record: {name}"
                    )
                elif sha256(content) != expected:
                    errors.append(f"{ident}: frozen/output file hash mismatch: {name}")
            recovery_of = context.get("conditions", {}).get("recovery_of")
            if status == "attempted":
                category = "recovery-alternative-pending" if recovery_of else "pending"
            elif status in NATIVE_STATUSES - {"attempted", "completed"}:
                category = f"noncompleted:{status}"
            else:
                response = artifacts.get("response.txt")
                runtime = artifacts.get("runtime.json")
                if status == "completed" or (status is None and response is not None):
                    retained_response_hash = payload.get("response_sha256") or (
                        payload_files.get("response.txt")
                    )
                    if not response or sha256(response) != retained_response_hash:
                        errors.append(f"{ident}: response hash missing or inconsistent")
                    if not runtime:
                        errors.append(
                            f"{ident}: completed model output has no runtime artifact"
                        )
                    try:
                        runtime_info = json.loads(runtime or b"null")
                    except (ValueError, TypeError):
                        runtime_info = None
                        errors.append(f"{ident}: runtime artifact is invalid JSON")
                    model = context.get("model") or {}
                    if (
                        not model.get("id")
                        or not isinstance(runtime_info, dict)
                        or not runtime_info.get("model")
                    ):
                        category = "unknown-runtime"
                    elif runtime_info["model"] != model["id"]:
                        errors.append(
                            f"{ident}: runtime model differs from record context"
                        )
                        category = "unknown-runtime"
                    elif payload.get("grade") is None:
                        if runtime_info.get("transport_degraded"):
                            category = "transport-degraded-alternative"
                        else:
                            category = (
                                "recovery-alternative-model-ungraded"
                                if recovery_of
                                else "observed-model-ungraded"
                            )
                    else:
                        category = (
                            "recovery-alternative-model-graded"
                            if recovery_of
                            else "observed-model-graded"
                        )
                else:
                    category = "unknown-status"
            counts[category] += 1
            continue

        if producer == "waza":
            conditions = context.get("conditions", {})
            if (
                conditions.get("executor") == "mock"
                or conditions.get("model_calls") is False
            ):
                category = "mock-plumbing"
            elif (context.get("model") or {}).get("id"):
                category = (
                    "waza-model-output-ungraded"
                    if payload.get("grade") is None
                    else "waza-model-output-graded"
                )
            else:
                category = "waza-runtime-unknown"
            counts[category] += 1
            continue

        # Retrieval output is descriptive evidence only, never a model-effectiveness score.
        counts["descriptive-retrieval"] += 1
        conditions = context.get("conditions", {})
        query = conditions.get("query")
        paths = payload.get("paths", [])
        if not isinstance(paths, list):
            errors.append(f"{ident}: result paths are not a list")
            counts["invalid-payload"] += 1
            continue
        if payload.get("expected_source_hit_at_5") is False:
            finding = {
                "record_id": ident,
                "provider": producer,
                "query_id": str(payload.get("query_id", "unknown")),
            }
            failed_checks.append(finding)
            if isinstance(query, dict) and query.get("expected") is None and paths:
                false_positives.append(finding)
        if len(paths) != len(set(map(str, paths))):
            duplicate_path_results.append(
                {
                    "record_id": ident,
                    "provider": producer,
                    "query_id": str(payload.get("query_id", "unknown")),
                }
            )
        if not isinstance(query, dict):
            warnings.append(f"{ident}: query provenance absent")
        else:
            expected = query.get("expected")
            observed = (
                any(str(path).endswith(expected) for path in paths)
                if expected
                else not paths
            )
            if payload.get("expected_source_hit_at_5") is not observed:
                errors.append(
                    f"{ident}: reported source/abstention check differs from retained paths"
                )
        native_output = artifacts.get("native-output.json")
        if native_output is not None:
            try:
                output = json.loads(native_output)
                stdout = output.get("stdout", "")
                parsed = json.loads(stdout)
                hits = parsed if isinstance(parsed, list) else parsed.get("results", [])
                output_paths = [hit.get("file", hit.get("path", "")) for hit in hits]
                if output.get("exit") != payload.get("exit"):
                    errors.append(
                        f"{ident}: retained output exit status differs from summary"
                    )
                if output_paths != payload.get("paths"):
                    errors.append(f"{ident}: retained output paths differ from summary")
            except (ValueError, TypeError, AttributeError):
                errors.append(f"{ident}: retained native output is not readable JSON")
        corpora = [
            rel.get("id")
            for rel in record.get("relations", [])
            if rel.get("relation") == "corpus"
        ]
        if len(corpora) != 1 or corpora[0] not in by_id:
            errors.append(f"{ident}: missing or ambiguous corpus relation")
        elif conditions.get("fixture_sha256"):
            corpus = by_id[corpora[0]]
            frozen = next(
                (
                    a
                    for a in corpus.get("artifacts", [])
                    if a.get("name") == "frozen-inputs.json"
                ),
                None,
            )
            if not frozen or frozen.get("sha256") != conditions["fixture_sha256"]:
                errors.append(f"{ident}: corpus fixture digest mismatch")

    for ident, count in seen.items():
        if count > 1:
            errors.append(f"{ident}: duplicate record ID ({count} records)")

    return {
        "valid": not errors,
        "integrity_valid": not errors,
        "effectiveness_claim_status": "not-established",
        "records": len(selected),
        "counts": dict(sorted(counts.items())),
        "quality_findings": {
            "failed_expected_source_checks": failed_checks,
            "absent_term_false_positives": false_positives,
            "duplicate_path_results": duplicate_path_results,
        },
        "errors": errors,
        "warnings": warnings,
        "eligible_for_descriptive_analysis": counts["descriptive-retrieval"]
        + counts["observed-model-ungraded"]
        + counts["observed-model-graded"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state",
        type=Path,
        default=Path.home() / ".local/state/skills-workshop/memory",
    )
    parser.add_argument("--ledger", type=Path)
    args = parser.parse_args()
    ledger = args.ledger or args.state / "shared/ledger.sqlite"
    try:
        report = audit_records(read_records(ledger), args.state)
    except (OSError, sqlite3.Error, ValueError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "valid": False,
                    "errors": [f"cannot read audit input ({type(exc).__name__})"],
                },
                indent=2,
            )
        )
        return 1
    print(json.dumps(report, indent=2))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
