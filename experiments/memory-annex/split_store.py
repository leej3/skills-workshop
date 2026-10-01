"""Put synthetic private memory refs and payloads in different Hub repositories."""

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path

from trial import PREFIX, Trial


def configure_payload(trial, repo):
    trial.git(repo, "test", "remote", "add", "payload", trial.url("test"))
    remote_id, annex_url = trial.remote_config("test")
    for key, value in [
        ("annex-ignore", "false"),
        ("annex-uuid", remote_id),
        ("annexUrl", annex_url),
    ]:
        trial.git(repo, "test", "config", "remote.payload." + key, value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--credential-dir", type=Path, required=True)
    parser.add_argument("--provenance-script", type=Path, required=True)
    args = parser.parse_args()
    trial = Trial(args)
    results = {"synthetic": True, "checks": {}}
    # Initialize the explicitly supplied empty test repository without copying memory refs.
    bootstrap = trial.root / "payload-bootstrap"
    trial.git(trial.root, "test", "clone", trial.url("test"), str(bootstrap))
    trial.git(bootstrap, "test", "config", "user.name", "Workshop synthetic trial")
    trial.git(bootstrap, "test", "config", "user.email", "codex@openai.com")
    trial.git(bootstrap, "test", "config", "commit.gpgsign", "false")
    trial.git(bootstrap, "test", "annex", "init", "Synthetic separate payload store")
    if trial.git(
        bootstrap, "test", "rev-parse", "--verify", "HEAD", check=False
    ).returncode:
        (bootstrap / "README.md").write_text(
            "# Synthetic annex payload store\n\nMemory refs live in a separate repository.\n"
        )
        trial.git(bootstrap, "test", "add", "README.md")
        trial.git(
            bootstrap,
            "test",
            "commit",
            "-F",
            "-",
            input="test(memory): initialize separate payload store\n\n"
            + trial.trailers(),
        )
        trial.git(bootstrap, "test", "push", "origin", "HEAD:main")
    trial.remote_config("test")
    trial.git(
        bootstrap, "test", "annex", "sync", "--only-annex", "--no-content", "origin"
    )
    writer, _ = trial.clone("writer", "sensitive")
    configure_payload(trial, writer)
    # ~1 MiB with deterministic varied evidence, not a giant repeated string.
    records = [
        {
            "id": str(uuid.uuid4()),
            "sensitive": True,
            "outcome": "success",
            "text": "Synthetic assessment " + str(i),
            "evidence": "".join(
                hashlib.sha256(f"{i}/{j}".encode()).hexdigest() for j in range(12)
            ),
        }
        for i in range(1000)
    ]
    start = time.monotonic()
    batch = trial.batch(
        writer,
        "sensitive",
        "split-store-writer",
        records,
        content_remote="payload",
        content_store="test",
    )
    results["batch_creation_and_upload_seconds"] = round(time.monotonic() - start, 3)
    trial.git(writer, "sensitive", "push", "origin", batch["ref"])
    trial.git(
        writer, "sensitive", "annex", "sync", "--only-annex", "--no-content", "origin"
    )
    assert (
        trial.git(
            writer,
            "test",
            "annex",
            "checkpresentkey",
            batch["key"],
            "payload",
            check=False,
        ).returncode
        == 0
    )
    assert (
        trial.git(
            writer,
            "sensitive",
            "annex",
            "checkpresentkey",
            batch["key"],
            "origin",
            check=False,
        ).returncode
        != 0
    )
    results["checks"]["payload_only_on_test_store"] = True
    refs = trial.git(writer, "test", "ls-remote", "payload", PREFIX + "*")
    assert batch["ref"] not in refs
    results["checks"]["memory_ref_not_on_payload_remote"] = True
    reader, elapsed = trial.clone("reader", "sensitive")
    results["git_clone_seconds"] = round(elapsed, 3)
    start = time.monotonic()
    trial.git(reader, "sensitive", "fetch", "origin", batch["ref"] + ":" + batch["ref"])
    results["one_ref_fetch_seconds"] = round(time.monotonic() - start, 3)
    assert (
        trial.git(
            reader, "sensitive", "annex", "contentlocation", batch["key"], check=False
        ).returncode
        != 0
    )
    results["checks"]["metadata_fetch_did_not_download_payload"] = True
    # A metadata-only reader cannot retrieve the new object from origin.
    unavailable = trial.git(
        reader,
        "sensitive",
        "annex",
        "get",
        "--from=origin",
        "--key=" + batch["key"],
        check=False,
    )
    results["missing_origin_get_exit_code"] = unavailable.returncode
    assert (
        trial.git(
            reader, "sensitive", "annex", "contentlocation", batch["key"], check=False
        ).returncode
        != 0
    )
    results["checks"]["metadata_remote_cannot_supply_payload"] = True
    configure_payload(trial, reader)
    denied = trial.git(
        reader,
        "test",
        "annex",
        "get",
        "--from=payload",
        "--key=" + batch["key"],
        authenticated=False,
        check=False,
    )
    assert denied.returncode != 0
    results["checks"]["payload_requires_separate_credentials"] = True
    start = time.monotonic()
    trial.git(reader, "test", "annex", "get", "--from=payload", "--key=" + batch["key"])
    results["payload_get_seconds"] = round(time.monotonic() - start, 3)
    location = trial.git(reader, "sensitive", "annex", "contentlocation", batch["key"])
    assert (
        hashlib.sha256((reader / location).read_bytes()).hexdigest() == batch["sha256"]
    )
    results["checks"]["retrieved_payload_hash_matches"] = True
    results["batch"] = batch
    (trial.root / "split-results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
