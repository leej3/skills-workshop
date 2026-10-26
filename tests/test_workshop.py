from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from scripts import workshop as workshop_cli


@pytest.fixture
def catalog_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills-workshop"
    root.mkdir()
    return root


@pytest.fixture
def invoke(catalog_root: Path) -> Callable[..., int]:
    def run(*arguments: str) -> int:
        return workshop_cli.main(["--root", str(catalog_root), *arguments])

    return run


def test_local_find_searches_every_registered_upstream(
    catalog_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    scientific = catalog_root / "upstreams" / "scientific"
    maintenance = catalog_root / "upstreams" / "maintenance"
    for directory, name, description in (
        (scientific / "skills" / "genomics", "genomics", "Analyze genomic data."),
        (maintenance / "triage", "issue-triage", "Triage repository issues."),
    ):
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n",
            encoding="utf-8",
        )
    (catalog_root / "registry.toml").write_text(
        """schema_version = 1

[[upstreams]]
name = "k-dense"
url = "https://example.test/k-dense.git"
path = "upstreams/scientific"
role = "Scientific skills"

[[upstreams]]
name = "con-skills"
url = "https://example.test/con-skills.git"
path = "upstreams/maintenance"
role = "Maintenance skills"
""",
        encoding="utf-8",
    )

    assert (
        invoke(
            "find",
            "genomic",
            "--provider",
            "local",
            "--json",
        )
        == 0
    )
    output = json.loads(capsys.readouterr().out)
    assert output["local"] == [
        {
            "provider": "local",
            "name": "genomics",
            "description": "Analyze genomic data.",
            "collection": "k-dense",
            "source": "https://example.test/k-dense.git",
            "path": "upstreams/scientific/skills/genomics",
            "revision": None,
            "score": output["local"][0]["score"],
            "matched_terms": ["genomic"],
            "matched_fields": ["description"],
        }
    ]

    assert invoke("find", "triage", "--provider", "local", "--json") == 0
    output = json.loads(capsys.readouterr().out)
    assert [result["collection"] for result in output["local"]] == ["con-skills"]


def test_default_find_orders_local_sources_before_public_providers() -> None:
    assert workshop_cli.selected_providers(None) == [
        "local",
        "installed",
        "asm",
        "github",
        "vercel",
    ]


def test_external_find_dry_run_prints_exact_pinned_commands(
    catalog_root: Path,
    invoke: Callable[..., int],
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        invoke(
            "find",
            "brain imaging",
            "--provider",
            "asm",
            "--provider",
            "github",
            "--provider",
            "vercel",
            "--limit",
            "7",
            "--dry-run",
            "--json",
        )
        == 0
    )

    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["asm"]["executed"] is False
    assert output["github"]["executed"] is False
    assert output["vercel"]["executed"] is False
    assert output["asm"]["command"] == [
        "npx",
        "--yes",
        f"agent-skill-manager@{workshop_cli.ASM_VERSION}",
        "search",
        "brain imaging",
        "--available",
        "--machine",
    ]
    assert output["github"]["command"][-2:] == [
        "--json",
        "skillName,description,repo,path,namespace,stars",
    ]
    assert output["vercel"]["command"] == [
        "npx",
        "--yes",
        f"skills@{workshop_cli.VERCEL_SKILLS_VERSION}",
        "find",
        "brain imaging",
    ]
    assert captured.err.count("read-only search") == 3
    assert f"cwd={catalog_root}" in captured.err
    assert (
        f"agent-skill-manager@{workshop_cli.ASM_VERSION} search 'brain imaging'"
        in captured.err
    )
    assert "gh skill search 'brain imaging' --limit 7" in captured.err
    assert (
        f"skills@{workshop_cli.VERCEL_SKILLS_VERSION} find 'brain imaging'"
        in captured.err
    )


def test_parse_asm_json_results_honors_limit() -> None:
    payload = json.dumps(
        {
            "success": True,
            "data": [
                {
                    "name": "first-skill",
                    "description": "First result",
                    "source": "community",
                },
                "provider progress message",
                {
                    "name": "second-skill",
                    "description": "Second result",
                    "source": "community",
                },
                {"name": "third-skill", "description": "Beyond the limit"},
            ],
        }
    )

    assert workshop_cli.parse_provider_results("asm", payload, 2) == [
        {
            "name": "first-skill",
            "description": "First result",
            "source": "community",
        },
        {
            "name": "second-skill",
            "description": "Second result",
            "source": "community",
        },
    ]


def test_parse_github_json_results_honors_limit() -> None:
    payload = json.dumps(
        [
            {
                "skillName": "first-skill",
                "description": "First result",
                "repo": "example/skills",
                "path": "skills/first-skill",
                "namespace": "example/skills/first-skill",
                "stars": 42,
            },
            {
                "skillName": "second-skill",
                "description": "Beyond the limit",
                "repo": "example/skills",
                "path": "skills/second-skill",
                "namespace": "example/skills/second-skill",
                "stars": 21,
            },
        ]
    )

    assert workshop_cli.parse_provider_results("github", payload, 1) == [
        {
            "skillName": "first-skill",
            "description": "First result",
            "repo": "example/skills",
            "path": "skills/first-skill",
            "namespace": "example/skills/first-skill",
            "stars": 42,
        }
    ]


def test_parse_ansi_vercel_results_strips_presentation_and_honors_limit() -> None:
    output = (
        "\x1b[1mexample/skills@first-skill\x1b[0m "
        "\x1b[32m1.2K installs\x1b[0m\n"
        "\x1b[2m└ https://skills.sh/example/skills/first-skill\x1b[0m\n"
        "example/skills@second-skill 98 installs\n"
        "└ https://skills.sh/example/skills/second-skill\n"
        "example/skills@third-skill 10 installs\n"
        "└ https://skills.sh/example/skills/third-skill\n"
    )

    assert workshop_cli.parse_provider_results("vercel", output, 2) == [
        {
            "candidate": "example/skills@first-skill",
            "popularity": "1.2K installs",
            "url": "https://skills.sh/example/skills/first-skill",
        },
        {
            "candidate": "example/skills@second-skill",
            "popularity": "98 installs",
            "url": "https://skills.sh/example/skills/second-skill",
        },
    ]


def test_preview_dry_run_prints_exact_non_installing_gh_command(
    catalog_root: Path,
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        workshop_cli,
        "command_version",
        lambda command: "gh version 2.97.0",
    )
    assert (
        invoke(
            "preview",
            "con/skills",
            "scan-projects@abc123",
            "--allow-hidden-dirs",
            "--dry-run",
        )
        == 0
    )

    captured = capsys.readouterr()
    assert captured.err.splitlines() == [
        (
            "[github] runner=gh version 2.97.0; read-only candidate preview; "
            f"may use network and GitHub authentication; cwd={catalog_root}"
        ),
        "$ gh skill preview con/skills scan-projects@abc123 --allow-hidden-dirs",
    ]
    assert captured.out == "Dry run; preview command not executed.\n"
    assert "install" not in captured.err


def test_doctor_json_explains_versions_and_authority_boundaries(
    invoke: Callable[..., int],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    versions = {
        "apm": "APM 0.28.0",
        "gh": "gh version 2.97.0",
        "node": "v22.0.0",
    }
    monkeypatch.setattr(
        workshop_cli,
        "command_version",
        lambda command: versions.get(command[0]),
    )

    assert invoke("doctor", "--json") == 0

    report = json.loads(capsys.readouterr().out)
    assert set(report) == {
        "apm",
        "gh-skill",
        "asm",
        "vercel-skills",
        "workshop",
        "node",
    }
    assert report["apm"]["authority"] == "external dependency state"
    assert report["gh-skill"]["authority"] == "discovery only in this workflow"
    assert report["workshop"]["authority"] == "discovery coordination"
    assert report["asm"]["version"].endswith(workshop_cli.ASM_VERSION)
    assert report["vercel-skills"]["version"].endswith(
        workshop_cli.VERCEL_SKILLS_VERSION
    )
    assert report["node"]["version"] == "v22.0.0"


def test_apm_version_extracts_semver_before_misleading_revision_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        workshop_cli,
        "command_version",
        lambda command: "Agent Package Manager (APM) CLI version 0.28.0 (ae66f92)",
    )

    assert workshop_cli.apm_version() == "0.28.0"


def test_full_content_and_symlinked_installed_search(
    catalog_root, invoke, tmp_path, capsys
):
    skill = tmp_path / "original" / "buried-tool"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: buried-tool\ndescription: Process images\n---\nDetect hippocampal segmentation defects.\n"
    )
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "buried-tool").symlink_to(skill, target_is_directory=True)
    (catalog_root / "registry.toml").write_text(
        f'[[skill_roots]]\nname="test"\npath={json.dumps(str(installed))}\n'
    )
    assert invoke("find", "hippocampal", "--offline", "--json") == 0
    rows = json.loads(capsys.readouterr().out)["installed"]
    assert rows[0]["name"] == "buried-tool"
    assert rows[0]["matched_fields"] == ["content"]
    assert not (catalog_root / "memory").exists()


def test_find_survives_provider_failure_and_emits_local_first(
    catalog_root, invoke, monkeypatch, capsys, make_skill
):
    make_skill(catalog_root / ".agents/skills/commit-provenance", "commit-provenance")
    capsys.readouterr()
    calls = []

    def external(provider, command, cwd, mutation, **kwargs):
        calls.append(provider)
        if provider == "asm":
            if len(calls) == 1:
                assert "commit-provenance" in capsys.readouterr().out
            raise workshop_cli.WorkshopError("provider unavailable")
        return subprocess.CompletedProcess(command, 0, "[]", "")

    monkeypatch.setattr(workshop_cli, "run_external", external)
    assert invoke("find", "commit") == 0
    assert calls == ["asm", "github", "vercel"]
    assert "provider unavailable" in capsys.readouterr().err
    assert invoke("find", "commit", "--provider", "asm") == 1


def test_offline_browse_and_tsv_never_contact_providers(
    catalog_root, invoke, monkeypatch, capsys, make_skill
):
    make_skill(catalog_root / ".agents/skills/first-tool", "first-tool")
    capsys.readouterr()
    monkeypatch.setattr(
        workshop_cli,
        "run_external",
        lambda *a, **k: pytest.fail("network in offline search"),
    )
    assert invoke("find", "", "--offline", "--tsv") == 0
    line = capsys.readouterr().out.strip()
    assert line.startswith("first-tool\tlocal\t")
    assert len(line.split("\t")) == 4
    assert invoke("find", "", "--json") == 2
    assert invoke("find", "first", "--limit", "0") == 2


def test_find_searches_canonical_sources_without_deployed_duplicates(
    catalog_root, invoke, make_skill, capsys
):
    make_skill(catalog_root / ".apm/skills/published", "published")
    make_skill(catalog_root / ".apm/skills/old-source", "old-source")
    make_skill(catalog_root / ".agents/skills/published", "published")
    make_skill(catalog_root / ".agents/skills/native", "native")
    (catalog_root / "apm.yml").write_text("includes:\n  - .apm/skills/published\n")
    (catalog_root / "apm.lock.yaml").write_text(
        "local_deployed_files:\n  - .agents/skills/published/SKILL.md\n"
    )
    before = set(catalog_root.rglob("*"))

    assert invoke("find", "", "--offline", "--json") == 0

    rows = json.loads(capsys.readouterr().out)["local"]
    assert {row["name"]: row["path"] for row in rows} == {
        "native": ".agents/skills/native",
        "published": ".apm/skills/published",
    }
    assert set(catalog_root.rglob("*")) == before


def test_local_ranking_retains_typo_and_full_text_matches(
    catalog_root, invoke, make_skill, capsys
):
    make_skill(
        catalog_root / ".agents/skills/commit-provenance",
        "commit-provenance",
        "Verify commit trailers before committing.\n",
    )
    make_skill(catalog_root / ".agents/skills/brain-imaging", "brain-imaging")
    for query in ("commit provennce", "verify commit trailers"):
        assert invoke("find", query, "--offline", "--json") == 0
        rows = json.loads(capsys.readouterr().out)["local"]
        assert rows[0]["name"] == "commit-provenance"
    assert workshop_cli.local_search(catalog_root, "quasar spectroscopy", 10) == []
    assert workshop_cli.local_search(catalog_root, "the and something", 10) == []


def test_help_and_retired_commands_do_not_require_or_create_state(tmp_path):
    script = workshop_cli.REPOSITORY / "scripts/workshop.py"
    for arguments, status in [
        (["--help"], 0),
        (["--version"], 0),
        (["recall", "a past task"], 2),
        (["find", "query", "--provider", "memory"], 2),
    ]:
        result = subprocess.run(
            [sys.executable, str(script), "--root", str(tmp_path), *arguments],
            cwd=tmp_path,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == status, result.stderr
        assert "Traceback" not in result.stderr
    assert list(tmp_path.iterdir()) == []
