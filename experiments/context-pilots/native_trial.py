"""Freeze and retain account-backed native trials without a provider dependency."""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.memory_store import (
    MemoryStore,
    artifact,
    atomic_bytes,
    canonical,
    digest,
    envelope,
)

STATE = Path.home() / ".local/state/skills-workshop/memory"


def prepare(kind, state, assigned_treatment=None):
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
        "treatment": treatment,
        "prompt": prompt,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {name: digest(data) for name, data in files.items()},
        "evidence_level": "exploratory",
        "budget": "one native scheduled response; ambient host limits",
        "host_context_isolation": False,
    }
    atomic_bytes(work / "manifest.json", canonical(manifest).encode())
    return {"workspace": str(work), "treatment": treatment, "prompt": prompt}


def finish(work, state):
    manifest = json.loads((work / "manifest.json").read_text())
    attachments = []
    for name, expected in manifest["files"].items():
        data = (work / name).read_bytes()
        if digest(data) != expected:
            raise ValueError("frozen input changed")
        attachments.append(artifact(name, data))
    runtime = json.loads((work / "runtime.json").read_text())
    response = (work / "response.txt").read_bytes()
    if not response.strip():
        raise ValueError("empty response is not a completed trial")
    for name in ("manifest.json", "response.txt", "runtime.json"):
        attachments.append(artifact(name, (work / name).read_bytes()))
    packet = envelope(
        {"trial": manifest, "grade": None, "response_sha256": digest(response)},
        ident=manifest["id"],
        kind="evaluation" if manifest["kind"] == "cli" else "retrieval",
        occurred_at=manifest["created_at"],
        store="shared",
        producer="native-luna-pilot",
        version="1",
        source_schema="native-trial-v1",
        context={
            "task_id": manifest["id"],
            "agent_id": "scheduled-native",
            "runtime": runtime,
            "model": {"id": runtime["model"]} if runtime.get("model") else None,
            "skill": {
                "sha256": manifest["files"]["treatment-skill.md"],
                "exposure": manifest["treatment"],
            },
            "conditions": {
                "evidence_level": "exploratory",
                "host_context_isolation": False,
                "budget": manifest["budget"],
                "fixture_sha256": manifest["files"]["fixture.json"],
                "protocol_sha256": manifest["files"]["protocol.md"],
                "rubric_location": "fixture.json",
                "self_grading": False,
            },
        },
        artifacts=attachments,
    )
    result = MemoryStore(state).append(packet, "scheduled-native")
    atomic_bytes(
        work / "receipt.json", canonical({**result, "kind": manifest["kind"]}).encode()
    )
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, default=STATE)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--kind", choices=["cli", "tree"], required=True)
    end = commands.add_parser("finish")
    end.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = (
        prepare(args.kind, args.state)
        if args.command == "prepare"
        else finish(args.workspace, args.state)
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
