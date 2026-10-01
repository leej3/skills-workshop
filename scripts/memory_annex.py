"""Annex transport: content first, immutable ref second, metadata sync last."""

import base64
import configparser
import json
import os
import shlex
import subprocess
import sys
import urllib.request
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.memory_store import atomic_bytes, digest

PREFIX = "refs/workshop/memory/v2/"
ARTIFACT_PREFIX = "refs/workshop/artifacts/v1/"


def credential(config, store):
    fields = dict(line.rstrip().split("=", 1) for line in sys.stdin if "=" in line)
    from urllib.parse import urlparse

    remote = config["stores"][store]
    role = os.environ.get("WORKSHOP_MEMORY_ROLE", "metadata")
    endpoints = [remote.get(role, remote["metadata"])]
    for entry in endpoints:
        url = urlparse(entry["url"])
        if fields.get("protocol") == "https" and fields.get("host") in (
            url.netloc,
            url.netloc + ":443",
        ):
            path = fields.get("path", "")
            if path == url.path.lstrip("/") or path.startswith("git-annex-p2phttp"):
                token = Path(entry["token_file"]).read_text().strip()
                print("username=" + entry["username"])
                print("password=" + token)
                return


class AnnexTransport:
    def __init__(self, root, config_path, store):
        self.config_path = Path(config_path).resolve()
        self.config = json.loads(self.config_path.read_text())
        self.store = store
        self.settings = self.config["stores"][store]
        self.repo = Path(root) / store / "transport"
        self.env = os.environ.copy()
        if self.config.get("annex_bin"):
            self.env["PATH"] = self.config["annex_bin"] + os.pathsep + self.env["PATH"]
        self.env.update(
            GIT_TERMINAL_PROMPT="0",
            GIT_CONFIG_COUNT="3",
            GIT_CONFIG_KEY_0="credential.helper",
            GIT_CONFIG_VALUE_0="",
            GIT_CONFIG_KEY_1="credential.helper",
            GIT_CONFIG_VALUE_1="!"
            + shlex.join(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    "--credential",
                    str(self.config_path),
                    store,
                ]
            ),
            GIT_CONFIG_KEY_2="credential.useHttpPath",
            GIT_CONFIG_VALUE_2="true",
        )

    def git(self, *args, input=None, check=True, role="metadata"):
        p = subprocess.run(
            ["git", *args],
            cwd=self.repo,
            env={**self.env, "WORKSHOP_MEMORY_ROLE": role},
            input=input,
            text=True,
            capture_output=True,
            check=False,
            timeout=180,
        )
        if check and p.returncode:
            # Diagnostics may contain server data; do not leak it into public logs.
            raise RuntimeError("annex/Git operation failed: " + args[0])
        return p.stdout.strip() if check else p

    def configure_remote(self, name, entry):
        request = urllib.request.Request(
            entry["url"] + "/config",
            headers={
                "User-Agent": "git-annex/workshop-memory",
                "Authorization": "Basic "
                + base64.b64encode(
                    (
                        entry["username"]
                        + ":"
                        + Path(entry["token_file"]).read_text().strip()
                    ).encode()
                ).decode(),
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            config = configparser.ConfigParser(strict=False)
            config.read_string(response.read().decode())
        if name not in self.git("remote").splitlines():
            self.git("remote", "add", name, entry["url"])
        elif self.git("remote", "get-url", name) != entry["url"]:
            raise ValueError("configured remote differs from existing transport")
        for key, value in [
            ("annex-ignore", "false"),
            ("annex-uuid", config["annex"]["uuid"]),
            ("annexUrl", config["annex"]["url"]),
        ]:
            self.git("config", f"remote.{name}.{key}", value)

    def setup(self):
        if not (self.repo / ".git").exists():
            self.repo.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.git("clone", self.settings["metadata"]["url"], ".")
            self.git("config", "user.name", "Workshop memory collector")
            self.git("config", "user.email", "codex@openai.com")
            self.git("config", "commit.gpgsign", "false")
            self.git("annex", "init", "Workshop " + self.store)
        self.configure_remote("origin", self.settings["metadata"])
        self.configure_remote(
            "payload", self.settings.get("payload", self.settings["metadata"])
        )
        self.git("config", "annex.used-refspec", "+refs/*:+HEAD")

    def __call__(self, ident, raw):
        return self._put(ident, raw, PREFIX)

    def publish_artifact(self, item, raw):
        if (
            item["store"] != self.store
            or digest(raw) != item["sha256"]
            or len(raw) != item["size"]
        ):
            raise ValueError("external artifact mismatch")
        return self._put(item["sha256"], raw, ARTIFACT_PREFIX)

    def fetch_artifact(self, item):
        if item["store"] != self.store:
            raise ValueError("artifact store mismatch")
        key = item["annex_key"]
        self.git("annex", "get", "--from=payload", "--key=" + key, role="payload")
        location = self.git("annex", "contentlocation", key)
        raw = (self.repo / location).read_bytes()
        if digest(raw) != item["sha256"] or len(raw) != item["size"]:
            raise ValueError("artifact integrity failure")
        return raw

    def _put(self, ident, raw, prefix):
        ref = prefix + ident
        filename = ident + (".json" if prefix == PREFIX else ".tar.gz")
        path = "batches/" + filename
        old = self.git("rev-parse", "--verify", ref, check=False)
        if old.returncode:
            # Fetch a remotely existing ref before creating a replacement after local loss.
            remote = self.git("ls-remote", "origin", ref)
            if remote:
                self.git("fetch", "origin", ref + ":" + ref)
                old = self.git("rev-parse", "--verify", ref, check=False)
        if old.returncode == 0:
            pointer = self.git("show", ref + ":" + path)
            key = pointer.split("/")[-1]
            # SHA256 backend key binds exact uploaded bytes, including trailing newline.
            expected = f"SHA256-s{len(raw)}--{digest(raw)}"
            if key != expected:
                raise ValueError("batch ref conflicts with outbox content")
        else:
            atomic_bytes(self.repo / path, raw)
            self.git("annex", "add", "--backend=SHA256", "--", path)
            key = self.git("annex", "lookupkey", path)
            entry = self.git("ls-files", "-s", "--", path).split()[1]
            # Nested tree contains exactly the batch pointer, never other staged files.
            tree = self.git("mktree", input=f"120000 blob {entry}\t{filename}\n")
            tree = self.git("mktree", input=f"040000 tree {tree}\tbatches\n")
            trailers = subprocess.check_output(
                ["bash", self.config["provenance_script"]], text=True
            )
            commit = self.git(
                "commit-tree",
                tree,
                input="feat(memory): publish immutable evidence batch\n\n" + trailers,
            )
            self.git("update-ref", ref, commit, "0" * 40)
            self.git("reset", "HEAD", "--", path)
            (self.repo / path).unlink()
        # Restore bytes locally if recovering only Git metadata.
        location = self.git("annex", "contentlocation", key, check=False)
        if location.returncode:
            raw_path = self.repo / "restore-payload"
            atomic_bytes(raw_path, raw)
            self.git("annex", "setkey", key, str(raw_path))
        self.git("annex", "copy", "--to=payload", "--key=" + key, role="payload")
        self.git("annex", "checkpresentkey", key, "payload", role="payload")
        self.git("push", "origin", ref)
        commit = self.git("rev-parse", ref)
        if self.git("ls-remote", "origin", ref).split()[0] != commit:
            raise ValueError("remote ref verification failed")
        self.git("annex", "sync", "--only-annex", "--no-content", "origin")
        return {"sha256": digest(raw), "key": key, "ref": ref, "commit": commit}

    def retrieve(self):
        self.git("fetch", "origin", PREFIX + "*:" + PREFIX + "*")
        for ref in self.git("for-each-ref", "--format=%(refname)", PREFIX).splitlines():
            ident = ref.removeprefix(PREFIX)
            pointer = self.git("show", ref + ":batches/" + ident + ".json")
            key = pointer.split("/")[-1]
            self.git("annex", "get", "--from=payload", "--key=" + key, role="payload")
            location = self.git("annex", "contentlocation", key)
            raw = (self.repo / location).read_bytes()
            if key != f"SHA256-s{len(raw)}--{digest(raw)}":
                raise ValueError("retrieved batch digest mismatch")
            yield ref, raw


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "--credential" and sys.argv[4] == "get":
        credential(json.loads(Path(sys.argv[2]).read_text()), sys.argv[3])
