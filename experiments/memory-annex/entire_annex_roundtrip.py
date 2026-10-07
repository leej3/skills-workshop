"""Probe real Entire reads before/after annex storage and Git-tree hydration.

Uses a synthetic checkpoint from entire_probe.py, isolated local Git/annex remotes,
and no hosted service. Every fixture commit resolves fresh Codex provenance.
"""

import argparse
import io
import json
import os
import subprocess
import tarfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--entire", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--provenance-script", type=Path, required=True)
    args = parser.parse_args()
    root = args.workspace.resolve()
    root.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(DO_NOT_TRACK="1", GIT_TERMINAL_PROMPT="0")
    for name in ("CONFIG", "DATA", "STATE", "CACHE"):
        env[f"XDG_{name}_HOME"] = str(root / ("xdg-" + name.lower()))
    results = []

    def run(cwd, *command, data=None, check=True):
        p = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            input=data,
            capture_output=True,
            timeout=120,
            check=False,
        )
        results.append(
            {
                "command": list(command),
                "exit": p.returncode,
                "stdout": p.stdout.decode(errors="replace")
                if len(p.stdout) < 20000
                else "binary/large output retained separately",
                "stderr": p.stderr.decode(errors="replace"),
            }
        )
        (root / "commands.json").write_text(json.dumps(results, indent=2) + "\n")
        if check and p.returncode:
            raise RuntimeError("probe command failed; see commands.json")
        return p

    def git(cwd, *args, **kwargs):
        return run(cwd, "git", *args, **kwargs).stdout.strip().decode()

    def commit(repo, tree, ref, message):
        trailers = subprocess.check_output(
            ["bash", str(args.provenance_script)], env=env
        )
        sha = git(
            repo, "commit-tree", tree, data=(message + "\n\n").encode() + trailers
        )
        git(repo, "update-ref", ref, sha)
        return sha

    def init(repo):
        repo.mkdir()
        git(repo, "init", "-b", "main")
        git(repo, "config", "user.name", "Workshop compatibility probe")
        git(repo, "config", "user.email", "codex@openai.com")
        git(repo, "config", "commit.gpgsign", "false")

    source = args.source_repo.resolve()
    ref = git(
        source, "for-each-ref", "--format=%(refname)", "refs/entire/checkpoints/"
    ).splitlines()[0]
    ident = ref.split("/")[-1]
    archive = run(source, "git", "archive", "--format=tar", ref).stdout
    files = {}
    with tarfile.open(fileobj=io.BytesIO(archive)) as saved:
        for member in saved:
            if member.isfile():
                files[member.name] = saved.extractfile(member).read()
    (root / "checkpoint.tar").write_bytes(archive)
    writer = root / "writer"
    init(writer)
    empty = git(writer, "mktree", data=b"")
    commit(
        writer,
        empty,
        "refs/heads/main",
        "test(entire): initialize annex compatibility fixture",
    )
    git(writer, "annex", "init", "compatibility-writer")
    payload = root / "payload"
    payload.mkdir()
    git(
        writer,
        "annex",
        "initremote",
        "payload",
        "type=directory",
        f"directory={payload}",
        "encryption=none",
    )
    (writer / "checkpoint.tar").write_bytes(archive)
    git(writer, "annex", "add", "--backend=SHA256", "checkpoint.tar")
    key = git(writer, "annex", "lookupkey", "checkpoint.tar")
    (writer / "index.json").write_text(
        json.dumps({"checkpoint_ref": ref, "annex_key": key}) + "\n"
    )
    git(writer, "add", "index.json")
    tree = git(writer, "write-tree")
    commit(
        writer,
        tree,
        "refs/heads/workshop/captures/v1",
        "test(entire): index annex checkpoint on catalog branch",
    )
    git(writer, "annex", "copy", "--to=payload", "checkpoint.tar")
    metadata = root / "metadata.git"
    git(root, "init", "--bare", str(metadata))
    git(
        writer,
        "push",
        str(metadata),
        "refs/heads/workshop/captures/v1",
        "refs/heads/git-annex",
    )
    reader = root / "reader"
    run(
        root,
        "git",
        "clone",
        "--no-local",
        "--branch",
        "workshop/captures/v1",
        str(metadata),
        str(reader),
    )
    git(reader, "config", "user.name", "Workshop compatibility probe")
    git(reader, "config", "user.email", "codex@openai.com")
    git(reader, "config", "commit.gpgsign", "false")
    git(reader, "annex", "init", "compatibility-reader")
    assert not (reader / "checkpoint.tar").exists(), (
        "clone unexpectedly contains payload"
    )
    git(reader, "annex", "enableremote", "payload", f"directory={payload}")
    git(reader, "annex", "get", "--from=payload", "checkpoint.tar")
    assert (reader / "checkpoint.tar").read_bytes() == archive
    (reader / ".entire").mkdir()
    (reader / ".entire/settings.json").write_text(
        json.dumps(
            {
                "enabled": True,
                "telemetry": False,
                "checkpoints": {"primary": {"type": "git-refs"}},
            }
        )
    )
    # Build a metadata-preserving checkpoint with annex pointers at transcript paths.
    transcript_names = [name for name in files if name.endswith(".jsonl")]
    assert transcript_names
    git(reader, "read-tree", "--empty")
    for name, data in files.items():
        path = reader / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if name in transcript_names:
            git(reader, "annex", "add", "--backend=SHA256", "--", name)
        else:
            git(reader, "add", "--", name)
    pointer_tree = git(reader, "write-tree")
    commit(
        reader,
        pointer_tree,
        ref,
        "test(entire): probe annex pointers in checkpoint tree",
    )
    entire = str(args.entire.resolve())
    version = run(reader, entire, "version").stdout.decode()
    pointer = run(
        reader,
        entire,
        "checkpoint",
        "explain",
        ident,
        "--transcript",
        "--no-pager",
        check=False,
    )
    (root / "pointer-transcript.out").write_bytes(pointer.stdout)
    # Even with payload present locally, Git blob readers do not follow annex links.
    git(reader, "read-tree", "--empty")
    for name, data in files.items():
        blob = git(reader, "hash-object", "-w", "--stdin", data=data)
        git(reader, "update-index", "--add", "--cacheinfo", "100644", blob, name)
    hydrated_tree = git(reader, "write-tree")
    assert hydrated_tree == git(source, "rev-parse", ref + "^{tree}")
    commit(
        reader,
        hydrated_tree,
        ref,
        "test(entire): hydrate original checkpoint tree from annex",
    )
    read = run(
        reader, entire, "checkpoint", "explain", ident, "--transcript", "--no-pager"
    )
    parsed = run(reader, entire, "checkpoint", "explain", ident, "--json", "--no-pager")
    json.loads(parsed.stdout)
    assert read.stdout in files.values(), (
        "Entire did not return an exact stored transcript"
    )
    assert pointer.returncode != 0 or pointer.stdout != read.stdout
    (root / "hydrated-transcript.jsonl").write_bytes(read.stdout)
    (root / "metadata.json").write_bytes(parsed.stdout)
    result = {
        "entire_version": version.strip(),
        "checkpoint": ident,
        "source_ref": ref,
        "annex_key": key,
        "fresh_clone_payload_absent": True,
        "annex_roundtrip_exact": True,
        "pointer_read_exit": pointer.returncode,
        "pointer_read_matches_transcript": False,
        "hydrated_tree_exact": True,
        "entire_metadata_read": True,
        "entire_transcript_exact": True,
        "scope": "local bare metadata remote and directory annex remote; synthetic checkpoint; no hosted Entire or Brain",
    }
    (root / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
