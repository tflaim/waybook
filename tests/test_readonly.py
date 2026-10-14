"""warm-start --read-only writes nothing; the default still updates the board."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from test_acceptance import McpClient, _error_code, _tool_text, init, run


def _stamp(path: Path) -> tuple[int, int]:
    info = path.stat()
    return info.st_ino, info.st_mtime_ns


def _tree(project: Path) -> dict[str, object]:
    way = project / ".waybook"
    found: dict[str, object] = {}
    for dirpath, dirnames, filenames in os.walk(way):
        dirnames.sort()
        for name in filenames:
            path = Path(dirpath) / name
            rel = path.relative_to(way).as_posix()
            if path.is_symlink():
                found[rel] = ("symlink", os.readlink(path))
            elif path.is_file():
                found[rel] = ("file", path.read_bytes(), _stamp(path))
    return found


class ReadOnlyWarmStartTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()
        init(self.project)
        body = self.project / "body.md"
        body.write_text("UNIQUEBODY\n", encoding="utf-8")
        added = run(
            [
                "add",
                "decisions",
                "--title",
                "Parser choice",
                "--one-liner",
                "zebra habitat",
                "--body-file",
                str(body),
            ],
            self.project,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        self.entry_id = added.stdout.strip().split()[-1]

    def _entry(self) -> Path:
        files = list((self.project / ".waybook" / "board").rglob("*.md"))
        self.assertEqual(len(files), 1)
        return files[0]

    def test_read_only_leaves_index_and_usefulness_untouched(self):
        before = _tree(self.project)
        warmed = run(["warm-start", "--read-only", "--query", "zebra"], self.project)
        self.assertEqual(warmed.returncode, 0, warmed.stderr)
        self.assertIn("UNIQUEBODY", warmed.stdout)
        self.assertIn("## decisions", warmed.stdout)
        self.assertEqual(_tree(self.project), before)
        self.assertIn("usefulness: 0.0", self._entry().read_text(encoding="utf-8"))

    def test_default_rewrites_index_and_bumps_usefulness(self):
        index = self.project / ".waybook" / "index.md"
        before_index = _stamp(index)
        before_journal = (self.project / ".waybook" / "log" / "writes.jsonl").read_bytes()
        warmed = run(["warm-start", "--query", "zebra"], self.project)
        self.assertEqual(warmed.returncode, 0, warmed.stderr)
        self.assertIn("UNIQUEBODY", warmed.stdout)
        self.assertNotEqual(_stamp(index), before_index)
        text = self._entry().read_text(encoding="utf-8")
        self.assertIn("usefulness: 0.1", text)
        journal = (self.project / ".waybook" / "log" / "writes.jsonl").read_bytes()
        self.assertNotEqual(journal, before_journal)
        self.assertIn(b'"op":"touch"', journal)

    def test_read_only_without_query_does_not_rewrite_index(self):
        before = _tree(self.project)
        warmed = run(["warm-start", "--read-only"], self.project)
        self.assertEqual(warmed.returncode, 0, warmed.stderr)
        self.assertIn(self.entry_id, warmed.stdout)
        self.assertNotIn("UNIQUEBODY", warmed.stdout)
        self.assertEqual(_tree(self.project), before)

    def test_read_only_does_not_finish_a_crashed_publish(self):
        crashed = run(
            ["add", "decisions", "--title", "Healed later", "--one-liner", "Still unpublished"],
            self.project,
            extra={"WAYBOOK_CRASH_AFTER": "journal"},
        )
        self.assertNotEqual(crashed.returncode, 0)
        before = _tree(self.project)
        warmed = run(["warm-start", "--read-only"], self.project)
        self.assertEqual(warmed.returncode, 0, warmed.stderr)
        self.assertNotIn("Healed later", warmed.stdout)
        self.assertEqual(_tree(self.project), before)
        healed = run(["warm-start"], self.project)
        self.assertEqual(healed.returncode, 0, healed.stderr)
        self.assertIn("Healed later", healed.stdout)


class McpReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()
        init(self.project)
        added = run(
            ["add", "decisions", "--title", "Parser choice", "--one-liner", "zebra habitat"],
            self.project,
        )
        self.assertEqual(added.returncode, 0, added.stderr)

    def _entry(self) -> Path:
        files = list((self.project / ".waybook" / "board").rglob("*.md"))
        self.assertEqual(len(files), 1)
        return files[0]

    def _warm(self, read_only):
        client = McpClient(self.project)
        try:
            return client.call("board_warm_start", {"query": "zebra", "read_only": read_only})
        finally:
            client.close()

    def test_false_strings_still_bump_usefulness(self):
        for token, score in (("false", "0.1"), ("0", "0.2"), ("no", "0.3")):
            response = self._warm(token)
            self.assertFalse(response["result"]["isError"], _tool_text(response))
            self.assertIn(f"usefulness: {score}", self._entry().read_text(encoding="utf-8"))

    def test_true_string_writes_nothing(self):
        before = _tree(self.project)
        response = self._warm("true")
        self.assertFalse(response["result"]["isError"], _tool_text(response))
        self.assertEqual(_tree(self.project), before)
        self.assertIn("usefulness: 0.0", self._entry().read_text(encoding="utf-8"))

    def test_non_bool_read_only_is_rejected(self):
        before = _tree(self.project)
        response = self._warm("maybe")
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(_error_code(response), "E_USAGE")
        self.assertEqual(_tree(self.project), before)


if __name__ == "__main__":
    unittest.main()
