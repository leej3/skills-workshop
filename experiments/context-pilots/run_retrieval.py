"""Compare lexical retrieval with retained native outputs and frozen inputs."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.memory_capture import store_archive
from scripts.memory_store import MemoryStore, artifact, canonical, digest, envelope


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--entire-bin", type=Path, required=True)
    parser.add_argument("--provenance-script", type=Path, required=True)
    args = parser.parse_args()
    work = args.workspace.resolve()
    work.mkdir(parents=True, exist_ok=False)
    repo = work / "corpus"
    (repo / "docs").mkdir(parents=True)
    spec_path = Path(__file__).with_name("queries.json")
    spec = json.loads(spec_path.read_text())
    corpus = {Path(p).name: (ROOT / p).read_text() for p in spec["documents"]}
    for name, body in corpus.items():
        (repo / "docs" / name).write_text(body)
    frozen = {"spec": spec, "documents": corpus}
    frozen_bytes = canonical(frozen).encode()
    (work / "frozen-inputs.json").write_bytes(frozen_bytes)
    # Deterministic heading outline supports the scheduled native tree baseline.
    tree = [
        {
            "source": name,
            "sha256": digest(body.encode()),
            "nodes": [
                {"line": i, "heading": line.lstrip("# ")}
                for i, line in enumerate(body.splitlines(), 1)
                if line.startswith("#")
            ],
        }
        for name, body in corpus.items()
    ]
    (work / "heading-tree.json").write_text(json.dumps(tree, indent=2) + "\n")
    env = os.environ.copy()
    env.update(
        PATH=str(args.entire_bin.resolve()) + os.pathsep + env["PATH"],
        XDG_CONFIG_HOME=str(work / "config"),
        XDG_CACHE_HOME=str(work / "cache"),
        XDG_DATA_HOME=str(work / "data"),
        XDG_STATE_HOME=str(work / "state"),
        INDEX_PATH=str(work / "qmd.sqlite"),
        QMD_CONFIG_DIR=str(work / "qmd-config"),
        ENTIRE_REPO_ROOT=str(repo),
        ENTIRE_PLUGIN_CONFIG_DIR=str(work / "brain-config"),
        ENTIRE_PLUGIN_DATA_DIR=str(work / "brain-data"),
        ENTIRE_PLUGIN_STATE_DIR=str(work / "brain-state"),
        ENTIRE_PLUGIN_CACHE_DIR=str(work / "brain-cache"),
        ENTIRE_BRAIN_NO_EGRESS="1",
        ENTIRE_BRAIN_LOCAL_ONLY="1",
        ENTIRE_BRAIN_NO_GLOBAL_FACTS="1",
        ENTIRE_BRAIN_DAEMON_NO_REGISTER="1",
        ENTIRE_BRAIN_DAEMON_DIR=str(work / "daemon"),
        DO_NOT_TRACK="1",
    )
    setup = []

    def run(cmd, input=None):
        started = time.perf_counter()
        p = subprocess.run(
            cmd,
            cwd=repo,
            env=env,
            input=input,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        return {
            "command": cmd,
            "exit": p.returncode,
            "stdout": p.stdout,
            "stderr": p.stderr,
            "seconds": time.perf_counter() - started,
        }

    for cmd in [
        ["git", "init", "-b", "main"],
        ["git", "config", "user.name", "Workshop retrieval fixture"],
        ["git", "config", "user.email", "codex@openai.com"],
        ["git", "config", "commit.gpgsign", "false"],
        ["git", "add", "docs"],
    ]:
        result = run(cmd)
        setup.append(result)
        assert result["exit"] == 0
    trailers = subprocess.check_output(["bash", str(args.provenance_script)], text=True)
    setup.append(
        run(
            ["git", "commit", "-F", "-"],
            input="test(retrieval): freeze comparison corpus\n\n" + trailers,
        )
    )
    qmd = str(ROOT / "experiments/context-pilots/node_modules/.bin/qmd")
    setup.append(
        run([qmd, "collection", "add", str(repo / "docs"), "--name", "corpus"])
    )
    setup.append(
        run(
            [
                "entire-brain",
                "setup",
                "--no-backfill",
                "--no-daemon",
                "--agent",
                "none",
                "--json",
            ]
        )
    )
    (work / "setup.json").write_text(json.dumps(setup, indent=2) + "\n")
    assert all(r["exit"] == 0 for r in setup), "see setup.json"
    memory = MemoryStore(args.state)
    run_id = str(uuid.uuid4())
    corpus_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    corpus_packet = envelope(
        {"fixture_sha256": digest(frozen_bytes), "files": list(corpus)},
        ident=corpus_id,
        kind="evidence",
        occurred_at=now,
        store="shared",
        producer="workshop-retrieval-pilot",
        version="1",
        source_schema="corpus-v1",
        context={
            "task_id": run_id,
            "conditions": {"synthetic": False, "public_documents_only": True},
        },
        artifacts=[
            artifact("frozen-inputs.json", frozen_bytes, "application/json"),
            artifact("protocol.py", Path(__file__).read_bytes(), "text/x-python"),
        ],
    )
    corpus_packet["external_artifacts"] = [
        store_archive(
            memory,
            "shared",
            "setup-log.tar.gz",
            {"setup.json": canonical(setup).encode()},
        )
    ]
    memory.append(corpus_packet, "retrieval-pilot")
    db = sqlite3.connect(work / "baseline.sqlite")
    db.execute("CREATE VIRTUAL TABLE docs USING fts5(name UNINDEXED,body)")
    db.executemany("INSERT INTO docs VALUES(?,?)", corpus.items())
    db.commit()
    results = []
    for query in spec["queries"]:
        for provider, version in [
            ("sqlite", sqlite3.sqlite_version),
            ("qmd", "2.8.3"),
            ("brain", "0.1.0"),
        ]:
            parse_error = False
            if provider == "sqlite":
                start = time.perf_counter()
                # Phrase escaping makes punctuation safe; same literal query is passed to all providers.
                hits = [
                    {"file": r[0]}
                    for r in db.execute(
                        "SELECT name FROM docs WHERE docs MATCH ? ORDER BY bm25(docs) LIMIT 5",
                        ('"' + query["query"].replace('"', '""') + '"',),
                    )
                ]
                native = {
                    "exit": 0,
                    "stdout": json.dumps(hits),
                    "stderr": "",
                    "seconds": time.perf_counter() - start,
                    "command": ["sqlite-fts5", query["query"]],
                }
            else:
                cmd = (
                    [qmd, "search", query["query"], "--json", "-n", "5"]
                    if provider == "qmd"
                    else [
                        "entire-brain",
                        "query",
                        "--keyword",
                        query["query"],
                        "--source",
                        "doc",
                        "--limit",
                        "5",
                        "--json",
                    ]
                )
                native = run(cmd)
                try:
                    parsed = json.loads(native["stdout"])
                    hits = (
                        parsed
                        if isinstance(parsed, list)
                        else parsed.get("results", [])
                    )
                except (ValueError, AttributeError):
                    hits = []
                    parse_error = True
            paths = [h.get("file", h.get("path", "")) for h in hits]
            success = (
                (
                    any(p.endswith(query["expected"]) for p in paths)
                    if query["expected"]
                    else not hits
                )
                if native["exit"] == 0 and not parse_error
                else None
            )
            result = {
                "provider": provider,
                "query_id": query["id"],
                "paths": paths,
                "expected_source_hit_at_5": success,
                "seconds": native["seconds"],
                "exit": native["exit"],
                "parse_error": parse_error,
            }
            results.append(result)
            context = {
                "task_id": run_id,
                "agent_id": "deterministic-pilot",
                "runtime": {"python": sys.version.split()[0]},
                "conditions": {
                    "fixture_sha256": digest(frozen_bytes),
                    "protocol_sha256": digest(Path(__file__).read_bytes()),
                    "query": query,
                    "mode": "lexical",
                    "metric": "expected_source_hit_at_5",
                    "evidence_level": "exploratory",
                    "startup_included": provider != "sqlite",
                    "model_calls": False,
                },
            }
            packet = envelope(
                result,
                ident=str(uuid.uuid4()),
                kind="retrieval",
                occurred_at=now,
                store="shared",
                producer=provider,
                version=version,
                source_schema="native-query-result",
                context=context,
                relations=[{"relation": "corpus", "id": corpus_id}],
            )
            packet["external_artifacts"] = [
                store_archive(
                    memory,
                    "shared",
                    "query-log.tar.gz",
                    {"native-output.json": canonical(native).encode()},
                )
            ]
            memory.append(packet, "retrieval-pilot")
    db.close()
    (work / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps({"run_id": run_id, "queries": len(results), "results": results}))


if __name__ == "__main__":
    main()
