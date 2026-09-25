import pytest

from scripts.setup_agent import END, START, setup, status, store_path


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / "workshop"
    home = tmp_path / "user"
    for name in ("skills-workshop", "workshop-feedback"):
        path = store_path(home) / ".agents" / "skills" / name
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    home = tmp_path / "user"
    return root, home, home / ".codex"


def test_preview_is_read_only_and_install_is_repeatable(installation):
    _root, home, codex_home = installation
    setup(*installation)
    assert not (home / ".codex").exists()
    assert not (home / ".config").exists()
    setup(*installation, apply=True)
    instructions = codex_home / "AGENTS.md"
    original = instructions.read_bytes()
    setup(*installation, apply=True)
    assert instructions.read_bytes() == original
    assert instructions.read_text().count(START) == 1
    for name in ("skills-workshop", "workshop-feedback"):
        assert (home / ".agents" / "skills" / name).resolve() == store_path(
            home
        ) / ".agents" / "skills" / name


def test_conflict_does_not_partially_install(installation):
    _root, home, codex_home = installation
    conflict = home / ".agents/skills/workshop-feedback"
    conflict.mkdir(parents=True)
    (conflict / "SKILL.md").write_text("Existing custom instructions")
    with pytest.raises(ValueError, match="existing skill"):
        setup(*installation, apply=True)
    assert not (home / ".agents/skills/skills-workshop").exists()
    assert not (codex_home / "AGENTS.md").exists()
    assert (conflict / "SKILL.md").read_text() == "Existing custom instructions"


def test_preserves_user_instructions_and_unrelated_config(installation):
    _root, home, codex_home = installation
    codex_home.mkdir(parents=True)
    instructions = codex_home / "AGENTS.md"
    instructions.write_text(
        "User rules\n\n" + START + "\nOld block\n" + END + "\nMore rules\n"
    )
    config = home / ".config/skills-workshop/config.json"
    config.parent.mkdir(parents=True)
    config.write_text('{"other_setting": true}')
    setup(*installation, apply=True)
    assert instructions.read_text().startswith("User rules\n\n")
    assert instructions.read_text().endswith("\nMore rules\n")
    assert "Old block" not in instructions.read_text()
    assert '"other_setting": true' in config.read_text()


def test_reuses_canonical_legacy_link(installation):
    root, home, codex_home = installation
    legacy = codex_home / "skills/skills-workshop"
    legacy.parent.mkdir(parents=True)
    legacy.symlink_to(root / ".agents/skills/skills-workshop", target_is_directory=True)
    setup(*installation, apply=True)
    assert not (home / ".agents/skills/skills-workshop").exists()
    assert legacy.is_symlink()


@pytest.mark.parametrize("text", [START, END, END + START, START + END + START + END])
def test_malformed_markers_do_not_write(installation, text):
    _root, home, codex_home = installation
    codex_home.mkdir(parents=True)
    (codex_home / "AGENTS.md").write_text(text)
    with pytest.raises(ValueError, match="markers"):
        setup(*installation, apply=True)
    assert not (home / ".agents").exists()


def test_other_checkout_configuration_is_preserved(installation):
    _root, home, _codex_home = installation
    config = home / ".config/skills-workshop/config.json"
    config.parent.mkdir(parents=True)
    original = '{"workshop_root": "/another/checkout"}'
    config.write_text(original)
    with pytest.raises(ValueError, match="another checkout"):
        setup(*installation, apply=True)
    assert config.read_text() == original
    assert not (home / ".agents").exists()


def test_all_transitions_preserve_memory_and_keep_off_recovery(installation):
    _root, home, codex_home = installation
    memory = home / "memory.json"
    memory.write_text('{"preserve": true}')
    for mode in ("on", "manual", "off", "off", "manual", "on"):
        setup(*installation, apply=True, mode=mode)
        report = status(*installation)
        assert report["mode"] == mode
        text = (codex_home / "AGENTS.md").read_text()
        assert f"Workshop mode: {mode}" in text
        assert "workshop enable" in text and "workshop manual" in text
        for name in ("skills-workshop", "workshop-feedback"):
            assert (home / ".agents/skills" / name).is_symlink() == (mode != "off")
            assert (store_path(home) / ".agents/skills" / name / "SKILL.md").exists()
        assert memory.read_text() == '{"preserve": true}'
    setup(*installation, apply=True, mode="off")
    setup(*installation, apply=True)
    assert status(*installation)["mode"] == "off"


def test_disable_removes_both_owned_aliases_and_preserves_foreign(installation):
    root, home, codex_home = installation
    setup(*installation, apply=True)
    legacy = codex_home / "skills/skills-workshop"
    legacy.parent.mkdir(parents=True)
    legacy.symlink_to(root / ".agents/skills/skills-workshop")
    setup(*installation, apply=True, mode="off")
    assert not legacy.is_symlink()
    foreign = home / ".agents/skills/workshop-feedback"
    foreign.symlink_to(home / "someone-elses-skill")
    before = (codex_home / "AGENTS.md").read_bytes()
    with pytest.raises(ValueError, match="existing skill"):
        setup(*installation, apply=True, mode="off")
    assert foreign.is_symlink()
    assert (codex_home / "AGENTS.md").read_bytes() == before


def test_failed_restore_does_not_activate_or_write_guidance(installation, monkeypatch):
    import subprocess

    from scripts import setup_agent

    _root, home, codex_home = installation

    def fail(*args):
        raise subprocess.CalledProcessError(1, "apm")

    monkeypatch.setattr(setup_agent, "restore_controls", fail)
    with pytest.raises(subprocess.CalledProcessError):
        setup(*installation, apply=True, restore=True)
    assert not (home / ".agents").exists()
    assert not (codex_home / "AGENTS.md").exists()


def test_preview_never_restores(installation, monkeypatch):
    from scripts import setup_agent

    def fail(*args):
        raise AssertionError("preview called installer")

    monkeypatch.setattr(setup_agent, "restore_controls", fail)
    setup(*installation, restore=True)


def test_real_apm_install_stays_intact_across_modes(tmp_path):
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    home = tmp_path / "user"
    store = store_path(home)
    store.mkdir(parents=True)
    (store / "apm.yml").write_text(
        "name: user-test\nversion: 0.1.0\ntargets: [agent-skills]\n"
    )
    # This isolated fixture has no organization policy or credentials.
    subprocess.run(
        ["apm", "install", str(root / "controls"), "--no-policy"], cwd=store, check=True
    )
    lock = (store / "apm.lock.yaml").read_bytes()
    for mode in ("on", "manual", "off", "on"):
        setup(root, home, home / ".codex", mode=mode, apply=True)
        subprocess.run(["apm", "audit", "--ci", "--no-policy"], cwd=store, check=True)
        assert (store / "apm.lock.yaml").read_bytes() == lock
    assert not (root / ".agents/skills/skills-workshop").exists()
