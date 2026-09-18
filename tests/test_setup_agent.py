import pytest

from scripts.setup_agent import END, START, setup


@pytest.fixture
def installation(tmp_path):
    root = tmp_path / "workshop"
    for name in ("skills-workshop", "workshop-feedback"):
        path = root / ".agents" / "skills" / name
        path.mkdir(parents=True)
        (path / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    home = tmp_path / "user"
    return root, home, home / ".codex"


def test_preview_is_read_only_and_install_is_repeatable(installation):
    root, home, codex_home = installation
    setup(*installation)
    assert not home.exists()
    setup(*installation, apply=True)
    instructions = codex_home / "AGENTS.md"
    original = instructions.read_bytes()
    setup(*installation, apply=True)
    assert instructions.read_bytes() == original
    assert instructions.read_text().count(START) == 1
    for name in ("skills-workshop", "workshop-feedback"):
        assert (
            home / ".agents" / "skills" / name
        ).resolve() == root / ".agents" / "skills" / name


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
