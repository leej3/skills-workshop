#!/usr/bin/env python3
"""Validate workshop manifests and coordination metadata contracts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import tomllib

REPOSITORY = Path(__file__).resolve().parents[1]
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
PROJECT_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
DIGEST = re.compile(r"[0-9a-f]{64}")
MANIFEST_KEYS = {"schema_version", "name", "description", "skills"}
LOCK_KEYS = {"schema_version", "bundle", "project", "skills"}
LOCK_SKILL_KEYS = {
    "name",
    "source",
    "identity",
    "source_sha256",
    "project_sha256",
    "status",
    "revision",
    "origin_url",
    "upstream_url",
    "source_dirty",
}
TRUST_STATES = {"unreviewed", "in-review", "reviewed", "rejected"}
TRUST_REVIEW_KEYS = {
    "source",
    "name",
    "state",
    "sha256",
    "revision",
    "reviewer",
    "reviewed_at",
    "notes",
}


def canonical_source(value: object) -> Path | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    relative = Path(value)
    if (
        relative.is_absolute()
        or relative.as_posix() != value
        or any(part in {".", ".."} for part in relative.parts)
    ):
        return None
    repository = REPOSITORY.resolve()
    candidate = repository / relative
    current = repository
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return None
    resolved = candidate.resolve()
    if resolved == repository or repository not in resolved.parents:
        return None
    return candidate


def declared_skill_name(skill_file: Path) -> str | None:
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("'\"") or None
    return None


def validate_manifest(path: Path) -> list[str]:
    errors: list[str] = []
    with path.open("rb") as stream:
        manifest = tomllib.load(stream)
    unexpected = set(manifest) - MANIFEST_KEYS
    if unexpected:
        errors.append(f"{path}: unexpected fields: {', '.join(sorted(unexpected))}")
    if manifest.get("schema_version") != 1:
        errors.append(f"{path}: schema_version must be 1")
    name = manifest.get("name", "")
    if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
        errors.append(f"{path}: invalid name {name!r}")
    if not isinstance(manifest.get("description"), str):
        errors.append(f"{path}: description must be a string")
    if path.parent.name == "bundles" and isinstance(name, str) and path.stem != name:
        errors.append(f"{path}: filename must match bundle name")
    skills = manifest.get("skills")
    if not isinstance(skills, list):
        errors.append(f"{path}: skills must be an array")
        return errors
    seen_names: set[str] = set()
    seen_identities: set[str] = set()
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            errors.append(f"{path}: skill {index} must be a table")
            continue
        unexpected = set(skill) - {"name", "source"}
        if unexpected:
            errors.append(
                f"{path}: skill {index} has unexpected fields: "
                + ", ".join(sorted(unexpected))
            )
        skill_name = skill.get("name", "")
        source = skill.get("source", "")
        identity = f"{source}#{skill_name}"
        if not isinstance(skill_name, str) or not SAFE_NAME.fullmatch(skill_name):
            errors.append(f"{path}: invalid skill name {skill_name!r}")
        if isinstance(skill_name, str) and skill_name in seen_names:
            errors.append(f"{path}: duplicate install name {skill_name!r}")
        if identity in seen_identities:
            errors.append(f"{path}: duplicate identity {identity!r}")
        if isinstance(skill_name, str):
            seen_names.add(skill_name)
        seen_identities.add(identity)
        source_path = canonical_source(source)
        if (
            source_path is None
            or not source_path.is_dir()
            or source_path.is_symlink()
            or not (source_path / "SKILL.md").is_file()
        ):
            errors.append(f"{path}: invalid source {source!r}")
            continue
        links = [item for item in source_path.rglob("*") if item.is_symlink()]
        if links:
            shown = ", ".join(str(item.relative_to(source_path)) for item in links[:3])
            errors.append(f"{path}: source {source!r} contains symlinks: {shown}")
            continue
        declared_name = declared_skill_name(source_path / "SKILL.md")
        if not isinstance(declared_name, str) or not SAFE_NAME.fullmatch(declared_name):
            errors.append(f"{path}: source {source!r} has no valid declared name")
        elif declared_name != skill_name:
            errors.append(
                f"{path}: source {source!r} declares {declared_name!r}, "
                f"expected {skill_name!r}"
            )
    return errors


def validate_lock(path: Path) -> list[str]:
    errors: list[str] = []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return [f"{path}: lock must be an object"]
    unexpected = set(data) - LOCK_KEYS
    if unexpected:
        errors.append(f"{path}: unexpected fields: {', '.join(sorted(unexpected))}")
    version = data.get("schema_version", 1)
    if version != 2:
        errors.append(f"{path}: schema_version {version}; run migrate-metadata --apply")
        return errors
    bundle = data.get("bundle")
    if not isinstance(bundle, str) or not SAFE_NAME.fullmatch(bundle):
        errors.append(f"{path}: invalid bundle {bundle!r}")
    project = data.get("project")
    if not isinstance(project, dict):
        errors.append(f"{path}: project must be an object")
    else:
        unexpected = set(project) - {"id", "remote"}
        if unexpected:
            errors.append(
                f"{path}: project has unexpected fields: "
                + ", ".join(sorted(unexpected))
            )
        project_id = project.get("id")
        if not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id):
            errors.append(f"{path}: invalid project.id {project_id!r}")
        if "remote" not in project or not (
            project.get("remote") is None or isinstance(project.get("remote"), str)
        ):
            errors.append(f"{path}: project.remote must be a string or null")
    skills = data.get("skills")
    if not isinstance(skills, list):
        errors.append(f"{path}: skills must be an array")
        return errors
    seen: set[str] = set()
    seen_names: set[str] = set()
    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            errors.append(f"{path}: skill {index} must be an object")
            continue
        unexpected = set(skill) - LOCK_SKILL_KEYS
        if unexpected:
            errors.append(
                f"{path}: skill {index} has unexpected fields: "
                + ", ".join(sorted(unexpected))
            )
        missing = {
            "name",
            "source",
            "identity",
            "source_sha256",
            "project_sha256",
            "status",
        } - set(skill)
        if missing:
            errors.append(
                f"{path}: skill {index} is missing: {', '.join(sorted(missing))}"
            )
        name = skill.get("name")
        source = skill.get("source")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
            errors.append(f"{path}: invalid skill name {name!r}")
        if canonical_source(source) is None:
            errors.append(f"{path}: invalid skill source {source!r}")
        expected = f"{skill.get('source')}#{skill.get('name')}"
        if skill.get("identity") != expected:
            errors.append(f"{path}: invalid identity for {skill.get('name')}")
        if expected in seen:
            errors.append(f"{path}: duplicate identity {expected}")
        seen.add(expected)
        if isinstance(name, str) and name in seen_names:
            errors.append(f"{path}: duplicate install name {name!r}")
        if isinstance(name, str):
            seen_names.add(name)
        if skill.get("status") not in {"synced", "diverged"}:
            errors.append(f"{path}: invalid status for {skill.get('name')}")
        source_digest = skill.get("source_sha256")
        project_digest = skill.get("project_sha256")
        if not isinstance(source_digest, str) or not DIGEST.fullmatch(source_digest):
            errors.append(f"{path}: invalid source digest for {skill.get('name')}")
        if project_digest is not None and (
            not isinstance(project_digest, str) or not DIGEST.fullmatch(project_digest)
        ):
            errors.append(f"{path}: invalid project digest for {skill.get('name')}")
        expected_status = "synced" if source_digest == project_digest else "diverged"
        if skill.get("status") != expected_status:
            errors.append(f"{path}: inconsistent hashes/status for {skill.get('name')}")
        for key in ("revision", "origin_url", "upstream_url"):
            value = skill.get(key)
            if value is not None and not isinstance(value, str):
                errors.append(
                    f"{path}: {key} must be a string or null for {skill.get('name')}"
                )
        if "source_dirty" in skill and not isinstance(skill["source_dirty"], bool):
            errors.append(
                f"{path}: source_dirty must be boolean for {skill.get('name')}"
            )
    return errors


def validate_trust_registry(path: Path) -> list[str]:
    errors: list[str] = []
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    unexpected = set(data) - {"schema_version", "identity_format", "reviews"}
    if unexpected:
        errors.append(f"{path}: unexpected fields: {', '.join(sorted(unexpected))}")
    if data.get("schema_version") != 1:
        errors.append(f"{path}: schema_version must be 1")
    if data.get("identity_format") != "<source>#<name>":
        errors.append(f"{path}: unsupported identity_format")
    reviews = data.get("reviews")
    if not isinstance(reviews, dict):
        errors.append(f"{path}: reviews must be a table")
        return errors
    for identity, review in reviews.items():
        if not isinstance(review, dict):
            errors.append(f"{path}: review {identity!r} must be a table")
            continue
        unexpected = set(review) - TRUST_REVIEW_KEYS
        if unexpected:
            errors.append(
                f"{path}: review {identity!r} has unexpected fields: "
                + ", ".join(sorted(unexpected))
            )
        source = review.get("source")
        name = review.get("name")
        if canonical_source(source) is None:
            errors.append(f"{path}: review {identity!r} has invalid source")
        if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
            errors.append(f"{path}: review {identity!r} has invalid name")
        if identity != f"{source}#{name}":
            errors.append(f"{path}: review key {identity!r} does not match its fields")
        state = review.get("state", "unreviewed")
        if not isinstance(state, str) or state not in TRUST_STATES:
            errors.append(f"{path}: review {identity!r} has invalid state")
        digest = review.get("sha256")
        if digest is not None and (
            not isinstance(digest, str) or not DIGEST.fullmatch(digest)
        ):
            errors.append(f"{path}: review {identity!r} has invalid digest")
        for key in ("revision", "reviewer", "reviewed_at", "notes"):
            value = review.get(key)
            if value is not None and not isinstance(value, str):
                errors.append(f"{path}: review {identity!r} has invalid {key}")
        if state == "reviewed" and (
            digest is None
            or not isinstance(review.get("reviewer"), str)
            or not isinstance(review.get("reviewed_at"), str)
        ):
            errors.append(
                f"{path}: reviewed record {identity!r} needs digest, reviewer, and date"
            )
    return errors


def main() -> None:
    errors: list[str] = []
    for path in sorted((REPOSITORY / "bundles").glob("*.toml")):
        errors.extend(validate_manifest(path))
    errors.extend(validate_manifest(REPOSITORY / "profiles" / "core.toml"))
    for path in sorted((REPOSITORY / "materializations").glob("*.lock.json")):
        errors.extend(validate_lock(path))
    trust_registry = REPOSITORY / "policy" / "trust.toml"
    if trust_registry.exists():
        errors.extend(validate_trust_registry(trust_registry))
    if errors:
        raise SystemExit("\n".join(errors))
    print("Workshop metadata is valid.")


if __name__ == "__main__":
    main()
