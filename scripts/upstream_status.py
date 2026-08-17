#!/usr/bin/env python3
"""Inspect upstream lifecycle state and the trust posture of workshop skills.

The update command is a planner by default.  It only moves a submodule checkout
when ``--apply`` is supplied and all safety checks pass; it never stages or
commits the resulting superproject gitlink change.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tomllib

try:
    from .materialization_metadata import lock_bundle
except ImportError:  # Direct execution: python scripts/upstream_status.py
    from materialization_metadata import lock_bundle

REPOSITORY = Path(__file__).resolve().parents[1]
REGISTRY = REPOSITORY / "registry.toml"
TRUST_REGISTRY = REPOSITORY / "policy" / "trust.toml"
REVIEW_STATES = ("unreviewed", "in-review", "reviewed", "rejected")
LICENSE_NAMES = re.compile(
    r"^(?:licen[cs]e|copying|copyright|notice)(?:[._-].*)?$", re.IGNORECASE
)
SCRIPT_SUFFIXES = {
    ".bash",
    ".fish",
    ".js",
    ".mjs",
    ".pl",
    ".ps1",
    ".py",
    ".rb",
    ".sh",
    ".ts",
    ".zsh",
}
NETWORK_PATTERNS = {
    "url": re.compile(r"https?://", re.IGNORECASE),
    "download-command": re.compile(r"\b(?:curl|wget)\b", re.IGNORECASE),
    "network-library": re.compile(
        r"\b(?:requests|httpx|urllib|aiohttp|fetch|socket)\b", re.IGNORECASE
    ),
    "remote-service": re.compile(
        r"\b(?:api|github|gitlab|s3|ssh|remote endpoint)\b", re.IGNORECASE
    ),
}
CREDENTIAL_PATTERNS = {
    "secret-name": re.compile(
        r"\b[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|PASSWORD|SECRET|CREDENTIALS?)\b"
    ),
    "environment-access": re.compile(
        r"\b(?:getenv|os\.environ|process\.env|\.env\b)", re.IGNORECASE
    ),
    "authentication": re.compile(
        r"\b(?:authorization|authenticate|bearer token|secret manager)\b",
        re.IGNORECASE,
    ),
}
TEXT_FILE_LIMIT = 1_000_000


def load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML document."""
    with path.open("rb") as stream:
        return tomllib.load(stream)


def git(
    path: Path, *arguments: str, check: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run Git without invoking a shell."""
    return subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=check,
        capture_output=True,
        text=True,
    )


def git_text(path: Path, *arguments: str) -> str | None:
    """Return stripped Git output, or None when the command fails."""
    result = git(path, *arguments)
    return (
        result.stdout.strip()
        if result.returncode == 0 and result.stdout.strip()
        else None
    )


def normalize_remote_url(url: str | None) -> str | None:
    """Normalize common GitHub SSH and HTTPS spellings for comparison."""
    if not url:
        return None
    value = url.strip().rstrip("/")
    scp = re.match(r"^(?:[^@]+@)?([^:]+):(.+)$", value)
    if scp and "://" not in value:
        value = f"{scp.group(1)}/{scp.group(2)}"
    else:
        value = re.sub(r"^[a-z][a-z0-9+.-]*://", "", value, flags=re.IGNORECASE)
        value = re.sub(r"^[^@/]+@", "", value)
    return re.sub(r"\.git$", "", value).lower()


def registered_upstreams() -> list[dict[str, Any]]:
    """Load and validate registered upstream records."""
    data = load_toml(REGISTRY)
    records = data.get("upstreams", [])
    if not isinstance(records, list):
        raise TypeError("registry.toml: upstreams must be an array")
    seen_names: set[str] = set()
    seen_paths: set[str] = set()
    for record in records:
        missing = {"name", "path", "url", "fork_url"} - record.keys()
        if missing:
            raise ValueError(
                f"registry.toml: upstream record is missing {', '.join(sorted(missing))}"
            )
        if record["name"] in seen_names or record["path"] in seen_paths:
            raise ValueError(
                f"registry.toml: duplicate upstream {record['name']!r} or path"
            )
        path = (REPOSITORY / record["path"]).resolve()
        if REPOSITORY not in path.parents:
            raise ValueError(f"registry.toml: path escapes workshop: {record['path']}")
        seen_names.add(record["name"])
        seen_paths.add(record["path"])
    return records


def find_upstream(name: str) -> dict[str, Any]:
    """Find a registered upstream by name."""
    for record in registered_upstreams():
        if record["name"] == name:
            return record
    choices = ", ".join(record["name"] for record in registered_upstreams())
    raise ValueError(f"unknown upstream {name!r}; choose one of: {choices}")


def gitlink_revision(relative_path: str, *, index: bool = False) -> str | None:
    """Return the superproject's index or HEAD gitlink revision."""
    if index:
        result = git(REPOSITORY, "ls-files", "--stage", "--", relative_path)
        fields = result.stdout.split()
        if result.returncode == 0 and len(fields) >= 2 and fields[0] == "160000":
            return fields[1]
        return None
    result = git(REPOSITORY, "ls-tree", "HEAD", "--", relative_path)
    fields = result.stdout.split()
    if result.returncode == 0 and len(fields) >= 3 and fields[0] == "160000":
        return fields[2]
    return None


def remote_ref(
    path: Path, remote: str, requested: str | None = None
) -> tuple[str, str] | None:
    """Resolve a requested or inferred remote-tracking branch and its commit."""
    candidates: list[str] = []
    if requested:
        if requested.startswith(f"refs/remotes/{remote}/"):
            candidates.append(requested)
        elif requested.startswith(f"{remote}/"):
            candidates.append(f"refs/remotes/{requested}")
        elif not requested.startswith("refs/") and not re.match(
            r"^(?:origin|upstream)/", requested
        ):
            candidates.append(f"refs/remotes/{remote}/{requested}")
    else:
        symbolic = git_text(path, "symbolic-ref", f"refs/remotes/{remote}/HEAD")
        if symbolic:
            candidates.append(symbolic)
        branch = git_text(path, "symbolic-ref", "--short", "HEAD")
        if branch:
            candidates.append(f"refs/remotes/{remote}/{branch}")
        candidates.extend(
            (
                f"refs/remotes/{remote}/main",
                f"refs/remotes/{remote}/master",
            )
        )
        refs = git_text(
            path,
            "for-each-ref",
            "--format=%(refname)",
            f"refs/remotes/{remote}",
        )
        if refs:
            candidates.extend(
                ref for ref in refs.splitlines() if ref != f"refs/remotes/{remote}/HEAD"
            )
    for candidate in dict.fromkeys(candidates):
        revision = git_text(path, "rev-parse", "--verify", f"{candidate}^{{commit}}")
        if revision:
            return candidate.removeprefix("refs/remotes/"), revision
    return None


def ahead_behind(
    path: Path, left: str | None, right: str | None
) -> dict[str, int] | None:
    """Return commits unique to left (ahead) and right (behind)."""
    if not left or not right:
        return None
    result = git(path, "rev-list", "--left-right", "--count", f"{left}...{right}")
    if result.returncode != 0:
        return None
    fields = result.stdout.split()
    if len(fields) != 2:
        return None
    return {"ahead": int(fields[0]), "behind": int(fields[1])}


def configured_remote(path: Path, remote: str) -> str | None:
    """Return a remote's fetch URL."""
    return git_text(path, "remote", "get-url", remote)


def verify_remote(path: Path, remote: str, expected: str) -> None:
    """Refuse network or update work against an unexpected remote."""
    actual = configured_remote(path, remote)
    if normalize_remote_url(actual) != normalize_remote_url(expected):
        raise RuntimeError(
            f"{path}: {remote} URL is {actual!r}, expected {expected!r}; "
            "run the workshop's configure-upstreams command first"
        )


def fetch_remote(path: Path, remote: str, expected: str) -> None:
    """Fetch a verified remote without changing the checkout."""
    verify_remote(path, remote, expected)
    result = git(path, "fetch", "--prune", remote)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"fetch failed for {path.name}/{remote}: {message}")


def relationships() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read bundle entries and materialization skill records."""
    bundles: list[dict[str, Any]] = []
    bundle_dir = REPOSITORY / "bundles"
    if bundle_dir.is_dir():
        for path in sorted(bundle_dir.glob("*.toml")):
            manifest = load_toml(path)
            for skill in manifest.get("skills", []):
                bundles.append(
                    {
                        "bundle": manifest.get("name", path.stem),
                        "manifest": path.relative_to(REPOSITORY).as_posix(),
                        "name": skill.get("name"),
                        "source": skill.get("source"),
                    }
                )

    materializations: list[dict[str, Any]] = []
    lock_dir = REPOSITORY / "materializations"
    if lock_dir.is_dir():
        for path in sorted(lock_dir.glob("*.lock.json")):
            try:
                lock = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as error:
                materializations.append(
                    {
                        "lock": path.relative_to(REPOSITORY).as_posix(),
                        "error": str(error),
                        "source": None,
                    }
                )
                continue
            project = lock.get("project", {})
            bundle = lock_bundle(lock, context=f"materialization lock {path}")
            for skill in lock.get("skills", []):
                materializations.append(
                    {
                        "lock": path.relative_to(REPOSITORY).as_posix(),
                        "project": project.get("id"),
                        "bundle": bundle,
                        "name": skill.get("name"),
                        "source": skill.get("source"),
                        "status": skill.get("status"),
                    }
                )
    return bundles, materializations


def affected_relationships(
    prefix: str, changed_sources: set[str] | None = None
) -> dict[str, list[dict[str, Any]]]:
    """Return bundle and project relationships below a source prefix."""
    bundles, materializations = relationships()

    def relevant(item: dict[str, Any]) -> bool:
        source = item.get("source")
        if not isinstance(source, str) or not (
            source == prefix or source.startswith(prefix.rstrip("/") + "/")
        ):
            return False
        return changed_sources is None or source in changed_sources

    bundle_rows = [item for item in bundles if relevant(item)]
    materialization_rows = [item for item in materializations if relevant(item)]
    return {
        "bundles": bundle_rows,
        "materializations": materialization_rows,
    }


def upstream_status(record: dict[str, Any], fetch: bool = False) -> dict[str, Any]:
    """Build one upstream lifecycle record."""
    path = (REPOSITORY / record["path"]).resolve()
    if not (path / ".git").exists():
        return {
            "name": record["name"],
            "path": record["path"],
            "initialized": False,
            "error": "submodule is not initialized",
            "affected": affected_relationships(record["path"]),
        }
    if fetch:
        fetch_remote(path, "origin", record["fork_url"])
        fetch_remote(path, "upstream", record["url"])
    fork = remote_ref(path, "origin")
    canonical = remote_ref(path, "upstream")
    pinned = gitlink_revision(record["path"])
    indexed = gitlink_revision(record["path"], index=True)
    local = git_text(path, "rev-parse", "HEAD")
    dirty = not submodule_worktree_clean(path)
    fork_revision = fork[1] if fork else None
    upstream_revision = canonical[1] if canonical else None
    return {
        "name": record["name"],
        "path": record["path"],
        "role": record.get("role"),
        "initialized": True,
        "pinned_revision": pinned,
        "index_revision": indexed,
        "local_revision": local,
        "fork": {
            "url": record["fork_url"],
            "configured_url": configured_remote(path, "origin"),
            "ref": fork[0] if fork else None,
            "revision": fork_revision,
        },
        "upstream": {
            "url": record["url"],
            "configured_url": configured_remote(path, "upstream"),
            "ref": canonical[0] if canonical else None,
            "revision": upstream_revision,
        },
        "fork_vs_upstream": ahead_behind(path, fork_revision, upstream_revision),
        "pinned_vs_fork": ahead_behind(path, pinned, fork_revision),
        "pinned_vs_upstream": ahead_behind(path, pinned, upstream_revision),
        "dirty": dirty,
        "affected": affected_relationships(record["path"]),
    }


def all_upstream_status(fetch: bool = False) -> list[dict[str, Any]]:
    """Build lifecycle records for every registered upstream."""
    return [upstream_status(record, fetch=fetch) for record in registered_upstreams()]


def changed_files(path: Path, old: str, new: str) -> list[dict[str, str]]:
    """Return name-status records between two revisions."""
    result = git(path, "diff", "--name-status", "--find-renames", old, new, "--")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "could not calculate update diff")
    rows: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        row = {"status": fields[0], "path": fields[-1]}
        if len(fields) == 3:
            row["old_path"] = fields[1]
        rows.append(row)
    return rows


def skill_roots_at(path: Path, revision: str) -> set[str]:
    """Find skill directories recorded at a Git revision."""
    result = git(path, "ls-tree", "-r", "--name-only", revision)
    if result.returncode != 0:
        return set()
    return {
        filename.removesuffix("/SKILL.md")
        for filename in result.stdout.splitlines()
        if filename == "SKILL.md" or filename.endswith("/SKILL.md")
    }


def changed_skill_sources(
    record: dict[str, Any], path: Path, old: str, new: str, files: list[dict[str, str]]
) -> set[str]:
    """Map changed paths onto skill identities present at either revision."""
    roots = skill_roots_at(path, old) | skill_roots_at(path, new)
    changed_paths = {
        candidate
        for row in files
        for candidate in (row.get("path"), row.get("old_path"))
        if candidate
    }
    sources: set[str] = set()
    for root in roots:
        if any(
            item == root or item.startswith(root.rstrip("/") + "/")
            for item in changed_paths
        ):
            suffix = f"/{root}" if root else ""
            sources.add(record["path"].rstrip("/") + suffix)
    return sources


def superproject_path_clean(relative_path: str) -> bool:
    """Check that the superproject has no staged or unstaged gitlink delta."""
    unstaged = git(REPOSITORY, "diff", "--quiet", "--", relative_path)
    staged = git(REPOSITORY, "diff", "--cached", "--quiet", "--", relative_path)
    return unstaged.returncode == 0 and staged.returncode == 0


def submodule_worktree_clean(path: Path) -> bool:
    """Return true only when Git successfully reports an empty worktree status."""
    result = git(path, "status", "--porcelain")
    return result.returncode == 0 and not result.stdout.strip()


def plan_update(
    record: dict[str, Any], remote: str, requested_ref: str | None, fetch: bool
) -> dict[str, Any]:
    """Plan a safe fast-forward update for one registered submodule."""
    path = (REPOSITORY / record["path"]).resolve()
    expected_url = record["fork_url"] if remote == "origin" else record["url"]
    if not (path / ".git").exists():
        raise RuntimeError(f"submodule is not initialized: {record['path']}")
    verify_remote(path, remote, expected_url)
    if fetch:
        fetch_remote(path, remote, expected_url)
    target = remote_ref(path, remote, requested_ref)
    if not target:
        hint = "; use --fetch to refresh remote-tracking refs" if not fetch else ""
        raise RuntimeError(f"cannot resolve {remote} target{hint}")
    target_ref, target_revision = target
    pinned = gitlink_revision(record["path"])
    indexed = gitlink_revision(record["path"], index=True)
    local = git_text(path, "rev-parse", "HEAD")
    clean = submodule_worktree_clean(path)
    fast_forward = bool(
        local
        and git(path, "merge-base", "--is-ancestor", local, target_revision).returncode
        == 0
    )
    checks = {
        "submodule_worktree_clean": clean,
        "checkout_matches_pinned_revision": bool(local and local == pinned),
        "index_matches_pinned_revision": bool(indexed and indexed == pinned),
        "superproject_gitlink_clean": superproject_path_clean(record["path"]),
        "target_is_fast_forward": fast_forward,
    }
    files = changed_files(path, local, target_revision) if local else []
    changed_sources = (
        changed_skill_sources(record, path, local, target_revision, files)
        if local
        else set()
    )
    return {
        "schema_version": 1,
        "operation": "update-submodule-pin",
        "dry_run": True,
        "name": record["name"],
        "path": record["path"],
        "remote": remote,
        "target_ref": target_ref,
        "current_revision": local,
        "pinned_revision": pinned,
        "target_revision": target_revision,
        "up_to_date": local == target_revision,
        "checks": checks,
        "safe_to_apply": all(checks.values()),
        "changed_files": files,
        "changed_skill_sources": sorted(changed_sources),
        "affected": affected_relationships(record["path"], changed_sources),
        "apply_effect": (
            "move the submodule checkout only; review and commit the gitlink in the "
            "workshop separately"
        ),
    }


def apply_update(plan: dict[str, Any]) -> dict[str, Any]:
    """Apply a previously validated update plan."""
    if (
        plan.get("schema_version") != 1
        or plan.get("operation") != "update-submodule-pin"
    ):
        raise RuntimeError("unsupported or invalid update plan")
    if plan.get("remote") not in {"origin", "upstream"}:
        raise RuntimeError("update plan names an unsupported remote")
    if not plan["safe_to_apply"]:
        failed = ", ".join(name for name, ok in plan["checks"].items() if not ok)
        raise RuntimeError(f"refusing unsafe update; failed checks: {failed}")
    record = find_upstream(plan["name"])
    if record["path"] != plan["path"]:
        raise RuntimeError("planned upstream path no longer matches the registry")
    path = (REPOSITORY / record["path"]).resolve()
    expected_url = record["fork_url"] if plan["remote"] == "origin" else record["url"]
    verify_remote(path, plan["remote"], expected_url)
    current = git_text(path, "rev-parse", "HEAD")
    pinned = gitlink_revision(plan["path"])
    indexed = gitlink_revision(plan["path"], index=True)
    target = remote_ref(path, plan["remote"], plan["target_ref"])
    rechecks = {
        "submodule_worktree_clean": submodule_worktree_clean(path),
        "checkout_matches_planned_revision": bool(
            current and current == plan["current_revision"]
        ),
        "checkout_matches_pinned_revision": bool(current and current == pinned),
        "pinned_matches_planned_revision": bool(
            pinned and pinned == plan["pinned_revision"]
        ),
        "index_matches_pinned_revision": bool(indexed and indexed == pinned),
        "superproject_gitlink_clean": superproject_path_clean(plan["path"]),
        "target_ref_unchanged": bool(target and target[1] == plan["target_revision"]),
        "target_is_fast_forward": bool(
            current
            and git(
                path,
                "merge-base",
                "--is-ancestor",
                current,
                plan["target_revision"],
            ).returncode
            == 0
        ),
    }
    if not all(rechecks.values()):
        failed = ", ".join(name for name, ok in rechecks.items() if not ok)
        raise RuntimeError(
            f"state changed after planning; refusing to update; failed checks: {failed}"
        )
    if plan["up_to_date"]:
        return {
            **plan,
            "dry_run": False,
            "applied": False,
            "rechecks": rechecks,
            "message": "already up to date",
        }
    result = git(path, "checkout", "--detach", plan["target_revision"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "submodule checkout failed")
    actual = git_text(path, "rev-parse", "HEAD")
    if actual != plan["target_revision"]:
        raise RuntimeError("submodule checkout did not reach the planned revision")
    return {
        **plan,
        "dry_run": False,
        "applied": True,
        "rechecks": rechecks,
        "message": "submodule checkout updated; superproject gitlink is unstaged",
    }


def frontmatter_name(skill_file: Path) -> str:
    """Return a skill's declared name, falling back to its directory name."""
    try:
        lines = skill_file.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return skill_file.parent.name
    if not lines or lines[0].strip() != "---":
        return skill_file.parent.name
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("'\"") or skill_file.parent.name
    return skill_file.parent.name


def digest_tree(path: Path) -> str:
    """Hash relative paths, modes, and contents for a skill tree."""
    digest = hashlib.sha256()
    for item in sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() or candidate.is_symlink()
    ):
        relative = item.relative_to(path).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(f"{item.lstat().st_mode & 0o777:o}".encode())
        digest.update(b"\0")
        if item.is_symlink():
            digest.update(b"symlink\0")
            digest.update(os.readlink(item).encode())
        else:
            digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def is_license_file(path: Path) -> bool:
    """Recognize conventional license and notice filenames."""
    return bool(LICENSE_NAMES.match(path.name))


def relative(path: Path) -> str:
    """Return a portable workshop-relative path."""
    return path.absolute().relative_to(REPOSITORY).as_posix()


def license_files(skill: Path, boundary: Path) -> tuple[list[str], str]:
    """Find embedded and governing collection-level license files."""
    embedded = [
        path
        for path in skill.rglob("*")
        if (path.is_file() or path.is_symlink()) and is_license_file(path)
    ]
    governing: list[Path] = []
    cursor = skill.parent
    while cursor == boundary or boundary in cursor.parents:
        governing.extend(
            path
            for path in cursor.iterdir()
            if (path.is_file() or path.is_symlink()) and is_license_file(path)
        )
        if cursor == boundary:
            break
        cursor = cursor.parent
    found = sorted({relative(path) for path in embedded + governing})
    if embedded:
        status = "skill"
    elif governing:
        status = "collection"
    else:
        status = "missing"
    return found, status


def readable_text(path: Path) -> str | None:
    """Read a bounded text file, skipping binaries and oversized artifacts."""
    try:
        if path.is_symlink():
            return None
        if path.stat().st_size > TEXT_FILE_LIMIT:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan_skill_files(skill: Path) -> dict[str, Any]:
    """Collect executable, script, network, credential, and SPDX hints."""
    scripts: list[str] = []
    executables: list[str] = []
    symlinks: list[str] = []
    network: set[str] = set()
    credentials: set[str] = set()
    spdx: set[str] = set()
    hint_files: set[str] = set()
    files = sorted(
        candidate
        for candidate in skill.rglob("*")
        if candidate.is_file() or candidate.is_symlink()
    )
    for path in files:
        rel = path.relative_to(skill).as_posix()
        if path.is_symlink():
            symlinks.append(rel)
            continue
        if path.suffix.lower() in SCRIPT_SUFFIXES or {"scripts", "bin"} & set(
            path.parts
        ):
            scripts.append(rel)
        if os.access(path, os.X_OK):
            executables.append(rel)
        text = readable_text(path)
        if text is None:
            continue
        matched = False
        for label, pattern in NETWORK_PATTERNS.items():
            if pattern.search(text):
                network.add(label)
                matched = True
        for label, pattern in CREDENTIAL_PATTERNS.items():
            if pattern.search(text):
                credentials.add(label)
                matched = True
        if matched:
            hint_files.add(rel)
        spdx.update(
            match.strip()
            for match in re.findall(r"SPDX-License-Identifier:\s*([^\r\n*]+)", text)
            if match.strip()
        )
    return {
        "file_count": len(files),
        "script_files": scripts,
        "executable_files": executables,
        "symlink_files": symlinks,
        "network_hints": sorted(network),
        "credential_hints": sorted(credentials),
        "hint_files": sorted(hint_files),
        "spdx_identifiers": sorted(spdx),
    }


def load_trust_registry(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Load review records keyed by the stable source-and-name identity."""
    path = path or TRUST_REGISTRY
    if not path.exists():
        return {}
    data = load_toml(path)
    if data.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version")
    if data.get("identity_format", "<source>#<name>") != "<source>#<name>":
        raise ValueError(f"{path}: unsupported identity_format")
    reviews = data.get("reviews", {})
    if not isinstance(reviews, dict):
        raise TypeError(f"{path}: reviews must be a table")
    for key, review in reviews.items():
        if not isinstance(review, dict):
            raise TypeError(f"{path}: review {key!r} must be a table")
        expected = f"{review.get('source')}#{review.get('name')}"
        if key != expected:
            raise ValueError(
                f"{path}: review key {key!r} does not match source + name {expected!r}"
            )
        if review.get("state", "unreviewed") not in REVIEW_STATES:
            raise ValueError(f"{path}: invalid state in review {key!r}")
    return reviews


def skill_collections() -> list[dict[str, Any]]:
    """Return workshop-owned and registered upstream skill collections."""
    collections: list[dict[str, Any]] = []
    owned = REPOSITORY / "skills"
    if owned.is_dir():
        collections.append(
            {
                "name": "first-party",
                "scope": "workshop",
                "root": owned,
                "revision": git_text(REPOSITORY, "rev-parse", "HEAD"),
            }
        )
    for record in registered_upstreams():
        root = (REPOSITORY / record["path"]).resolve()
        if root.is_dir():
            collections.append(
                {
                    "name": record["name"],
                    "scope": "upstream",
                    "root": root,
                    "revision": git_text(root, "rev-parse", "HEAD"),
                }
            )
    return collections


def trust_inventory() -> list[dict[str, Any]]:
    """Inspect all catalogued skills and merge their review records."""
    reviews = load_trust_registry()
    rows: list[dict[str, Any]] = []
    identities: set[str] = set()
    for collection in skill_collections():
        root = collection["root"]
        for skill_file in sorted(root.rglob("SKILL.md")):
            skill = skill_file.parent
            source = relative(skill)
            name = frontmatter_name(skill_file)
            identity = f"{source}#{name}"
            if identity in identities:
                raise ValueError(f"duplicate skill identity: {identity}")
            identities.add(identity)
            digest = digest_tree(skill)
            review = reviews.get(identity, {})
            state = review.get("state", "unreviewed")
            licenses, license_status = license_files(skill, root)
            inspection = scan_skill_files(skill)
            rows.append(
                {
                    "key": identity,
                    "name": name,
                    "source": source,
                    "collection": collection["name"],
                    "scope": collection["scope"],
                    "revision": collection["revision"],
                    "sha256": digest,
                    "review_state": state,
                    "review_current": bool(
                        state == "reviewed" and review.get("sha256") == digest
                    ),
                    "reviewer": review.get("reviewer"),
                    "reviewed_at": review.get("reviewed_at"),
                    "reviewed_revision": review.get("revision"),
                    "review_notes": review.get("notes"),
                    "license_status": license_status,
                    "license_files": licenses,
                    "has_scripts": bool(inspection["script_files"]),
                    "has_executables": bool(inspection["executable_files"]),
                    "has_symlinks": bool(inspection["symlink_files"]),
                    "uses_network": bool(inspection["network_hints"]),
                    "uses_credentials": bool(inspection["credential_hints"]),
                    **inspection,
                }
            )
    unknown = set(reviews) - identities
    if unknown:
        raise ValueError(
            "trust registry contains unknown skill identities: "
            + ", ".join(sorted(unknown))
        )
    return sorted(rows, key=lambda row: (row["collection"], row["source"], row["name"]))


def toml_string(value: str) -> str:
    """Encode a Python string as a TOML basic string."""
    return json.dumps(value, ensure_ascii=False)


def write_trust_registry(reviews: dict[str, dict[str, Any]]) -> None:
    """Write a deterministic trust registry without third-party dependencies."""
    lines = [
        "# Review records are keyed by the stable identity <source>#<name>.",
        "# A reviewed record is current only while its sha256 matches the skill tree.",
        "schema_version = 1",
        'identity_format = "<source>#<name>"',
        "",
        "[reviews]",
    ]
    field_order = (
        "source",
        "name",
        "state",
        "sha256",
        "revision",
        "reviewer",
        "reviewed_at",
        "notes",
    )
    for key in sorted(reviews):
        lines.extend(("", f"[reviews.{toml_string(key)}]"))
        review = reviews[key]
        for field in field_order:
            value = review.get(field)
            if value is not None:
                lines.append(f"{field} = {toml_string(str(value))}")
    TRUST_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    temporary = TRUST_REGISTRY.with_suffix(".toml.tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(TRUST_REGISTRY)


def set_review(
    source: str, name: str, state: str, reviewer: str | None, notes: str | None
) -> dict[str, Any]:
    """Set a review state for an existing catalogued skill identity."""
    identity = f"{source}#{name}"
    inventory = {row["key"]: row for row in trust_inventory()}
    if identity not in inventory:
        raise ValueError(f"unknown skill identity: {identity}")
    row = inventory[identity]
    reviews = load_trust_registry()
    record: dict[str, Any] = {"source": source, "name": name, "state": state}
    if state == "reviewed":
        if not reviewer:
            raise ValueError("--reviewer is required when marking a skill reviewed")
        record.update(
            {
                "sha256": row["sha256"],
                "revision": row["revision"],
                "reviewer": reviewer,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    elif reviewer:
        record["reviewer"] = reviewer
    if notes:
        record["notes"] = notes
    reviews[identity] = record
    write_trust_registry(reviews)
    return {"key": identity, **record}


def flatten(value: Any) -> str:
    """Flatten structured values for TSV output."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, dict)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def write_output(payload: Any, output_format: str, output: Path | None) -> None:
    """Emit JSON or TSV to stdout or a requested file."""
    if output_format == "json":
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    else:
        rows = payload if isinstance(payload, list) else [payload]
        columns: list[str] = []
        for row in rows:
            columns.extend(key for key in row if key not in columns)
        stream = io.StringIO()
        writer = csv.DictWriter(stream, fieldnames=columns, delimiter="\t")
        writer.writeheader()
        writer.writerows(
            {key: flatten(value) for key, value in row.items()} for row in rows
        )
        rendered = stream.getvalue()
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    else:
        sys.stdout.write(rendered)


def human_status(rows: Iterable[dict[str, Any]]) -> None:
    """Print a compact lifecycle summary."""
    for row in rows:
        print(f"{row['name']} ({row['path']})")
        if not row.get("initialized"):
            print(f"  unavailable: {row['error']}")
            continue
        print(f"  pinned:   {row['pinned_revision']}")
        fork = row["fork"]
        canonical = row["upstream"]
        print(f"  fork:     {fork['revision'] or 'not fetched'} ({fork['ref'] or '-'})")
        print(
            f"  upstream: {canonical['revision'] or 'not fetched'} "
            f"({canonical['ref'] or '-'})"
        )
        relation = row["fork_vs_upstream"]
        if relation:
            print(
                f"  fork is {relation['ahead']} ahead / {relation['behind']} behind "
                "upstream"
            )
        print(
            f"  affected: {len(row['affected']['bundles'])} bundle mappings, "
            f"{len(row['affected']['materializations'])} materializations"
        )
        if row["dirty"]:
            print("  warning: submodule worktree is dirty")


def human_update(plan: dict[str, Any]) -> None:
    """Print a compact update plan."""
    mode = "APPLIED" if plan.get("applied") else "DRY RUN"
    print(f"{mode}: {plan['name']} via {plan['target_ref']}")
    print(f"  {plan['current_revision']} -> {plan['target_revision']}")
    print(f"  changed files: {len(plan['changed_files'])}")
    print(f"  changed skills: {len(plan['changed_skill_sources'])}")
    print(
        f"  affected: {len(plan['affected']['bundles'])} bundle mappings, "
        f"{len(plan['affected']['materializations'])} materializations"
    )
    failed = [name for name, ok in plan["checks"].items() if not ok]
    if failed:
        print("  blocked: " + ", ".join(failed))
    elif plan["up_to_date"]:
        print("  already up to date")
    elif plan.get("applied"):
        print("  checkout moved; review and commit the workshop gitlink separately")
    else:
        print("  safe to apply; rerun with --apply after reviewing this plan")


def human_trust(rows: list[dict[str, Any]]) -> None:
    """Print trust posture counts and actionable review candidates."""
    states = Counter(row["review_state"] for row in rows)
    print(f"Catalogued skills: {len(rows)}")
    print(
        "Review states: " + ", ".join(f"{key}={states[key]}" for key in REVIEW_STATES)
    )
    print(
        f"Missing detected license: {sum(row['license_status'] == 'missing' for row in rows)}"
    )
    print(f"Script-bearing: {sum(row['has_scripts'] for row in rows)}")
    print(f"Executable-bearing: {sum(row['has_executables'] for row in rows)}")
    print(f"Symlink-bearing: {sum(row['has_symlinks'] for row in rows)}")
    print(f"Network hints: {sum(row['uses_network'] for row in rows)}")
    print(f"Credential hints: {sum(row['uses_credentials'] for row in rows)}")


def add_output_arguments(
    parser: argparse.ArgumentParser, *, human: bool = True
) -> None:
    choices = ("human", "json", "tsv") if human else ("json", "tsv")
    parser.add_argument("--format", choices=choices, default=choices[0])
    parser.add_argument(
        "--output",
        type=Path,
        help="write JSON or TSV to a file (requires --format json or tsv)",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    status_parser = commands.add_parser(
        "status", help="report every upstream lifecycle"
    )
    status_parser.add_argument(
        "--fetch",
        action="store_true",
        help="refresh verified fork and canonical remote-tracking refs first",
    )
    add_output_arguments(status_parser)

    update_parser = commands.add_parser(
        "update", help="plan or explicitly apply a fast-forward submodule update"
    )
    update_parser.add_argument("name")
    update_parser.add_argument(
        "--remote",
        choices=("upstream", "origin"),
        default="upstream",
        help="canonical upstream or personal fork (default: upstream)",
    )
    update_parser.add_argument("--ref", help="branch on the selected remote")
    update_parser.add_argument(
        "--fetch",
        action="store_true",
        help="refresh the selected verified remote first",
    )
    mode = update_parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run", action="store_true", help="show the plan (the default)"
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="move the checkout if every safety check passes",
    )
    add_output_arguments(update_parser)

    trust_parser = commands.add_parser(
        "trust", help="inventory license, executable, network, and review signals"
    )
    add_output_arguments(trust_parser)

    review_parser = commands.add_parser(
        "review", help="record a review state by stable source-and-name identity"
    )
    review_parser.add_argument("source")
    review_parser.add_argument("name")
    review_parser.add_argument("--state", choices=REVIEW_STATES, required=True)
    review_parser.add_argument(
        "--reviewer", help="reviewer identity (required with --state reviewed)"
    )
    review_parser.add_argument("--notes")

    args = parser.parse_args()
    if (
        getattr(args, "format", None) == "human"
        and getattr(args, "output", None) is not None
    ):
        parser.error("--output requires --format json or --format tsv")
    try:
        if args.command == "status":
            payload = all_upstream_status(fetch=args.fetch)
            if args.format == "human":
                human_status(payload)
            elif args.format == "json":
                write_output(
                    {"schema_version": 1, "upstreams": payload},
                    args.format,
                    args.output,
                )
            else:
                write_output(payload, args.format, args.output)
        elif args.command == "update":
            record = find_upstream(args.name)
            payload = plan_update(record, args.remote, args.ref, args.fetch)
            if args.apply:
                payload = apply_update(payload)
            if args.format == "human":
                human_update(payload)
            else:
                write_output(payload, args.format, args.output)
        elif args.command == "trust":
            payload = trust_inventory()
            if args.format == "human":
                human_trust(payload)
            elif args.format == "json":
                write_output(
                    {
                        "schema_version": 1,
                        "identity_format": "<source>#<name>",
                        "skills": payload,
                    },
                    args.format,
                    args.output,
                )
            else:
                write_output(payload, args.format, args.output)
        else:
            payload = set_review(
                args.source, args.name, args.state, args.reviewer, args.notes
            )
            write_output(
                {
                    "schema_version": 1,
                    "identity_format": "<source>#<name>",
                    "review": payload,
                },
                "json",
                None,
            )
    except (OSError, RuntimeError, TypeError, ValueError) as error:
        parser.exit(2, f"error: {error}\n")


if __name__ == "__main__":
    main()
