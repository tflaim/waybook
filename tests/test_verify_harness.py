"""control-waybook must not delete outside its state root."""

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "skills/verify-waybook/helpers/control-waybook"
_LOCAL = re.compile(r"^\s*local\b(.*)$")
_ASSIGNED = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)=")


def _env(state: Path, evidence: Path, run_id: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["WAYBOOK_VERIFY_STATE_ROOT"] = str(state)
    env["WAYBOOK_VERIFY_EVIDENCE_ROOT"] = str(evidence)
    env.pop("WAYBOOK_VERIFY_RUN_ID", None)
    if run_id is not None:
        env["WAYBOOK_VERIFY_RUN_ID"] = run_id
    return env


def _run(state: Path, evidence: Path, *args: str, run_id: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(HELPER), *args],
        cwd=str(ROOT),
        env=_env(state, evidence, run_id),
        capture_output=True,
        text=True,
    )


class HarnessSafetyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.state = self.base / "state"
        self.evidence = self.base / "evidence"
        self.state.mkdir()
        self.evidence.mkdir()

    def test_local_name_is_not_expanded_on_the_same_line(self):
        """A `local name=… out=$name` line expands out before name is set."""
        roots = [
            ROOT / "skills/verify-waybook",
            ROOT / "hooks",
        ]
        files = [ROOT / "install.sh"]
        for root in roots:
            files.extend(path for path in root.rglob("*") if path.is_file())
        bad: list[str] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for number, line in enumerate(text.splitlines(), 1):
                match = _LOCAL.match(line)
                if not match:
                    continue
                body = match.group(1)
                for name in _ASSIGNED.findall(body):
                    if re.search(r"\$\{?" + re.escape(name) + r"\b", body):
                        bad.append(f"{path.relative_to(ROOT)}:{number}:{line.strip()}")
        self.assertEqual(bad, [])

    def test_cleanup_flag_does_not_escape_the_state_root(self):
        outside = self.base / "x"
        outside.mkdir()
        marker = outside / "keep"
        marker.write_text("keep\n", encoding="utf-8")
        result = _run(self.state, self.evidence, "cleanup", "--run-id", "../x")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing run id", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse((outside / "project").exists())

    def test_cleanup_env_does_not_escape_the_state_root(self):
        outside = self.base / "x"
        outside.mkdir()
        marker = outside / "keep"
        marker.write_text("keep\n", encoding="utf-8")
        result = _run(self.state, self.evidence, "cleanup", run_id="../x")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing run id", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")

    def test_cleanup_rejects_dots_only_and_slashes(self):
        for run_id in (".", "..", "...", "foo/bar", "a..b"):
            with self.subTest(run_id=run_id):
                result = _run(self.state, self.evidence, "cleanup", "--run-id", run_id)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("refusing run id", result.stderr)
                self.assertEqual(list(self.state.iterdir()), [])

    def test_cleanup_does_not_follow_a_symlink_outside_the_state_root(self):
        victim = self.base / "victim"
        victim.mkdir()
        marker = victim / "keep"
        marker.write_text("keep\n", encoding="utf-8")
        link = self.state / "linked"
        link.symlink_to(victim)
        result = _run(self.state, self.evidence, "cleanup", "--run-id", "linked")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing run id", result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")
        self.assertTrue(link.is_symlink())

    def test_launch_refuses_a_traversing_run_id_before_mkdir(self):
        outside = self.base / "x"
        outside.mkdir()
        marker = outside / "keep"
        marker.write_text("keep\n", encoding="utf-8")
        result = _run(self.state, self.evidence, "launch", "--run-id", "../x")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")
        self.assertFalse((outside / "project").exists())

    def test_cleanup_removes_only_the_run_directory(self):
        launched = _run(self.state, self.evidence, "launch", "--run-id", "ok-run")
        self.assertEqual(launched.returncode, 0, launched.stderr)
        self.assertTrue((self.state / "ok-run" / "project" / ".waybook").is_dir())
        doctor = _run(self.state, self.evidence, "doctor", "--run-id", "ok-run")
        self.assertEqual(doctor.returncode, 0, doctor.stderr)
        self.assertIn("doctor: READY", doctor.stdout)
        proof = self.evidence / "ok-run" / "note.txt"
        proof.parent.mkdir(parents=True, exist_ok=True)
        proof.write_text("keep\n", encoding="utf-8")
        cleaned = _run(self.state, self.evidence, "cleanup", "--run-id", "ok-run")
        self.assertEqual(cleaned.returncode, 0, cleaned.stderr)
        self.assertFalse((self.state / "ok-run").exists())
        self.assertEqual(proof.read_text(encoding="utf-8"), "keep\n")
        mode = HELPER.stat().st_mode
        self.assertTrue(mode & stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
