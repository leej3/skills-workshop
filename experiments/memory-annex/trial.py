"""Synthetic integration trial; run through the adjacent locked Pixi environment.

Writes only new refs and synthetic payloads to the two explicitly selected stores.
Credentials are read by a Git credential helper, never placed in URLs or argv.
"""

import argparse
import base64
import concurrent.futures
import configparser
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

HOST = "hub.datalad.org"
REPOS = {"shared": "skills-workshop", "sensitive": "skills-memories-sensitive"}
PREFIX = "refs/workshop/memory/v1/"


def credential():
    if sys.argv[-1] != "get":
        return
    fields = dict(line.rstrip("\n").split("=", 1) for line in sys.stdin if "=" in line)
    store = os.environ["WORKSHOP_TRIAL_STORE"]
    if fields.get("host") not in (HOST, HOST + ":443"):
        return
    if fields.get("protocol") != "https":
        return
    path = fields.get("path", "")
    repo_path = "leej3/" + REPOS[store] + ".git"
    if not (
        path == repo_path
        or path.startswith((repo_path + "/", "git-annex-p2phttp/"))
        or path == "git-annex-p2phttp"
    ):
        return
    token = (
        (Path(os.environ["WORKSHOP_TRIAL_CREDENTIAL_DIR"]) / ("workshop-" + store))
        .read_text()
        .strip()
    )
    print("username=leej3")
    print("password=" + token)


class Trial:
    def __init__(self, args):
        self.root = args.workspace.resolve()
        self.root.mkdir(parents=True, exist_ok=False)
        self.credentials = args.credential_dir.resolve()
        self.provenance = args.provenance_script.resolve()
        self.results = {"synthetic": True, "batches": [], "checks": {}}

    def env(self, store, authenticated=True):
        env = os.environ.copy()
        # Isolate trial credentials from credential stores and interactive prompts.
        env.update(
            WORKSHOP_TRIAL_STORE=store,
            WORKSHOP_TRIAL_CREDENTIAL_DIR=str(self.credentials),
            GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_COUNT="3",
            GIT_CONFIG_KEY_0="credential.helper",
            GIT_CONFIG_VALUE_0="",
            GIT_CONFIG_KEY_1="credential.helper",
            GIT_CONFIG_VALUE_1=(
                "!"
                + shlex.quote(sys.executable)
                + " "
                + shlex.quote(str(Path(__file__).resolve()))
                + " --credential"
                if authenticated
                else ""
            ),
            GIT_CONFIG_KEY_2="credential.useHttpPath",
            GIT_CONFIG_VALUE_2="true",
        )
        return env

    def run(self, repo, store, *args, input=None, authenticated=True, check=True):
        result = subprocess.run(
            args,
            cwd=repo,
            env=self.env(store, authenticated),
            input=input,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
        if check and result.returncode:
            raise RuntimeError(f"{args}: {result.stdout}\n{result.stderr}")
        return result.stdout.strip() if check else result

    def git(self, repo, store, *args, **kwargs):
        return self.run(repo, store, "git", *args, **kwargs)

    def trailers(self):
        return subprocess.check_output(["bash", str(self.provenance)], text=True)

    def url(self, store):
        return f"https://{HOST}/leej3/{REPOS[store]}.git"

    def remote_config(self, store):
        token = (self.credentials / ("workshop-" + store)).read_text().strip()
        request = urllib.request.Request(
            self.url(store) + "/config",
            headers={
                "User-Agent": "git-annex/workshop-synthetic-trial",
                "Authorization": "Basic "
                + base64.b64encode(("leej3:" + token).encode()).decode(),
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            config = configparser.ConfigParser(strict=False)
            config.read_string(response.read().decode())
        return config["annex"]["uuid"], config["annex"]["url"]

    def clone(self, name, store, authenticated=True):
        repo = self.root / name
        start = time.monotonic()
        self.git(
            self.root,
            store,
            "clone",
            self.url(store),
            str(repo),
            authenticated=authenticated,
        )
        elapsed = time.monotonic() - start
        self.git(repo, store, "config", "user.name", "Workshop synthetic trial")
        self.git(repo, store, "config", "user.email", "codex@openai.com")
        self.git(repo, store, "config", "commit.gpgsign", "false")
        self.git(repo, store, "annex", "init", name)
        remote_id, annex_url = self.remote_config(store)
        for key, value in [
            ("annex-ignore", "false"),
            ("annex-uuid", remote_id),
            ("annexUrl", annex_url),
        ]:
            self.git(repo, store, "config", "remote.origin." + key, value)
        return repo, elapsed

    def batch(self, repo, store, writer, records):
        # Classification applies to each complete record; mixed batches are refused.
        if any(
            ("sensitive" if record["sensitive"] else "shared") != store
            for record in records
        ):
            raise ValueError("mixed-visibility batch")
        ident = str(uuid.uuid4())
        path = "batches/" + ident + ".json"
        (repo / "batches").mkdir(exist_ok=True)
        payload = (
            json.dumps(
                {
                    "schema_version": 1,
                    "batch_id": ident,
                    "synthetic": True,
                    "writer": writer,
                    "visibility": store,
                    "records": records,
                },
                sort_keys=True,
            ).encode()
            + b"\n"
        )
        (repo / path).write_bytes(payload)
        self.git(repo, store, "annex", "add", "--backend=SHA256", path)
        key = self.git(repo, store, "annex", "lookupkey", path)
        tree = self.git(repo, store, "write-tree")
        commit = self.git(
            repo,
            store,
            "commit-tree",
            tree,
            input="test(memory): add synthetic immutable batch\n\n" + self.trailers(),
        )
        ref = PREFIX + ident
        self.git(repo, store, "update-ref", ref, commit, "0" * 40)
        self.git(repo, store, "reset", "HEAD", "--", path)
        (repo / path).unlink()
        # Upload bytes before publishing the discoverable ref.
        self.git(repo, store, "annex", "copy", "--to=origin", "--key=" + key)
        return {
            "ref": ref,
            "key": key,
            "path": path,
            "commit": commit,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "records": len(records),
            "store": store,
            "writer": writer,
        }

    def execute(self):
        start = time.monotonic()
        writers = [
            self.clone("writer-a", "shared")[0],
            self.clone("writer-b", "shared")[0],
        ]
        before = [self.git(repo, "shared", "rev-parse", "HEAD") for repo in writers]
        assert len(set(before)) == 1
        batches = []
        for index, repo in enumerate(writers):
            records = [
                {
                    "id": str(uuid.uuid4()),
                    "sensitive": False,
                    "text": f"Synthetic shared observation {index}/{n}",
                }
                for n in range(100)
            ]
            batches.append(self.batch(repo, "shared", f"writer-{index}", records))
        # Both clones publish from the same starting code state, without rebasing.
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            jobs = [
                pool.submit(self.git, repo, "shared", "push", "origin", batch["ref"])
                for repo, batch in zip(writers, batches)
            ]
            for job in jobs:
                job.result()
        # Annex location logs still require their own merge/sync, separate from refs.
        for repo in writers:
            self.git(
                repo,
                "shared",
                "annex",
                "sync",
                "--only-annex",
                "--no-content",
                "origin",
            )
        assert before == [
            self.git(repo, "shared", "rev-parse", "HEAD") for repo in writers
        ]
        self.results["checks"]["concurrent_independent_ref_pushes"] = True
        self.results["checks"]["writer_main_unchanged"] = True
        sensitive, _ = self.clone("sensitive-writer", "sensitive")
        private_batch = self.batch(
            sensitive,
            "sensitive",
            "sensitive-writer",
            [
                {
                    "id": str(uuid.uuid4()),
                    "sensitive": True,
                    "text": "Synthetic private record, including an otherwise shareable portion",
                }
            ],
        )
        self.git(sensitive, "sensitive", "push", "origin", private_batch["ref"])
        self.git(
            sensitive,
            "sensitive",
            "annex",
            "sync",
            "--only-annex",
            "--no-content",
            "origin",
        )
        batches.append(private_batch)
        self.results["batches"] = batches
        for store in REPOS:
            reader, seconds = self.clone(
                store + "-reader", store, authenticated=store == "sensitive"
            )
            assert not self.git(
                reader, store, "for-each-ref", "--format=%(refname)", PREFIX
            )
            self.results["checks"][store + "_ordinary_clone_omits_memory_refs"] = True
            self.results[store + "_clone_seconds"] = round(seconds, 3)
            self.results[store + "_git_size"] = self.git(
                reader, store, "count-objects", "-v"
            )
            self.git(reader, store, "fetch", "origin", PREFIX + "*:" + PREFIX + "*")
            own = [batch for batch in batches if batch["store"] == store]
            foreign = [batch for batch in batches if batch["store"] != store]
            refs = self.git(
                reader, store, "for-each-ref", "--format=%(refname)", PREFIX
            )
            assert all(batch["ref"] in refs for batch in own)
            assert all(batch["ref"] not in refs for batch in foreign)
            self.results["checks"][store + "_routing"] = True
            for batch in own:
                assert (
                    self.git(
                        reader,
                        store,
                        "annex",
                        "contentlocation",
                        batch["key"],
                        check=False,
                    ).returncode
                    != 0
                )
                # Resolve key from the Git pointer rather than a vendor index.
                pointer = self.git(
                    reader, store, "show", batch["ref"] + ":" + batch["path"]
                )
                assert pointer.endswith("/" + batch["key"])
                self.git(
                    reader,
                    store,
                    "annex",
                    "get",
                    "--from=origin",
                    "--key=" + batch["key"],
                    authenticated=store == "sensitive",
                )
                location = self.git(
                    reader, store, "annex", "contentlocation", batch["key"]
                )
                payload = (reader / location).read_bytes()
                assert hashlib.sha256(payload).hexdigest() == batch["sha256"]
                assert len(json.loads(payload)["records"]) == batch["records"]
            self.results["checks"][store + "_fresh_retrieval_and_hash_verification"] = (
                True
            )
            self.git(reader, store, "annex", "unused")
            unused = reader / ".git/annex/unused"
            text = unused.read_text() if unused.exists() else ""
            self.results["checks"][
                store + "_default_retention_recognizes_custom_refs"
            ] = all(batch["key"] not in text for batch in own)
            assert self.results["checks"][
                store + "_default_retention_recognizes_custom_refs"
            ]
            self.git(
                reader, store, "annex", "unused", "--used-refspec=+refs/heads/*:+HEAD"
            )
            text = unused.read_text() if unused.exists() else ""
            assert all(batch["key"] in text for batch in own)
            self.git(reader, store, "annex", "unused", "--used-refspec=+refs/*:+HEAD")
            self.results["checks"][store + "_retention_negative_control"] = True
        denied = self.git(
            self.root,
            "sensitive",
            "ls-remote",
            self.url("sensitive"),
            authenticated=False,
            check=False,
        )
        assert denied.returncode != 0
        self.results["checks"]["anonymous_sensitive_git_denied"] = True
        try:
            self.batch(writers[0], "shared", "invalid", [{"sensitive": True}])
        except ValueError:
            self.results["checks"]["mixed_visibility_batch_rejected"] = True
        else:
            raise AssertionError("sensitive record accepted by shared batch")
        self.results["elapsed_seconds"] = round(time.monotonic() - start, 3)
        (self.root / "results.json").write_text(
            json.dumps(self.results, indent=2) + "\n"
        )
        print(json.dumps(self.results, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workspace", type=Path, required=True, help="New directory for trial clones"
    )
    parser.add_argument("--credential-dir", type=Path, required=True)
    parser.add_argument("--provenance-script", type=Path, required=True)
    args = parser.parse_args()
    trial = Trial(args)
    try:
        trial.execute()
    finally:
        (trial.root / "partial-results.json").write_text(
            json.dumps(trial.results, indent=2) + "\n"
        )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--credential":
        credential()
    else:
        main()
