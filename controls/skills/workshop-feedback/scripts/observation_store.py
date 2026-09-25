"""Schema-validated shareable observations with a matching private overlay tree."""

from __future__ import annotations

import fcntl
import json
import math
import os
import re
import tempfile
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas/observation-v2.schema.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
FORMATS = FormatChecker()


@FORMATS.checks("date-time", raises=ValueError)
def valid_datetime(value):
    if not isinstance(value, str):
        return True
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})",
        value,
    ):
        return False
    return (
        datetime.fromisoformat(value.upper().replace("Z", "+00:00")).tzinfo is not None
    )


VALIDATOR = Draft202012Validator(SCHEMA, format_checker=FORMATS)


def private_root():
    return (
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "skills-workshop/feedback-overlay"
    )


def public_root():
    root = os.environ.get("SKILLS_WORKSHOP_ROOT")
    if not root:
        try:
            root = json.loads(
                (Path.home() / ".config/skills-workshop/config.json").read_text()
            )["workshop_root"]
        except (OSError, ValueError, KeyError):
            return private_root().parent / "feedback-shareable"
    return Path(root).expanduser() / "memory/observations"


def validate(row):
    errors = sorted(VALIDATOR.iter_errors(row), key=lambda e: str(e.path))
    if errors:
        # Do not echo possibly sensitive rejected values into command output.
        raise ValueError("observation does not conform to observation-v2.schema.json")

    def finite(value):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric observations must be finite")
        if isinstance(value, dict):
            for item in value.values():
                finite(item)
        if isinstance(value, list):
            for item in value:
                finite(item)

    finite(row)
    execution = row.get("execution", {})
    if execution.get("started_at") and execution.get("ended_at"):
        start = datetime.fromisoformat(
            execution["started_at"].upper().replace("Z", "+00:00")
        )
        end = datetime.fromisoformat(
            execution["ended_at"].upper().replace("Z", "+00:00")
        )
        if end < start:
            raise ValueError("ended_at precedes started_at")
    return row


def check_roots(store, overlay):
    store, overlay = store.expanduser().resolve(), overlay.expanduser().resolve()
    if store == overlay or store in overlay.parents or overlay in store.parents:
        raise ValueError("shareable tree and private overlay must be disjoint")
    if any((p / ".git").exists() for p in (overlay, *overlay.parents)):
        raise ValueError("private overlay must be outside Git")
    return store, overlay


@contextmanager
def locked(store, overlay):
    store, overlay = check_roots(store, overlay)
    store.mkdir(parents=True, exist_ok=True)
    overlay.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(overlay, 0o700)
    fd = os.open(store / ".feedback.lock", os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, "r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield store, overlay


def read_tree(root):
    result = {}
    for path in sorted(root.glob("records/*/*/*.json")):
        row = validate(json.loads(path.read_text()))
        if row["id"] in result:
            raise ValueError("duplicate observation ID in tree")
        result[row["id"]] = row
    return result


def read(store, overlay, public_only=False):
    with locked(store, overlay) as (public_dir, private_dir):
        rows = read_tree(public_dir)
        if not public_only:
            rows.update(read_tree(private_dir))
        return sorted(rows.values(), key=lambda r: (r["recorded_at"], r["id"]))


def atomic_write(path, row, private=False):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    fd, tmp = tempfile.mkstemp(prefix=".feedback-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(
                json.dumps(row, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
            )
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp, path)  # Never overwrite an existing observation.
    finally:
        os.unlink(tmp)


def omit(row, pointer):
    if not pointer.startswith("/"):
        raise ValueError(
            "private fields must use JSON pointers, e.g. /context/session_id"
        )
    keys = [k.replace("~1", "/").replace("~0", "~") for k in pointer[1:].split("/")]
    parent = row
    for key in keys[:-1]:
        if not isinstance(parent, dict) or key not in parent:
            raise ValueError("private field pointer does not exist")
        parent = parent[key]
    if not isinstance(parent, dict) or keys[-1] not in parent:
        raise ValueError(
            "private field pointer does not exist; redact arrays as a whole"
        )
    del parent[keys[-1]]


def write(
    store, overlay, payload, event_id=None, visibility="shareable", sensitivity=None
):
    event_id = event_id or str(uuid.uuid4())
    row = {
        "schema_version": 2,
        "id": event_id,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        **payload,
        "visibility": visibility,
    }
    if sensitivity:
        row["sensitivity"] = sensitivity
    if visibility == "private" and not sensitivity:
        raise ValueError("private records require a sensitivity reason and category")
    validate(row)
    public = json.loads(json.dumps(row))
    public.pop("sensitivity", None)
    if sensitivity:
        for pointer in sensitivity["fields"]:
            omit(public, pointer)
    if visibility != "private":
        try:
            validate(public)
        except ValueError as exc:
            raise ValueError(
                "redaction removed required fields; use --visibility private for the whole record"
            ) from exc
    with locked(store, overlay) as (public_dir, private_dir):
        existing = read_tree(public_dir)
        existing.update(read_tree(private_dir))
        if event_id in existing:
            original = existing[event_id]
            if {k: v for k, v in original.items() if k != "recorded_at"} != {
                k: v for k, v in row.items() if k != "recorded_at"
            }:
                raise ValueError("event ID already exists with different content")
            # Retry also repairs an interrupted two-tree write using the original timestamp.
            row["recorded_at"] = public["recorded_at"] = original["recorded_at"]
        date = datetime.fromisoformat(row["recorded_at"])
        relative = (
            Path("records")
            / f"{date.year:04d}"
            / f"{date.month:02d}"
            / f"{event_id}.json"
        )
        if sensitivity or visibility == "private":
            target = private_dir / relative
            if not target.exists():
                atomic_write(target, row, private=True)
        if visibility != "private":
            target = public_dir / relative
            if not target.exists():
                atomic_write(target, public)
        return {
            "id": event_id,
            "duplicate": event_id in existing,
            "visibility": visibility,
            "overlay": bool(sensitivity),
        }
