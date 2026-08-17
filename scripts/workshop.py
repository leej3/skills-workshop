#!/usr/bin/env python3
"""Human and agent interface to the source-agnostic skills memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import yaml
from jsonschema import Draft202012Validator, FormatChecker

VERSION = "0.1.0"
REPOSITORY = Path(__file__).resolve().parents[1]

SCHEMA_NAMES = {
    "skills": "skill-v0.schema.json",
    "projects": "project-v0.schema.json",
    "events": "event-v0.schema.json",
    "evaluations": "evaluation-v0.schema.json",
    "tags": "tag-v0.schema.json",
    "bundles": "bundle-v0.schema.json",
}
SCHEMA_BASE = "https://github.com/leej3/skills-workshop/schemas/memory"
URN_PREFIX = "urn:uuid:"
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
WORD = re.compile(r"[a-z0-9]+")
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

ASM_VERSION = "2.14.0"
VERCEL_SKILLS_VERSION = "1.5.22"


class WorkshopError(RuntimeError):
    """A concise, user-actionable workshop failure."""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def new_id() -> str:
    return f"{URN_PREFIX}{uuid.uuid4()}"


def bare_id(value: str) -> str:
    if not value.startswith(URN_PREFIX):
        raise WorkshopError(f"not a workshop UUID: {value}")
    return value.removeprefix(URN_PREFIX)


def schema_uri(kind: str) -> str:
    return f"{SCHEMA_BASE}/{SCHEMA_NAMES[kind]}"


def memory_dir(root: Path, kind: str) -> Path:
    return root / "memory" / kind


def json_text(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def atomic_write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json_text(value))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkshopError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise WorkshopError(f"{path}: expected a JSON object")
    return value


def record_paths(root: Path, kind: str) -> list[Path]:
    directory = memory_dir(root, kind)
    if not directory.exists():
        return []
    if kind == "events":
        return sorted(directory.rglob("*.json"))
    return sorted(directory.glob("*.json"))


def load_records(root: Path, kind: str) -> list[tuple[Path, dict[str, Any]]]:
    return [(path, read_json(path)) for path in record_paths(root, kind)]


def schema_validator(root: Path, kind: str) -> Draft202012Validator:
    path = root / "schemas" / "memory" / SCHEMA_NAMES[kind]
    if not path.is_file():
        raise WorkshopError(f"missing schema: {path}")
    schema = read_json(path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def expected_record_name(kind: str, record: dict[str, Any]) -> str:
    suffix = f"{bare_id(record['id'])}.json"
    if kind == "events":
        return suffix
    return suffix


def validate_memory(root: Path) -> list[str]:
    errors: list[str] = []
    records: dict[str, list[tuple[Path, dict[str, Any]]]] = {}
    seen_ids: dict[str, Path] = {}
    schema_invalid: set[Path] = set()

    for kind in SCHEMA_NAMES:
        try:
            validator = schema_validator(root, kind)
            records[kind] = load_records(root, kind)
        except WorkshopError as error:
            errors.append(str(error))
            records[kind] = []
            continue
        for path, record in records[kind]:
            failures = sorted(
                validator.iter_errors(record), key=lambda item: list(item.path)
            )
            if failures:
                schema_invalid.add(path)
            for failure in failures:
                location = ".".join(str(part) for part in failure.path) or "<root>"
                errors.append(f"{path}: {location}: {failure.message}")
            record_id = record.get("id")
            if isinstance(record_id, str):
                previous = seen_ids.setdefault(record_id, path)
                if previous != path:
                    errors.append(
                        f"{path}: duplicate id {record_id}; first seen in {previous}"
                    )
                try:
                    expected = expected_record_name(kind, record)
                except WorkshopError:
                    pass
                else:
                    filename_matches = (
                        path.name.endswith(expected)
                        if kind == "events"
                        else path.name == expected
                    )
                    if not filename_matches:
                        errors.append(f"{path}: filename must end with {expected}")

    # Cross-record checks assume schema-valid shapes. A malformed record already
    # has actionable schema errors; skipping it here keeps `validate` diagnostic
    # rather than letting one wrong type crash the validator.
    records = {
        kind: [(path, record) for path, record in items if path not in schema_invalid]
        for kind, items in records.items()
    }

    skills = {record["id"]: record for _, record in records["skills"] if "id" in record}
    projects = {
        record["id"]: record for _, record in records["projects"] if "id" in record
    }
    evaluations = {
        record["id"]: record for _, record in records["evaluations"] if "id" in record
    }
    tags = {record["id"]: record for _, record in records["tags"] if "id" in record}
    artifacts: dict[str, str] = {}
    artifact_records: dict[str, dict[str, Any]] = {}

    for path, skill in records["skills"]:
        source_ids = {source.get("id") for source in skill.get("sources", [])}
        if len(source_ids) != len(skill.get("sources", [])):
            errors.append(f"{path}: duplicate source id")
        preferred = skill.get("preferred_source_id")
        if preferred is not None and preferred not in source_ids:
            errors.append(
                f"{path}: preferred_source_id is not one of this skill's sources"
            )
        for artifact in skill.get("artifacts", []):
            artifact_id = artifact.get("id")
            if artifact.get("source_id") not in source_ids:
                errors.append(
                    f"{path}: artifact {artifact_id} refers to an unknown source"
                )
            if artifact_id in artifacts:
                errors.append(f"{path}: duplicate artifact id {artifact_id}")
            elif isinstance(artifact_id, str):
                artifacts[artifact_id] = skill.get("id", "")
                artifact_records[artifact_id] = artifact
        for tag_id in skill.get("tag_ids", []):
            if tag_id not in tags:
                errors.append(f"{path}: unknown tag_id {tag_id}")
        for relation in skill.get("relations", []):
            if relation.get("skill_id") not in skills:
                errors.append(
                    f"{path}: relation refers to unknown skill {relation.get('skill_id')}"
                )
        merged_into = skill.get("merged_into")
        if merged_into is not None and merged_into not in skills:
            errors.append(f"{path}: merged_into refers to unknown skill {merged_into}")

    for path, tag in records["tags"]:
        replacement = tag.get("deprecated_by")
        if replacement is not None and replacement not in tags:
            errors.append(f"{path}: deprecated_by refers to unknown tag {replacement}")

    for path, bundle in records["bundles"]:
        members = [member.get("skill_id") for member in bundle.get("members", [])]
        if len(members) != len(set(members)):
            errors.append(f"{path}: duplicate bundle member")
        for skill_id in members:
            if skill_id not in skills:
                errors.append(f"{path}: bundle refers to unknown skill {skill_id}")

    for path, evaluation in records["evaluations"]:
        skill_id = evaluation.get("skill_id")
        if skill_id not in skills:
            errors.append(f"{path}: evaluation refers to unknown skill {skill_id}")
        condition_ids = [item.get("id") for item in evaluation.get("conditions", [])]
        case_ids = [item.get("id") for item in evaluation.get("cases", [])]
        metric_ids = [item.get("id") for item in evaluation.get("metrics", [])]
        for label, values in (
            ("condition", condition_ids),
            ("case", case_ids),
            ("metric", metric_ids),
        ):
            if len(values) != len(set(values)):
                errors.append(f"{path}: duplicate {label} id")
        for condition in evaluation.get("conditions", []):
            artifact_id = condition.get("artifact_id")
            if artifact_id is not None and artifacts.get(artifact_id) != skill_id:
                errors.append(
                    f"{path}: condition refers to an artifact of another skill"
                )
        for run in evaluation.get("runs", []):
            if run.get("condition_id") not in condition_ids:
                errors.append(
                    f"{path}: run refers to unknown condition {run.get('condition_id')}"
                )
            if run.get("case_id") not in case_ids:
                errors.append(
                    f"{path}: run refers to unknown case {run.get('case_id')}"
                )
            unknown_metrics = set(run.get("metrics", {})) - set(metric_ids)
            if unknown_metrics:
                errors.append(
                    f"{path}: run contains unknown metrics {sorted(unknown_metrics)}"
                )
        if evaluation.get("status") != "complete":
            continue

        design = evaluation.get("design")
        analysis = evaluation.get("analysis", {})
        grading = evaluation.get("grading", {})
        conditions = evaluation.get("conditions", [])
        runs = evaluation.get("runs", [])
        if analysis.get("conclusion") == "planned":
            errors.append(f"{path}: complete evaluation still has a planned conclusion")
        if not str(analysis.get("summary", "")).strip():
            errors.append(f"{path}: complete evaluation requires an analysis summary")
        if not runs:
            errors.append(f"{path}: complete evaluation requires recorded runs")
        if (
            grading.get("kind") == "unassigned"
            or grading.get("grader") is None
            or grading.get("rubric") is None
        ):
            errors.append(f"{path}: complete evaluation requires assigned grading")

        enabled_states = {condition.get("skill_enabled") for condition in conditions}
        if enabled_states != {False, True}:
            errors.append(
                f"{path}: complete evaluation requires with-skill and without-skill conditions"
            )
        for condition in conditions:
            runtime = condition.get("runtime", {})
            missing_runtime = [
                key
                for key in ("agent_version", "model", "reasoning_effort")
                if not runtime.get(key)
            ]
            if runtime.get("agent") in {None, "", "unknown"}:
                missing_runtime.insert(0, "agent")
            budget = runtime.get("budget") or {}
            if (
                not any(
                    budget.get(key) is not None
                    for key in ("time_seconds", "token_limit", "turn_limit")
                )
                and not str(budget.get("notes", "")).strip()
            ):
                missing_runtime.append("budget")
            if missing_runtime:
                errors.append(
                    f"{path}: condition {condition.get('id')} lacks concrete runtime "
                    f"fields {sorted(set(missing_runtime))}"
                )

        expected_metrics = set(metric_ids)
        coverage: dict[tuple[str, str], int] = {}
        for run in runs:
            condition_id = run.get("condition_id")
            case_id = run.get("case_id")
            coverage[(condition_id, case_id)] = (
                coverage.get((condition_id, case_id), 0) + 1
            )
            missing_metrics = expected_metrics - set(run.get("metrics", {}))
            if missing_metrics:
                errors.append(
                    f"{path}: run {run.get('id')} lacks metrics "
                    f"{sorted(missing_metrics)}"
                )
        minimum_runs = 2 if design == "replicated" else 1
        for condition_id in condition_ids:
            for case_id in case_ids:
                if coverage.get((condition_id, case_id), 0) < minimum_runs:
                    errors.append(
                        f"{path}: complete {design} evaluation requires at least "
                        f"{minimum_runs} run(s) for condition {condition_id}, case {case_id}"
                    )

        if design not in {"controlled-paired", "replicated"}:
            continue
        if not evaluation.get("protocol", {}).get("digest"):
            errors.append(f"{path}: {design} completion requires a protocol digest")
        if not evaluation.get("fixture", {}).get("digest"):
            errors.append(f"{path}: {design} completion requires a fixture digest")
        rubric = grading.get("rubric") or {}
        if not rubric.get("digest"):
            errors.append(f"{path}: {design} completion requires a rubric digest")
        runtimes = [condition.get("runtime") for condition in conditions]
        if runtimes and any(runtime != runtimes[0] for runtime in runtimes[1:]):
            errors.append(f"{path}: {design} conditions must use identical runtimes")
        for condition in conditions:
            if condition.get("skill_enabled"):
                artifact_id = condition.get("artifact_id")
                artifact = artifact_records.get(artifact_id, {})
                if not artifact.get("resolved_revision") or not artifact.get("digests"):
                    errors.append(
                        f"{path}: treatment condition {condition.get('id')} requires "
                        "an exact revision and digest"
                    )
        for run in runs:
            if not run.get("evidence"):
                errors.append(
                    f"{path}: {design} run {run.get('id')} requires retained evidence"
                )

    for path, event in records["events"]:
        skill_id = event.get("skill_id")
        if skill_id not in skills:
            errors.append(f"{path}: event refers to unknown skill {skill_id}")
        artifact_id = event.get("artifact_id")
        if artifact_id is not None and artifacts.get(artifact_id) != skill_id:
            errors.append(f"{path}: event refers to an artifact of another skill")
        project_evidence = event.get("project_evidence")
        if project_evidence and project_evidence.get("project_id") not in projects:
            errors.append(
                f"{path}: event refers to unknown project {project_evidence.get('project_id')}"
            )
        if event.get("type") == "evaluation":
            evaluation_id = event.get("payload", {}).get("evaluation_id")
            evaluation = evaluations.get(evaluation_id)
            if evaluation is None or evaluation.get("skill_id") != skill_id:
                errors.append(f"{path}: invalid evaluation pointer {evaluation_id}")

    return errors


def require_valid_memory(root: Path) -> None:
    errors = validate_memory(root)
    if errors:
        raise WorkshopError(
            "memory validation failed:\n" + "\n".join(f"- {item}" for item in errors)
        )


def atomic_write_validated(root: Path, path: Path, value: object) -> None:
    """Write one record, restoring the previous valid state on failure."""
    require_valid_memory(root)
    previous = path.read_bytes() if path.exists() else None
    atomic_write(path, value)
    errors = validate_memory(root)
    if not errors:
        return
    if previous is None:
        path.unlink()
    else:
        path.write_bytes(previous)
    raise WorkshopError(
        "record would invalidate memory:\n" + "\n".join(f"- {item}" for item in errors)
    )


def resolve_record(
    root: Path, kind: str, value: str, *, allow_missing: bool = False
) -> dict[str, Any] | None:
    normalized = value.casefold()
    matches: list[dict[str, Any]] = []
    for _, record in load_records(root, kind):
        candidates = [record.get("id", ""), bare_id(record.get("id", URN_PREFIX))]
        if kind in {"skills", "projects"}:
            candidates.extend([record.get("name", ""), *record.get("aliases", [])])
        elif kind in {"tags", "bundles"}:
            candidates.append(record.get("slug", ""))
        if normalized in {str(candidate).casefold() for candidate in candidates}:
            matches.append(record)
    if not matches and allow_missing:
        return None
    if not matches:
        raise WorkshopError(f"unknown {kind.removesuffix('s')}: {value}")
    if len(matches) > 1:
        choices = ", ".join(record["id"] for record in matches)
        raise WorkshopError(f"ambiguous {kind.removesuffix('s')} {value!r}: {choices}")
    return matches[0]


def event_path(root: Path, timestamp: str, event_id: str) -> Path:
    parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    stamp = parsed.strftime("%Y%m%dT%H%M%SZ")
    return (
        memory_dir(root, "events")
        / parsed.strftime("%Y")
        / parsed.strftime("%m")
        / f"{stamp}-{bare_id(event_id)}.json"
    )


def actor_from_args(args: argparse.Namespace) -> dict[str, str]:
    actor = {"kind": args.asserted_kind, "id": args.asserted_by}
    for key in ("model", "runtime", "runtime_version", "reasoning_effort"):
        value = getattr(args, key, None)
        if value:
            actor[key] = value
    return actor


def make_event(
    args: argparse.Namespace,
    skill_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    project_evidence: dict[str, Any] | None = None,
    artifact_id: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    timestamp = now()
    event_id = new_id()
    record: dict[str, Any] = {
        "schema": schema_uri("events"),
        "id": event_id,
        "type": event_type,
        "skill_id": skill_id,
        "occurred_at": timestamp,
        "asserted_by": actor_from_args(args),
        "recorded_by": {"tool": "skills-workshop", "version": VERSION},
        "review": {"state": "unreviewed"},
        "payload": payload,
        "evidence": [],
        "extensions": {},
    }
    if artifact_id:
        record["artifact_id"] = artifact_id
    if project_evidence:
        record["project_evidence"] = project_evidence
    return event_path(args.root, timestamp, event_id), record


def redact_token(token: str) -> str:
    try:
        parsed = urlsplit(token)
    except ValueError:
        return token
    if not parsed.scheme or parsed.password is None:
        return token
    hostname = parsed.hostname or ""
    if parsed.port:
        hostname += f":{parsed.port}"
    username = parsed.username or "user"
    return urlunsplit(
        (
            parsed.scheme,
            f"{username}:***@{hostname}",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def show_external_command(
    provider: str, command: Sequence[str], cwd: Path, mutation: str
) -> None:
    shown = shlex.join(redact_token(token) for token in command)
    runner_version = command_version([command[0], "--version"]) or "version unknown"
    package = ""
    if command[0] == "npx" and len(command) > 2:
        package = f"; package={command[2]}"
    print(
        f"[{provider}] runner={runner_version}{package}; {mutation}; cwd={cwd}",
        file=sys.stderr,
    )
    print(f"$ {shown}", file=sys.stderr)


def run_external(
    provider: str,
    command: Sequence[str],
    cwd: Path,
    mutation: str,
    *,
    dry_run: bool = False,
) -> subprocess.CompletedProcess[str]:
    show_external_command(provider, command, cwd, mutation)
    if dry_run:
        return subprocess.CompletedProcess(command, 0, "", "")
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=True,
            timeout=120,
        )
    except FileNotFoundError as error:
        raise WorkshopError(f"{provider} executable not found: {command[0]}") from error
    except subprocess.TimeoutExpired as error:
        raise WorkshopError(
            f"{provider} command timed out after 120 seconds"
        ) from error


def iter_text(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_text(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_text(child)


def memory_search(root: Path, query: str, limit: int) -> list[dict[str, Any]]:
    terms = WORD.findall(query.casefold())
    if not terms:
        raise WorkshopError("search query must contain a letter or number")
    events_by_skill: dict[str, list[dict[str, Any]]] = {}
    for _, event in load_records(root, "events"):
        events_by_skill.setdefault(event.get("skill_id", ""), []).append(event)
    results: list[dict[str, Any]] = []
    for _, skill in load_records(root, "skills"):
        name = skill.get("name", "").casefold()
        summary = skill.get("summary", "").casefold()
        aliases = " ".join(skill.get("aliases", [])).casefold()
        history = " ".join(
            iter_text(events_by_skill.get(skill.get("id", ""), []))
        ).casefold()
        sources = " ".join(iter_text(skill.get("sources", []))).casefold()
        haystack = " ".join(
            (
                name,
                summary,
                aliases,
                history,
                sources,
                skill.get("notes", "").casefold(),
            )
        )
        if not all(term in haystack for term in terms):
            continue
        score = sum(
            10 * name.count(term)
            + 6 * aliases.count(term)
            + 4 * summary.count(term)
            + 2 * history.count(term)
            + sources.count(term)
            for term in terms
        )
        results.append(
            {
                "provider": "memory",
                "skill_id": skill["id"],
                "name": skill["name"],
                "summary": skill["summary"],
                "sources": [source["locator"] for source in skill.get("sources", [])],
                "score": score,
            }
        )
    return sorted(results, key=lambda item: (-item["score"], item["name"]))[:limit]


def provider_commands(query: str, limit: int) -> dict[str, list[str]]:
    return {
        "asm": [
            "npx",
            "--yes",
            f"agent-skill-manager@{ASM_VERSION}",
            "search",
            query,
            "--available",
            "--machine",
        ],
        "github": [
            "gh",
            "skill",
            "search",
            query,
            "--limit",
            str(limit),
            "--json",
            "skillName,description,repo,path,namespace,stars",
        ],
        "vercel": ["npx", "--yes", f"skills@{VERCEL_SKILLS_VERSION}", "find", query],
    }


def parse_provider_results(
    provider: str, stdout: str, limit: int
) -> list[dict[str, Any]]:
    if not stdout:
        return []
    if provider == "asm":
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return []
        data = payload.get("data", []) if isinstance(payload, dict) else []
        return [item for item in data if isinstance(item, dict)][:limit]
    if provider == "github":
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return []
        return [item for item in payload if isinstance(item, dict)][:limit]
    if provider == "vercel":
        lines = [
            line.strip()
            for line in ANSI_ESCAPE.sub("", stdout).splitlines()
            if line.strip()
        ]
        results: list[dict[str, Any]] = []
        previous = ""
        for line in lines:
            if line.startswith("└ http") and previous:
                match = re.match(
                    r"^(?P<candidate>.+?)\s+(?P<popularity>[0-9.]+[KMB]? installs?)$",
                    previous,
                    re.IGNORECASE,
                )
                results.append(
                    {
                        "candidate": match.group("candidate") if match else previous,
                        "popularity": match.group("popularity") if match else None,
                        "url": line.removeprefix("└ "),
                    }
                )
                if len(results) >= limit:
                    break
            previous = line
        return results
    raise WorkshopError(f"unknown discovery provider: {provider}")


def compact_text(value: str, length: int = 300) -> str:
    normalized = " ".join(value.split())
    return normalized if len(normalized) <= length else normalized[: length - 1] + "…"


def print_provider_result(item: dict[str, Any]) -> None:
    name = (
        item.get("name")
        or item.get("skillName")
        or item.get("candidate")
        or "candidate"
    )
    print(name)
    description = item.get("description")
    if description:
        print(f"  {compact_text(str(description))}")
    locator = item.get("url")
    if not locator and item.get("repo"):
        locator = item["repo"]
        if item.get("path"):
            locator += f" :: {item['path']}"
    if locator:
        print(f"  source: {locator}")
    popularity = item.get("popularity")
    if popularity:
        print(f"  signal: {popularity}")


def cmd_validate(args: argparse.Namespace) -> int:
    errors = validate_memory(args.root)
    if args.json:
        print(json.dumps({"valid": not errors, "errors": errors}, indent=2))
    elif errors:
        print("Memory is invalid:")
        for error in errors:
            print(f"- {error}")
    else:
        counts = {kind: len(record_paths(args.root, kind)) for kind in SCHEMA_NAMES}
        print("Memory is valid (v0).")
        print("; ".join(f"{kind}: {count}" for kind, count in counts.items()))
    return 1 if errors else 0


def command_version(command: Sequence[str]) -> str | None:
    if shutil.which(command[0]) is None:
        return None
    try:
        completed = subprocess.run(
            command, check=False, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.TimeoutExpired):
        return "available (version check failed)"
    text = (completed.stdout or completed.stderr).strip().splitlines()
    return text[0] if text else f"available (exit {completed.returncode})"


def apm_version() -> str:
    reported = command_version(["apm", "--version"]) or "unknown"
    match = re.search(
        r"\bversion\s+([0-9]+(?:\.[0-9]+)+(?:[-+][0-9A-Za-z.-]+)?)", reported
    )
    return match.group(1) if match else reported


def cmd_doctor(args: argparse.Namespace) -> int:
    tools = {
        "apm": {
            "role": "project manifest, lock, dependency resolution, deployment, and audit",
            "version": apm_version(),
            "authority": "project state",
        },
        "gh-skill": {
            "role": "GitHub search, preview, source provenance, and publication",
            "version": command_version(["gh", "--version"]),
            "authority": "discovery only in this workflow",
        },
        "asm": {
            "role": "cross-provider catalog search and inspection",
            "version": f"npx package pinned to {ASM_VERSION}",
            "authority": "discovery only in this workflow",
        },
        "vercel-skills": {
            "role": "skills.sh and .well-known discovery",
            "version": f"npx package pinned to {VERCEL_SKILLS_VERSION}",
            "authority": "discovery only in this workflow",
        },
        "workshop": {
            "role": "source-agnostic recall, use evidence, ratings, evaluations, and contributions",
            "version": VERSION,
            "authority": "cross-project memory only",
        },
    }
    tools["node"] = {
        "role": "runtime for pinned discovery CLIs",
        "version": command_version(["node", "--version"]),
        "authority": "runtime",
    }
    if args.json:
        print(json.dumps(tools, indent=2))
    else:
        print("Authority boundaries")
        for name, detail in tools.items():
            version = detail["version"] or "not found"
            print(f"- {name}: {detail['role']}")
            print(f"  authority: {detail['authority']}; {version}")
        print("\nDiscovery tools never install into APM-managed project paths.")
        print("Every delegated command is printed before it runs.")
    return 0


def selected_providers(values: list[str] | None) -> list[str]:
    requested = values or ["memory"]
    if "all" in requested:
        return ["memory", "asm", "github", "vercel"]
    output: list[str] = []
    for provider in requested:
        if provider not in output:
            output.append(provider)
    return output


def cmd_find(args: argparse.Namespace) -> int:
    providers = selected_providers(args.provider)
    output: dict[str, Any] = {}
    failures = 0
    if "memory" in providers:
        output["memory"] = memory_search(args.root, args.query, args.limit)
    for provider in [item for item in providers if item != "memory"]:
        command = provider_commands(args.query, args.limit)[provider]
        completed = run_external(
            provider,
            command,
            args.root,
            "read-only search: no project skill writes; may use network, auth, telemetry, and caches",
            dry_run=args.dry_run,
        )
        output[provider] = {
            "command": command,
            "executed": not args.dry_run,
            "exit_code": completed.returncode,
            "results": parse_provider_results(provider, completed.stdout, args.limit),
            "stderr": completed.stderr,
        }
        if completed.returncode:
            failures += 1
    if args.json:
        print(json.dumps(output, indent=2))
    else:
        for provider in providers:
            print(f"\n== {provider} ==")
            result = output[provider]
            if provider == "memory":
                if not result:
                    print("No remembered skills matched.")
                for skill in result:
                    print(f"{skill['name']} [{skill['skill_id']}]")
                    print(f"  {skill['summary']}")
                    for source in skill["sources"]:
                        print(f"  source: {source}")
            elif args.dry_run:
                print("Dry run; command not executed.")
            else:
                if not result["results"]:
                    print("No candidates returned.")
                for candidate in result["results"]:
                    print_provider_result(candidate)
                if result["stderr"]:
                    print(result["stderr"].rstrip(), file=sys.stderr)
                if result["exit_code"]:
                    print(f"Provider exited {result['exit_code']}.")
    return (
        1
        if failures == len([item for item in providers if item != "memory"])
        and failures
        else 0
    )


def cmd_preview(args: argparse.Namespace) -> int:
    command = ["gh", "skill", "preview", args.repository, args.skill]
    if args.allow_hidden_dirs:
        command.append("--allow-hidden-dirs")
    completed = run_external(
        "github",
        command,
        args.root,
        "read-only candidate preview; may use network and GitHub authentication",
        dry_run=args.dry_run,
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    if args.dry_run:
        print("Dry run; preview command not executed.")
    return completed.returncode


def cmd_remember(args: argparse.Namespace) -> int:
    if not SKILL_NAME.fullmatch(args.name):
        raise WorkshopError("name must follow the Agent Skills lowercase-hyphen form")
    if resolve_record(args.root, "skills", args.name, allow_missing=True):
        raise WorkshopError(f"skill already remembered: {args.name}")
    timestamp = now()
    skill_id = new_id()
    sources: list[dict[str, Any]] = []
    preferred_source_id: str | None = None
    if args.source:
        source_id = new_id()
        sources.append(
            {
                "id": source_id,
                "kind": args.source_kind,
                "locator": args.source,
                "subpath": args.subpath,
                "role": args.source_role,
                "first_seen_at": timestamp,
                "external_ids": {},
                "notes": args.source_notes,
            }
        )
        preferred_source_id = source_id
    record: dict[str, Any] = {
        "schema": schema_uri("skills"),
        "id": skill_id,
        "name": args.name,
        "aliases": args.alias,
        "summary": args.summary,
        "sources": sources,
        "artifacts": [],
        "tag_ids": [],
        "relations": [],
        "created_at": timestamp,
        "updated_at": timestamp,
        "notes": args.notes,
        "extensions": {},
    }
    if preferred_source_id:
        record["preferred_source_id"] = preferred_source_id
    path = memory_dir(args.root, "skills") / f"{bare_id(skill_id)}.json"
    atomic_write_validated(args.root, path, record)
    print(f"Remembered {args.name}: {skill_id}")
    print(path)
    return 0


def cmd_source_add(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    duplicate = next(
        (
            source
            for source in skill["sources"]
            if source["kind"] == args.source_kind
            and source["locator"] == args.source
            and source.get("subpath") == args.subpath
        ),
        None,
    )
    if duplicate:
        raise WorkshopError(f"source already recorded as {duplicate['id']}")
    source_id = new_id()
    skill["sources"].append(
        {
            "id": source_id,
            "kind": args.source_kind,
            "locator": args.source,
            "subpath": args.subpath,
            "role": args.source_role,
            "first_seen_at": now(),
            "external_ids": {},
            "notes": args.notes,
        }
    )
    if args.preferred or "preferred_source_id" not in skill:
        skill["preferred_source_id"] = source_id
    skill["updated_at"] = now()
    path = memory_dir(args.root, "skills") / f"{bare_id(skill['id'])}.json"
    atomic_write_validated(args.root, path, skill)
    print(f"Added source to {skill['name']}: {source_id}")
    print(path)
    return 0


def cmd_artifact_add(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    sources = skill["sources"]
    if args.source:
        source_matches = [
            source
            for source in sources
            if args.source in {source["id"], bare_id(source["id"]), source["locator"]}
        ]
        if len(source_matches) != 1:
            raise WorkshopError("--source must identify exactly one recorded source")
        source = source_matches[0]
    else:
        preferred = skill.get("preferred_source_id")
        source = next((item for item in sources if item["id"] == preferred), None)
        if source is None:
            raise WorkshopError("no preferred source; specify --source")
    digest = {
        "scheme": args.digest_scheme,
        "algorithm": args.digest_algorithm,
        "scope": args.digest_scope,
        "value": args.digest_value,
    }
    duplicate = next(
        (
            artifact
            for artifact in skill["artifacts"]
            if artifact["source_id"] == source["id"]
            and artifact["resolved_revision"] == args.revision
            and digest in artifact["digests"]
        ),
        None,
    )
    if duplicate:
        raise WorkshopError(f"artifact already recorded as {duplicate['id']}")
    artifact_id = new_id()
    skill["artifacts"].append(
        {
            "id": artifact_id,
            "source_id": source["id"],
            "version_label": args.version_label,
            "resolved_revision": args.revision,
            "digests": [digest],
            "observed_at": now(),
        }
    )
    skill["updated_at"] = now()
    path = memory_dir(args.root, "skills") / f"{bare_id(skill['id'])}.json"
    atomic_write_validated(args.root, path, skill)
    print(f"Added exact artifact to {skill['name']}: {artifact_id}")
    print(path)
    return 0


def cmd_project_add(args: argparse.Namespace) -> int:
    if resolve_record(args.root, "projects", args.name, allow_missing=True):
        raise WorkshopError(f"project already remembered: {args.name}")
    timestamp = now()
    project_id = new_id()
    record = {
        "schema": schema_uri("projects"),
        "id": project_id,
        "name": args.name,
        "aliases": args.alias,
        "repository": {"url": args.repo_url, "subpath": args.subpath}
        if args.repo_url
        else None,
        "managers": [
            {
                "kind": "apm",
                "manifest_path": args.manifest,
                "lock_path": args.lock,
            }
        ],
        "created_at": timestamp,
        "updated_at": timestamp,
        "notes": args.notes,
        "extensions": {},
    }
    path = memory_dir(args.root, "projects") / f"{bare_id(project_id)}.json"
    atomic_write_validated(args.root, path, record)
    print(f"Remembered project {args.name}: {project_id}")
    print(path)
    return 0


def apm_lock_memberships(lock: dict[str, Any]) -> list[dict[str, Any]]:
    """Return dependency and root-local skill observations from an APM lock."""
    dependencies = lock.get("dependencies")
    if not isinstance(dependencies, list):
        raise WorkshopError("APM lock has no dependencies array")

    observations: list[dict[str, Any]] = []
    for dependency in dependencies:
        if not isinstance(dependency, dict) or not isinstance(
            dependency.get("name"), str
        ):
            continue
        observations.append(
            {
                "name": dependency["name"],
                "selector": dependency.get("local_path")
                or dependency.get("repo_url")
                or dependency["name"],
                "resolution": dependency,
            }
        )

    deployments = lock.get("deployments", [])
    local_files = lock.get("local_deployed_files", [])
    local_hashes = lock.get("local_deployed_file_hashes", {})
    if not isinstance(deployments, list):
        deployments = []
    if not isinstance(local_files, list):
        local_files = []
    if not isinstance(local_hashes, dict):
        local_hashes = {}

    roots_by_name: dict[str, set[str]] = {}
    for deployment in deployments:
        if not isinstance(deployment, dict):
            continue
        value = deployment.get("value")
        if (
            deployment.get("active_owner") != "."
            or deployment.get("content_hash") is not None
            or not isinstance(value, str)
        ):
            continue
        parts = Path(value).parts
        if len(parts) < 2 or parts[-2] != "skills":
            continue
        roots_by_name.setdefault(parts[-1], set()).add(value)

    for name, roots in sorted(roots_by_name.items()):
        files = {
            path: local_hashes.get(path)
            for path in sorted(item for item in local_files if isinstance(item, str))
            if any(path == root or path.startswith(f"{root}/") for root in roots)
        }
        observations.append(
            {
                "name": name,
                "selector": f".apm/skills/{name}",
                "resolution": {
                    "source": "project-local",
                    "source_path": f".apm/skills/{name}",
                    "deployed_roots": sorted(roots),
                    "deployed_file_hashes": files,
                },
            }
        )
    return observations


def cmd_project_scan(args: argparse.Namespace) -> int:
    project = resolve_record(args.root, "projects", args.project)
    assert project is not None
    manager = project["managers"][0]
    lock_path = args.project_path.resolve() / manager["lock_path"]
    if not lock_path.is_file():
        raise WorkshopError(f"APM lock not found: {lock_path}")
    try:
        lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise WorkshopError(f"cannot read APM lock: {error}") from error
    if not isinstance(lock, dict):
        raise WorkshopError("APM lock root must be an object")
    observations = apm_lock_memberships(lock)

    known = {record["name"]: record for _, record in load_records(args.root, "skills")}
    existing = [event for _, event in load_records(args.root, "events")]
    base_evidence = project_evidence(args.root, project, args.project_path)
    added = 0
    skipped: set[str] = set()
    args.asserted_kind = "tool"
    args.asserted_by = "apm-lock"
    args.model = None
    args.runtime = "apm"
    args.runtime_version = base_evidence["apm_version"]
    args.reasoning_effort = None
    for observation in observations:
        name = observation["name"]
        skill = known.get(name)
        if skill is None:
            skipped.add(name)
            continue
        evidence = dict(base_evidence)
        evidence["dependency_selector"] = observation["selector"]

        resolution_digest = (
            "sha256:"
            + hashlib.sha256(
                json.dumps(
                    observation["resolution"],
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
        )
        duplicate = any(
            event.get("type") == "project-membership"
            and event.get("skill_id") == skill["id"]
            and event.get("payload", {}).get("state") == "resolved"
            and event.get("project_evidence", {}).get("project_id") == project["id"]
            and event.get("payload", {}).get("resolution_digest") == resolution_digest
            for event in existing
        )
        if duplicate:
            continue
        path, record = make_event(
            args,
            skill["id"],
            "project-membership",
            {
                "state": "resolved",
                "skill_name": name,
                "resolution_digest": resolution_digest,
            },
            project_evidence=evidence,
        )
        atomic_write_validated(args.root, path, record)
        existing.append(record)
        added += 1
    print(f"Recorded {added} APM membership event(s) for {project['name']}.")
    if skipped:
        print("Not remembered; left only in APM: " + ", ".join(sorted(skipped)))
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    history = [
        event
        for _, event in load_records(args.root, "events")
        if event.get("skill_id") == skill["id"]
    ]
    if args.json:
        print(json.dumps({"skill": skill, "events": history}, indent=2))
    else:
        print(f"{skill['name']} [{skill['id']}]")
        print(skill["summary"])
        if skill["aliases"]:
            print("Aliases: " + ", ".join(skill["aliases"]))
        for source in skill["sources"]:
            subpath = f" :: {source['subpath']}" if source.get("subpath") else ""
            print(
                f"Source ({source['role']}, {source['kind']}): "
                f"{source['locator']}{subpath}"
            )
            if source.get("notes"):
                print(f"  {source['notes']}")
        for artifact in skill["artifacts"]:
            print(
                f"Artifact: {artifact['id']} at {artifact['resolved_revision']} "
                f"({len(artifact['digests'])} digest(s))"
            )
        print(f"History: {len(history)} event(s)")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    events = sorted(
        (
            event
            for _, event in load_records(args.root, "events")
            if event.get("skill_id") == skill["id"]
        ),
        key=lambda item: item["occurred_at"],
    )
    if args.json:
        print(json.dumps(events, indent=2))
    else:
        print(f"History for {skill['name']} ({len(events)} event(s))")
        for event in events:
            payload = event["payload"]
            summary = payload.get("reason") or payload.get("task_summary")
            summary = summary or payload.get("summary")
            if not summary and event["type"] == "project-membership":
                summary = f"{payload['state']} {payload['skill_name']}"
            if not summary and event["type"] == "evaluation":
                summary = f"evaluation {payload['conclusion']}"
            summary = summary or "no human summary"
            actor = event["asserted_by"]
            review = event["review"]["state"]
            print(
                f"- {event['occurred_at']} {event['type']} "
                f"[{actor['kind']}:{actor['id']}; {review}]: {summary}"
            )
    return 0


def cmd_consider(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    path, record = make_event(
        args,
        skill["id"],
        "consideration",
        {"decision": args.decision, "reason": args.reason},
    )
    atomic_write_validated(args.root, path, record)
    print(f"Recorded {args.decision} for {skill['name']}")
    print(path)
    return 0


def cmd_contribution_add(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    path, record = make_event(
        args,
        skill["id"],
        "contribution",
        {
            "kind": args.kind,
            "direction": args.direction,
            "url": args.url,
            "state": args.state,
            "summary": args.summary,
        },
        artifact_id=args.artifact,
    )
    atomic_write_validated(args.root, path, record)
    print(f"Recorded {args.state} {args.kind} for {skill['name']}")
    print(path)
    return 0


def project_evidence(
    root: Path, project: dict[str, Any], project_path: Path
) -> dict[str, Any]:
    project_path = project_path.resolve()
    manager = project["managers"][0]
    manifest = project_path / manager["manifest_path"]
    lock = project_path / manager["lock_path"]
    if not manifest.is_file() or not lock.is_file():
        raise WorkshopError(
            f"project evidence requires {manager['manifest_path']} and {manager['lock_path']}"
        )
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_path,
        check=False,
        text=True,
        capture_output=True,
    )
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=project_path,
        check=False,
        text=True,
        capture_output=True,
    )
    import hashlib

    lock_digest = hashlib.sha256(lock.read_bytes()).hexdigest()
    return {
        "project_id": project["id"],
        "repository_commit": revision.stdout.strip()
        if revision.returncode == 0
        else None,
        "dirty": bool(status.stdout.strip()) if status.returncode == 0 else True,
        "manifest_path": manager["manifest_path"],
        "lock_path": manager["lock_path"],
        "lock_digest": f"sha256:{lock_digest}",
        "dependency_selector": None,
        "command": ["apm", "deps", "list"],
        "apm_version": apm_version(),
    }


def cmd_use(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    evidence = None
    if args.project:
        project = resolve_record(args.root, "projects", args.project)
        assert project is not None
        if args.project_path is None:
            raise WorkshopError("--project-path is required when --project is used")
        evidence = project_evidence(args.root, project, args.project_path)
    payload: dict[str, Any] = {
        "task_summary": args.task,
        "invocation": args.invocation,
        "outcome": args.outcome,
        "rationale": args.rationale,
        "listing_state": args.listing_state,
    }
    if args.rating is not None:
        payload["rating"] = args.rating
        payload["scale_id"] = "workshop-overall-v1"
    if args.duration_seconds is not None:
        payload["duration_seconds"] = args.duration_seconds
    path, record = make_event(
        args,
        skill["id"],
        "use",
        payload,
        project_evidence=evidence,
        artifact_id=args.artifact,
    )
    atomic_write_validated(args.root, path, record)
    print(f"Recorded use of {skill['name']}")
    print(path)
    return 0


def cmd_where_used(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    projects = {
        record["id"]: record for _, record in load_records(args.root, "projects")
    }
    rows = []
    for _, event in load_records(args.root, "events"):
        if event.get("skill_id") != skill["id"] or event.get("type") not in {
            "use",
            "project-membership",
        }:
            continue
        evidence = event.get("project_evidence") or {}
        project = projects.get(evidence.get("project_id"), {})
        rows.append(
            {
                "event_id": event["id"],
                "type": event["type"],
                "occurred_at": event["occurred_at"],
                "project_id": evidence.get("project_id"),
                "project_name": project.get("name"),
                "payload": event["payload"],
            }
        )
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"Project evidence for {skill['name']} ({len(rows)} event(s))")
        for row in rows:
            project = row["project_name"] or row["project_id"] or "no project recorded"
            print(f"- {row['occurred_at']} {row['type']}: {project}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    project = args.project.resolve()
    if not project.is_dir():
        raise WorkshopError(f"project directory does not exist: {project}")
    command = ["apm", "install", args.package]
    for skill in args.skill:
        command.extend(["--skill", skill])
    if args.target:
        command.extend(["--target", args.target])
    if args.no_policy:
        command.append("--no-policy")
    mutation = (
        "will update the project's apm.yml, apm.lock.yaml, cache, and deployed files"
    )
    if not args.apply:
        command.append("--dry-run")
        mutation = "preview only; APM may read the network and cache metadata"
    completed = run_external("apm", command, project, mutation)
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    if not args.apply:
        output = f"{completed.stdout or ''}\n{completed.stderr or ''}".casefold()
        inconsistent = "would add " in output and "would install no changes" in output
        if inconsistent:
            print(
                "WARNING: APM's preview is internally inconsistent: it reports a "
                "package addition but no installation change. Do not treat this "
                "preview as approval to apply; inspect with APM or defer the change.",
                file=sys.stderr,
            )
            print(
                "Preview complete with an unresolved APM inconsistency; do not apply."
            )
        else:
            print(
                "Preview complete. Re-run with --apply to let APM own the project change."
            )
    return completed.returncode


def cmd_audit(args: argparse.Namespace) -> int:
    project = args.project.resolve()
    command = ["apm", "audit"]
    if args.ci:
        command.append("--ci")
    if args.no_policy:
        command.append("--no-policy")
    if args.format:
        command.extend(["--format", args.format])
    completed = run_external(
        "apm", command, project, "read-only integrity, drift, and hidden-Unicode audit"
    )
    if completed.stdout:
        print(completed.stdout.rstrip())
    if completed.stderr:
        print(completed.stderr.rstrip(), file=sys.stderr)
    return completed.returncode


def cmd_eval_init(args: argparse.Namespace) -> int:
    skill = resolve_record(args.root, "skills", args.skill)
    assert skill is not None
    if args.design != "exploratory" and not args.artifact:
        raise WorkshopError("controlled and replicated designs require --artifact")
    timestamp = now()
    evaluation_id = new_id()
    runtime = {
        "agent": args.agent,
        "agent_version": args.agent_version,
        "model": args.model,
        "reasoning_effort": args.reasoning_effort,
        "tools": args.tool,
        "permissions": args.permission,
        "budget": {
            "time_seconds": args.time_budget_seconds,
            "token_limit": args.token_budget,
            "turn_limit": args.turn_budget,
            "notes": args.budget_notes,
        },
    }
    record = {
        "schema": schema_uri("evaluations"),
        "id": evaluation_id,
        "skill_id": skill["id"],
        "created_at": timestamp,
        "status": "planned",
        "design": args.design,
        "hypothesis": args.hypothesis,
        "protocol": {"uri": args.protocol, "digest": args.protocol_digest},
        "fixture": {"uri": args.fixture, "digest": args.fixture_digest},
        "conditions": [
            {
                "id": "without-skill",
                "label": "Baseline without the skill",
                "skill_enabled": False,
                "artifact_id": None,
                "runtime": runtime,
                "isolation": args.isolation,
            },
            {
                "id": "with-skill",
                "label": "Treatment with the exact skill artifact",
                "skill_enabled": True,
                "artifact_id": args.artifact,
                "runtime": runtime,
                "isolation": args.isolation,
            },
        ],
        "cases": [
            {
                "id": "case-1",
                "prompt": args.prompt,
                "fixture_revision": args.fixture_revision,
                "expected": args.expected,
            }
        ],
        "metrics": [
            {
                "id": "primary",
                "description": args.metric,
                "unit": args.metric_unit,
                "direction": args.metric_direction,
            }
        ],
        "runs": [],
        "grading": {
            "kind": "unassigned",
            "grader": None,
            "rubric": None,
            "blinded": False,
        },
        "analysis": {"conclusion": "planned", "summary": "", "limitations": []},
        "extensions": {},
    }
    path = memory_dir(args.root, "evaluations") / f"{bare_id(evaluation_id)}.json"
    atomic_write_validated(args.root, path, record)
    print(f"Created {args.design} evaluation scaffold for {skill['name']}")
    print(path)
    print(
        "A single agent pair is exploratory evidence; fill runs and grading before concluding."
    )
    return 0


def add_actor_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--asserted-kind", choices=["human", "agent", "tool"], required=True
    )
    parser.add_argument(
        "--asserted-by", required=True, help="identity making the assertion"
    )
    parser.add_argument("--model")
    parser.add_argument("--runtime")
    parser.add_argument("--runtime-version")
    parser.add_argument("--reasoning-effort")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remember, discover, install, and evaluate skills without duplicating APM state."
    )
    parser.add_argument("--root", type=Path, default=REPOSITORY, help=argparse.SUPPRESS)
    parser.add_argument(
        "--version", action="version", version=f"skills-workshop {VERSION}"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser(
        "validate", help="validate schemas, records, and references"
    )
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(handler=cmd_validate)

    doctor = commands.add_parser(
        "doctor", help="show tool availability and authority boundaries"
    )
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=cmd_doctor)

    find = commands.add_parser(
        "find", help="search local memory and selected external providers"
    )
    find.add_argument("query")
    find.add_argument(
        "--provider",
        action="append",
        choices=["memory", "asm", "github", "vercel", "all"],
        help="repeat to combine; defaults to memory",
    )
    find.add_argument("--limit", type=int, default=10)
    find.add_argument("--dry-run", action="store_true")
    find.add_argument("--json", action="store_true")
    find.set_defaults(handler=cmd_find)

    preview = commands.add_parser(
        "preview", help="delegate a non-installing GitHub skill-tree preview"
    )
    preview.add_argument("repository", help="GitHub OWNER/REPO or repository URL")
    preview.add_argument("skill", help="skill name, path, or name@commit")
    preview.add_argument("--allow-hidden-dirs", action="store_true")
    preview.add_argument("--dry-run", action="store_true")
    preview.set_defaults(handler=cmd_preview)

    remember = commands.add_parser(
        "remember", help="create a source-agnostic skill record"
    )
    remember.add_argument("name")
    remember.add_argument("--summary", required=True)
    remember.add_argument("--alias", action="append", default=[])
    remember.add_argument("--source")
    remember.add_argument(
        "--source-kind",
        choices=["git", "registry", "well-known", "http", "local", "unknown"],
        default="unknown",
    )
    remember.add_argument(
        "--source-role",
        choices=["canonical", "fork", "mirror", "discovery", "deprecated"],
        default="discovery",
    )
    remember.add_argument("--subpath")
    remember.add_argument("--source-notes", default="")
    remember.add_argument("--notes", default="")
    remember.set_defaults(handler=cmd_remember)

    source = commands.add_parser(
        "source", help="manage source candidates for a logical skill"
    )
    source_commands = source.add_subparsers(dest="source_command", required=True)
    source_add = source_commands.add_parser(
        "add", help="add a source without changing skill identity"
    )
    source_add.add_argument("skill")
    source_add.add_argument("--source", required=True)
    source_add.add_argument(
        "--source-kind",
        required=True,
        choices=["git", "registry", "well-known", "http", "local", "unknown"],
    )
    source_add.add_argument(
        "--source-role",
        required=True,
        choices=["canonical", "fork", "mirror", "discovery", "deprecated"],
    )
    source_add.add_argument("--subpath")
    source_add.add_argument("--notes", default="")
    source_add.add_argument("--preferred", action="store_true")
    source_add.set_defaults(handler=cmd_source_add)

    artifact = commands.add_parser(
        "artifact", help="record exact observed skill artifacts for evidence"
    )
    artifact_commands = artifact.add_subparsers(dest="artifact_command", required=True)
    artifact_add = artifact_commands.add_parser(
        "add", help="bind a source revision and scoped digest to a logical skill"
    )
    artifact_add.add_argument("skill")
    artifact_add.add_argument(
        "--source",
        help="source UUID, bare UUID, or exact locator; defaults to preferred",
    )
    artifact_add.add_argument("--revision", required=True)
    artifact_add.add_argument("--version-label")
    artifact_add.add_argument("--digest-scheme", required=True)
    artifact_add.add_argument("--digest-algorithm", required=True)
    artifact_add.add_argument("--digest-scope", required=True)
    artifact_add.add_argument("--digest-value", required=True)
    artifact_add.set_defaults(handler=cmd_artifact_add)

    show = commands.add_parser("show", help="show a skill and its evidence count")
    show.add_argument("skill")
    show.add_argument("--json", action="store_true")
    show.set_defaults(handler=cmd_show)

    history = commands.add_parser(
        "history", help="show append-only history for a skill"
    )
    history.add_argument("skill")
    history.add_argument("--json", action="store_true")
    history.set_defaults(handler=cmd_history)

    consider = commands.add_parser("consider", help="record an adoption decision")
    consider.add_argument("skill")
    consider.add_argument(
        "--decision",
        required=True,
        choices=["considering", "adopted", "deferred", "rejected", "retired"],
    )
    consider.add_argument("--reason", required=True)
    add_actor_options(consider)
    consider.set_defaults(handler=cmd_consider)

    contribution = commands.add_parser(
        "contribution", help="record an upstream, downstream, or peer contribution"
    )
    contribution_commands = contribution.add_subparsers(
        dest="contribution_command", required=True
    )
    contribution_add = contribution_commands.add_parser(
        "add", help="append a contribution link and observed state"
    )
    contribution_add.add_argument("skill")
    contribution_add.add_argument(
        "--kind",
        required=True,
        choices=[
            "issue",
            "pull-request",
            "commit",
            "release",
            "publication",
            "discussion",
        ],
    )
    contribution_add.add_argument(
        "--direction", required=True, choices=["upstream", "downstream", "peer"]
    )
    contribution_add.add_argument("--url", required=True)
    contribution_add.add_argument(
        "--state",
        required=True,
        choices=["draft", "submitted", "open", "merged", "closed", "released"],
    )
    contribution_add.add_argument("--summary", required=True)
    contribution_add.add_argument("--artifact")
    add_actor_options(contribution_add)
    contribution_add.set_defaults(handler=cmd_contribution_add)

    use = commands.add_parser(
        "use", help="record actual use and an optional lightweight rating"
    )
    use.add_argument("skill")
    use.add_argument("--task", required=True)
    use.add_argument(
        "--invocation", required=True, choices=["explicit", "automatic", "unknown"]
    )
    use.add_argument(
        "--outcome",
        required=True,
        choices=["success", "partial", "failure", "abandoned", "unknown"],
    )
    use.add_argument("--rating", type=int, choices=range(1, 6))
    use.add_argument("--rationale", required=True)
    use.add_argument("--duration-seconds", type=float)
    use.add_argument(
        "--listing-state",
        default="unknown",
        choices=["full-description", "name-only", "manual-only", "off", "unknown"],
    )
    use.add_argument("--project")
    use.add_argument("--project-path", type=Path)
    use.add_argument("--artifact")
    add_actor_options(use)
    use.set_defaults(handler=cmd_use)

    where_used = commands.add_parser(
        "where-used", help="show declared and actual project use"
    )
    where_used.add_argument("skill")
    where_used.add_argument("--json", action="store_true")
    where_used.set_defaults(handler=cmd_where_used)

    project = commands.add_parser("project", help="manage project memory pointers")
    project_commands = project.add_subparsers(dest="project_command", required=True)
    project_add = project_commands.add_parser(
        "add", help="remember APM authority files for a project"
    )
    project_add.add_argument("name")
    project_add.add_argument("--alias", action="append", default=[])
    project_add.add_argument("--repo-url")
    project_add.add_argument("--subpath")
    project_add.add_argument("--manifest", default="apm.yml")
    project_add.add_argument("--lock", default="apm.lock.yaml")
    project_add.add_argument("--notes", default="")
    project_add.set_defaults(handler=cmd_project_add)
    project_scan = project_commands.add_parser(
        "scan", help="record APM-resolved membership without claiming actual use"
    )
    project_scan.add_argument("project")
    project_scan.add_argument("--project-path", type=Path, required=True)
    project_scan.set_defaults(handler=cmd_project_scan)

    install = commands.add_parser(
        "install", help="preview or delegate installation to project-local APM"
    )
    install.add_argument("package")
    install.add_argument("--project", type=Path, required=True)
    install.add_argument("--skill", action="append", default=[])
    install.add_argument("--target")
    install.add_argument(
        "--no-policy",
        action="store_true",
        help="explicitly skip APM organization-policy discovery",
    )
    install.add_argument(
        "--apply", action="store_true", help="apply after the default APM dry run"
    )
    install.set_defaults(handler=cmd_install)

    audit = commands.add_parser(
        "audit", help="delegate integrity and drift audit to APM"
    )
    audit.add_argument("project", type=Path)
    audit.add_argument("--ci", action="store_true")
    audit.add_argument(
        "--no-policy",
        action="store_true",
        help="explicitly skip APM organization-policy discovery",
    )
    audit.add_argument("--format", choices=["text", "json", "sarif", "markdown"])
    audit.set_defaults(handler=cmd_audit)

    evaluation = commands.add_parser("eval", help="manage explicit skill evaluations")
    evaluation_commands = evaluation.add_subparsers(
        dest="evaluation_command", required=True
    )
    evaluation_init = evaluation_commands.add_parser(
        "init", help="create a paired with-skill/without-skill evaluation scaffold"
    )
    evaluation_init.add_argument("skill")
    evaluation_init.add_argument(
        "--design",
        choices=["exploratory", "controlled-paired", "replicated"],
        default="exploratory",
    )
    evaluation_init.add_argument("--hypothesis", required=True)
    evaluation_init.add_argument("--protocol", default="docs/evaluation-protocol.md")
    evaluation_init.add_argument("--protocol-digest")
    evaluation_init.add_argument("--fixture", required=True)
    evaluation_init.add_argument("--fixture-digest")
    evaluation_init.add_argument("--fixture-revision")
    evaluation_init.add_argument("--prompt", required=True)
    evaluation_init.add_argument("--expected", required=True)
    evaluation_init.add_argument("--metric", required=True)
    evaluation_init.add_argument("--metric-unit", default="score")
    evaluation_init.add_argument(
        "--metric-direction",
        choices=["higher-better", "lower-better", "target"],
        default="higher-better",
    )
    evaluation_init.add_argument("--artifact")
    evaluation_init.add_argument("--agent", default="unknown")
    evaluation_init.add_argument("--agent-version")
    evaluation_init.add_argument("--model")
    evaluation_init.add_argument("--reasoning-effort")
    evaluation_init.add_argument("--tool", action="append", default=[])
    evaluation_init.add_argument("--permission", action="append", default=[])
    evaluation_init.add_argument("--time-budget-seconds", type=float)
    evaluation_init.add_argument("--token-budget", type=int)
    evaluation_init.add_argument("--turn-budget", type=int)
    evaluation_init.add_argument("--budget-notes", default="")
    evaluation_init.add_argument(
        "--isolation",
        default="Fresh independent context; no treatment output visible to baseline.",
    )
    evaluation_init.set_defaults(handler=cmd_eval_init)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.root = args.root.resolve()
    try:
        return args.handler(args)
    except WorkshopError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
