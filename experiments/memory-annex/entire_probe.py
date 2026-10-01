"""Evaluate pinned Entire binaries against synthetic, isolated local inputs."""

import argparse
import json
import os
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--bin-dir", type=Path, required=True)
    parser.add_argument("--provenance-script", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=False)
    repo = root / "repo"
    repo.mkdir()
    env = os.environ.copy()
    env["PATH"] = str(args.bin_dir.resolve()) + os.pathsep + env["PATH"]
    for name in ("CONFIG", "DATA", "STATE", "CACHE"):
        env[f"XDG_{name}_HOME"] = str(root / ("xdg-" + name.lower()))
        env[f"ENTIRE_PLUGIN_{name}_DIR"] = str(root / ("plugin-" + name.lower()))
    env.update(
        ENTIRE_REPO_ROOT=str(repo),
        ENTIRE_BRAIN_NO_EGRESS="1",
        ENTIRE_BRAIN_LOCAL_ONLY="1",
        ENTIRE_BRAIN_NO_GLOBAL_FACTS="1",
        ENTIRE_BRAIN_DAEMON_NO_REGISTER="1",
        ENTIRE_BRAIN_DAEMON_DIR=str(root / "daemon"),
        DO_NOT_TRACK="1",
    )
    outputs = []

    def run(*cmd, check=True, input=None):
        p = subprocess.run(
            cmd,
            cwd=repo,
            env=env,
            text=True,
            input=input,
            check=False,
            capture_output=True,
            timeout=120,
        )
        outputs.append(
            {
                "command": list(cmd),
                "exit": p.returncode,
                "stdout": p.stdout,
                "stderr": p.stderr,
            }
        )
        (root / "results.json").write_text(json.dumps(outputs, indent=2) + "\n")
        print(json.dumps({"command": list(cmd), "exit": p.returncode}), flush=True)
        if check and p.returncode:
            raise RuntimeError(f"{cmd} failed; see results.json")
        return p

    run("git", "init", "-b", "main")
    run("git", "config", "user.name", "Workshop synthetic evaluation")
    run("git", "config", "user.email", "codex@openai.com")
    run("git", "config", "commit.gpgsign", "false")
    (repo / "docs").mkdir()
    (repo / "docs" / "memory.md").write_text(
        "# Synthetic memory\n\nAggregate all agents per store daily into batches of 1000 records.\n"
    )
    run("git", "add", "docs/memory.md")
    trailers = subprocess.check_output(["bash", str(args.provenance_script)], text=True)
    run(
        "git",
        "commit",
        "-F",
        "-",
        input="test(memory): initialize Entire evaluation fixture\n\n" + trailers,
    )
    transcripts = root / "transcripts"
    transcripts.mkdir()
    session = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        {
            "timestamp": now,
            "type": "session_meta",
            "payload": {"id": session, "cwd": str(repo)},
        },
        {
            "timestamp": now,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Why use daily memory aggregation?"}
                ],
            },
        },
        {
            "timestamp": now,
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": "Synthetic evidence: daily aggregation combines agents into 1000-record batches and reduces inode use.",
                    }
                ],
            },
        },
    ]
    (transcripts / f"rollout-{session}.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows)
    )
    run("entire", "version")
    run("entire-brain", "version")
    (repo / ".entire").mkdir()
    (repo / ".entire" / "settings.json").write_text(
        json.dumps(
            {
                "enabled": False,
                "telemetry": False,
                "checkpoints": {"primary": {"type": "git-refs"}},
            }
        )
        + "\n"
    )
    run("entire", "import", "codex", "--path", str(transcripts), "--dry-run")
    run("entire", "import", "codex", "--path", str(transcripts))
    run("entire", "import", "codex", "--path", str(transcripts))
    run("git", "for-each-ref", "--format=%(refname)")
    run(
        "entire-brain",
        "setup",
        "--no-backfill",
        "--no-daemon",
        "--agent",
        "none",
        "--json",
        check=False,
    )
    run(
        "entire-brain",
        "remember",
        "Synthetic decision: aggregate memory daily into 1000-record batches.",
        "--path",
        "workflow.memory.batching",
        "--agent",
        "none",
        "--json",
        check=False,
    )
    run("entire-brain", "query", "--keyword", "aggregation", "--json", check=False)
    run(
        "entire-brain",
        "query",
        "--keyword",
        "daily",
        "--source",
        "fact",
        "--json",
        check=False,
    )
    run(
        "entire-brain",
        "query",
        "--keyword",
        "aggregation",
        "--source",
        "conversation",
        "--json",
        check=False,
    )
    # Diagnostic adapter: replace only the disposable exported transcript with
    # its original Codex dialect. Preserve the compact export as evidence.
    exported = list((root / "plugin-data" / "repos").glob("**/sessions/**/*.jsonl"))
    assert len(exported) == 1
    (root / "compact-export.jsonl").write_bytes(exported[0].read_bytes())
    exported[0].write_bytes((transcripts / f"rollout-{session}.jsonl").read_bytes())
    run("entire-brain", "refresh", "history")
    result = run(
        "entire-brain",
        "query",
        "--keyword",
        "aggregation",
        "--source",
        "conversation",
        "--json",
    )
    assert json.loads(result.stdout)["results"], (
        "Original transcript was not retrievable"
    )
    run("entire-brain", "status", "--json", check=False)


if __name__ == "__main__":
    main()
