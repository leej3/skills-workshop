"""Help agents retain their identity when publishing GitHub prose."""

import json
import shlex
import sys
from pathlib import Path

NOTICE = "**AI-generated draft — not reviewed by John**"
REMINDER = (
    "Before publishing GitHub prose, put this exact notice on the first "
    f"non-empty line: {NOTICE}. Preserve human-edited messages. "
    "This hook checks attribution, not human approval."
)


def response(reason=None, reminder=False):
    output = {"hookEventName": "PreToolUse"}
    if reason:
        output.update(permissionDecision="deny", permissionDecisionReason=reason)
    elif reminder:
        output["additionalContext"] = REMINDER
    return {"hookSpecificOutput": output} if reason or reminder else {}


def check_body(body):
    if body.lstrip().splitlines()[:1] != [NOTICE]:
        return response(REMINDER + " Correct the body and retry.")
    return {}


def check(event):
    name = event.get("tool_name", "")
    args = event.get("tool_input", {})
    if not isinstance(args, dict):
        return {}
    if "github" in name.lower():
        if any(
            word in name.lower()
            for word in ("create", "update", "comment", "review", "reply", "edit")
        ):
            for key in ("body", "body_text", "comment", "text"):
                if isinstance(args.get(key), str):
                    return check_body(args[key])
            return response(reminder=True)
        return {}
    if name not in {"Bash", "exec_command", "shell", "shell_command"}:
        return {}
    command = args.get("command", args.get("cmd", ""))
    if not isinstance(command, str):
        return {}
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return response(reminder="gh" in command)
    # Inspect each visible gh invocation, including close --comment in a chain.
    for start, token in enumerate(tokens):
        if Path(token).name != "gh":
            continue
        end = next(
            (
                i
                for i in range(start + 1, len(tokens))
                if tokens[i] in {";", "&&", "||", "|"}
            ),
            len(tokens),
        )
        call = tokens[start:end]
        if len(call) < 3 or call[1] not in {"pr", "issue"}:
            continue
        action = call[2]
        if action not in {"create", "comment", "review", "edit", "close", "reopen"}:
            continue
        bodies = []
        for i, arg in enumerate(call):
            option, equal, inline = arg.partition("=")
            if option not in {"--body", "-b", "--body-file", "-F", "--comment", "-c"}:
                continue
            if action == "review" and option in {"--comment", "-c"}:
                continue
            value = inline if equal else (call[i + 1] if i + 1 < len(call) else "")
            if option in {"--body-file", "-F"}:
                if value == "-":
                    return response(reminder=True)
                path = Path(value)
                if not path.is_absolute():
                    path = Path(args.get("workdir") or event.get("cwd", ".")) / path
                try:
                    value = path.read_text()
                except (OSError, UnicodeError):
                    return response(reminder=True)
            elif "$" in value or "`" in value:
                return response(reminder=True)
            bodies.append(value)
        for body in bodies:
            result = check_body(body)
            if result:
                return result
        if not bodies and action in {"create", "comment", "review"}:
            return response(reminder=True)
    return {}


def main():
    try:
        result = check(json.load(sys.stdin))
    except (ValueError, TypeError, KeyError):
        result = response(reminder=True)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
