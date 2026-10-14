"""Probe gwq in disposable repositories without changing user configuration.

Run from the Workshop Pixi environment so git-annex is available:
    pixi run python experiments/gwq-worktrees/probe.py /absolute/path/to/gwq

The probe retains its temporary directory and emits observed results.
It does not patch gwq, install it, or access real repositories.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(tempfile.mkdtemp(prefix="gwq-probe-")).resolve()
home = root / "home"
home.mkdir(exist_ok=True)
env = dict(
    os.environ,
    HOME=str(home),
    XDG_CONFIG_HOME=str(home / ".config"),
    GIT_CONFIG_GLOBAL=os.devnull,
    GIT_CONFIG_NOSYSTEM="1",
    GIT_AUTHOR_NAME="Fixture",
    GIT_AUTHOR_EMAIL="fixture@example.org",
    GIT_COMMITTER_NAME="Fixture",
    GIT_COMMITTER_EMAIL="fixture@example.org",
    GIT_TERMINAL_PROMPT="0",
)
binary = Path(sys.argv[1]).resolve()
results = {}


def call(cwd, args, *, check=True, timeout=10):
    try:
        p = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"code": "timeout", "stdout": "", "stderr": "timed out"}
    out = {"code": p.returncode, "stdout": p.stdout, "stderr": p.stderr}
    if check and p.returncode:
        raise RuntimeError(out)
    return out


def git(repo, *args, check=True):
    return call(repo, ["git", *args], check=check)


def gwq(repo, *args, check=True):
    return call(repo, [str(binary), *args], check=check)


def init(path, remote):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-b", "main")
    (path / "file").write_text("fixture\n")
    git(path, "add", "file")
    git(path, "commit", "-m", "test: initialize disposable repository")
    git(path, "remote", "add", "origin", remote)


repo = home / "code/repo"
module_source = home / "code/module-source"
init(repo, "https://github.com/fixture/project.git")
init(module_source, "https://github.com/fixture/module.git")
detached = home / ".codex/worktrees/a/repo"
linked = home / ".local/share/wt-utils/worktrees/b/repo"
ghost = home / ".codex/worktrees/ghost/repo"
git(repo, "worktree", "add", "--detach", str(detached))
git(repo, "worktree", "add", "-b", "human-branch", str(linked))
git(repo, "worktree", "add", "-b", "missing-branch", str(ghost))
shutil.rmtree(ghost)
results["version"] = gwq(root, "--version")
results["local_list"] = gwq(repo, "list", "--json")
results["local_display"] = gwq(repo, "list")
results["detached_get"] = gwq(repo, "get", str(detached))
results["ambiguous_get"] = gwq(repo, "get", "repo", check=False)
gwq(root, "config", "set", "worktree.basedir", str(home))
gwq(
    root,
    "config",
    "set",
    "naming.template",
    ".local/share/gwq/worktrees/{{.Host}}/{{.Owner}}/{{.Repository}}/{{.Branch}}",
)
results["global_list"] = gwq(root, "list", "-g", "--json")
results["create_with_common_root"] = gwq(repo, "add", "-b", "probe-created")
results["after_create"] = gwq(repo, "list", "--json")
# Global traversal through symlink-only roots is checked separately.
symlink_root = root / "symlink-root"
symlink_root.mkdir(exist_ok=True)
(symlink_root / "codex").symlink_to(home / ".codex/worktrees", target_is_directory=True)
(symlink_root / "wt").symlink_to(
    home / ".local/share/wt-utils/worktrees", target_is_directory=True
)
gwq(root, "config", "set", "worktree.basedir", str(symlink_root))
results["symlink_discovery"] = gwq(root, "list", "-g", "--json")
gwq(root, "config", "set", "worktree.basedir", str(home))
# An absorbed ordinary submodule and a linked worktree of that submodule.
git(
    repo,
    "-c",
    "protocol.file.allow=always",
    "submodule",
    "add",
    str(module_source),
    "module",
)
git(repo, "submodule", "absorbgitdirs")
git(repo, "commit", "-am", "test: add disposable submodule")
module = repo / "module"
results["absorbed_module_git_list"] = git(module, "worktree", "list", "--porcelain")
results["absorbed_module_gwq_list"] = gwq(module, "list", "--json")
results["absorbed_module_add"] = gwq(
    module, "add", "-b", "module-probe", str(home / "module-linked"), check=False
)
results["absorbed_module_after_add"] = gwq(module, "list", "--json")
git(module, "remote", "set-url", "origin", "https://github.com/fixture/module.git")
results["global_after_submodule"] = gwq(root, "list", "-g", "--json")
results["absorbed_main_get"] = gwq(module, "get", "main")
child = root / "child-shell"
child.write_text("#!/bin/sh\npwd\n")
child.chmod(0o755)
env["SHELL"] = str(child)
results["absorbed_main_cd"] = gwq(module, "cd", "main")
dirty = home / "dirty-linked"
git(repo, "worktree", "add", "-b", "dirty-probe", str(dirty))
(dirty / "file").write_text("do not remove\n")
results["dirty_remove"] = gwq(repo, "remove", "dirty-probe", check=False)
results["dirty_survives"] = dirty.is_dir()
# Compare ignored-file removal with ordinary Git restrictions.
ignored = home / "ignored-linked"
git(repo, "worktree", "add", "-b", "ignored-probe", str(ignored))
(ignored / "ignored-data").write_text("keep me\n")
common = Path(git(repo, "rev-parse", "--git-common-dir")["stdout"].strip())
common = common if common.is_absolute() else repo / common
(common / "info/exclude").write_text("ignored-data\n")
results["ignored_remove"] = gwq(repo, "remove", "ignored-probe", check=False)
results["ignored_content_survives"] = (ignored / "ignored-data").exists()
# Annex content exists only in the module's primary checkout.
annex_source = home / "code/annex-source"
init(annex_source, "https://github.com/fixture/annex.git")
git(annex_source, "annex", "init", "fixture annex source")
(annex_source / "payload.bin").write_bytes(b"annex fixture payload")
git(annex_source, "annex", "add", "payload.bin")
git(annex_source, "commit", "-m", "test: add disposable annex content")
git(
    repo,
    "-c",
    "protocol.file.allow=always",
    "submodule",
    "add",
    str(annex_source),
    "annex-module",
)
git(repo, "submodule", "absorbgitdirs")
git(repo, "commit", "-am", "test: add disposable annex submodule")
annex_module = repo / "annex-module"
git(annex_module, "annex", "init", "fixture annex submodule")
git(annex_module, "-c", "protocol.file.allow=always", "annex", "get", "payload.bin")
results["annex_module_list"] = gwq(annex_module, "list", "--json")
annex_linked = home / "annex-linked"
results["annex_module_add"] = gwq(
    annex_module, "add", "-b", "annex-probe", str(annex_linked), check=False
)
if annex_linked.exists():
    results["annex_linked_git_status"] = git(
        annex_linked, "status", "--porcelain", check=False
    )
    results["annex_linked_content"] = (annex_linked / "payload.bin").exists()
    results["annex_linked_annex_init"] = git(
        annex_linked, "annex", "init", "fixture annex linked", check=False
    )
    results["annex_linked_annex_get"] = git(
        annex_linked, "annex", "get", "payload.bin", check=False
    )
    results["annex_linked_content_after_get"] = (annex_linked / "payload.bin").exists()
(root / "results-release.json").write_text(json.dumps(results, indent=2))
for key, value in results.items():
    print(key, json.dumps(value))
