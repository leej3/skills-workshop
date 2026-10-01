"""Four local writers publish independent memory refs and reconcile annex metadata."""

import argparse
import concurrent.futures
import json
import time
from pathlib import Path

from trial import PREFIX, Trial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--credential-dir", type=Path, required=True)
    parser.add_argument("--provenance-script", type=Path, required=True)
    args = parser.parse_args()
    trial = Trial(args)
    remote = trial.root / "remote.git"
    trial.git(trial.root, "shared", "init", "--bare", str(remote))
    trial.git(remote, "shared", "annex", "init", "Local burst destination")

    def writer(number):
        repo = trial.root / f"writer-{number}"
        trial.git(trial.root, "shared", "clone", str(remote), str(repo))
        for key, value in [
            ("user.name", "Workshop synthetic trial"),
            ("user.email", "codex@openai.com"),
            ("commit.gpgsign", "false"),
        ]:
            trial.git(repo, "shared", "config", key, value)
        trial.git(repo, "shared", "annex", "init", f"writer-{number}")
        # A private initial commit supplies HEAD for the batch helper's index reset.
        trial.git(
            repo,
            "shared",
            "commit",
            "--allow-empty",
            "-F",
            "-",
            input="test(memory): initialize burst writer\n\n" + trial.trailers(),
        )
        batches = []
        syncs = []
        for n in range(5):
            batch = trial.batch(
                repo,
                "shared",
                f"writer-{number}",
                [
                    {
                        "id": f"{number}-{n}-{i}",
                        "sensitive": False,
                        "text": "Synthetic burst assessment",
                    }
                    for i in range(100)
                ],
            )
            trial.git(repo, "shared", "push", "origin", batch["ref"])
            sync = trial.git(
                repo,
                "shared",
                "annex",
                "sync",
                "--only-annex",
                "--no-content",
                "origin",
                check=False,
            )
            syncs.append(sync.returncode)
            batches.append(batch)
        return {"writer": number, "batches": batches, "sync_exit_codes": syncs}

    start = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        writers = list(pool.map(writer, range(4)))
    elapsed = time.monotonic() - start
    # A final reconciliation also checks convergence after simultaneous syncs.
    for number in range(4):
        trial.git(
            trial.root / f"writer-{number}",
            "shared",
            "annex",
            "sync",
            "--only-annex",
            "--no-content",
            "origin",
        )
    refs = trial.git(
        remote, "shared", "for-each-ref", "--format=%(refname)", PREFIX
    ).splitlines()
    assert len(refs) == 20
    for writer_result in writers:
        for batch in writer_result["batches"]:
            assert batch["ref"] in refs
            assert trial.git(remote, "shared", "annex", "contentlocation", batch["key"])
    result = {
        "synthetic": True,
        "local_only": True,
        "writers": 4,
        "records": 2000,
        "batches": 20,
        "burst_seconds": round(elapsed, 3),
        "sync_exit_codes": [w["sync_exit_codes"] for w in writers],
        "all_refs_and_payloads_present": True,
    }
    (trial.root / "burst-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
