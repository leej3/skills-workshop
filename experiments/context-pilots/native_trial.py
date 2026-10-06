"""Freeze and retain account-backed native trials without a provider dependency."""

import argparse
import fcntl
import json
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.memory_capture import store_archive
from scripts.memory_store import (
    MemoryStore,
    atomic_bytes,
    canonical,
    digest,
    envelope,
    validate,
)

STATE = Path.home() / ".local/state/skills-workshop/memory"


def prepare(kind, state, assigned_treatment=None, pair_id=None, recovery_of=None):
    ident = str(uuid.uuid4())
    work = state / "native-trials" / ident
    work.mkdir(parents=True, mode=0o700)
    completed = sorted((state / "native-trials").glob("*/receipt.json"))
    cli_count = sum(json.loads(p.read_text()).get("kind") == "cli" for p in completed)
    treatment = (
        ("explicit-skill" if cli_count % 2 else "ambient-baseline")
        if kind == "cli"
        else "heading-tree"
    )
    if assigned_treatment is not None:
        if kind != "cli" or assigned_treatment not in (
            "ambient-baseline",
            "explicit-skill",
        ):
            raise ValueError("invalid treatment assignment")
        treatment = assigned_treatment
    skill = (ROOT / ".agents/skills/unix-cli-design/SKILL.md").read_bytes()
    if kind == "cli":
        prompt = yaml.safe_load(
            (Path(__file__).parent / "waza/tasks/cli-stream.yaml").read_text()
        )["inputs"]["prompt"]
        fixture = {
            "prompt": prompt,
            "rubric": [
                "stdout contains only records",
                "diagnostics use stderr",
                "malformed input has a documented nonzero status",
                "broken pipe has no traceback",
                "pipeline tests cover exit status and stream separation",
            ],
        }
    else:
        # Long synthetic inputs with unique locators, repeated topics and a superseded decision.
        docs = "\n\n".join(
            f"## D{i:03d}: operating area {i}\n"
            + ("This area uses the ordinary daily collection policy. " * 25)
            for i in range(120)
        )
        docs += "\n\n## D120: recovery exception\nAfter a lost upload acknowledgement, retry the identical batch ID and bytes. Never regenerate the batch.\n"
        conversation = [
            {
                "id": f"T{i:03d}",
                "text": "Routine discussion of daily collection and retrieval projections."
                * 12,
            }
            for i in range(160)
        ]
        conversation[12]["text"] = (
            "Proposal: flush after every 100 records. This is a proposal, not a decision."
        )
        conversation[145]["text"] = (
            "Accepted decision: aggregate once daily per store, targeting 1000 records per file. Keep at most one remainder for that day and store."
        )
        prompt = "Using the supplied heading outline, document and conversation, answer with exact D/T citations: What should happen after a lost upload acknowledgement? What flush policy was accepted, and which earlier proposal did it supersede? What encryption cipher was approved? Abstain if not specified."
        fixture = {
            "prompt": prompt,
            "document": docs,
            "conversation": conversation,
            "outline": {
                "document": [
                    "D000-D119: ordinary operating areas",
                    "D120: recovery exception",
                ],
                "conversation": [
                    "T000-T079: proposals and routine discussion",
                    "T080-T159: later decisions and routine discussion",
                ],
            },
            "rubric": [
                "identical batch ID and bytes, D120",
                "daily/store and 1000 records, T145",
                "supersedes 100-record proposal, T012",
                "cipher unknown; abstain",
            ],
        }
    if kind == "cli":
        fixture["prompt"] += (
            "\nAlso consider a producer that emits two valid records then a malformed line; "
            "a final valid line without a newline; input from a non-seekable pipe; "
            "an early-closing consumer; and a batch-mode default that existing scripts rely on. "
            "Specify partial-output semantics, exit-status propagation through a shell pipeline, "
            "and executable test examples without silently changing the default mode."
        )
        prompt = fixture["prompt"]
        fixture["rubric"] += [
            "defines already-emitted output when later input fails",
            "handles final unterminated input and output framing",
            "handles non-seekable input without requiring seek",
            "distinguishes producer failure from shell pipeline status with pipefail",
            "preserves existing batch defaults while proposing explicit streaming behavior",
            "gives executable tests with expected output and exit status",
        ]
    agent_input = {key: value for key, value in fixture.items() if key != "rubric"}
    if treatment == "explicit-skill":
        agent_input["skill"] = skill.decode()
    files = {
        "agent-input.json": canonical(agent_input).encode(),
        "fixture.json": canonical(fixture).encode(),
        "treatment-skill.md": skill,
        "protocol.md": Path(__file__).with_name("scheduled-protocol.md").read_bytes(),
        "collector.py": Path(__file__).read_bytes(),
    }
    for name, data in files.items():
        atomic_bytes(work / name, data)
    manifest = {
        "id": ident,
        "kind": kind,
        "pair_id": pair_id,
        "recovery_of": recovery_of,
        "treatment": treatment,
        "prompt": prompt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {name: digest(data) for name, data in files.items()},
        "evidence_level": "exploratory",
        "budget": "one native scheduled response; ambient host limits",
        "host_context_isolation": False,
    }
    atomic_bytes(work / "manifest.json", canonical(manifest).encode())
    record_event(work, state, "attempted")
    return {"workspace": str(work), "treatment": treatment, "prompt": prompt}


def record_event(work, state, status, reason=None):
    """Persist the immutable event before journal append, allowing exact replay."""
    work = Path(work)
    manifest = json.loads((work / "manifest.json").read_text())
    with (work / ".event.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        files = {}
        for name, expected in manifest["files"].items():
            data = (work / name).read_bytes()
            if digest(data) != expected and status == "completed":
                raise ValueError("frozen input changed")
            files[name] = data
        files["manifest.json"] = (work / "manifest.json").read_bytes()
        if status != "attempted":
            for name in (
                "response.txt",
                "runtime.json",
                "failure.txt",
                "supplemental-interim-response.txt",
            ):
                if (work / name).exists():
                    files[name] = (work / name).read_bytes()
        runtime = None
        if "runtime.json" in files:
            try:
                runtime = json.loads(files["runtime.json"])
                if not isinstance(runtime, dict):
                    raise TypeError("runtime must be an object")
            except (ValueError, TypeError):
                if status == "completed":
                    raise
                runtime = None
        if status == "completed" and (
            not files.get("response.txt", b"").strip() or runtime is None
        ):
            raise ValueError(
                "completion requires a nonempty response and runtime object"
            )
        event_path = work / (
            "attempt-event.json" if status == "attempted" else "outcome-event.json"
        )
        snapshot = {name: digest(data) for name, data in files.items()}
        memory = MemoryStore(state)
        if event_path.exists():
            packet = json.loads(event_path.read_text())
            if (
                packet["payload"]["status"] != status
                or packet["payload"]["files"] != snapshot
                or packet["payload"]["reason"] != reason
            ):
                raise ValueError(
                    "event already frozen; changed outcome requires a new trial"
                )
        else:
            item = store_archive(memory, "shared", "trial-evidence.tar.gz", files)
            packet = envelope(
                {
                    "trial": manifest,
                    "status": status,
                    "reason": reason,
                    "files": snapshot,
                    "response_sha256": snapshot.get("response.txt"),
                    "grade": None,
                },
                ident=str(uuid.uuid5(uuid.UUID(manifest["id"]), status)),
                kind="evaluation" if manifest["kind"] == "cli" else "retrieval",
                occurred_at=datetime.now(timezone.utc).isoformat(),
                store="shared",
                producer="native-luna-pilot",
                version="2",
                source_schema="native-trial-v2",
                context={
                    "task_id": manifest["id"],
                    "agent_id": "scheduled-native",
                    "runtime": runtime,
                    "model": {"id": runtime["model"]}
                    if runtime and runtime.get("model")
                    else None,
                    "skill": {
                        "sha256": manifest["files"]["treatment-skill.md"],
                        "exposure": manifest["treatment"],
                    },
                    "conditions": {
                        "evidence_level": "exploratory",
                        "host_context_isolation": False,
                        "pair_id": manifest.get("pair_id"),
                        "recovery_of": manifest.get("recovery_of"),
                        "transport_revision": (manifest.get("transport") or {}).get(
                            "revision"
                        ),
                        "transport_wrapper_sha256": (
                            manifest.get("transport") or {}
                        ).get("wrapper_sha256"),
                        "fixture_sha256": manifest["files"]["fixture.json"],
                        "protocol_sha256": manifest["files"]["protocol.md"],
                    },
                },
                relations=[{"relation": "trial", "id": manifest["id"]}],
            )
            packet["external_artifacts"] = [item]
            atomic_bytes(event_path, canonical(packet).encode())
        result = memory.append(packet, "scheduled-native")
        if status != "attempted":
            atomic_bytes(
                work / "receipt.json",
                canonical(
                    {**result, "kind": manifest["kind"], "status": status}
                ).encode(),
            )
        return result


def finish(work, state, status="completed", reason=None):
    if status not in ("completed", "failed", "interrupted", "blocked", "abandoned"):
        raise ValueError("invalid outcome status")
    if status != "completed" and not reason:
        raise ValueError("non-completion requires a reason")
    return record_event(work, state, status, reason)


def pending(state):
    """Replay events and distinguish actionable work from superseded admissions."""
    for path in sorted((state / "native-trials").glob("*/manifest.json")):
        work = path.parent
        if (work / "receipt.json").exists() and not (
            work / "attempt-event.json"
        ).exists():
            continue  # Historical v1 completions remain immutable, not new attempts.
        if not (work / "attempt-event.json").exists():
            record_event(work, state, "attempted")
        for name in ("attempt-event.json", "outcome-event.json"):
            if (work / name).exists():
                MemoryStore(state).append(
                    json.loads((work / name).read_text()), "scheduled-native"
                )
    resolutions = _reconcile_completed_recoveries(state)
    superseded = {
        trial_id: resolution
        for resolution in resolutions.values()
        for trial_id in resolution["original_trial_ids"]
    }
    unresolved, historical, reconciliation = [], [], []
    for path in sorted((state / "native-trials").glob("*/manifest.json")):
        work = path.parent
        ident = json.loads(path.read_text())["id"]
        has_attempt = (work / "attempt-event.json").exists()
        has_outcome = (work / "outcome-event.json").exists()
        resolution = superseded.get(ident)
        if resolution:
            if has_outcome:
                reconciliation.append(
                    {
                        "trial_id": ident,
                        "status": "late-original-alternative-requires-reconciliation",
                        "resolution_id": resolution["resolution_id"],
                    }
                )
            elif has_attempt:
                historical.append(
                    {
                        "trial_id": ident,
                        "status": "admission-unknown-superseded-operationally",
                        "resolution_id": resolution["resolution_id"],
                    }
                )
            continue
        if has_attempt and not has_outcome:
            unresolved.append({"trial_id": ident, "workspace": str(work)})
    return {
        "unresolved": unresolved,
        "historical_admission_unknown": historical,
        "reconciliation_required": reconciliation,
    }


def _grade_receipt(state, plan):
    """Return a grade receipt only when its saved record and raw bytes verify."""
    root = Path(state) / "native-recoveries"
    recovery_id = plan.get("id")
    receipt_path = root / f"{recovery_id}.grade-receipt.json"
    record_path = root / f"{recovery_id}.grade-record.json"
    grade_path = root / f"{recovery_id}.grade.json"
    if (
        not receipt_path.is_file()
        or not record_path.is_file()
        or not grade_path.is_file()
    ):
        return None
    receipt = json.loads(receipt_path.read_text())
    record_raw = record_path.read_bytes()
    record = json.loads(record_raw)
    validate(record)
    for item in record.get("external_artifacts", []):
        artifact_path = Path(state) / item["store"] / "objects" / item["sha256"]
        if (
            not artifact_path.is_file()
            or artifact_path.stat().st_size != item["size"]
            or digest(artifact_path.read_bytes()) != item["sha256"]
        ):
            raise ValueError(
                "recovery grade evidence archive is missing or has changed"
            )
    grade_raw = grade_path.read_bytes()
    packet_path = Path(receipt.get("packet_path", ""))
    if not packet_path.is_file():
        raise ValueError("recovery grader packet is missing")
    packet_raw = packet_path.read_bytes()
    packet = json.loads(packet_raw)
    grade = json.loads(grade_raw)
    if grade.get("method", {}).get("input_sha256") != digest(packet_raw):
        raise ValueError("grade does not identify the retained blinded packet")
    labels = {row.get("label") for row in packet.get("responses", [])}
    if (
        labels != {row.get("label") for row in grade.get("responses", [])}
        or len(labels) != 2
    ):
        raise ValueError("grade labels do not match the blinded packet")
    rubric = packet.get("rubric", [])
    for response in grade.get("responses", []):
        items = response.get("items", [])
        if {item.get("rubric_item") for item in items} != set(rubric) or len(
            items
        ) != len(rubric):
            raise ValueError("grade rubric items do not match the blinded packet")
        if any(
            type(item.get("score")) is not int or item["score"] not in (0, 1, 2)
            for item in items
        ):
            raise ValueError("grade contains a score outside the retained rubric scale")
    captured = receipt.get("captured_responses", [])
    members = {Path(path).name for path in plan.get("workspaces", [])}
    if len(captured) != 2 or {item.get("trial_id") for item in captured} != members:
        raise ValueError("grade capture lineage does not match the recovery pair")
    for item in captured:
        source = Path(item.get("path", ""))
        if not source.is_file() or digest(source.read_bytes()) != item.get("sha256"):
            raise ValueError("graded response capture is missing or has changed")
    if {digest(row["response"].encode()) for row in packet["responses"]} != {
        item["sha256"] for item in captured
    }:
        raise ValueError("blinded packet responses do not match retained captures")
    if (
        receipt.get("recovery_id") != recovery_id
        or receipt.get("pair_id") != plan.get("pair_id")
        or receipt.get("grade_record_id") != record.get("id")
        or receipt.get("grade_record_sha256") != digest(record_raw)
        or digest(grade_raw) != receipt.get("grade_sha256")
        or digest(packet_raw) != receipt.get("packet_sha256")
        or record.get("source", {}).get("producer") != "native-blinded-grader-ingest"
        or record.get("payload", {}).get("recovery_id") != recovery_id
        or record.get("payload", {}).get("pair_id") != plan.get("pair_id")
        or record.get("payload", {}).get("grade_sha256") != receipt.get("grade_sha256")
        or record.get("payload", {}).get("packet_sha256")
        != receipt.get("packet_sha256")
        or record.get("payload", {}).get("source_response_sha256")
        != sorted(item["sha256"] for item in captured)
    ):
        raise ValueError(
            "recovery grade receipt does not match its immutable grade record"
        )
    return receipt


def _completed_recovery_outcomes(plan):
    """Verify both alternatives are complete, paired and backed by frozen inputs."""
    outcomes = []
    treatments = set()
    originals = set(plan.get("original_trial_ids", []))
    if len(originals) != 2 or len(plan.get("workspaces", [])) != 2:
        return None
    for workspace in plan["workspaces"]:
        work = Path(workspace)
        manifest = json.loads((work / "manifest.json").read_text())
        event_path = work / "outcome-event.json"
        if not event_path.is_file():
            return None
        event_raw = event_path.read_bytes()
        event = json.loads(event_raw)
        if (
            manifest.get("pair_id") != plan.get("pair_id")
            or manifest.get("recovery_id") != plan.get("id")
            or manifest.get("recovery_of") not in originals
            or manifest.get("recovery_role")
            != "operator-authorized-alternative-execution"
            or event.get("payload", {}).get("status") != "completed"
            or event.get("context", {}).get("task_id") != manifest.get("id")
            or event.get("payload", {}).get("trial", {}).get("id") != manifest.get("id")
            or event.get("context", {}).get("conditions", {}).get("pair_id")
            != plan.get("pair_id")
            or event.get("context", {}).get("conditions", {}).get("recovery_of")
            != manifest.get("recovery_of")
        ):
            return None
        files = event["payload"].get("files", {})
        response = (work / "response.txt").read_bytes()
        runtime = (work / "runtime.json").read_bytes()
        runtime_info = json.loads(runtime)
        response_sha = event["payload"].get("response_sha256") or files.get(
            "response.txt"
        )
        if (
            not response.strip()
            or digest(response) != files.get("response.txt")
            or files.get("response.txt") != response_sha
            or digest(runtime) != files.get("runtime.json")
            or runtime_info.get("transport_degraded")
        ):
            return None
        for name, expected in manifest.get("files", {}).items():
            if digest((work / name).read_bytes()) != expected:
                return None
        treatment = manifest.get("treatment")
        if treatment in treatments:
            return None
        treatments.add(treatment)
        outcomes.append(
            {
                "trial_id": manifest["id"],
                "original_trial_id": manifest["recovery_of"],
                "treatment": treatment,
                "outcome_event_id": event.get("id"),
                "outcome_event_sha256": digest(event_raw),
                "response_sha256": digest(response),
                "runtime_sha256": digest(runtime),
            }
        )
    if (
        treatments != {"ambient-baseline", "explicit-skill"}
        or {item["original_trial_id"] for item in outcomes} != originals
    ):
        return None
    return outcomes


def _reconcile_completed_recoveries(state):
    """Append supersession metadata after a verified grade, without editing originals."""
    root = Path(state) / "native-recoveries"
    resolutions = {}
    claimed_originals = set()
    for plan_path in sorted(root.glob("*.json")):
        if plan_path.name.endswith(("-transport-assessment.json", ".grading-key.json")):
            continue
        plan = json.loads(plan_path.read_text())
        if not plan.get("operator_authorized") or not plan.get("recovery_of_pair"):
            continue
        receipt = _grade_receipt(state, plan)
        outcomes = _completed_recovery_outcomes(plan)
        if receipt is None or outcomes is None:
            continue
        pair_path = Path(plan.get("original_pair", ""))
        if not pair_path.is_file():
            continue
        pair = json.loads(pair_path.read_text())
        original_ids = set(plan.get("original_trial_ids", []))
        if original_ids & claimed_originals:
            raise ValueError("multiple graded recoveries target the same logical pair")
        original_workspaces = [Path(path) for path in pair.get("workspaces", [])]
        if (
            pair.get("id") != plan.get("pair_id")
            or {
                json.loads((work / "manifest.json").read_text()).get("id")
                for work in original_workspaces
            }
            != original_ids
        ):
            continue
        resolution_path = root / f"{plan['id']}.supersession.json"
        if not resolution_path.exists() and any(
            (work / "outcome-event.json").exists() for work in original_workspaces
        ):
            continue
        resolution = {
            "schema": "native-recovery-supersession-v1",
            "resolution_id": str(uuid.uuid5(uuid.UUID(plan["id"]), "supersession-v1")),
            "recovery_id": plan["id"],
            "pair_id": plan["pair_id"],
            "original_trial_ids": sorted(original_ids),
            "accepted_recovery_trial_ids": sorted(
                item["trial_id"] for item in outcomes
            ),
            "accepted_outcomes": outcomes,
            "grade_record_id": receipt["grade_record_id"],
            "grade_record_sha256": receipt["grade_record_sha256"],
            "grade_sha256": receipt["grade_sha256"],
            "packet_sha256": receipt["packet_sha256"],
            "acceptance_scope": "operational admission supersession only; no effectiveness claim",
            "original_admission_status": "unknown, unchanged",
            "late_original_rule": "retain and report as an alternative requiring reconciliation; never count as a second observation",
        }
        raw = canonical(resolution).encode()
        if resolution_path.exists():
            if resolution_path.read_bytes() != raw:
                raise ValueError(
                    "recovery supersession metadata conflicts with lineage"
                )
        else:
            atomic_bytes(resolution_path, raw)
        resolutions[plan["id"]] = resolution
        claimed_originals.update(original_ids)
    return resolutions


def _unresolved_manifests(state):
    """Read unresolved trial attempts without replaying or mutating their events."""
    resolutions = _reconcile_completed_recoveries(state)
    superseded = {
        ident
        for resolution in resolutions.values()
        for ident in resolution["original_trial_ids"]
    }
    result = []
    for path in sorted((state / "native-trials").glob("*/manifest.json")):
        work = path.parent
        manifest = json.loads(path.read_text())
        if (
            (work / "attempt-event.json").exists()
            and not (work / "outcome-event.json").exists()
            and manifest["id"] not in superseded
        ):
            result.append(manifest)
    return result


def prepare_pair(state):
    _reconcile_completed_recoveries(state)
    unresolved = _unresolved_manifests(state)
    if unresolved:
        ids = ", ".join(item["id"] for item in unresolved)
        raise ValueError(
            f"unresolved trial attempts exist ({ids}); reconcile them or use an "
            "operator-authorized recovery for a known pair"
        )
    pair_id = str(uuid.uuid4())
    order = ["ambient-baseline", "explicit-skill"]
    random.SystemRandom().shuffle(order)
    members = [prepare("cli", state, condition, pair_id) for condition in order]
    manifests = [
        json.loads((Path(m["workspace"]) / "manifest.json").read_text())
        for m in members
    ]
    for name in ("fixture.json", "treatment-skill.md", "protocol.md", "collector.py"):
        if manifests[0]["files"][name] != manifests[1]["files"][name]:
            raise ValueError(
                "pair inputs changed during preparation; retain attempts and prepare a new pair"
            )
    pair = {
        "id": pair_id,
        "workspaces": [m["workspace"] for m in members],
        "order": order,
        "fixture_sha256": manifests[0]["files"]["fixture.json"],
    }
    path = state / "native-pairs" / (pair_id + ".json")
    atomic_bytes(path, canonical(pair).encode())
    return {"pair": str(path), **pair}


def prepare_recovery(
    pair_path,
    state,
    operator_authorized=False,
    transport_wrapper=None,
    transport_revision=None,
):
    """Create alternative executions for one known pair, preserving the originals."""
    if not operator_authorized:
        raise ValueError("recovery requires explicit operator authorization")
    if bool(transport_wrapper) != bool(transport_revision):
        raise ValueError("transport wrapper and revision must be supplied together")
    pair_path = Path(pair_path)
    pair = json.loads(pair_path.read_text())
    pair_id = pair.get("id")
    members = pair.get("workspaces")
    if (
        not isinstance(pair_id, str)
        or not isinstance(members, list)
        or len(members) != 2
    ):
        raise ValueError("recovery requires a recorded two-member pair")
    originals = []
    for member in members:
        work = Path(member)
        manifest = json.loads((work / "manifest.json").read_text())
        if manifest.get("pair_id") != pair_id or manifest.get("kind") != "cli":
            raise ValueError("pair member lineage does not match its pair record")
        if (
            not (work / "attempt-event.json").is_file()
            or (work / "outcome-event.json").exists()
        ):
            raise ValueError("recovery requires exactly unresolved original attempts")
        originals.append((work, manifest))
    if {item[1].get("treatment") for item in originals} != {
        "ambient-baseline",
        "explicit-skill",
    }:
        raise ValueError("pair treatments are incomplete or duplicated")
    expected = pair.get("fixture_sha256")
    if any(
        item[1].get("files", {}).get("fixture.json") != expected for item in originals
    ):
        raise ValueError("pair fixture lineage mismatch")
    recovery_id = str(uuid.uuid4())
    recovery_workspaces = []
    recovery_order = []
    for work, manifest in originals:
        ident = str(uuid.uuid4())
        recovery = state / "native-trials" / ident
        recovery.mkdir(parents=True, mode=0o700)
        for name, expected_digest in manifest["files"].items():
            data = (work / name).read_bytes()
            if digest(data) != expected_digest:
                raise ValueError("original frozen input changed; recovery stopped")
            atomic_bytes(recovery / name, data)
        recovery_files = dict(manifest["files"])
        recovery_transport = None
        if transport_wrapper:
            source_agent_input = (recovery / "agent-input.json").read_bytes()
            recovery_files["source-agent-input.json"] = digest(source_agent_input)
            atomic_bytes(recovery / "source-agent-input.json", source_agent_input)
            agent_input = json.loads(source_agent_input)
            agent_input["prompt"] = transport_wrapper + "\n\n" + agent_input["prompt"]
            delivered = canonical(agent_input).encode()
            atomic_bytes(recovery / "agent-input.json", delivered)
            recovery_files["agent-input.json"] = digest(delivered)
            wrapper_data = transport_wrapper.encode()
            recovery_files["transport-wrapper.txt"] = digest(wrapper_data)
            atomic_bytes(recovery / "transport-wrapper.txt", wrapper_data)
            recovery_transport = {
                "revision": transport_revision,
                "wrapper_sha256": digest(wrapper_data),
                "source_agent_input_sha256": manifest["files"]["agent-input.json"],
                "delivered_agent_input_sha256": digest(delivered),
                "delivered_prompt_sha256": digest(agent_input["prompt"].encode()),
            }
        new_manifest = {
            **manifest,
            "id": ident,
            "files": recovery_files,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "recovery_of": manifest["id"],
            "recovery_id": recovery_id,
            "recovery_role": "operator-authorized-alternative-execution",
            "transport": recovery_transport,
        }
        atomic_bytes(recovery / "manifest.json", canonical(new_manifest).encode())
        record_event(recovery, state, "attempted")
        recovery_workspaces.append(str(recovery))
        recovery_order.append(manifest["treatment"])
    recovery_pair = {
        "id": recovery_id,
        "pair_id": pair_id,
        "recovery_of_pair": pair_id,
        "workspaces": recovery_workspaces,
        "order": recovery_order,
        "fixture_sha256": expected,
        "original_pair": str(pair_path),
        "original_trial_ids": [item[1]["id"] for item in originals],
        "operator_authorized": True,
        "analysis_rule": "alternative executions; do not pool with originals as independent observations",
        "transport_revision": transport_revision,
        "transport_wrapper_sha256": digest(transport_wrapper.encode())
        if transport_wrapper
        else None,
    }
    output = state / "native-recoveries" / f"{recovery_id}.json"
    atomic_bytes(output, canonical(recovery_pair).encode())
    return {"recovery": str(output), **recovery_pair}


def grading_packet(pair_path, output):
    """Withhold assignment/runtime metadata; answers may still reveal treatment."""
    pair = json.loads(pair_path.read_text())
    members = list(pair["workspaces"])
    random.SystemRandom().shuffle(members)
    responses = []
    mapping = {}
    fixture = None
    for index, member in enumerate(members):
        work = Path(member)
        event = json.loads((work / "outcome-event.json").read_text())
        if event["payload"]["status"] != "completed":
            raise ValueError(
                "pair is incomplete; retain failures but do not score missing answers"
            )
        response = (work / "response.txt").read_bytes()
        if digest(response) != event["payload"]["files"]["response.txt"]:
            raise ValueError("response changed after outcome")
        fixture_raw = (work / "fixture.json").read_bytes()
        if digest(fixture_raw) != pair["fixture_sha256"]:
            raise ValueError("pair fixture changed")
        fixture = json.loads(fixture_raw)
        label = chr(ord("A") + index)
        responses.append({"label": label, "response": response.decode()})
        mapping[label] = event["context"]["task_id"]
    output.mkdir(parents=True, exist_ok=False)
    atomic_bytes(
        output / "grader-input.json",
        canonical(
            {
                "prompt": fixture["prompt"],
                "rubric": fixture["rubric"],
                "responses": responses,
            }
        ).encode(),
    )
    atomic_bytes(
        pair_path.with_suffix(".grading-key.json"), canonical(mapping).encode()
    )
    return {
        "grader_input": str(output / "grader-input.json"),
        "limitations": "answer style can reveal treatment; grader must use fresh context",
    }


def ingest_grade(recovery_path, state, grade_path, packet_path):
    """Validate and retain a blinded grade plus corrected response provenance."""
    recovery_path, grade_path, packet_path = map(
        Path, (recovery_path, grade_path, packet_path)
    )
    plan = json.loads(recovery_path.read_text())
    if not plan.get("operator_authorized") or plan.get("recovery_of_pair") != plan.get(
        "pair_id"
    ):
        raise ValueError(
            "grade ingestion requires an operator-authorized recovery pair"
        )
    outcomes = _completed_recovery_outcomes(plan)
    if outcomes is None:
        raise ValueError(
            "grade ingestion requires two integrity-valid completed alternatives"
        )
    grade_raw, packet_raw = grade_path.read_bytes(), packet_path.read_bytes()
    grade, packet = json.loads(grade_raw), json.loads(packet_raw)
    if grade.get("method", {}).get("input_sha256") != digest(packet_raw):
        raise ValueError("grade does not identify the supplied blinded packet")
    if set(packet) != {"prompt", "rubric", "responses"} or {
        row.get("label") for row in packet["responses"]
    } != {"A", "B"}:
        raise ValueError(
            "grader packet is not the expected blinded two-response format"
        )
    fixtures = []
    captures = []
    for workspace in plan["workspaces"]:
        work = Path(workspace)
        manifest = json.loads((work / "manifest.json").read_text())
        fixture_raw = (work / "fixture.json").read_bytes()
        if digest(fixture_raw) != plan.get("fixture_sha256"):
            raise ValueError("recovery fixture differs from its recorded pair")
        fixtures.append(json.loads(fixture_raw))
        event = json.loads((work / "outcome-event.json").read_text())
        correction_path = work / "response-correction-v1.json"
        if correction_path.is_file():
            correction = json.loads(correction_path.read_text())
            response_path = work / "response.correction-v1.txt"
            response = response_path.read_bytes()
            if (
                correction.get("trial_id") != manifest.get("id")
                or correction.get("immutable_outcome_event") != event.get("id")
                or correction.get("corrected_response_sha256") != digest(response)
                or correction.get("supersedes_for_grading")
                != "Only the corrupted response capture; does not alter the immutable outcome/event or constitute a new model run."
            ):
                raise ValueError("corrected response capture provenance is invalid")
            captures.append(
                {
                    "trial_id": manifest["id"],
                    "path": str(response_path),
                    "sha256": digest(response),
                    "revision": correction.get("revision"),
                }
            )
        else:
            response_path = work / "response.txt"
            response = response_path.read_bytes()
            event_files = event.get("payload", {}).get("files", {})
            if digest(response) != (
                event.get("payload", {}).get("response_sha256")
                or event_files.get("response.txt")
            ):
                raise ValueError("response capture differs from its immutable outcome")
            captures.append(
                {
                    "trial_id": manifest["id"],
                    "path": str(response_path),
                    "sha256": digest(response),
                    "revision": "outcome-response-v1",
                }
            )
    if any(fixture != fixtures[0] for fixture in fixtures[1:]):
        raise ValueError("recovery pair fixtures are not identical")
    fixture = fixtures[0]
    if packet.get("prompt") != fixture.get("prompt") or packet.get(
        "rubric"
    ) != fixture.get("rubric"):
        raise ValueError(
            "blinded packet prompt or rubric differs from the frozen fixture"
        )
    if {digest(row["response"].encode()) for row in packet["responses"]} != {
        item["sha256"] for item in captures
    }:
        raise ValueError(
            "blinded packet responses do not match retained response captures"
        )
    rubric = packet["rubric"]
    if not isinstance(rubric, list) or len(rubric) != 11:
        raise ValueError(
            "grader packet rubric does not match the frozen eleven-item rubric"
        )
    score_summary = []
    for response in grade.get("responses", []):
        items = response.get("items", [])
        if {item.get("rubric_item") for item in items} != set(rubric) or len(
            items
        ) != len(rubric):
            raise ValueError("grade rubric items do not match the blinded packet")
        if any(
            type(item.get("score")) is not int or item["score"] not in (0, 1, 2)
            for item in items
        ):
            raise ValueError("grade contains a score outside the retained rubric scale")
        score_summary.append(
            {
                "label": response["label"],
                "total": sum(item["score"] for item in items),
                "maximum": 2 * len(rubric),
                "items": items,
            }
        )
    if {row["label"] for row in score_summary} != {"A", "B"}:
        raise ValueError("grade response labels do not match the blinded packet")
    recovery_id = plan["id"]
    root = Path(state) / "native-recoveries"
    grade_output = root / f"{recovery_id}.grade.json"
    packet_sha = digest(packet_raw)
    grade_sha = digest(grade_raw)
    if grade_output.exists() and grade_output.read_bytes() != grade_raw:
        raise ValueError("a different raw grade is already retained for this recovery")
    atomic_bytes(grade_output, grade_raw)
    archive_files = {
        "workshop-blind-grade.json": grade_raw,
        "grader-input.json": packet_raw,
        "recovery-plan.json": recovery_path.read_bytes(),
    }
    for item in captures:
        archive_files[f"response-{item['trial_id']}.txt"] = Path(
            item["path"]
        ).read_bytes()
        workspace = Path(item["path"]).parent
        correction = workspace / "response-correction-v1.json"
        if correction.is_file():
            archive_files[f"response-correction-{item['trial_id']}.json"] = (
                correction.read_bytes()
            )
    archive = store_archive(
        MemoryStore(state),
        "shared",
        "native-blinded-grade-evidence.tar.gz",
        archive_files,
    )
    occurred = datetime.fromtimestamp(
        grade_path.stat().st_mtime, timezone.utc
    ).isoformat()
    ident = str(uuid.uuid5(uuid.UUID(recovery_id), "blinded-grade:" + grade_sha))
    record = envelope(
        {
            "pair_id": plan["pair_id"],
            "recovery_id": recovery_id,
            "grade_sha256": grade_sha,
            "packet_sha256": packet_sha,
            "rubric": rubric,
            "scores": score_summary,
            "comparative_conclusion": grade.get("comparative_conclusion"),
            "evaluation_scope": grade.get("evaluation_scope"),
            "grader_method": grade.get("method", {}).get("assessment"),
            "grader_identity": None,
            "grader_identity_missing": "The raw grade does not report an exact grader runtime or model identity.",
            "source_response_sha256": sorted(item["sha256"] for item in captures),
            "evidence_archive_sha256": archive["sha256"],
        },
        ident=ident,
        kind="evaluation",
        occurred_at=occurred,
        store="shared",
        producer="native-blinded-grader-ingest",
        version="1",
        source_schema="native-blinded-grade-v1",
        context={
            "conditions": {"pair_id": plan["pair_id"], "recovery_id": recovery_id}
        },
        relations=[
            {"relation": "evaluates-pair", "id": plan["pair_id"]},
            *[
                {"relation": "grades-response-in-pair", "id": item["trial_id"]}
                for item in captures
            ],
        ],
    )
    result = MemoryStore(state).append(record, "native-blinded-grade-ingest")
    record_raw = canonical(record).encode()
    record_path = root / f"{recovery_id}.grade-record.json"
    if record_path.exists() and record_path.read_bytes() != record_raw:
        raise ValueError(
            "a different grade record is already retained for this recovery"
        )
    atomic_bytes(record_path, record_raw)
    receipt = {
        "pair_id": plan["pair_id"],
        "recovery_id": recovery_id,
        "grade_record_id": ident,
        "grade_record_sha256": digest(record_raw),
        "grade_sha256": grade_sha,
        "packet_sha256": packet_sha,
        "packet_path": str(packet_path),
        "captured_responses": captures,
    }
    atomic_bytes(
        root / f"{recovery_id}.grade-receipt.json", canonical(receipt).encode()
    )
    return {**result, "grade_sha256": grade_sha, "packet_sha256": packet_sha}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--kind", choices=["cli", "tree"], required=True)
    commands.add_parser("prepare-pair")
    recovery = commands.add_parser("prepare-recovery")
    recovery.add_argument("--pair", type=Path, required=True)
    recovery.add_argument("--operator-authorized", action="store_true")
    recovery.add_argument("--transport-wrapper-file", type=Path)
    recovery.add_argument("--transport-revision")
    commands.add_parser("pending")
    end = commands.add_parser("finish")
    end.add_argument("--workspace", type=Path, required=True)
    end.add_argument(
        "--status",
        choices=["completed", "failed", "interrupted", "blocked", "abandoned"],
        default="completed",
    )
    end.add_argument("--reason")
    grade = commands.add_parser("grading-packet")
    grade.add_argument("--pair", type=Path, required=True)
    grade.add_argument("--output", type=Path, required=True)
    ingest = commands.add_parser("ingest-grade")
    ingest.add_argument("--recovery", type=Path, required=True)
    ingest.add_argument("--grade-json", type=Path, required=True)
    ingest.add_argument("--packet-json", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.kind, args.state)
        elif args.command == "prepare-pair":
            result = prepare_pair(args.state)
        elif args.command == "prepare-recovery":
            wrapper = (
                args.transport_wrapper_file.read_text()
                if args.transport_wrapper_file
                else None
            )
            result = prepare_recovery(
                args.pair,
                args.state,
                args.operator_authorized,
                wrapper,
                args.transport_revision,
            )
        elif args.command == "pending":
            result = pending(args.state)
        elif args.command == "grading-packet":
            result = grading_packet(args.pair, args.output)
        elif args.command == "ingest-grade":
            result = ingest_grade(
                args.recovery, args.state, args.grade_json, args.packet_json
            )
        else:
            result = finish(args.workspace, args.state, args.status, args.reason)
        print(json.dumps(result))
    except (ValueError, TypeError, OSError) as exc:
        print(
            f"trial operation failed ({type(exc).__name__}); local evidence retained",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
