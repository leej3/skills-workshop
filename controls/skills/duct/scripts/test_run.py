"""Integration checks; requires installed con-duct, uses temporary log storage."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.project = self.base / "project with spaces"
        self.project.mkdir()
        self.store = self.base / "logs {literal}"
        self.helper = Path(__file__).with_name("run.py")

    def run_command(self, *options, code="print('ok')", extra=(), cwd=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("DUCT_")}
        return subprocess.run(
            [
                sys.executable,
                str(self.helper),
                "--store",
                str(self.store),
                "--project",
                str(self.project),
                *options,
                "--",
                sys.executable,
                "-c",
                code,
                *extra,
            ],
            cwd=cwd or self.project,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_failure_arguments_retention_and_export(self):
        result = self.run_command(
            code="import sys; print(repr(sys.argv[1])); print('failure', file=sys.stderr); sys.exit(7)",
            extra=("a b;$literal",),
        )
        self.assertEqual(result.returncode, 7, result.stderr)
        (info_path,) = self.store.glob("*/*/run_info.json")
        run = info_path.parent
        self.assertIn("a b;$literal", (run / "run_stdout").read_text())
        self.assertIn("failure", (run / "run_stderr").read_text())
        self.assertEqual(
            json.loads(info_path.read_text())["execution_summary"]["exit_code"], 7
        )
        self.assertEqual(run.stat().st_mode & 0o777, 0o700)
        copied = self.base / "export"
        shutil.copytree(run, copied)

        def digests(root):
            return {
                p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.iterdir()
            }

        self.assertEqual(digests(run), digests(copied))
        self.assertEqual(list(self.project.iterdir()), [])

    def test_stable_identity_unique_runs_and_capture_none(self):
        subdir = self.project / "subdir"
        subdir.mkdir()
        for cwd in (self.project, subdir):
            result = self.run_command(
                "--project-id", "portable-project", "--capture", "none", cwd=cwd
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        runs = list((self.store / "portable-project").iterdir())
        self.assertEqual(len(runs), 2)
        for run in runs:
            self.assertFalse((run / "run_stdout").exists())
            context = json.loads((run / "context.json").read_text())
            self.assertEqual(context["project_id"], "portable-project")

    def test_invalid_id_does_not_execute(self):
        result = self.run_command(
            "--project-id", "../escape", code="open('sentinel', 'w').close()"
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.project / "sentinel").exists())
        self.assertFalse(self.store.exists())


if __name__ == "__main__":
    unittest.main()
