#!/usr/bin/env python3
"""Import and organize project skills with an interactive terminal UI."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlsplit

import tomllib
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.suggester import SuggestFromList
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    Select,
    SelectionList,
    Static,
    TextArea,
)

try:
    from .backup_store import store_snapshot
except ImportError:  # Direct execution: python scripts/import_skills.py
    from backup_store import store_snapshot

REPOSITORY = Path(__file__).resolve().parents[1]
MATERIALIZATIONS = REPOSITORY / "materializations"
BACKUPS = REPOSITORY / ".backups"
SAFE_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
DIGEST = re.compile(r"[0-9a-f]{64}")


@dataclass
class SkillMapping:
    name: str
    project_path: Path
    source: str
    bundles: set[str] = field(default_factory=set)
    original_source: str | None = field(default=None, compare=False)


def digest_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(file for file in path.rglob("*") if file.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def project_identity(
    project: Path, requested: str | None = None
) -> tuple[str, str | None]:
    result = subprocess.run(
        ["git", "-C", str(project), "remote", "get-url", "origin"],
        check=False,
        capture_output=True,
        text=True,
    )
    remote = result.stdout.strip() or None
    candidate = requested or project.name
    if not requested and remote:
        if "://" in remote:
            candidate = urlsplit(remote).path.lstrip("/")
        else:
            scp = re.match(r"^(?:[^@/]+@)?[^:/]+:(.+)$", remote)
            candidate = scp.group(1) if scp else remote.strip("/")
        candidate = re.sub(r"\.git$", "", candidate).replace("/", "--")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", candidate):
        raise ValueError(
            "project identifier must contain only letters, digits, dots, "
            "underscores, and hyphens"
        )
    return candidate, remote


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


def validate_skill_tree(
    path: Path, *, context: str, expected_name: str | None = None
) -> None:
    if not path.is_dir() or path.is_symlink() or not (path / "SKILL.md").is_file():
        raise ValueError(f"{context} is not a real skill directory: {path}")
    links = [item for item in path.rglob("*") if item.is_symlink()]
    if links:
        shown = ", ".join(str(item.relative_to(path)) for item in links[:3])
        extra = f" (+{len(links) - 3} more)" if len(links) > 3 else ""
        raise ValueError(
            f"{context} contains symlinks, which import refuses: {shown}{extra}"
        )
    declared_name = declared_skill_name(path / "SKILL.md")
    if not isinstance(declared_name, str) or not SAFE_NAME.fullmatch(declared_name):
        raise ValueError(f"{context} has no valid declared name: {path / 'SKILL.md'}")
    if expected_name is not None and declared_name != expected_name:
        raise ValueError(
            f"{context} declares {declared_name!r}, expected {expected_name!r}"
        )


def validate_project_skills_root(project: Path) -> Path:
    agents = project / ".agents"
    root = agents / "skills"
    for path in (agents, root):
        if (path.exists() or path.is_symlink()) and (
            not path.is_dir() or path.is_symlink()
        ):
            raise ValueError(f"project skill path is not a real directory: {path}")
    return root


def replace_tree(source: Path, destination: Path) -> None:
    validate_skill_tree(source, context="replacement project skill")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{destination.name}.skills-workshop-", dir=destination.parent
    ) as temporary:
        staged = Path(temporary) / "tree"
        shutil.copytree(source, staged, symlinks=False)
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        elif destination.exists() or destination.is_symlink():
            raise FileExistsError(
                f"refusing to replace a non-directory workshop source: {destination}"
            )
        staged.replace(destination)


def source_metadata(source: Path) -> dict[str, str | bool | None]:
    result = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "--show-superproject-working-tree"],
        check=False,
        capture_output=True,
        text=True,
    )
    if not result.stdout.strip():
        return {
            "revision": None,
            "origin_url": None,
            "upstream_url": None,
            "source_dirty": False,
        }
    revision = subprocess.run(
        ["git", "-C", str(source), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    metadata: dict[str, str | bool | None] = {"revision": revision}
    for remote in ("origin", "upstream"):
        result = subprocess.run(
            ["git", "-C", str(source), "remote", "get-url", remote],
            check=False,
            capture_output=True,
            text=True,
        )
        metadata[f"{remote}_url"] = result.stdout.strip() or None
    result = subprocess.run(
        ["git", "-C", str(source), "status", "--porcelain", "--", "."],
        check=True,
        capture_output=True,
        text=True,
    )
    metadata["source_dirty"] = bool(result.stdout)
    return metadata


def backup_source(path: Path, name: str) -> None:
    store_snapshot(
        path,
        BACKUPS,
        ("project-import", name),
        expected_name=name,
    )


def text_diff(source: Path, project: Path) -> str:
    if not source.is_dir():
        return "Source does not exist yet."
    source_file = source / "SKILL.md"
    project_file = project / "SKILL.md"
    return (
        "\n".join(
            difflib.unified_diff(
                source_file.read_text(encoding="utf-8").splitlines(),
                project_file.read_text(encoding="utf-8").splitlines(),
                fromfile="workshop/SKILL.md",
                tofile="project/SKILL.md",
                lineterm="",
            )
        )
        or "SKILL.md is identical."
    )


def read_skill_name(skill_file: Path) -> str:
    return declared_skill_name(skill_file) or skill_file.parent.name


def load_bundles() -> dict[str, dict[str, object]]:
    bundles: dict[str, dict[str, object]] = {}
    for path in sorted((REPOSITORY / "bundles").glob("*.toml")):
        with path.open("rb") as stream:
            manifest = tomllib.load(stream)
        name = manifest.get("name")
        if (
            manifest.get("schema_version") != 1
            or not isinstance(name, str)
            or not SAFE_NAME.fullmatch(name)
            or path.stem != name
            or not isinstance(manifest.get("skills"), list)
        ):
            raise ValueError(f"invalid bundle manifest: {path}")
        seen: set[str] = set()
        for item in manifest["skills"]:
            if not isinstance(item, dict):
                raise TypeError(f"invalid skill entry in {path}")
            skill_name = item.get("name")
            source = item.get("source")
            if not isinstance(skill_name, str) or not SAFE_NAME.fullmatch(skill_name):
                raise ValueError(f"invalid skill name in {path}: {skill_name!r}")
            if skill_name in seen:
                raise ValueError(f"duplicate skill name in {path}: {skill_name!r}")
            seen.add(skill_name)
            if not isinstance(source, str):
                raise TypeError(f"invalid skill source in {path}: {source!r}")
            source_path = validate_source(source)
            if source_path.exists() or source_path.is_symlink():
                validate_skill_tree(
                    source_path,
                    context=f"bundle skill source {source!r}",
                    expected_name=skill_name,
                )
        bundles[name] = manifest
    return bundles


def previous_sources(project: Path, project_id: str | None = None) -> dict[str, str]:
    identity, _ = project_identity(project, project_id)
    candidates: dict[str, set[str]] = {}
    for path in sorted(
        (REPOSITORY / "materializations").glob(f"{identity}--*.lock.json")
    ):
        data = json.loads(path.read_text(encoding="utf-8"))
        lock_project = data.get("project", {})
        if not isinstance(lock_project, dict) or lock_project.get("id") != identity:
            continue
        for skill in data.get("skills", []):
            name = skill.get("name")
            source = skill.get("source")
            if (
                not isinstance(name, str)
                or not SAFE_NAME.fullmatch(name)
                or not isinstance(source, str)
            ):
                raise ValueError(f"invalid skill mapping in {path}")
            validate_source(source)
            candidates.setdefault(name, set()).add(source)
    return {
        name: next(iter(sources))
        for name, sources in candidates.items()
        if len(sources) == 1
    }


def known_source_paths() -> list[str]:
    paths: set[str] = set()
    for skill_file in REPOSITORY.rglob("SKILL.md"):
        if ".pixi" in skill_file.parts or ".backups" in skill_file.parts:
            continue
        try:
            candidate = skill_file.parent.resolve().relative_to(REPOSITORY).as_posix()
        except ValueError:
            continue
        paths.add(candidate)
    return sorted(paths)


def scan_project(project: Path, project_id: str | None = None) -> list[SkillMapping]:
    project = project.resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"project does not exist: {project}")
    root = validate_project_skills_root(project)
    if not root.is_dir():
        raise FileNotFoundError(f"project has no .agents/skills directory: {project}")
    bundles = load_bundles()
    known_sources = previous_sources(project, project_id)
    memberships: dict[tuple[str, str], set[str]] = {}
    for bundle_name, manifest in bundles.items():
        for skill in manifest.get("skills", []):
            memberships.setdefault((skill["name"], skill["source"]), set()).add(
                bundle_name
            )

    mappings: list[SkillMapping] = []
    seen: set[str] = set()
    discovered: list[tuple[Path, str]] = []
    for skill_file in sorted(root.glob("*/SKILL.md")):
        name = read_skill_name(skill_file)
        if not SAFE_NAME.fullmatch(name):
            raise ValueError(f"unsafe skill name in project: {name!r}")
        if name in seen:
            raise ValueError(f"duplicate skill name in project: {name}")
        seen.add(name)
        discovered.append((skill_file, name))
    for skill_file, name in discovered:
        if skill_file.parent.name != name:
            raise ValueError(
                f"skill directory/name mismatch: {skill_file.parent.name!r} != {name!r}"
            )
        source = known_sources.get(name, f"skills/{name}")
        validate_skill_tree(skill_file.parent, context=f"project skill {name!r}")
        mappings.append(
            SkillMapping(
                name=name,
                project_path=skill_file.parent,
                source=source,
                bundles=memberships.get((name, source), set()).copy(),
                original_source=source,
            )
        )
    if not mappings:
        raise ValueError(f"no skills found under {root}")
    return mappings


def validate_source(source: str) -> Path:
    if not isinstance(source, str) or not source or "\\" in source:
        raise ValueError(f"source must stay inside the workshop: {source}")
    relative = Path(source)
    if (
        relative.is_absolute()
        or relative == Path(".")
        or any(part == ".." for part in relative.parts)
    ):
        raise ValueError(f"source must stay inside the workshop: {source}")
    if relative.as_posix() != source or any(part == "." for part in relative.parts):
        raise ValueError(f"invalid source path: {source}")
    repository = REPOSITORY.resolve()
    path = repository / relative
    current = repository
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"source must stay inside the workshop: {source}")
    resolved = path.resolve()
    if repository not in resolved.parents or resolved == repository:
        raise ValueError(f"source must stay inside the workshop: {source}")
    return resolved


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_bundle(manifest: dict[str, object]) -> str:
    lines = [
        f"schema_version = {manifest.get('schema_version', 1)}",
        f"name = {quote(manifest['name'])}",
        f"description = {quote(manifest.get('description', ''))}",
    ]
    skills = sorted(manifest.get("skills", []), key=lambda item: item["name"])
    if not skills:
        lines.append("skills = []")
    for skill in skills:
        lines.extend(
            [
                "",
                "[[skills]]",
                f"name = {quote(skill['name'])}",
                f"source = {quote(skill['source'])}",
            ]
        )
    return "\n".join(lines) + "\n"


def import_mappings(
    mappings: list[SkillMapping],
    new_bundles: set[str] | None = None,
    conflict: str = "abort",
    project: Path | None = None,
    project_id: str | None = None,
) -> tuple[int, int]:
    if conflict not in {"abort", "record", "back-propagate"}:
        raise ValueError(f"unknown import policy: {conflict}")
    if project is not None and not project.resolve().is_dir():
        raise FileNotFoundError(f"project does not exist: {project}")
    if project is not None:
        validate_existing_materialization_locks(project, project_id)
    requested_bundles = set(new_bundles or set())
    for bundle_name in requested_bundles:
        if not SAFE_NAME.fullmatch(bundle_name):
            raise ValueError(f"invalid bundle name: {bundle_name}")
    available_bundles = set(load_bundles()) | requested_bundles
    planned: list[tuple[SkillMapping, Path, str | None]] = []
    conflicts: list[tuple[SkillMapping, Path]] = []
    source_targets: list[tuple[SkillMapping, Path]] = []
    seen_names: set[str] = set()
    expected_root = (
        validate_project_skills_root(project.resolve()).resolve()
        if project is not None
        else None
    )
    for mapping in mappings:
        if not SAFE_NAME.fullmatch(mapping.name):
            raise ValueError(f"unsafe project skill name: {mapping.name!r}")
        if mapping.name in seen_names:
            raise ValueError(f"duplicate project skill mapping: {mapping.name!r}")
        seen_names.add(mapping.name)
        validate_skill_tree(
            mapping.project_path,
            context=f"project skill {mapping.name!r}",
            expected_name=mapping.name,
        )
        if (
            expected_root is not None
            and mapping.project_path.resolve().parent != expected_root
        ):
            raise ValueError(
                f"project skill is outside the selected project: {mapping.project_path}"
            )
        if (
            mapping.project_path.name != mapping.name
            or read_skill_name(mapping.project_path / "SKILL.md") != mapping.name
        ):
            raise ValueError(
                f"project skill directory and declared name must match {mapping.name!r}"
            )
        unknown_bundles = mapping.bundles - available_bundles
        if unknown_bundles:
            raise ValueError(
                f"unknown bundles for {mapping.name!r}: "
                + ", ".join(sorted(unknown_bundles))
            )
        source = validate_source(mapping.source)
        for other_mapping, other_source in source_targets:
            if (
                source == other_source
                or source in other_source.parents
                or other_source in source.parents
            ):
                raise ValueError(
                    "workshop skill sources must be unique and non-overlapping: "
                    f"{other_mapping.name!r} -> {other_mapping.source!r}, "
                    f"{mapping.name!r} -> {mapping.source!r}"
                )
        source_targets.append((mapping, source))
        if source.exists() or source.is_symlink():
            validate_skill_tree(
                source,
                context=f"workshop source {mapping.source!r}",
                expected_name=mapping.name,
            )
            source_digest = digest_tree(source)
            if source_digest != digest_tree(mapping.project_path):
                conflicts.append((mapping, source))
        else:
            source_digest = None
        if mapping.original_source is not None:
            validate_source(mapping.original_source)
        planned.append((mapping, source, source_digest))
    if conflicts and conflict == "abort":
        names = ", ".join(mapping.name for mapping, _ in conflicts)
        raise FileExistsError(f"workshop sources differ: {names}")

    copied = 0
    for mapping, source, source_digest in planned:
        if source_digest is None:
            if source.exists() or source.is_symlink():
                raise RuntimeError(f"workshop source appeared during import: {source}")
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(mapping.project_path, source, symlinks=False)
            copied += 1
        elif any(conflict_mapping is mapping for conflict_mapping, _ in conflicts):
            if conflict == "back-propagate":
                if digest_tree(source) != source_digest:
                    raise RuntimeError(
                        f"workshop source changed during import: {source}"
                    )
                backup_source(source, mapping.name)
                replace_tree(mapping.project_path, source)

    for bundle_name in sorted(requested_bundles):
        path = REPOSITORY / "bundles" / f"{bundle_name}.toml"
        if not path.exists():
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(
                render_bundle(
                    {
                        "name": bundle_name,
                        "schema_version": 1,
                        "description": "Project-imported skill bundle",
                        "skills": [],
                    }
                ),
                encoding="utf-8",
            )
            temporary.replace(path)

    bundles = load_bundles()
    changed_bundles = 0
    for bundle_name, manifest in bundles.items():
        old_skills = {item["name"]: item for item in manifest.get("skills", [])}
        new_skills = dict(old_skills)
        for mapping in mappings:
            if bundle_name in mapping.bundles:
                new_skills[mapping.name] = {
                    "name": mapping.name,
                    "source": mapping.source,
                }
            else:
                controlled_source = mapping.original_source or mapping.source
                existing = new_skills.get(mapping.name)
                if existing and existing.get("source") == controlled_source:
                    new_skills.pop(mapping.name)
        manifest["skills"] = list(new_skills.values())
        rendered = render_bundle(manifest)
        path = REPOSITORY / "bundles" / f"{bundle_name}.toml"
        if path.read_text(encoding="utf-8") != rendered:
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(rendered, encoding="utf-8")
            temporary.replace(path)
            changed_bundles += 1
    if project is not None:
        write_materialization_locks(project, mappings, project_id)
    return copied, changed_bundles


def normalize_lock_entry(item: object, path: Path) -> dict[str, object]:
    if not isinstance(item, dict):
        raise TypeError(f"invalid skill entry in materialization lock: {path}")
    name = item.get("name")
    source = item.get("source")
    if not isinstance(name, str) or not SAFE_NAME.fullmatch(name):
        raise ValueError(f"unsafe locked skill name in {path}: {name!r}")
    if not isinstance(source, str):
        raise TypeError(f"invalid locked skill source in {path}: {source!r}")
    validate_source(source)
    source_digest = item.get("source_sha256", item.get("sha256"))
    project_digest = item.get("project_sha256", item.get("sha256"))
    if not isinstance(source_digest, str) or not DIGEST.fullmatch(source_digest):
        raise ValueError(f"invalid source digest for {name!r} in {path}")
    if project_digest is not None and (
        not isinstance(project_digest, str) or not DIGEST.fullmatch(project_digest)
    ):
        raise ValueError(f"invalid project digest for {name!r} in {path}")
    for key in ("revision", "origin_url", "upstream_url"):
        value = item.get(key)
        if value is not None and not isinstance(value, str):
            raise TypeError(f"invalid {key} for {name!r} in {path}")
    if "source_dirty" in item and not isinstance(item["source_dirty"], bool):
        raise TypeError(f"invalid source_dirty for {name!r} in {path}")
    return {
        "name": name,
        "source": source,
        "identity": f"{source}#{name}",
        "source_sha256": source_digest,
        "project_sha256": project_digest,
        "status": "synced" if source_digest == project_digest else "diverged",
        "revision": item.get("revision"),
        "origin_url": item.get("origin_url", item.get("url")),
        "upstream_url": item.get("upstream_url"),
        "source_dirty": item.get("source_dirty", False),
    }


def load_existing_lock(
    path: Path, *, project_id: str, bundle: str
) -> tuple[dict[str, object], list[dict[str, object]]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read materialization lock {path}: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("skills"), list):
        raise TypeError(f"invalid materialization lock: {path}")
    if data.get("schema_version", 1) not in {1, 2}:
        raise ValueError(f"unsupported materialization lock schema: {path}")
    lock_project = data.get("project")
    if (
        not isinstance(lock_project, dict)
        or lock_project.get("id") != project_id
        or data.get("bundle") != bundle
    ):
        raise ValueError(f"materialization lock identity mismatch: {path}")
    entries = [normalize_lock_entry(item, path) for item in data["skills"]]
    names = [str(item["name"]) for item in entries]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate install names in materialization lock: {path}")
    return data, entries


def validate_existing_materialization_locks(
    project: Path, requested_project_id: str | None = None
) -> None:
    project_id, _ = project_identity(project.resolve(), requested_project_id)
    for path in sorted(MATERIALIZATIONS.glob(f"{project_id}--*.lock.json")):
        bundle = path.name.removeprefix(f"{project_id}--").removesuffix(".lock.json")
        if not SAFE_NAME.fullmatch(bundle):
            raise ValueError(f"invalid bundle name in lock filename: {bundle!r}")
        load_existing_lock(path, project_id=project_id, bundle=bundle)


def write_materialization_locks(
    project: Path, mappings: list[SkillMapping], requested_project_id: str | None = None
) -> None:
    project = project.resolve()
    if not project.is_dir():
        raise FileNotFoundError(f"project does not exist: {project}")
    project_id, remote = project_identity(project, requested_project_id)
    MATERIALIZATIONS.mkdir(parents=True, exist_ok=True)
    selected_bundles = {item for mapping in mappings for item in mapping.bundles}
    previous_bundles = {
        path.name.removeprefix(f"{project_id}--").removesuffix(".lock.json")
        for path in MATERIALIZATIONS.glob(f"{project_id}--*.lock.json")
    }
    for bundle in sorted(selected_bundles | previous_bundles):
        if not SAFE_NAME.fullmatch(bundle):
            raise ValueError(f"invalid bundle name in lock filename: {bundle!r}")
        path = MATERIALIZATIONS / f"{project_id}--{bundle}.lock.json"
        if path.exists():
            _, normalized = load_existing_lock(
                path, project_id=project_id, bundle=bundle
            )
        else:
            normalized = []
        entries = {item["name"]: item for item in normalized}
        for mapping in mappings:
            if bundle not in mapping.bundles:
                controlled_source = mapping.original_source or mapping.source
                existing = entries.get(mapping.name)
                if existing and existing.get("source") == controlled_source:
                    entries.pop(mapping.name)
                continue
            source = validate_source(mapping.source)
            source_digest = digest_tree(source)
            project_digest = digest_tree(mapping.project_path)
            entries[mapping.name] = {
                "name": mapping.name,
                "source": mapping.source,
                "identity": f"{mapping.source}#{mapping.name}",
                "source_sha256": source_digest,
                "project_sha256": project_digest,
                "status": "synced" if source_digest == project_digest else "diverged",
                **source_metadata(source),
            }
        lock = {
            "schema_version": 2,
            "bundle": bundle,
            "project": {"id": project_id, "remote": remote},
            "skills": sorted(entries.values(), key=lambda item: item["name"]),
        }
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)


class ImportSkillsApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #workspace { height: 1fr; }
    #skills-pane { width: 25%; border: round $accent; }
    #mapping-pane { width: 34%; border: round $accent; padding: 0 1; }
    #preview-pane { width: 41%; border: round $accent; }
    #skill-list, #bundle-list, #preview { height: 1fr; }
    #search, #source, #new-bundle { margin-bottom: 1; }
    #source-info { height: 3; color: $text-muted; }
    #bundle-actions { height: 3; }
    #status { height: 3; padding: 1; }
    #actions { height: 3; align: right middle; }
    Button { margin-left: 1; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+s", "import_skills", "Import"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, project: Path, project_id: str | None = None) -> None:
        super().__init__()
        self.project = project.resolve()
        self.project_id = project_id
        self.mappings = scan_project(self.project, project_id)
        self.bundle_names = sorted(load_bundles())
        self.new_bundles: set[str] = set()
        self.source_candidates = known_source_paths()
        self.visible_indices = list(range(len(self.mappings)))
        self.current_index = 0
        self.preview_diff = False

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with Vertical(id="skills-pane"):
                yield Label("Project skills")
                yield Input(placeholder="Filter skills", id="search")
                yield OptionList(
                    *(mapping.name for mapping in self.mappings), id="skill-list"
                )
            with Vertical(id="mapping-pane"):
                yield Label("Workshop source")
                yield Input(
                    id="source",
                    suggester=SuggestFromList(
                        self.source_candidates, case_sensitive=False
                    ),
                )
                yield Static(id="source-info")
                yield Select(
                    [
                        ("Stop on differing sources", "abort"),
                        ("Record mappings; preserve both", "record"),
                        ("Back-propagate project changes", "back-propagate"),
                    ],
                    value="abort",
                    id="import-policy",
                )
                yield Label("Bundles (space toggles)")
                yield SelectionList[str](
                    *((name, name) for name in self.bundle_names), id="bundle-list"
                )
                with Horizontal(id="bundle-actions"):
                    yield Input(placeholder="new-bundle", id="new-bundle")
                    yield Button("Add", id="add-bundle")
                with Horizontal(id="actions"):
                    yield Button("Import", variant="primary", id="import")
                    yield Button("Quit", id="quit")
            with Vertical(id="preview-pane"):
                yield Label("SKILL.md preview")
                yield Button("Toggle project/diff", id="toggle-preview")
                yield TextArea(read_only=True, language="markdown", id="preview")
        yield Static(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Skills Workshop Importer"
        self.sub_title = str(self.project)
        self.load_mapping(0)
        self.query_one("#skill-list", OptionList).focus()

    def save_mapping(self) -> None:
        mapping = self.mappings[self.current_index]
        mapping.source = self.query_one("#source", Input).value.strip()
        mapping.bundles = set(self.query_one("#bundle-list", SelectionList).selected)

    def update_source_info(self, source: str) -> None:
        try:
            path = validate_source(source)
        except ValueError as error:
            self.query_one("#source-info", Static).update(str(error))
            return
        if not path.exists():
            text = "New first-party workshop source"
        elif not path.is_dir() or path.is_symlink():
            text = "Invalid source: expected a real skill directory"
        else:
            licenses = sorted(
                item.name
                for item in path.iterdir()
                if item.is_file() and item.name.upper().startswith("LICENSE")
            )
            text = "Existing source"
            if licenses:
                text += f" · license: {', '.join(licenses)}"
        self.query_one("#source-info", Static).update(text)

    def load_mapping(self, index: int) -> None:
        self.current_index = index
        mapping = self.mappings[index]
        self.query_one("#source", Input).value = mapping.source
        self.update_source_info(mapping.source)
        bundle_list = self.query_one("#bundle-list", SelectionList)
        bundle_list.deselect_all()
        for bundle in mapping.bundles:
            bundle_list.select(bundle)
        try:
            source = validate_source(mapping.source)
            preview = (
                text_diff(source, mapping.project_path)
                if self.preview_diff
                else (mapping.project_path / "SKILL.md").read_text(encoding="utf-8")
            )
        except ValueError as error:
            preview = str(error)
        self.query_one("#preview", TextArea).load_text(preview)
        self.query_one("#status", Static).update(
            f"{index + 1}/{len(self.mappings)}  {mapping.project_path}"
        )

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if not self.is_mounted:
            return
        self.save_mapping()
        self.load_mapping(self.visible_indices[event.option_index])

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "source":
            self.update_source_info(event.value.strip())
            if self.preview_diff and self.is_mounted:
                self.save_mapping()
                self.load_mapping(self.current_index)
            return
        if event.input.id != "search" or not self.is_mounted:
            return
        self.save_mapping()
        query = event.value.casefold().strip()
        self.visible_indices = [
            index
            for index, mapping in enumerate(self.mappings)
            if query in mapping.name.casefold()
        ]
        options = self.query_one("#skill-list", OptionList)
        options.clear_options()
        options.add_options(self.mappings[index].name for index in self.visible_indices)
        if self.visible_indices:
            options.highlighted = 0

    def add_bundle(self) -> None:
        field = self.query_one("#new-bundle", Input)
        name = field.value.strip()
        if not SAFE_NAME.fullmatch(name):
            self.notify("Use a lowercase hyphenated bundle name", severity="error")
            return
        bundle_list = self.query_one("#bundle-list", SelectionList)
        if name not in self.bundle_names:
            self.bundle_names.append(name)
            self.bundle_names.sort()
            self.new_bundles.add(name)
            bundle_list.add_option((name, name))
        bundle_list.select(name)
        field.value = ""

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()
        elif event.button.id == "add-bundle":
            self.add_bundle()
        elif event.button.id == "toggle-preview":
            self.save_mapping()
            self.preview_diff = not self.preview_diff
            self.load_mapping(self.current_index)
        else:
            self.action_import_skills()

    def action_import_skills(self) -> None:
        self.save_mapping()
        try:
            policy = self.query_one("#import-policy", Select).value
            copied, bundles = import_mappings(
                self.mappings,
                self.new_bundles,
                str(policy),
                self.project,
                self.project_id,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.notify(str(error), severity="error", timeout=8)
            return
        self.notify(
            f"Imported {copied} new skills; updated {bundles} bundles",
            severity="information",
            timeout=6,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument(
        "--project-id",
        help="stable lock name; defaults to the project's origin remote or directory name",
    )
    args = parser.parse_args()
    ImportSkillsApp(args.project, args.project_id).run()


if __name__ == "__main__":
    main()
