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
)

STATE = Path.home() / ".local/state/skills-workshop/memory"


def prepare(kind, state, assigned_treatment=None, pair_id=None):
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
            for name in ("response.txt", "runtime.json", "failure.txt"):
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
    """Replay persisted events after crashes; report unresolved attempts without guessing death."""
    result = []
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
        if not (work / "outcome-event.json").exists():
            result.append(
                {"trial_id": json.loads(path.read_text())["id"], "workspace": str(work)}
            )
    return {"unresolved": result}


def prepare_pair(state):
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--kind", choices=["cli", "tree"], required=True)
    commands.add_parser("prepare-pair")
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
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare(args.kind, args.state)
        elif args.command == "prepare-pair":
            result = prepare_pair(args.state)
        elif args.command == "pending":
            result = pending(args.state)
        elif args.command == "grading-packet":
            result = grading_packet(args.pair, args.output)
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
