"""Report completeness of recorded uses without inferring unrecorded activity."""

import json
import re
import shlex
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timedelta, timezone

from scripts.memory_feedback import validate_input
from scripts.memory_store import ROOT, canonical, digest, validate


def read_rows(memory, store):
    """Read journals and active batches; never create or seal a database."""
    root = memory.root / store
    rows, publication = {}, {}
    historical = set(memory.batch_supersessions(store))
    held = memory.publication_holds(store)
    ledger = root / "ledger.sqlite"
    if ledger.exists():
        with sqlite3.connect(ledger.as_uri() + "?mode=ro", uri=True) as db:
            for ident, body, state, receipt in db.execute(
                "SELECT id,body,state,receipt FROM batches"
            ):
                if ident in historical:
                    continue
                for row in json.loads(body)["records"]:
                    rows[row["id"]] = validate(row)
                    publication[row["id"]] = {
                        "state": "held" if ident in held else state,
                        "batch_id": ident,
                        "receipt": json.loads(receipt) if receipt else None,
                    }
    for path in sorted((root / "agents").glob("*.sqlite")):
        with sqlite3.connect(path.as_uri() + "?mode=ro", uri=True) as db:
            for (body,) in db.execute("SELECT body FROM records"):
                row = validate(json.loads(body))
                if row["classification"]["store"] != store:
                    raise ValueError("journal classification mismatch")
                if row["id"] in rows and canonical(rows[row["id"]]) != canonical(row):
                    raise ValueError("conflicting health record identity")
                rows[row["id"]] = row
    return rows, publication


def health(
    memory,
    store,
    public,
    private,
    days=7,
    limit=50,
    remote=None,
    now=None,
    observation_id=None,
):
    if days < 1 or limit < 1:
        raise ValueError("days and limit must be positive")
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    rows, publication = read_rows(memory, store)
    observations, captures, linked_duct = {}, {}, {}
    for row in rows.values():
        if row["source"]["producer"] == "workshop-feedback":
            observations[row["id"]] = row["payload"]
        elif row["source"]["producer"] == "workshop-feedback-capture":
            report = row["payload"]["observation"]
            observations[report["id"]] = report
            if report["id"] in captures:
                raise ValueError("multiple captures for one observation")
            captures[report["id"]] = row
        elif row["source"]["producer"] == "con-duct" and row.get("external_artifacts"):
            for relation in row.get("relations", []):
                if relation["relation"] == "supports":
                    linked_duct.setdefault(relation["id"], []).append(row["id"])
    # Merge the private overlay before choosing a store, including uses not imported yet.
    sources = {}
    for tree, overlay in [(public, False), (private, True)]:
        if not tree.is_dir():
            raise ValueError("both observation trees are required for safe routing")
        for path in sorted(tree.glob("records/*/*/*.json")):
            report = json.loads(path.read_text())
            validate_input(report, "observation-v2.schema.json")
            sensitive = (
                overlay
                or report["visibility"] == "private"
                or bool(report.get("sensitivity"))
            )
            sources[report["id"]] = (report, "sensitive" if sensitive else "shared")
    for ident, (report, classification) in sources.items():
        if classification == store:
            observations[ident] = report
        elif store == "sensitive" and ident in captures:
            # A shareable assessment can accompany a private conversation capture.
            observations[ident] = captures[ident]["payload"]["observation"]
        else:
            observations.pop(ident, None)
            captures.pop(ident, None)
    selected = []
    for report in observations.values():
        if report["kind"] == "usage" and (
            (report["id"] == observation_id)
            if observation_id
            else datetime.fromisoformat(report["recorded_at"].replace("Z", "+00:00"))
            >= cutoff
        ):
            selected.append(report)
    selected.sort(
        key=lambda r: (
            datetime.fromisoformat(r["recorded_at"].replace("Z", "+00:00")),
            r["id"],
        ),
        reverse=True,
    )
    if observation_id and not selected:
        raise ValueError("observation not found in selected store")
    total = len(selected)
    entries = []
    for report in selected[:limit]:
        ident = report["id"]
        capture = captures.get(ident)
        manifest = capture["payload"]["manifest"] if capture else {}
        members = {f["path"] for f in manifest.get("files", [])}
        reference = manifest.get("skill_reference", {})
        present = {
            "assessment": bool(report.get("assessment")),
            "conversation": manifest.get("conversation", {}).get("path") in members,
            "duct_logs": bool(manifest.get("duct_runs"))
            and all(
                run["path"] + "run_info.json" in members
                and run["path"] + "context.json" in members
                for run in manifest.get("duct_runs", [])
            ),
            "pinned_skill_reference": reference.get("manager") == "apm"
            and reference.get("skill") == report["skill"]
            and bool(reference.get("package"))
            and bool(
                re.fullmatch(r"[0-9a-f]{40}", reference.get("resolved_commit", ""))
            ),
        }
        if linked_duct.get(ident):
            present["duct_logs"] = True
        missing = [name for name, value in present.items() if not value]
        declared = manifest.get("missing_evidence", [])
        issues = ["missing_" + name for name in missing]
        if declared:
            issues.append("declared_evidence_gaps")
        target = capture["id"] if capture else ident
        pub = publication.get(
            target, {"state": "journaled" if target in rows else "not_queued"}
        )
        storage = {
            "record": pub["state"],
            "payload_local": "no_capture",
            "upload": "unknown",
            "remote": "not_checked",
        }
        if capture:
            item = capture["external_artifacts"][0]
            path = memory.root / store / "objects" / item["sha256"]
            storage["payload_local"] = "missing"
            if path.is_file():
                raw = path.read_bytes()
                storage["payload_local"] = (
                    "verified"
                    if len(raw) == item["size"] and digest(raw) == item["sha256"]
                    else "corrupt"
                )
            receipt_path = (
                memory.root / store / "artifact-receipts" / (item["sha256"] + ".json")
            )
            if receipt_path.exists():
                receipt = json.loads(receipt_path.read_text())
                if (
                    receipt.get("sha256") == item["sha256"]
                    and receipt.get("key") == item["annex_key"]
                ):
                    storage["upload"] = "receipt_recorded"
            if pub["state"] == "published" and pub.get("receipt"):
                storage["upload"] = "confirmed_at_batch_publication"
            if storage["payload_local"] != "verified":
                issues.append("local_payload_" + storage["payload_local"])
            if remote:
                storage["remote"] = remote(capture, pub)
                if storage["remote"]["payload"] == "present":
                    storage["upload"] = "remote_presence_verified"
                for part in ("metadata", "payload"):
                    if storage["remote"][part] != "present":
                        issues.append("remote_" + part + "_" + storage["remote"][part])
        if pub["state"] != "published":
            issues.append("record_" + pub["state"])
        command = [
            "pixi",
            "run",
            "--manifest-path",
            str(ROOT / "pixi.toml"),
            "memory",
            "--state",
            str(memory.root),
            "show-capture",
            ident,
            "--store",
            store,
        ]
        entries.append(
            {
                "observation_id": ident,
                "capture_id": capture["id"] if capture else None,
                "recorded_at": report["recorded_at"],
                "skill": report["skill"],
                "task": report["task"],
                "present": present,
                "missing": missing,
                "linked_duct_evidence_ids": sorted(linked_duct.get(ident, [])),
                "declared_missing_evidence": declared,
                "storage": storage,
                "issues": issues,
                "inspect_command": shlex.join(command)
                if capture
                else shlex.join(
                    command[:7]
                    + [
                        "health",
                        "--id",
                        ident,
                        "--store",
                        store,
                        "--public",
                        str(public),
                        "--private",
                        str(private),
                    ]
                ),
                **(
                    {"observation": report, "capture": capture}
                    if observation_id
                    else {}
                ),
            }
        )
    return {
        "schema_version": 1,
        "store": store,
        "generated_at": now.isoformat(),
        "since": cutoff.isoformat(),
        "scope": "recorded skill uses only; unrecorded activity is unknown",
        "matching_uses": total,
        "returned_uses": len(entries),
        "truncated": total > limit,
        "summary_scope": "returned uses",
        "complete_evidence": sum(
            not e["missing"] and not e["declared_missing_evidence"] for e in entries
        ),
        "issue_counts": dict(Counter(issue for e in entries for issue in e["issues"])),
        "uses": entries,
    }


def remote_checker(transport):
    """Check current metadata visibility and payload presence, without downloading."""
    refs = dict(
        line.split()[::-1]
        for line in transport.git("ls-remote", "origin", "refs/workshop/*").splitlines()
    )

    def check(capture, publication):
        item = capture["external_artifacts"][0]
        try:
            ref = "refs/workshop/memory/v2/" + publication.get("batch_id", "")
            metadata = "present" if ref in refs else "absent"
            expected = (publication.get("receipt") or {}).get("commit")
            if expected and ref in refs and refs[ref] != expected:
                metadata = "mismatch"
            result = transport.git(
                "annex",
                "checkpresentkey",
                item["annex_key"],
                "payload",
                role="payload",
                check=False,
            )
            payload = {0: "present", 1: "absent"}.get(result.returncode, "unknown")
            return {
                "metadata": metadata,
                "payload": payload,
                "retrievable": metadata == "present" and payload == "present",
            }
        except (OSError, RuntimeError, subprocess.SubprocessError):
            return {"metadata": "unknown", "payload": "unknown", "retrievable": None}

    return check
