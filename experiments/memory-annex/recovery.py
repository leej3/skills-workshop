"""Verify an existing synthetic trial's Git backup and annex content recovery."""

import argparse
import hashlib
import json
from pathlib import Path

from trial import Trial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--credential-dir", type=Path, required=True)
    args = parser.parse_args()
    trial = Trial.__new__(Trial)
    trial.root = args.workspace.resolve()
    trial.credentials = args.credential_dir.resolve()
    results = json.loads((trial.root / "results.json").read_text())
    checks = {}
    for store in ("shared", "sensitive"):
        repo = trial.root / (store + "-reader")
        batch = next(item for item in results["batches"] if item["store"] == store)
        bundle = trial.root / (store + ".bundle")
        trial.git(repo, store, "bundle", "create", str(bundle), "--all")
        trial.git(repo, store, "bundle", "verify", str(bundle))
        # No force: drop only after annex verifies another available copy.
        trial.git(
            repo, store, "annex", "drop", "--key=" + batch["key"], "--numcopies=1"
        )
        missing = trial.git(
            repo, store, "annex", "contentlocation", batch["key"], check=False
        )
        assert missing.returncode != 0
        if store == "sensitive":
            denied = trial.git(
                repo,
                store,
                "annex",
                "get",
                "--from=origin",
                "--key=" + batch["key"],
                authenticated=False,
                check=False,
            )
            assert denied.returncode != 0
            checks["anonymous_sensitive_payload_denied"] = True
        trial.git(
            repo,
            store,
            "annex",
            "get",
            "--from=origin",
            "--key=" + batch["key"],
            authenticated=store == "sensitive",
        )
        location = trial.git(repo, store, "annex", "contentlocation", batch["key"])
        assert (
            hashlib.sha256((repo / location).read_bytes()).hexdigest()
            == batch["sha256"]
        )
        checks[store + "_safe_local_drop_and_reget"] = True
        restore = trial.root / (store + "-bundle-restore.git")
        trial.git(trial.root, store, "init", "--bare", str(restore))
        trial.git(restore, store, "fetch", str(bundle), "refs/*:refs/*")
        assert trial.git(restore, store, "rev-parse", batch["ref"]) == batch["commit"]
        checks[store + "_bundle_restores_custom_ref"] = True
    (trial.root / "recovery-results.json").write_text(
        json.dumps(checks, indent=2) + "\n"
    )
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
