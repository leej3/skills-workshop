import json
import shlex

import pytest

from scripts.setup_side_chat_archive import EVENTS, setup


@pytest.fixture
def host(tmp_path):
    root = tmp_path / "Workshop checkout"
    source = root / "scripts/archive_side_chat.py"
    source.parent.mkdir(parents=True)
    source.write_text("# fixture\n")
    return (
        root,
        tmp_path / "custom Codex home",
        tmp_path / "Python environment/bin/python",
    )


def test_preview_and_repeated_install_preserve_other_hooks_and_trust(host):
    root, home, python = host
    setup(*host)
    assert not home.exists()
    home.mkdir()
    config = home / "config.toml"
    config.write_text('[hooks.state.original]\ntrusted_hash = "unchanged"\n')
    original = {
        "description": "User hooks",
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "another-hook"}]}]
        },
    }
    path = home / "hooks.json"
    previous = json.dumps(original)
    path.write_text(previous)
    setup(*host, apply=True)
    data = json.loads(path.read_text())
    assert data["description"] == original["description"]
    assert data["hooks"]["Stop"][0] == original["hooks"]["Stop"][0]
    for event in EVENTS:
        handler = data["hooks"][event][-1]["hooks"][0]
        assert shlex.split(handler["command"]) == [
            str(python),
            str(root / "scripts/archive_side_chat.py"),
        ]
    installed = path.read_bytes()
    assert setup(*host, apply=True)[1] is False
    assert path.read_bytes() == installed
    assert config.read_text() == '[hooks.state.original]\ntrusted_hash = "unchanged"\n'
    backups = list((home / "backups").iterdir())
    assert len(backups) == 1 and backups[0].read_text() == previous


def test_migrates_local_prototype_without_duplicate_hooks(host):
    _, home, _ = host
    home.mkdir()
    command = shlex.join(["/old/python", str(home / "hooks/archive_side_chat.py")])
    original = {
        "hooks": {
            event: [{"hooks": [{"type": "command", "command": command, "timeout": 3}]}]
            for event in EVENTS
        }
    }
    path = home / "hooks.json"
    path.write_text(json.dumps(original))
    setup(*host, apply=True)
    data = json.loads(path.read_text())
    for event in EVENTS:
        assert len(data["hooks"][event]) == 1
        assert data["hooks"][event][0]["hooks"][0]["command"] != command


@pytest.mark.parametrize("content", ["{bad json", '{"hooks":{"Stop":{}}}'])
def test_invalid_configuration_is_preserved(host, content):
    _, home, _ = host
    home.mkdir()
    path = home / "hooks.json"
    path.write_text(content)
    with pytest.raises((ValueError, TypeError)):
        setup(*host, apply=True)
    assert path.read_text() == content
    assert not (home / "backups").exists()
