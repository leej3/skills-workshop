#!/usr/bin/env python3
"""Search skill sources and delegate candidate inspection to existing tools."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import tomllib
import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __package__:
    from .inventory import canonical_skill_collections
    from .search import rank
else:
    from inventory import canonical_skill_collections
    from search import rank

VERSION = "0.1.0"
REPOSITORY = Path(__file__).resolve().parents[1]
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")

ASM_VERSION = "2.14.0"
VERCEL_SKILLS_VERSION = "1.5.22"


class WorkshopError(RuntimeError):
    """A concise, user-actionable workshop failure."""


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


def local_skill_metadata(path: Path) -> dict[str, Any]:
    """Read the frontmatter needed for local candidate search."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}
    if not text.startswith("---\n"):
        return {}
    frontmatter, marker, _ = text[4:].partition("\n---\n")
    if not marker:
        return {}
    try:
        metadata = yaml.safe_load(frontmatter)
    except yaml.YAMLError:
        return {}
    return metadata if isinstance(metadata, dict) else {}


def git_head(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed.stdout.strip() if completed.returncode == 0 else None


def search_configuration(root: Path) -> dict[str, Any]:
    registry = root / "registry.toml"
    if not registry.is_file():
        return {}
    try:
        with registry.open("rb") as stream:
            return tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise WorkshopError(f"cannot read {registry}: {error}") from error


def tree_documents(
    directory: Path,
    *,
    provider: str,
    collection: str,
    source: str | None,
    revision: str | None,
    relative_to: Path | None = None,
) -> list[dict[str, Any]]:
    documents = []
    if not directory.is_dir():
        return documents
    candidates = set(directory.rglob("SKILL.md"))
    # User skill installations commonly link their immediate skill directories.
    if provider == "installed":
        for child in directory.iterdir():
            if child.is_symlink() and child.is_dir():
                candidates.update(child.rglob("SKILL.md"))
    for skill_file in sorted(candidates):
        if provider != "installed" and not skill_file.resolve().is_relative_to(
            directory.resolve()
        ):
            continue
        metadata = local_skill_metadata(skill_file)
        if not metadata.get("name") or not metadata.get("description"):
            continue
        try:
            body = skill_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        name = str(metadata["name"])
        description = str(metadata["description"])
        path = (
            skill_file.parent.relative_to(relative_to).as_posix()
            if relative_to
            else str(skill_file.parent)
        )
        documents.append(
            {
                "result": {
                    "provider": provider,
                    "name": name,
                    "description": description,
                    "collection": collection,
                    "source": source,
                    "path": path,
                    "revision": revision,
                },
                "fields": {
                    "name": (10, name),
                    "description": (5, description),
                    "content": (1, body.split("---", 2)[-1]),
                    "collection": (1, collection),
                },
            }
        )
    return documents


def local_search(root: Path, query: str, limit: int) -> list[dict[str, Any]]:
    root = root.resolve()
    documents = []
    revision = git_head(root)
    for collection in canonical_skill_collections(root):
        for skill in collection["skills"]:
            documents.extend(
                tree_documents(
                    skill,
                    provider="local",
                    collection=f"workshop-{collection['name']}",
                    source=None,
                    revision=revision,
                    relative_to=root,
                )
            )
    for upstream in search_configuration(root).get("upstreams", []):
        directory = (root / upstream["path"]).resolve()
        if root not in directory.parents:
            continue
        documents.extend(
            tree_documents(
                directory,
                provider="local",
                collection=upstream["name"],
                source=upstream.get("url"),
                revision=git_head(directory),
                relative_to=root,
            )
        )
    return rank(query, documents, limit)


def installed_search(root: Path, query: str, limit: int) -> list[dict[str, Any]]:
    documents = []
    seen: set[Path] = set()
    for entry in search_configuration(root).get("skill_roots", []):
        directory = Path(entry["path"]).expanduser()
        if not directory.is_absolute():
            directory = root / directory
        if directory.resolve() in seen:
            continue
        seen.add(directory.resolve())
        documents.extend(
            tree_documents(
                directory,
                provider="installed",
                collection=entry["name"],
                source=None,
                revision=None,
            )
        )
    # These paths are local observations, never sent to a public search provider.
    return rank(query, documents, limit)


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
            "role": "external project dependency manifest, lock, resolution, deployment, and audit",
            "version": apm_version(),
            "authority": "external dependency state",
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
            "role": "local and public skill discovery and candidate inspection",
            "version": VERSION,
            "authority": "discovery coordination",
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
        print(
            "\nDiscovery tools never install into native or APM-managed project paths."
        )
        print("Every delegated command is printed before it runs.")
    return 0


def selected_providers(values: list[str] | None) -> list[str]:
    requested = values or ["all"]
    if "all" in requested:
        return ["local", "installed", "asm", "github", "vercel"]
    output: list[str] = []
    for provider in requested:
        if provider not in output:
            output.append(provider)
    return output


def print_search_result(provider: str, result: Any, *, tsv: bool = False) -> None:
    rows = result if isinstance(result, list) else result["results"]
    if not tsv:
        print(f"\n== {provider} ==", flush=True)
        if not rows:
            print("No matches.")
    for row in rows:
        if tsv:
            values = [
                row.get("name") or row.get("skillName") or row.get("candidate", ""),
                provider,
                row.get("path") or row.get("url") or row.get("repo", ""),
                row.get("description", ""),
            ]
            print("\t".join(" ".join(str(value).split()) for value in values))
        elif provider in {"local", "installed"}:
            print(f"{row['name']}: {compact_text(row.get('description', ''))}")
            print(
                "  matched: "
                + ", ".join(row["matched_terms"])
                + " in "
                + ", ".join(row["matched_fields"])
            )
            print(
                f"  {row['collection']}: {row['path']} ({row.get('revision') or 'local/unpinned'})"
            )
        else:
            print_provider_result(row)
    if isinstance(result, dict) and result.get("stderr"):
        print(result["stderr"].rstrip(), file=sys.stderr)
    sys.stdout.flush()


def cmd_find(args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise WorkshopError("--limit must be positive")
    providers = selected_providers(args.provider)
    local = {
        "local": local_search,
        "installed": installed_search,
    }
    if args.offline:
        providers = [provider for provider in providers if provider in local]
        if not providers:
            raise WorkshopError("--offline requires a local provider")
    if not args.query.strip() and any(provider not in local for provider in providers):
        raise WorkshopError("use --offline to browse with an empty query")
    output: dict[str, Any] = {}
    failures = 0
    for provider in providers:
        try:
            if provider in local:
                output[provider] = local[provider](args.root, args.query, args.limit)
            else:
                command = provider_commands(args.query, args.limit)[provider]
                completed = run_external(
                    provider,
                    command,
                    args.root,
                    "read-only search of public providers; only the supplied query is sent",
                    dry_run=args.dry_run,
                )
                output[provider] = {
                    "command": command,
                    "executed": not args.dry_run,
                    "exit_code": completed.returncode,
                    "results": parse_provider_results(
                        provider, completed.stdout, args.limit
                    ),
                    "stderr": completed.stderr,
                }
                failures += bool(completed.returncode)
        except WorkshopError as error:
            failures += 1
            output[provider] = {
                "executed": False,
                "exit_code": 1,
                "results": [],
                "stderr": str(error),
            }
        if not args.json:
            print_search_result(provider, output[provider], tsv=args.tsv)
    if args.json:
        print(json.dumps(output, indent=2))
    return 1 if failures == len(providers) else 0


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover skills from local catalogs and public providers."
    )
    parser.add_argument("--root", type=Path, default=REPOSITORY, help=argparse.SUPPRESS)
    parser.add_argument(
        "--version", action="version", version=f"skills-workshop {VERSION}"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser(
        "doctor", help="show tool availability and authority boundaries"
    )
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(handler=cmd_doctor)

    find = commands.add_parser(
        "find", help="search local catalogs, installed skills, and public providers"
    )
    find.add_argument("query")
    find.add_argument(
        "--provider",
        action="append",
        choices=["local", "installed", "asm", "github", "vercel", "all"],
        help="repeat to narrow or combine; defaults to local, installed, then public providers",
    )
    find.add_argument("--limit", type=int, default=10)
    find.add_argument("--dry-run", action="store_true")
    find.add_argument(
        "--offline", action="store_true", help="search local trees without network"
    )
    output_format = find.add_mutually_exclusive_group()
    output_format.add_argument("--json", action="store_true")
    output_format.add_argument(
        "--tsv",
        action="store_true",
        help="name, provider, location, description; suitable for fzf",
    )
    find.set_defaults(handler=cmd_find)

    preview = commands.add_parser(
        "preview", help="delegate a non-installing GitHub skill-tree preview"
    )
    preview.add_argument("repository", help="GitHub OWNER/REPO or repository URL")
    preview.add_argument("skill", help="skill name, path, or name@commit")
    preview.add_argument("--allow-hidden-dirs", action="store_true")
    preview.add_argument("--dry-run", action="store_true")
    preview.set_defaults(handler=cmd_preview)

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
