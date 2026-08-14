#!/usr/bin/env python3
"""Import and organize project skills with an interactive terminal UI."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

import tomllib
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    SelectionList,
    Static,
    TextArea,
)

REPOSITORY = Path(__file__).resolve().parents[1]


@dataclass
class SkillMapping:
    name: str
    project_path: Path
    source: str
    clusters: set[str] = field(default_factory=set)


def digest_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(file for file in path.rglob("*") if file.is_file()):
        digest.update(item.relative_to(path).as_posix().encode())
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def read_skill_name(skill_file: Path) -> str:
    lines = skill_file.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return skill_file.parent.name
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, separator, value = line.partition(":")
        if separator and key.strip() == "name":
            return value.strip().strip("'\"") or skill_file.parent.name
    return skill_file.parent.name


def load_clusters() -> dict[str, dict[str, object]]:
    clusters: dict[str, dict[str, object]] = {}
    for path in sorted((REPOSITORY / "clusters").glob("*.toml")):
        with path.open("rb") as stream:
            manifest = tomllib.load(stream)
        clusters[manifest["name"]] = manifest
    return clusters


def previous_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in sorted((REPOSITORY / "materializations").glob("*.lock.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for skill in data.get("skills", []):
            sources.setdefault(skill["name"], skill["source"])
    return sources


def scan_project(project: Path) -> list[SkillMapping]:
    root = project.resolve() / ".agents" / "skills"
    if not root.is_dir():
        raise FileNotFoundError(f"project has no .agents/skills directory: {project}")
    clusters = load_clusters()
    known_sources = previous_sources()
    memberships: dict[str, set[str]] = {}
    for cluster_name, manifest in clusters.items():
        for skill in manifest.get("skills", []):
            memberships.setdefault(skill["name"], set()).add(cluster_name)

    mappings: list[SkillMapping] = []
    seen: set[str] = set()
    for skill_file in sorted(root.glob("*/SKILL.md")):
        name = read_skill_name(skill_file)
        if name in seen:
            raise ValueError(f"duplicate skill name in project: {name}")
        seen.add(name)
        mappings.append(
            SkillMapping(
                name=name,
                project_path=skill_file.parent,
                source=known_sources.get(name, f"skills/{name}"),
                clusters=memberships.get(name, set()).copy(),
            )
        )
    if not mappings:
        raise ValueError(f"no skills found under {root}")
    return mappings


def validate_source(source: str) -> Path:
    path = (REPOSITORY / source).resolve()
    if REPOSITORY not in path.parents or path == REPOSITORY:
        raise ValueError(f"source must stay inside the workshop: {source}")
    if path.name != Path(source).name:
        raise ValueError(f"invalid source path: {source}")
    return path


def quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_cluster(manifest: dict[str, object]) -> str:
    lines = [
        f"name = {quote(manifest['name'])}",
        f"description = {quote(manifest.get('description', ''))}",
    ]
    skills = sorted(manifest.get("skills", []), key=lambda item: item["name"])
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


def import_mappings(mappings: list[SkillMapping]) -> tuple[int, int]:
    planned: list[tuple[SkillMapping, Path]] = []
    for mapping in mappings:
        source = validate_source(mapping.source)
        if source.exists() and digest_tree(source) != digest_tree(mapping.project_path):
            raise FileExistsError(
                f"workshop source differs for {mapping.name}: {mapping.source}"
            )
        planned.append((mapping, source))

    copied = 0
    for mapping, source in planned:
        if not source.exists():
            source.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(mapping.project_path, source, symlinks=False)
            copied += 1

    clusters = load_clusters()
    changed_clusters = 0
    for cluster_name, manifest in clusters.items():
        old_skills = {item["name"]: item for item in manifest.get("skills", [])}
        new_skills = {
            name: item
            for name, item in old_skills.items()
            if not any(mapping.name == name for mapping in mappings)
        }
        for mapping in mappings:
            if cluster_name in mapping.clusters:
                new_skills[mapping.name] = {
                    "name": mapping.name,
                    "source": mapping.source,
                }
        manifest["skills"] = list(new_skills.values())
        rendered = render_cluster(manifest)
        path = REPOSITORY / "clusters" / f"{cluster_name}.toml"
        if path.read_text(encoding="utf-8") != rendered:
            path.write_text(rendered, encoding="utf-8")
            changed_clusters += 1
    return copied, changed_clusters


class ImportSkillsApp(App[None]):
    CSS = """
    Screen { layout: vertical; }
    #workspace { height: 1fr; }
    #skills-pane { width: 25%; border: round $accent; }
    #mapping-pane { width: 34%; border: round $accent; padding: 0 1; }
    #preview-pane { width: 41%; border: round $accent; }
    #skill-list, #cluster-list, #preview { height: 1fr; }
    #source { margin-bottom: 1; }
    #status { height: 3; padding: 1; }
    #actions { height: 3; align: right middle; }
    Button { margin-left: 1; }
    """
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("ctrl+s", "import_skills", "Import"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, project: Path) -> None:
        super().__init__()
        self.project = project.resolve()
        self.mappings = scan_project(self.project)
        self.cluster_names = sorted(load_clusters())
        self.current_index = 0

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="workspace"):
            with Vertical(id="skills-pane"):
                yield Label("Project skills")
                yield OptionList(
                    *(mapping.name for mapping in self.mappings), id="skill-list"
                )
            with Vertical(id="mapping-pane"):
                yield Label("Workshop source")
                yield Input(id="source")
                yield Label("Clusters (space toggles)")
                yield SelectionList[str](
                    *((name, name) for name in self.cluster_names), id="cluster-list"
                )
                with Horizontal(id="actions"):
                    yield Button("Import", variant="primary", id="import")
                    yield Button("Quit", id="quit")
            with Vertical(id="preview-pane"):
                yield Label("SKILL.md preview")
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
        mapping.clusters = set(self.query_one("#cluster-list", SelectionList).selected)

    def load_mapping(self, index: int) -> None:
        self.current_index = index
        mapping = self.mappings[index]
        self.query_one("#source", Input).value = mapping.source
        cluster_list = self.query_one("#cluster-list", SelectionList)
        cluster_list.deselect_all()
        for cluster in mapping.clusters:
            cluster_list.select(cluster)
        preview = mapping.project_path / "SKILL.md"
        self.query_one("#preview", TextArea).load_text(
            preview.read_text(encoding="utf-8")
        )
        self.query_one("#status", Static).update(
            f"{index + 1}/{len(self.mappings)}  {mapping.project_path}"
        )

    def on_option_list_option_highlighted(
        self, event: OptionList.OptionHighlighted
    ) -> None:
        if not self.is_mounted:
            return
        self.save_mapping()
        self.load_mapping(event.option_index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.exit()
        else:
            self.action_import_skills()

    def action_import_skills(self) -> None:
        self.save_mapping()
        try:
            copied, clusters = import_mappings(self.mappings)
        except (OSError, ValueError) as error:
            self.notify(str(error), severity="error", timeout=8)
            return
        self.notify(
            f"Imported {copied} new skills; updated {clusters} clusters",
            severity="information",
            timeout=6,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    ImportSkillsApp(args.project).run()


if __name__ == "__main__":
    main()
