#!/usr/bin/env python3
"""Inspect materialized skills and produce read-only reconciliation plans."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import tomllib

REPOSITORY = Path(__file__).resolve().parents[1]
MATERIALIZATIONS = REPOSITORY / "materializations"
PLAN_POLICIES = ("abort", "record", "back-propagate", "overwrite")
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")


@dataclass(frozen=True)
class LockEntry:
    """One skill record from a materialization lock."""

    name: str
    source: str
    identity: str
    source_sha256: str | None
    project_sha256: str | None
    bundle: str
    lock_path: Path
    revision: str | None = None
    upstream_url: str | None = None
    origin_url: str | None = None


@dataclass
class UpstreamStatus:
    """The locally or remotely observable state of a skill's upstream."""

    recorded_revision: str | None = None
    current_revision: str | None = None
    candidate_revision: str | None = None
    available: bool | None = None
    check: str = "not-determinable"
    relationship: str = "unknown"
    url: str | None = None
    error: str | None = None


@dataclass
class FileDifference:
    """A file-level difference between workshop and project trees."""

    path: str
    status: str
    patch: str | None = None
    detail: str | None = None


@dataclass
class SkillStatus:
    """Two-sided status for one logical skill mapping."""

    name: str
    source: str
    identity: str
    bundles: list[str]
    locks: list[str]
    workshop_path: str
    project_path: str
    state: str
    classifications: list[str]
    source_baseline_sha256: str | None
    project_baseline_sha256: str | None
    source_sha256: str | None
    project_sha256: str | None
    source_changed: bool | None
    project_changed: bool | None
    content_equal: bool
    baseline_conflict: bool = False
    name_collision: bool = False
    obsolete: bool = False
    upstream: UpstreamStatus = field(default_factory=UpstreamStatus)
    differences: list[FileDifference] = field(default_factory=list)


@dataclass
class PlanAction:
    """A proposed action. This script never executes these actions."""

    skill: str
    action: str
    reason: str
    identity: str | None = None
    source: str | None = None
    destination: str | None = None
    blocked: bool = False


@dataclass
class ReconciliationPlan:
    """A dry-run reconciliation and/or prune plan."""

    dry_run: bool
    policy: str | None
    prune: bool
    halted: bool
    actions: list[PlanAction]


@dataclass
class ProjectReport:
    """Complete status report for one downstream project."""

    project: str
    project_id: str
    project_remote: str | None
    locks: list[str]
    skills: list[SkillStatus]
    unmanaged_project_skills: list[str]
    summary: dict[str, int]
    plan: ReconciliationPlan | None = None


def run_git(path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    """Run a read-only Git query without raising on a non-repository path."""

    return subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def digest_tree(path: Path) -> str:
    """Return the digest format used by ``manage_skills.py`` locks."""

    digest = hashlib.sha256()
    for item in sorted(
        file for file in path.rglob("*") if file.is_file() or file.is_symlink()
    ):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        if item.is_symlink():
            digest.update(b"symlink:")
            digest.update(os.readlink(item).encode())
        else:
            digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def directory_digest(path: Path) -> str | None:
    """Digest a real directory, declining files and directory symlinks."""

    if not path.is_dir() or path.is_symlink():
        return None
    return digest_tree(path)


def validate_project_skills_root(project: Path) -> Path:
    agents = project / ".agents"
    root = agents / "skills"
    for path in (agents, root):
        if (path.exists() or path.is_symlink()) and (
            not path.is_dir() or path.is_symlink()
        ):
            raise ValueError(f"project skill path is not a real directory: {path}")
    return root


def normalize_remote(url: str | None) -> str | None:
    """Normalize common Git remote spellings for identity comparisons."""

    if not url:
        return None
    value = url.strip().rstrip("/")
    value = re.sub(r"^git@[^:]+:", "", value)
    value = re.sub(r"^(?:https?|ssh|git)://[^/]+/", "", value)
    value = re.sub(r"\.git$", "", value)
    return value.casefold() or None


def project_identity(
    project: Path, requested: str | None = None
) -> tuple[str, str | None]:
    """Return the same default project identity used during materialization."""

    result = run_git(project, "remote", "get-url", "origin")
    remote = result.stdout.strip() if result.returncode == 0 else None
    candidate = requested
    if not candidate and remote:
        if "://" in remote:
            candidate = urlsplit(remote).path.lstrip("/")
        else:
            scp = re.match(r"^(?:[^@/]+@)?[^:/]+:(.+)$", remote)
            candidate = scp.group(1) if scp else remote.strip("/")
        candidate = re.sub(r"\.git$", "", candidate).replace("/", "--")
    if not candidate:
        candidate = project.name
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", candidate):
        raise ValueError(
            "project identifier must contain only letters, digits, dots, "
            "underscores, and hyphens"
        )
    return candidate, remote


def _safe_source(repository: Path, source: str) -> Path:
    if not isinstance(source, str) or not source or "\\" in source:
        raise ValueError(f"invalid lock source: {source!r}")
    relative = Path(source)
    if (
        relative.is_absolute()
        or relative.as_posix() != source
        or any(part in {".", ".."} for part in relative.parts)
    ):
        raise ValueError(f"invalid lock source: {source}")
    path = (repository / source).resolve()
    if path == repository or repository not in path.parents:
        raise ValueError(f"lock source escapes the workshop: {source}")
    return path


def _safe_skill_name(name: object) -> str:
    if not isinstance(name, str):
        raise TypeError(
            f"skill name in lock must be a string, not {type(name).__name__}"
        )
    if not SAFE_NAME.fullmatch(name):
        raise ValueError(f"invalid skill name in lock: {name!r}")
    return name


def skill_identity(name: str, source: str) -> str:
    """Return the durable identity used by schema-v2 materialization locks."""

    return f"{source}#{name}"


def load_lock(path: Path) -> tuple[dict[str, Any], list[LockEntry]]:
    """Validate and load a materialization lock."""

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read materialization lock {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise TypeError(f"invalid materialization lock: {path}")
    schema_version = data.get("schema_version", 1)
    if schema_version not in {1, 2}:
        raise ValueError(
            f"unsupported materialization schema in {path}: "
            f"{data.get('schema_version')!r}"
        )
    bundle = data.get("bundle")
    if not isinstance(bundle, str) or not bundle:
        raise ValueError(f"materialization lock has no bundle: {path}")

    entries: list[LockEntry] = []
    for item in data["skills"]:
        if not isinstance(item, dict):
            raise TypeError(f"invalid skill entry in materialization lock: {path}")
        name = _safe_skill_name(item.get("name", ""))
        source = item.get("source")
        if not isinstance(source, str) or not source:
            raise ValueError(f"skill {name!r} has no source in {path}")
        identity = skill_identity(name, source)
        if schema_version == 2 and item.get("identity") != identity:
            raise ValueError(
                f"skill {name!r} has invalid identity in schema-v2 lock {path}"
            )
        source_sha256 = item.get("source_sha256", item.get("sha256"))
        project_sha256 = item.get(
            "project_sha256", item.get("sha256") if schema_version == 1 else None
        )
        if schema_version == 2 and not isinstance(source_sha256, str):
            raise TypeError(f"skill {name!r} has no source digest in {path}")
        if source_sha256 is not None and not isinstance(source_sha256, str):
            raise TypeError(f"skill {name!r} has an invalid source digest in {path}")
        if project_sha256 is not None and not isinstance(project_sha256, str):
            raise TypeError(f"skill {name!r} has an invalid project digest in {path}")
        entries.append(
            LockEntry(
                name=name,
                source=source,
                identity=identity,
                source_sha256=source_sha256,
                project_sha256=project_sha256,
                bundle=bundle,
                lock_path=path.resolve(),
                revision=item.get("revision"),
                upstream_url=item.get("upstream_url"),
                origin_url=item.get("origin_url"),
            )
        )
    return data, entries


def discover_locks(
    project: Path,
    materializations: Path = MATERIALIZATIONS,
    *,
    project_id: str | None = None,
    bundles: set[str] | None = None,
    explicit: Sequence[Path] = (),
) -> tuple[str, str | None, list[Path]]:
    """Find locks belonging to a project, with optional bundle filtering."""

    identity, remote = project_identity(project, project_id)
    candidates = (
        [path.resolve() for path in explicit]
        if explicit
        else sorted(materializations.glob("*.lock.json"))
    )
    matches: list[Path] = []
    for path in candidates:
        data, _ = load_lock(path)
        lock_project = data.get("project", {})
        lock_id = lock_project.get("id") if isinstance(lock_project, dict) else None
        lock_remote = (
            lock_project.get("remote") if isinstance(lock_project, dict) else None
        )
        bundle = data.get("bundle")
        identity_matches = bool(explicit) or lock_id == identity
        if not identity_matches and remote:
            identity_matches = normalize_remote(lock_remote) == normalize_remote(remote)
        if identity_matches and (not bundles or bundle in bundles):
            matches.append(path.resolve())
    if not matches:
        detail = f" for bundles {', '.join(sorted(bundles))}" if bundles else ""
        raise FileNotFoundError(
            f"no materialization locks found for project {identity!r}{detail}"
        )
    return identity, remote, sorted(set(matches))


def _git_repository(path: Path) -> Path | None:
    result = run_git(path, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return None
    candidate = Path(result.stdout.strip())
    return candidate.resolve() if candidate.is_dir() else None


@cache
def _local_upstream_candidate(git_root: Path) -> str | None:
    for reference in (
        "refs/remotes/upstream/HEAD",
        "refs/remotes/upstream/main",
        "refs/remotes/upstream/master",
    ):
        result = run_git(git_root, "rev-parse", "--verify", reference)
        if result.returncode == 0:
            return result.stdout.strip()
    return None


@cache
def _remote_head(url: str) -> tuple[str | None, str | None]:
    result = subprocess.run(
        ["git", "ls-remote", url, "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return None, result.stderr.strip() or "git ls-remote failed"
    fields = result.stdout.split()
    if not fields:
        return None, "upstream did not advertise HEAD"
    return fields[0], None


def _revision_relationship(
    git_root: Path, current: str | None, candidate: str | None
) -> tuple[str, bool | None]:
    if not current or not candidate:
        return "unknown", None
    if current == candidate:
        return "up-to-date", False
    candidate_exists = (
        run_git(git_root, "cat-file", "-e", f"{candidate}^{{commit}}").returncode == 0
    )
    if not candidate_exists:
        return "different-unfetched", None
    if (
        run_git(git_root, "merge-base", "--is-ancestor", current, candidate).returncode
        == 0
    ):
        return "behind", True
    if (
        run_git(git_root, "merge-base", "--is-ancestor", candidate, current).returncode
        == 0
    ):
        return "ahead", False
    return "diverged", False


def inspect_upstream(
    source: Path,
    entries: Sequence[LockEntry],
    *,
    check_remote: bool = False,
) -> UpstreamStatus:
    """Inspect revisions without fetching or modifying a repository."""

    revisions = {entry.revision for entry in entries if entry.revision}
    recorded = next(iter(revisions)) if len(revisions) == 1 else None
    urls = [entry.upstream_url or entry.origin_url for entry in entries]
    url = next((candidate for candidate in urls if candidate), None)
    status = UpstreamStatus(recorded_revision=recorded, url=url)
    if len(revisions) > 1:
        status.error = "locks disagree about the recorded revision"
        return status
    git_root = _git_repository(source) if source.exists() else None
    if not git_root:
        return status
    result = run_git(git_root, "rev-parse", "HEAD")
    if result.returncode == 0:
        status.current_revision = result.stdout.strip()

    if check_remote and url:
        try:
            candidate, error = _remote_head(url)
        except subprocess.TimeoutExpired:
            candidate, error = None, "upstream check timed out"
        status.candidate_revision = candidate
        status.error = error
        status.check = "remote-head"
    else:
        status.candidate_revision = _local_upstream_candidate(git_root)
        status.check = (
            "locally-fetched-upstream-head"
            if status.candidate_revision
            else "not-determinable"
        )
    status.relationship, status.available = _revision_relationship(
        git_root, status.current_revision, status.candidate_revision
    )
    return status


def _read_file(path: Path, limit: int) -> tuple[bytes | None, str | None]:
    try:
        size = path.stat().st_size
        if size > limit:
            return None, f"file is {size} bytes; patch limit is {limit} bytes"
        return path.read_bytes(), None
    except OSError as error:
        return None, str(error)


def _tree_files(root: Path) -> dict[str, Path]:
    if not root.is_dir() or root.is_symlink():
        return {}
    return {
        item.relative_to(root).as_posix(): item
        for item in sorted(root.rglob("*"))
        if item.is_file() or item.is_symlink()
    }


def diff_trees(
    workshop: Path,
    project: Path,
    *,
    include_patches: bool = False,
    context: int = 3,
    max_bytes: int = 262_144,
) -> list[FileDifference]:
    """Describe file-level differences from workshop to project."""

    workshop_files = _tree_files(workshop)
    project_files = _tree_files(project)
    differences: list[FileDifference] = []
    for relative in sorted(workshop_files.keys() | project_files.keys()):
        source_file = workshop_files.get(relative)
        project_file = project_files.get(relative)
        if source_file is None:
            differences.append(FileDifference(relative, "only-in-project"))
            continue
        if project_file is None:
            differences.append(FileDifference(relative, "only-in-workshop"))
            continue
        if source_file.is_symlink() or project_file.is_symlink():
            source_target = (
                os.readlink(source_file) if source_file.is_symlink() else None
            )
            project_target = (
                os.readlink(project_file) if project_file.is_symlink() else None
            )
            if (
                source_target == project_target
                and source_file.is_symlink() == project_file.is_symlink()
            ):
                continue
            differences.append(
                FileDifference(
                    relative,
                    "symlink-modified",
                    detail=(
                        f"workshop target={source_target!r}; "
                        f"project target={project_target!r}"
                    ),
                )
            )
            continue
        try:
            if source_file.read_bytes() == project_file.read_bytes():
                continue
        except OSError as error:
            differences.append(
                FileDifference(relative, "unreadable", detail=str(error))
            )
            continue
        difference = FileDifference(relative, "modified")
        if include_patches:
            source_bytes, source_error = _read_file(source_file, max_bytes)
            project_bytes, project_error = _read_file(project_file, max_bytes)
            if source_error or project_error:
                difference.detail = source_error or project_error
            elif source_bytes is not None and project_bytes is not None:
                if b"\0" in source_bytes or b"\0" in project_bytes:
                    difference.status = "binary-modified"
                    difference.detail = "binary content differs"
                else:
                    try:
                        source_text = source_bytes.decode("utf-8")
                        project_text = project_bytes.decode("utf-8")
                    except UnicodeDecodeError:
                        difference.status = "binary-modified"
                        difference.detail = "non-UTF-8 content differs"
                    else:
                        difference.patch = "".join(
                            difflib.unified_diff(
                                source_text.splitlines(keepends=True),
                                project_text.splitlines(keepends=True),
                                fromfile=f"workshop/{relative}",
                                tofile=f"project/{relative}",
                                n=context,
                            )
                        )
        differences.append(difference)
    return differences


def _single_baseline(
    entries: Sequence[LockEntry], attribute: str
) -> tuple[str | None, bool]:
    values = {getattr(entry, attribute) for entry in entries}
    return (next(iter(values)), False) if len(values) == 1 else (None, True)


def classify_skill(
    entries: Sequence[LockEntry],
    project: Path,
    repository: Path = REPOSITORY,
    *,
    include_patches: bool = False,
    diff_context: int = 3,
    max_diff_bytes: int = 262_144,
    check_upstream: bool = False,
    name_collision: bool = False,
) -> SkillStatus:
    """Classify one source/name mapping against its lock baselines."""

    if not entries:
        raise ValueError("at least one lock entry is required")
    name = entries[0].name
    source = entries[0].source
    if any(entry.name != name or entry.source != source for entry in entries):
        raise ValueError("cannot classify unrelated lock entries together")

    workshop_path = _safe_source(repository.resolve(), source)
    project_path = project.resolve() / ".agents" / "skills" / name
    source_digest = directory_digest(workshop_path)
    project_digest = directory_digest(project_path)
    source_baseline, source_conflict = _single_baseline(entries, "source_sha256")
    project_baseline, project_conflict = _single_baseline(entries, "project_sha256")
    baseline_conflict = source_conflict or project_conflict
    source_changed = (
        source_digest != source_baseline
        if source_digest is not None and source_baseline is not None
        else None
    )
    project_changed = (
        project_digest != project_baseline
        if project_digest is not None and project_baseline is not None
        else None
    )
    content_equal = source_digest is not None and source_digest == project_digest

    if name_collision:
        state = "name-collision"
    elif baseline_conflict:
        state = "lock-conflict"
    elif source_digest is None and project_digest is None:
        state = "missing-both"
    elif source_digest is None:
        state = "missing-workshop"
    elif project_digest is None:
        state = "missing-project"
    elif source_changed is None or project_changed is None:
        state = "unknown-baseline"
    elif source_changed and project_changed:
        state = "both-changed"
    elif source_changed:
        state = "workshop-changed"
    elif project_changed:
        state = "project-changed"
    elif content_equal:
        state = "synced"
    else:
        state = "recorded-divergence"

    upstream = inspect_upstream(workshop_path, entries, check_remote=check_upstream)
    classifications = [state]
    if (
        upstream.recorded_revision
        and upstream.current_revision
        and upstream.recorded_revision != upstream.current_revision
    ):
        classifications.append("source-revision-changed")
    if upstream.available:
        classifications.append("upstream-update-available")
    elif upstream.relationship in {"different-unfetched", "diverged"}:
        classifications.append("upstream-differs")
    return SkillStatus(
        name=name,
        source=source,
        identity=skill_identity(name, source),
        bundles=sorted({entry.bundle for entry in entries}),
        locks=sorted({str(entry.lock_path) for entry in entries}),
        workshop_path=str(workshop_path),
        project_path=str(project_path),
        state=state,
        classifications=classifications,
        source_baseline_sha256=source_baseline,
        project_baseline_sha256=project_baseline,
        source_sha256=source_digest,
        project_sha256=project_digest,
        source_changed=source_changed,
        project_changed=project_changed,
        content_equal=content_equal,
        baseline_conflict=baseline_conflict,
        name_collision=name_collision,
        upstream=upstream,
        differences=diff_trees(
            workshop_path,
            project_path,
            include_patches=include_patches,
            context=diff_context,
            max_bytes=max_diff_bytes,
        ),
    )


def current_bundle_memberships(
    repository: Path = REPOSITORY,
    bundles: set[str] | None = None,
) -> set[tuple[str, str]]:
    """Return skill identities selected by the relevant current bundles."""

    memberships: set[tuple[str, str]] = set()
    for path in sorted((repository / "bundles").glob("*.toml")):
        try:
            with path.open("rb") as stream:
                manifest = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"cannot read bundle manifest {path}: {error}") from error
        if bundles is not None and manifest.get("name") not in bundles:
            continue
        for item in manifest.get("skills", []):
            if isinstance(item, dict) and item.get("name") and item.get("source"):
                memberships.add((item["name"], item["source"]))
    return memberships


def scan_unmanaged_skills(project: Path, managed_names: set[str]) -> list[str]:
    """List project skill directories not represented by the selected locks."""

    root = project / ".agents" / "skills"
    if not root.is_dir():
        return []
    return sorted(
        child.name
        for child in root.iterdir()
        if child.name not in managed_names
        and child.is_dir()
        and (child / "SKILL.md").is_file()
    )


def _is_actionable(status: SkillStatus) -> bool:
    return status.state not in {"synced"}


def _reconciliation_action(status: SkillStatus, policy: str) -> PlanAction | None:
    if not _is_actionable(status):
        return None
    if status.state in {"name-collision", "lock-conflict", "unknown-baseline"}:
        return PlanAction(
            skill=status.name,
            action="blocked",
            reason=f"{status.state} must be resolved before reconciliation",
            identity=status.identity,
            blocked=True,
        )
    if policy == "abort":
        return PlanAction(
            skill=status.name,
            action="stop",
            reason=f"{status.state}: abort policy permits no changes",
            identity=status.identity,
            blocked=True,
        )
    if policy == "record":
        return PlanAction(
            skill=status.name,
            action="update-workshop-lock",
            reason="record the current workshop and project hashes separately",
            identity=status.identity,
            source=status.workshop_path,
            destination=", ".join(status.locks),
        )
    if status.content_equal:
        return PlanAction(
            skill=status.name,
            action="refresh-workshop-lock",
            reason="both live copies already match; refresh stale lock baselines",
            identity=status.identity,
            source=status.workshop_path,
            destination=", ".join(status.locks),
        )
    if policy == "back-propagate":
        if status.project_sha256 is None:
            return PlanAction(
                skill=status.name,
                action="blocked",
                reason="project skill is missing or is not a real directory",
                identity=status.identity,
                blocked=True,
            )
        return PlanAction(
            skill=status.name,
            action=(
                "create-workshop-skill"
                if status.source_sha256 is None
                else "replace-workshop-skill"
            ),
            reason="make the workshop match the project, then refresh the lock",
            identity=status.identity,
            source=status.project_path,
            destination=status.workshop_path,
        )
    if policy == "overwrite":
        if status.source_sha256 is None:
            return PlanAction(
                skill=status.name,
                action="blocked",
                reason="workshop skill is missing or is not a real directory",
                identity=status.identity,
                blocked=True,
            )
        return PlanAction(
            skill=status.name,
            action=(
                "create-project-skill"
                if status.project_sha256 is None
                else "replace-project-skill"
            ),
            reason="make the project match the workshop, then refresh the lock",
            identity=status.identity,
            source=status.workshop_path,
            destination=status.project_path,
        )
    raise ValueError(f"unknown plan policy: {policy}")


def build_plan(
    skills: Sequence[SkillStatus],
    *,
    policy: str | None = None,
    prune: bool = False,
) -> ReconciliationPlan:
    """Build a dry-run plan; no operation in this module mutates skill trees."""

    if policy is not None and policy not in PLAN_POLICIES:
        raise ValueError(f"unknown plan policy: {policy}")
    actions: list[PlanAction] = []
    if policy:
        for status in skills:
            if status.obsolete:
                continue
            action = _reconciliation_action(status, policy)
            if action:
                actions.append(action)
    if prune:
        for status in skills:
            if not status.obsolete:
                continue
            if status.project_sha256 is None:
                actions.append(
                    PlanAction(
                        skill=status.name,
                        action="retire-lock-entry",
                        reason="skill is no longer selected by a bundle and is absent",
                        identity=status.identity,
                        destination=", ".join(status.locks),
                    )
                )
            elif (
                status.baseline_conflict
                or status.name_collision
                or status.project_baseline_sha256 is None
            ):
                actions.append(
                    PlanAction(
                        skill=status.name,
                        action="blocked-prune",
                        reason="ambiguous lock metadata prevents safe pruning",
                        identity=status.identity,
                        destination=status.project_path,
                        blocked=True,
                    )
                )
            elif status.project_changed:
                actions.append(
                    PlanAction(
                        skill=status.name,
                        action="blocked-prune",
                        reason="obsolete project copy changed since its lock baseline",
                        identity=status.identity,
                        destination=status.project_path,
                        blocked=True,
                    )
                )
            else:
                actions.append(
                    PlanAction(
                        skill=status.name,
                        action="remove-project-skill",
                        reason=(
                            "skill is no longer selected by any current bundle; "
                            "retire its lock entry after removal"
                        ),
                        identity=status.identity,
                        destination=status.project_path,
                    )
                )
    halted = any(action.blocked for action in actions)
    return ReconciliationPlan(
        dry_run=True,
        policy=policy,
        prune=prune,
        halted=halted,
        actions=actions,
    )


def inspect_project(
    project: Path,
    *,
    repository: Path = REPOSITORY,
    materializations: Path | None = None,
    project_id: str | None = None,
    bundles: set[str] | None = None,
    explicit_locks: Sequence[Path] = (),
    include_patches: bool = False,
    diff_context: int = 3,
    max_diff_bytes: int = 262_144,
    check_upstream: bool = False,
    plan_policy: str | None = None,
    prune: bool = False,
) -> ProjectReport:
    """Inspect all selected materializations for a downstream project."""

    project = project.resolve()
    repository = repository.resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"project does not exist: {project}")
    validate_project_skills_root(project)
    identity, remote, lock_paths = discover_locks(
        project,
        materializations or repository / "materializations",
        project_id=project_id,
        bundles=bundles,
        explicit=explicit_locks,
    )
    grouped: dict[tuple[str, str], list[LockEntry]] = defaultdict(list)
    for path in lock_paths:
        _, entries = load_lock(path)
        for entry in entries:
            _safe_source(repository, entry.source)
            grouped[(entry.name, entry.source)].append(entry)

    sources_by_name: dict[str, set[str]] = defaultdict(set)
    for name, source in grouped:
        sources_by_name[name].add(source)
    materialized_bundles = {
        entry.bundle for entries in grouped.values() for entry in entries
    }
    try:
        _, _, all_lock_paths = discover_locks(
            project,
            materializations or repository / "materializations",
            project_id=project_id,
        )
    except FileNotFoundError:
        all_lock_paths = []
    for path in all_lock_paths:
        data, _ = load_lock(path)
        materialized_bundles.add(data["bundle"])
    active_memberships = current_bundle_memberships(repository, materialized_bundles)
    skills: list[SkillStatus] = []
    for (name, source), entries in sorted(grouped.items()):
        status = classify_skill(
            entries,
            project,
            repository,
            include_patches=include_patches,
            diff_context=diff_context,
            max_diff_bytes=max_diff_bytes,
            check_upstream=check_upstream,
            name_collision=len(sources_by_name[name]) > 1,
        )
        status.obsolete = (name, source) not in active_memberships
        skills.append(status)

    managed_names = set(sources_by_name)
    summary = dict(
        sorted(
            Counter(
                classification
                for status in skills
                for classification in status.classifications
            ).items()
        )
    )
    report = ProjectReport(
        project=str(project),
        project_id=identity,
        project_remote=remote,
        locks=[str(path) for path in lock_paths],
        skills=skills,
        unmanaged_project_skills=scan_unmanaged_skills(project, managed_names),
        summary=summary,
    )
    if plan_policy or prune:
        report.plan = build_plan(skills, policy=plan_policy, prune=prune)
    return report


def report_as_dict(report: ProjectReport) -> dict[str, Any]:
    """Convert a report into a stable JSON-ready representation."""

    return {"schema_version": 1, **asdict(report)}


def _table(rows: Iterable[Sequence[str]], headers: Sequence[str]) -> str:
    values = [tuple(headers), *(tuple(row) for row in rows)]
    widths = [max(len(row[index]) for row in values) for index in range(len(headers))]
    rendered = [
        "  ".join(value.ljust(widths[index]) for index, value in enumerate(row))
        for row in values
    ]
    rendered.insert(1, "  ".join("-" * width for width in widths))
    return "\n".join(rendered)


def render_human(report: ProjectReport, *, show_diffs: bool = False) -> str:
    """Render a concise terminal report."""

    lines = [
        f"Project: {report.project}",
        f"Identity: {report.project_id}",
        f"Materialization locks: {len(report.locks)}",
        "",
    ]
    rows = []
    for status in report.skills:
        if status.upstream.available is True:
            upstream = "yes"
        elif status.upstream.available is False:
            upstream = "no"
        else:
            upstream = "?"
        rows.append(
            (
                status.name,
                status.source,
                ",".join(status.bundles),
                status.state,
                upstream,
                str(len(status.differences)),
            )
        )
    lines.append(
        _table(
            rows,
            ("SKILL", "SOURCE", "BUNDLES", "STATE", "UPSTREAM", "FILES"),
        )
        if rows
        else "No locked skills."
    )
    lines.extend(
        [
            "",
            "Summary: "
            + ", ".join(f"{state}={count}" for state, count in report.summary.items()),
        ]
    )
    obsolete = [status.name for status in report.skills if status.obsolete]
    if obsolete:
        lines.append("Obsolete bundle selections: " + ", ".join(obsolete))
    if report.unmanaged_project_skills:
        lines.append(
            "Unmanaged project skills: " + ", ".join(report.unmanaged_project_skills)
        )

    if show_diffs:
        for status in report.skills:
            if not status.differences:
                continue
            lines.extend(["", f"Diff: {status.identity} (workshop -> project)"])
            for difference in status.differences:
                lines.append(f"  {difference.status:18} {difference.path}")
                if difference.detail:
                    lines.append(f"    {difference.detail}")
                if difference.patch:
                    lines.append(difference.patch.rstrip("\n"))

    if report.plan:
        policy = report.plan.policy or "prune-only"
        lines.extend(["", f"Dry-run plan ({policy}):"])
        if not report.plan.actions:
            lines.append("  No actions needed.")
        for action in report.plan.actions:
            marker = "BLOCKED" if action.blocked else "PLAN"
            label = action.identity or action.skill
            lines.append(f"  [{marker}] {label}: {action.action}")
            lines.append(f"    {action.reason}")
            if action.source:
                lines.append(f"    from: {action.source}")
            if action.destination:
                lines.append(f"    to:   {action.destination}")
        lines.append("No files were changed.")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="downstream project root")
    parser.add_argument(
        "--format", choices=("human", "json"), default="human", dest="output_format"
    )
    parser.add_argument(
        "--bundle",
        action="append",
        default=[],
        help="inspect only this bundle (repeatable)",
    )
    parser.add_argument(
        "--lock",
        action="append",
        type=Path,
        default=[],
        help="inspect an explicit lock path (repeatable)",
    )
    parser.add_argument(
        "--project-id",
        help="override the identity used to find materialization locks",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="include unified text patches for differing files",
    )
    parser.add_argument(
        "--diff-context", type=int, default=3, help="unified diff context lines"
    )
    parser.add_argument(
        "--max-diff-bytes",
        type=int,
        default=262_144,
        help="maximum size of each file rendered as a patch",
    )
    parser.add_argument(
        "--check-upstream",
        action="store_true",
        help="query each canonical upstream's HEAD without fetching",
    )
    parser.add_argument(
        "--plan",
        choices=PLAN_POLICIES,
        help="show a dry-run conflict-policy plan; never execute it",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="add a safe dry-run plan for obsolete locked skills",
    )
    parser.add_argument(
        "--fail-on-change",
        action="store_true",
        help="exit 1 unless every locked skill is synchronized",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.diff_context < 0:
        parser.error("--diff-context must be non-negative")
    if args.max_diff_bytes < 1:
        parser.error("--max-diff-bytes must be positive")
    try:
        report = inspect_project(
            args.project,
            project_id=args.project_id,
            bundles=set(args.bundle),
            explicit_locks=args.lock,
            include_patches=args.diff,
            diff_context=args.diff_context,
            max_diff_bytes=args.max_diff_bytes,
            check_upstream=args.check_upstream,
            plan_policy=args.plan,
            prune=args.prune,
        )
    except (FileNotFoundError, OSError, TypeError, ValueError) as error:
        parser.error(str(error))
    if args.output_format == "json":
        json.dump(report_as_dict(report), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_human(report, show_diffs=args.diff))
    if args.fail_on_change and any(_is_actionable(skill) for skill in report.skills):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
