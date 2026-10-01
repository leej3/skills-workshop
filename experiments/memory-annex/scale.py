"""Local synthetic scaling benchmark; no network writes or production memories."""

import argparse
import hashlib
import json
import os
import sqlite3
import statistics
import time
import uuid
from pathlib import Path

from trial import PREFIX, Trial


def timed(action):
    start = time.perf_counter()
    value = action()
    return value, round(time.perf_counter() - start, 4)


def inventory(root, exclude_annex=False):
    size = files = directories = 0
    for base, dirs, names in os.walk(root):
        if exclude_annex and Path(base) == root and "annex" in dirs:
            dirs.remove("annex")
        directories += len(dirs)
        for name in names:
            p = Path(base) / name
            size += p.lstat().st_size
            files += 1
    return {"bytes": size, "files": files, "directories": directories}


def assessment(i):
    return {
        "id": str(uuid.UUID(int=i + 1)),
        "skill": f"skill-{i % 32}",
        "task": f"task-{i % 7}",
        "outcome": "failure" if i % 10 == 0 else "success",
        "sensitive": False,
        "text": f"Synthetic assessment {i}: retry validation improved after checking inputs",
        "evidence": "".join(
            hashlib.sha256(f"{i}/{j}".encode()).hexdigest() for j in range(12)
        ),
    }


def bench(trial, records, batch_size):
    name = f"n{records}-b{batch_size}"
    repo = trial.root / name
    repo.mkdir()
    git = lambda *args, **kwargs: trial.git(repo, "shared", *args, **kwargs)
    git("init", "-b", "main")
    git("config", "user.name", "Workshop synthetic benchmark")
    git("config", "user.email", "codex@openai.com")
    git("config", "commit.gpgsign", "false")
    git("annex", "init", name)
    (repo / "README.md").write_text("Synthetic local benchmark.\n")
    git("add", "README.md")
    git(
        "commit",
        "-F",
        "-",
        input="test(memory): initialize local scale fixture\n\n" + trial.trailers(),
    )
    result = {"records": records, "batch_size": batch_size}
    paths = []
    start = time.perf_counter()
    for first in range(0, records, batch_size):
        path = f"batch-{first:09d}.json"
        paths.append(path)
        payload = {
            "schema_version": 1,
            "synthetic": True,
            "visibility": "shared",
            "records": [
                assessment(i) for i in range(first, min(records, first + batch_size))
            ],
        }
        (repo / path).write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    result["generate_seconds"] = round(time.perf_counter() - start, 4)
    result["payload_bytes"] = sum((repo / p).stat().st_size for p in paths)
    result["batches"] = len(paths)
    _, result["annex_add_seconds"] = timed(
        lambda: git(
            "annex", "add", "--backend=SHA256", "--batch", input="\n".join(paths) + "\n"
        )
    )
    entries = {}
    for line in git("ls-files", "-s").splitlines():
        metadata, path = line.split("\t", 1)
        if path in paths:
            entries[path] = metadata.split()[1]
    keys = git(
        "annex", "lookupkey", "--batch", input="\n".join(paths) + "\n"
    ).splitlines()
    assert len(keys) == len(paths)
    refs = []
    start = time.perf_counter()
    provenance_seconds = 0
    for index, path in enumerate(paths):
        tree = git("mktree", input=f"120000 blob {entries[path]}\t{path}\n")
        trailers, elapsed = timed(trial.trailers)
        provenance_seconds += elapsed
        commit = git(
            "commit-tree",
            tree,
            input="test(memory): create synthetic batch fixture\n\n" + trailers,
        )
        refs.append((PREFIX + str(uuid.uuid4()), commit))
        if index and index % 250 == 0:
            print(f"{name}: built {index}/{len(paths)} refs", flush=True)
    git(
        "update-ref",
        "--stdin",
        input="".join(f"create {ref} {commit}\n" for ref, commit in refs),
    )
    result["ref_build_seconds_including_provenance"] = round(
        time.perf_counter() - start, 4
    )
    result["provenance_seconds"] = round(provenance_seconds, 4)
    git("reset", "--mixed", "HEAD")
    for path in paths:
        (repo / path).unlink()
    result["annex_object_inventory"] = inventory(repo / ".git/annex/objects")
    result["loose_memory_ref_inventory"] = inventory(repo / ".git/refs/workshop")
    _, result["enumerate_refs_seconds"] = timed(
        lambda: git("for-each-ref", "--format=%(refname)", PREFIX)
    )
    _, result["unused_scan_seconds"] = timed(lambda: git("annex", "unused"))
    unused = repo / ".git/annex/unused"
    assert not unused.exists() or not unused.read_text().strip()
    reader = trial.root / (name + "-reader")
    _, result["local_git_clone_seconds"] = timed(
        lambda: trial.git(
            trial.root, "shared", "clone", "--no-local", str(repo), str(reader)
        )
    )
    reader_git = lambda *args, **kwargs: trial.git(reader, "shared", *args, **kwargs)
    assert not reader_git("for-each-ref", "--format=%(refname)", PREFIX)
    result["clone_metadata_inventory"] = inventory(reader / ".git")
    _, result["fetch_all_memory_refs_seconds"] = timed(
        lambda: reader_git("fetch", "origin", PREFIX + "*:" + PREFIX + "*")
    )
    assert len(
        reader_git("for-each-ref", "--format=%(refname)", PREFIX).splitlines()
    ) == len(paths)
    result["after_ref_fetch_metadata_inventory"] = inventory(reader / ".git")
    reader_git("annex", "init", name + "-reader")
    assert reader_git("annex", "contentlocation", keys[0], check=False).returncode != 0
    _, result["get_one_batch_seconds"] = timed(
        lambda: reader_git("annex", "get", "--from=origin", "--key=" + keys[0])
    )
    locations = git(
        "annex", "contentlocation", "--batch", input="\n".join(keys) + "\n"
    ).splitlines()
    assert len(locations) == len(paths)
    # Disposable structured index built from payloads; no custom database engine.
    db = sqlite3.connect(trial.root / (name + ".sqlite"))
    db.execute(
        "CREATE TABLE records(id TEXT PRIMARY KEY, skill TEXT, outcome TEXT, batch TEXT, ordinal INTEGER)"
    )
    db.execute("CREATE INDEX by_skill_outcome ON records(skill,outcome)")
    db.execute("CREATE VIRTUAL TABLE prose USING fts5(id UNINDEXED,text)")
    start = time.perf_counter()
    for path, location in zip(paths, locations):
        rows = json.loads((repo / location).read_text())["records"]
        db.executemany(
            "INSERT INTO records VALUES(?,?,?,?,?)",
            [(r["id"], r["skill"], r["outcome"], path, i) for i, r in enumerate(rows)],
        )
        db.executemany(
            "INSERT INTO prose VALUES(?,?)", [(r["id"], r["text"]) for r in rows]
        )
    db.commit()
    result["sqlite_index_build_seconds"] = round(time.perf_counter() - start, 4)
    assert db.execute("SELECT count(*) FROM records").fetchone()[0] == records
    queries = []
    for _ in range(20):
        _, elapsed = timed(
            lambda: db.execute(
                "SELECT id,batch,ordinal FROM records WHERE skill=? AND outcome=?",
                ("skill-0", "failure"),
            ).fetchall()
        )
        queries.append(elapsed)
    result["structured_query_median_ms"] = round(statistics.median(queries) * 1000, 3)
    queries = []
    for _ in range(20):
        _, elapsed = timed(
            lambda: db.execute(
                "SELECT id FROM prose WHERE prose MATCH 'retry validation' LIMIT 20"
            ).fetchall()
        )
        queries.append(elapsed)
    result["fts_query_median_ms"] = round(statistics.median(queries) * 1000, 3)
    db.close()
    result["sqlite_bytes"] = (trial.root / (name + ".sqlite")).stat().st_size
    (trial.root / (name + "-result.json")).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps(result), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument(
        "--credential-dir",
        type=Path,
        required=True,
        help="Unused for local tests; supplied for common helper",
    )
    parser.add_argument("--provenance-script", type=Path, required=True)
    args = parser.parse_args()
    trial = Trial(args)
    results = []
    for records, batch_size in [
        (1000, 1),
        (100000, 100),
        (100000, 1000),
        (100000, 10000),
    ]:
        results.append(bench(trial, records, batch_size))
        (trial.root / "scale-results.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )


if __name__ == "__main__":
    main()
