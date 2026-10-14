"""A bad --link names the accepted forms and an example."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_acceptance import init, run


def _forms(message: str) -> None:
    if "commit:" not in message or "pr:" not in message:
        raise AssertionError(message)
    if "--link pr:12" not in message:
        raise AssertionError(message)


class LinkHelpTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()
        init(self.project)

    def test_missing_colon_lists_accepted_forms(self):
        result = run(
            ["add", "decisions", "--title", "Bad link", "--one-liner", "No colon", "--link", "foo"],
            self.project,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Bad arguments: link foo", result.stderr)
        _forms(result.stderr)
        payload = json.loads(
            run(
                ["--json", "add", "decisions", "--title", "Bad link", "--one-liner", "No colon", "--link", "foo"],
                self.project,
            ).stderr
        )
        self.assertEqual(payload["error"]["code"], "E_USAGE")
        _forms(payload["error"]["message"])

    def test_unknown_type_lists_accepted_forms(self):
        result = run(
            ["add", "decisions", "--title", "Bad type", "--one-liner", "Not a link", "--link", "issue:3"],
            self.project,
        )
        self.assertEqual(result.returncode, 4, result.stderr)
        self.assertIn("schema v2: links", result.stderr)
        _forms(result.stderr)
        self.assertEqual(list((self.project / ".waybook" / "board").rglob("*.md")), [])


if __name__ == "__main__":
    unittest.main()
