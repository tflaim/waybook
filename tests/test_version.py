"""waybook --version prints the package version and exits 0."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    with tempfile.TemporaryDirectory() as tmp:
        return subprocess.run(
            [sys.executable, "-m", "waybook", *args],
            cwd=tmp,
            env=env,
            capture_output=True,
            text=True,
        )


class VersionTests(unittest.TestCase):
    def test_version_flag_prints_package_version(self):
        result = _run("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "0.1.0\n")
        self.assertEqual(result.stderr, "")

    def test_version_does_not_require_a_board(self):
        result = _run("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("No .waybook/", result.stderr)

    def test_missing_command_still_exits_usage(self):
        result = _run()
        self.assertEqual(result.returncode, 2)
        self.assertNotEqual(result.stdout, "0.1.0\n")


if __name__ == "__main__":
    unittest.main()
