"""Warm-start computes the current default-branch tip and flags entries that
name a commit already on it, instead of trusting a stored 'main is X' fact."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from test_acceptance import init, run


def _git(cwd: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
    }
    out = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env=env, check=True)
    return out.stdout.strip()


class LiveMainTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()
        _git(self.project, "init", "-q", "-b", "main")
        (self.project / "a.txt").write_text("a\n")
        _git(self.project, "add", "a.txt")
        _git(self.project, "commit", "-q", "-m", "first")
        self.old = _git(self.project, "rev-parse", "--short=7", "HEAD")
        (self.project / "a.txt").write_text("b\n")
        _git(self.project, "commit", "-q", "-am", "second")
        self.new = _git(self.project, "rev-parse", "--short=7", "HEAD")
        _git(self.project, "update-ref", "refs/remotes/origin/main", "HEAD")
        init(self.project)

    def _add(self, title, one, sha):
        res = run(["add", "decisions", "--title", title, "--one-liner", one, "--link", f"commit:{sha}"], self.project)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_warm_start_prints_live_main(self):
        out = run(["warm-start"], self.project)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn(f"main: {self.new}", out.stdout)

    def test_entry_naming_older_commit_is_flagged(self):
        self._add("Merged so far", f"main at {self.old}", self.old)
        self._add("Current", f"tip is {self.new}", self.new)
        out = run(["warm-start"], self.project)
        lines = {line.split()[0]: line for line in out.stdout.splitlines() if line.startswith("dec-")}
        flagged = [l for l in lines.values() if "Merged so far" in l][0]
        fresh = [l for l in lines.values() if "Current" in l][0]
        self.assertIn("possibly stale", flagged)
        self.assertNotIn("possibly stale", fresh)

    def test_non_git_project_unchanged(self):
        other = Path(self._tmp.name) / "plain"
        other.mkdir()
        init(other)
        out = run(["warm-start"], other)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertNotIn("main:", out.stdout)
        self.assertNotIn("possibly stale", out.stdout)


if __name__ == "__main__":
    unittest.main()
