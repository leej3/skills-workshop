import importlib.util
import shlex
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "attribution", Path(__file__).parents[1] / "scripts/github_attribution_hook.py"
)
hook = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hook)


def shell(command, cwd="."):
    return hook.check(
        {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}}
    )


def test_missing_notice_in_common_posting_paths():
    for command in [
        "gh pr create --body hello",
        "gh issue comment 5 --body hello",
        "gh pr close 19 --comment hello",
        "gh pr review 19 --comment --body hello",
        "git status && gh pr close 19 --comment hello",
    ]:
        assert shell(command)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_notice_must_be_first_line():
    assert shell("gh pr comment 1 --body " + shlex.quote("hello\n" + hook.NOTICE))
    assert (
        shell("gh pr comment 1 --body " + shlex.quote("\n" + hook.NOTICE + "\n\nhello"))
        == {}
    )


def test_file_body(tmp_path):
    body = tmp_path / "body.md"
    body.write_text("hello")
    assert (
        shell("gh pr create --body-file body.md", str(tmp_path))["hookSpecificOutput"][
            "permissionDecision"
        ]
        == "deny"
    )
    body.write_text(hook.NOTICE + "\n\nhello")
    assert shell("gh pr create --body-file body.md", str(tmp_path)) == {}


def test_unrelated_operations_are_unaffected():
    for command in [
        "gh pr list",
        "gh pr merge 1 --merge",
        "gh pr edit 1 --title title",
        "git status",
        "gh pr close 1",
    ]:
        assert shell(command) == {}


def test_uninspectable_body_is_a_reminder():
    for command in [
        "gh pr create --fill",
        'gh pr comment 1 --body "$MESSAGE"',
        "gh pr comment 1 --body-file -",
    ]:
        result = shell(command)["hookSpecificOutput"]
        assert "additionalContext" in result
        assert "permissionDecision" not in result


def test_connector_body():
    assert (
        hook.check(
            {
                "tool_name": "mcp__github__create_comment",
                "tool_input": {"body": "hello"},
            }
        )["hookSpecificOutput"]["permissionDecision"]
        == "deny"
    )
    assert (
        hook.check(
            {
                "tool_name": "mcp__github__create_comment",
                "tool_input": {"body": hook.NOTICE},
            }
        )
        == {}
    )
