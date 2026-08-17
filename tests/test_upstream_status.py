from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import upstream_status


def write_empty_registry(workshop: Path) -> None:
    (workshop / "registry.toml").write_text(
        "schema_version = 1\n",
        encoding="utf-8",
    )


def git_command(path: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(path), *arguments],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def initialized_repository(path: Path) -> tuple[Path, str]:
    path.mkdir()
    git_command(path, "init")
    git_command(path, "config", "user.email", "tests@example.test")
    git_command(path, "config", "user.name", "Test Runner")
    (path / "README.md").write_text("test\n", encoding="utf-8")
    git_command(path, "add", "README.md")
    git_command(path, "commit", "-m", "test")
    return path, git_command(path, "rev-parse", "HEAD")


def test_relationships_reports_v2_cluster_as_bundle(workshop: Path) -> None:
    (workshop / "materializations" / "project--research.lock.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "cluster": "research",
                "project": {"id": "project", "remote": None},
                "skills": [
                    {
                        "name": "alpha",
                        "source": "skills/alpha",
                        "status": "synced",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    _, materializations = upstream_status.relationships()

    assert materializations[0]["bundle"] == "research"


def test_trust_inventory_detects_risk_license_and_review_staleness(
    workshop: Path, make_skill
) -> None:
    write_empty_registry(workshop)
    skill = make_skill(workshop / "skills" / "networked", "networked")
    (workshop / "skills" / "LICENSE").write_text("Test license", encoding="utf-8")
    script = skill / "run.py"
    script.write_text(
        "import os\nimport requests\n"
        "token = os.getenv('SERVICE_API_TOKEN')\n"
        "requests.get('https://example.test', headers={'Authorization': token})\n",
        encoding="utf-8",
    )
    script.chmod(0o755)

    row = upstream_status.trust_inventory()[0]

    assert row["key"] == "skills/networked#networked"
    assert row["review_state"] == "unreviewed"
    assert not row["review_current"]
    assert row["license_status"] == "collection"
    assert row["has_scripts"]
    assert row["has_executables"]
    assert row["uses_network"]
    assert row["uses_credentials"]

    upstream_status.set_review(
        "skills/networked",
        "networked",
        "reviewed",
        "Tester",
        "Reviewed in tests",
    )
    reviewed = upstream_status.trust_inventory()[0]
    assert reviewed["review_state"] == "reviewed"
    assert reviewed["review_current"]
    script.write_text(
        script.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8"
    )
    stale = upstream_status.trust_inventory()[0]
    assert stale["review_state"] == "reviewed"
    assert not stale["review_current"]


def test_reviewed_state_requires_reviewer(workshop: Path, make_skill) -> None:
    write_empty_registry(workshop)
    make_skill(workshop / "skills" / "alpha", "alpha")

    with pytest.raises(ValueError, match="reviewer is required"):
        upstream_status.set_review(
            "skills/alpha",
            "alpha",
            "reviewed",
            None,
            None,
        )


def test_update_rejects_unexpected_remote_before_network_or_checkout(
    workshop: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submodule = workshop / "upstreams" / "example"
    (submodule / ".git").mkdir(parents=True)
    record = {
        "name": "example",
        "path": "upstreams/example",
        "url": "https://github.com/canonical/example.git",
        "fork_url": "https://github.com/personal/example.git",
    }
    monkeypatch.setattr(
        upstream_status,
        "configured_remote",
        lambda path, remote: "https://github.com/attacker/example.git",
    )
    monkeypatch.setattr(
        upstream_status,
        "fetch_remote",
        lambda *args, **kwargs: pytest.fail("must not fetch an unverified remote"),
    )

    with pytest.raises(RuntimeError, match="expected"):
        upstream_status.plan_update(record, "upstream", None, fetch=True)


def test_remote_ref_never_resolves_a_different_remote_or_local_branch(
    workshop: Path,
) -> None:
    repository, revision = initialized_repository(workshop.parent / "repository")
    git_command(repository, "update-ref", "refs/heads/origin/main", revision)
    git_command(repository, "update-ref", "refs/remotes/origin/main", revision)

    assert upstream_status.remote_ref(repository, "upstream", "origin/main") is None
    assert (
        upstream_status.remote_ref(
            repository,
            "upstream",
            "refs/remotes/origin/main",
        )
        is None
    )


@pytest.mark.parametrize(
    "requested",
    [
        "team/feature",
        "upstream/team/feature",
        "refs/remotes/upstream/team/feature",
    ],
)
def test_remote_ref_resolves_slash_branch_only_under_selected_remote(
    workshop: Path, requested: str
) -> None:
    repository, revision = initialized_repository(workshop.parent / "repository")
    git_command(
        repository,
        "update-ref",
        "refs/remotes/upstream/team/feature",
        revision,
    )

    assert upstream_status.remote_ref(repository, "upstream", requested) == (
        "upstream/team/feature",
        revision,
    )


def test_update_plan_is_dry_run_and_surfaces_failed_safety_checks(
    workshop: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    submodule = workshop / "upstreams" / "example"
    (submodule / ".git").mkdir(parents=True)
    current = "a" * 40
    target = "b" * 40
    record = {
        "name": "example",
        "path": "upstreams/example",
        "url": "https://github.com/canonical/example.git",
        "fork_url": "https://github.com/personal/example.git",
    }
    calls: list[tuple[str, ...]] = []

    monkeypatch.setattr(upstream_status, "verify_remote", lambda *args: None)
    monkeypatch.setattr(
        upstream_status,
        "fetch_remote",
        lambda *args, **kwargs: pytest.fail("fetch=False must not fetch"),
    )
    monkeypatch.setattr(
        upstream_status,
        "remote_ref",
        lambda *args: ("upstream/main", target),
    )
    monkeypatch.setattr(
        upstream_status,
        "gitlink_revision",
        lambda *args, **kwargs: current,
    )

    def fake_git_text(path: Path, *arguments: str) -> str | None:
        if arguments == ("rev-parse", "HEAD"):
            return current
        pytest.fail(f"unexpected git_text query: {arguments}")

    def fake_git(path: Path, *arguments: str, check: bool = False):
        calls.append(arguments)
        if arguments[:2] == ("merge-base", "--is-ancestor"):
            return subprocess.CompletedProcess([], 0, "", "")
        pytest.fail(f"unexpected git command: {arguments}")

    monkeypatch.setattr(upstream_status, "git_text", fake_git_text)
    monkeypatch.setattr(upstream_status, "git", fake_git)
    monkeypatch.setattr(upstream_status, "submodule_worktree_clean", lambda path: False)
    monkeypatch.setattr(upstream_status, "superproject_path_clean", lambda path: True)
    monkeypatch.setattr(
        upstream_status,
        "changed_files",
        lambda *args: [{"status": "M", "path": "alpha/SKILL.md"}],
    )
    monkeypatch.setattr(
        upstream_status,
        "changed_skill_sources",
        lambda *args: {"upstreams/example/alpha"},
    )
    monkeypatch.setattr(
        upstream_status,
        "affected_relationships",
        lambda *args: {"bundles": [], "materializations": []},
    )

    plan = upstream_status.plan_update(record, "upstream", None, fetch=False)

    assert plan["dry_run"]
    assert not plan["safe_to_apply"]
    assert not plan["checks"]["submodule_worktree_clean"]
    assert plan["changed_skill_sources"] == ["upstreams/example/alpha"]
    assert not any(arguments and arguments[0] == "checkout" for arguments in calls)

    monkeypatch.setattr(
        upstream_status,
        "git",
        lambda *args, **kwargs: pytest.fail("unsafe plan must not run Git"),
    )
    with pytest.raises(RuntimeError, match="refusing unsafe update"):
        upstream_status.apply_update(plan)


@pytest.mark.parametrize(
    ("changed_state", "expected_check"),
    [
        ({"current": "c" * 40}, "checkout_matches_planned_revision"),
        ({"pinned": "c" * 40}, "pinned_matches_planned_revision"),
        ({"indexed": "c" * 40}, "index_matches_pinned_revision"),
        ({"clean": False}, "submodule_worktree_clean"),
        ({"super_clean": False}, "superproject_gitlink_clean"),
        ({"resolved_target": "c" * 40}, "target_ref_unchanged"),
        ({"fast_forward": False}, "target_is_fast_forward"),
    ],
)
def test_apply_update_rechecks_state_and_never_checks_out_stale_plan(
    workshop: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_state: dict[str, object],
    expected_check: str,
) -> None:
    current = "a" * 40
    target = "b" * 40
    state: dict[str, object] = {
        "current": current,
        "pinned": current,
        "indexed": current,
        "clean": True,
        "super_clean": True,
        "resolved_target": target,
        "fast_forward": True,
    }
    state.update(changed_state)
    plan = {
        "schema_version": 1,
        "operation": "update-submodule-pin",
        "dry_run": True,
        "name": "example",
        "path": "upstreams/example",
        "remote": "upstream",
        "target_ref": "upstream/main",
        "current_revision": current,
        "pinned_revision": current,
        "target_revision": target,
        "up_to_date": False,
        "checks": {"initial_checks": True},
        "safe_to_apply": True,
    }
    record = {
        "name": "example",
        "path": "upstreams/example",
        "url": "https://github.com/canonical/example.git",
        "fork_url": "https://github.com/personal/example.git",
    }
    checkout_calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(upstream_status, "find_upstream", lambda name: record)
    monkeypatch.setattr(upstream_status, "verify_remote", lambda *args: None)
    monkeypatch.setattr(
        upstream_status,
        "git_text",
        lambda path, *args: str(state["current"]),
    )
    monkeypatch.setattr(
        upstream_status,
        "gitlink_revision",
        lambda path, index=False: str(state["indexed" if index else "pinned"]),
    )
    monkeypatch.setattr(
        upstream_status,
        "remote_ref",
        lambda *args: ("upstream/main", str(state["resolved_target"])),
    )
    monkeypatch.setattr(
        upstream_status,
        "submodule_worktree_clean",
        lambda path: bool(state["clean"]),
    )
    monkeypatch.setattr(
        upstream_status,
        "superproject_path_clean",
        lambda path: bool(state["super_clean"]),
    )

    def fake_git(path: Path, *arguments: str, check: bool = False):
        if arguments and arguments[0] == "checkout":
            checkout_calls.append(arguments)
            pytest.fail("stale plan must not check out a revision")
        if arguments[:2] == ("merge-base", "--is-ancestor"):
            return subprocess.CompletedProcess(
                [],
                0 if state["fast_forward"] else 1,
                "",
                "",
            )
        pytest.fail(f"unexpected Git command: {arguments}")

    monkeypatch.setattr(upstream_status, "git", fake_git)

    with pytest.raises(RuntimeError, match=expected_check):
        upstream_status.apply_update(plan)

    assert checkout_calls == []


def test_apply_update_reverifies_remote_before_checkout(
    workshop: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = {
        "schema_version": 1,
        "operation": "update-submodule-pin",
        "name": "example",
        "path": "upstreams/example",
        "remote": "upstream",
        "safe_to_apply": True,
        "checks": {"initial_checks": True},
    }
    record = {
        "name": "example",
        "path": "upstreams/example",
        "url": "https://github.com/canonical/example.git",
        "fork_url": "https://github.com/personal/example.git",
    }
    monkeypatch.setattr(upstream_status, "find_upstream", lambda name: record)
    monkeypatch.setattr(
        upstream_status,
        "verify_remote",
        lambda *args: (_ for _ in ()).throw(RuntimeError("remote URL changed")),
    )
    monkeypatch.setattr(
        upstream_status,
        "git",
        lambda *args, **kwargs: pytest.fail("remote mismatch must prevent Git changes"),
    )

    with pytest.raises(RuntimeError, match="remote URL changed"):
        upstream_status.apply_update(plan)


def test_cli_rejects_human_output_file(
    workshop: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = workshop.parent / "status.txt"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "upstream_status.py",
            "status",
            "--format",
            "human",
            "--output",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as error:
        upstream_status.main()

    assert error.value.code == 2
    assert "--output requires --format json or --format tsv" in capsys.readouterr().err
    assert not output.exists()
