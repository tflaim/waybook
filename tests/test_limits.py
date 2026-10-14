"""Entry length and link limits: long bodies are truncated, links are uncapped."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from waybook.board import BODY_MAX, _fence_is_open, fit_body, truncation_pointer

from test_acceptance import init, run


class FitBodyTests(unittest.TestCase):
    def test_cap_is_relaxed_past_two_thousand(self):
        self.assertGreaterEqual(BODY_MAX, 20000)

    def test_short_body_is_unchanged(self):
        text = "x" * 2001
        self.assertEqual(fit_body(text), text)
        self.assertEqual(fit_body("x" * BODY_MAX), "x" * BODY_MAX)

    def test_over_cap_ends_with_a_pointer_and_fits(self):
        for extra in (1, 37, 1000, 50000):
            original = "abc" + ("y" * (BODY_MAX + extra - 3))
            fitted = fit_body(original)
            self.assertLessEqual(len(fitted), BODY_MAX)
            self.assertNotEqual(fitted, original)
            prefix, pointer = fitted.rsplit("\n", 1)
            omitted = len(original) - len(prefix)
            self.assertEqual(pointer, truncation_pointer(omitted))
            self.assertTrue(original.startswith(prefix))
            self.assertGreater(omitted, 0)

    def test_cut_backs_up_to_the_last_newline(self):
        line = "abcdef\n"
        original = line * ((BODY_MAX // len(line)) + 8) + "TAIL"
        fitted = fit_body(original)
        self.assertLessEqual(len(fitted), BODY_MAX)
        prefix, pointer = fitted.rsplit("\n", 1)
        self.assertEqual(pointer, truncation_pointer(len(original) - len(prefix)))
        self.assertTrue(original.startswith(prefix))
        self.assertGreater(len(prefix), 0)
        self.assertEqual(original[len(prefix)], "\n")
        self.assertTrue(prefix.endswith("abcdef"))

    def test_open_fence_is_closed_when_the_cut_lands_inside_it(self):
        original = "intro\n```python\n" + ("code line stays\n" * 4000)
        self.assertGreater(len(original), BODY_MAX)
        fitted = fit_body(original)
        self.assertLessEqual(len(fitted), BODY_MAX)
        lines = fitted.split("\n")
        self.assertEqual(lines[-2], "```")
        pointer = lines[-1]
        self.assertTrue(pointer.startswith("[truncated: omitted "))
        content = fitted.split("\n```\n", 1)[0]
        self.assertTrue(original.startswith(content))
        self.assertIn("```python", content)
        self.assertTrue(_fence_is_open(content))
        self.assertFalse(_fence_is_open("\n".join(lines[:-1])))


class EntryLimitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()
        init(self.project)

    def _entry_text(self) -> str:
        files = list((self.project / ".waybook" / "board").rglob("*.md"))
        self.assertEqual(len(files), 1)
        return files[0].read_text(encoding="utf-8")

    def test_body_over_old_cap_is_stored_whole(self):
        body = self.project / "body.md"
        text = "n" * 2001
        body.write_text(text + "\n", encoding="utf-8")
        added = run(
            ["add", "decisions", "--title", "Long note", "--one-liner", "Past 2000", "--body-file", str(body)],
            self.project,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        stored = self._entry_text()
        self.assertIn(text, stored)
        self.assertNotIn("[truncated:", stored)
        shown = run(["show", added.stdout.strip().split()[-1]], self.project)
        self.assertIn(text, shown.stdout)
        verified = run(["verify"], self.project)
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_body_over_cap_is_truncated_with_a_pointer(self):
        body = self.project / "body.md"
        original = "KEEP" + ("z" * (BODY_MAX + 250))
        body.write_text(original + "\n", encoding="utf-8")
        added = run(
            ["add", "decisions", "--title", "Too long", "--one-liner", "Cut it", "--body-file", str(body)],
            self.project,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        self.assertNotIn("E_SCHEMA_INVALID", added.stderr)
        stored = self._entry_text().split("---\n", 2)[-1]
        if stored.endswith("\n"):
            stored = stored[:-1]
        self.assertLessEqual(len(stored), BODY_MAX)
        self.assertTrue(stored.startswith("KEEP"))
        prefix, pointer = stored.rsplit("\n", 1)
        self.assertEqual(pointer, truncation_pointer(len(original) - len(prefix)))
        self.assertTrue(original.startswith(prefix))
        shown = run(["show", added.stdout.strip().split()[-1]], self.project)
        self.assertIn(pointer, shown.stdout)
        verified = run(["verify"], self.project)
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_secret_past_the_cut_is_still_refused(self):
        secret = "AKIA" + "A" * 16
        body = self.project / "body.md"
        body.write_text(("q" * (BODY_MAX + 50)) + secret, encoding="utf-8")
        added = run(
            ["add", "decisions", "--title", "Secret tail", "--one-liner", "Refuse", "--body-file", str(body)],
            self.project,
        )
        self.assertEqual(added.returncode, 13, added.stderr)
        self.assertIn("aws_access_key", added.stderr)
        self.assertNotIn(secret, added.stderr)
        self.assertEqual(list((self.project / ".waybook" / "board").rglob("*.md")), [])

    def test_flush_uses_the_same_pointer(self):
        pending = self.project / ".waybook" / ".pending" / "notes.txt"
        original = "flush" + ("m" * (BODY_MAX + 80))
        pending.write_text(original, encoding="utf-8")
        flushed = run(["flush"], self.project)
        self.assertEqual(flushed.returncode, 0, flushed.stderr)
        stored = self._entry_text().split("---\n", 2)[-1]
        if stored.endswith("\n"):
            stored = stored[:-1]
        prefix, pointer = stored.rsplit("\n", 1)
        self.assertEqual(pointer, truncation_pointer(len(original) - len(prefix)))
        self.assertLessEqual(len(stored), BODY_MAX)

    def test_many_links_are_stored(self):
        args = ["add", "decisions", "--title", "Lots of links", "--one-liner", "No cap"]
        for number in range(40):
            args.extend(["--link", f"pr:{number + 1}"])
        added = run(args, self.project)
        self.assertEqual(added.returncode, 0, added.stderr)
        stored = self._entry_text()
        for number in range(40):
            self.assertIn(f'ref: "{number + 1}"', stored)
        verified = run(["verify"], self.project)
        self.assertEqual(verified.returncode, 0, verified.stderr)


if __name__ == "__main__":
    unittest.main()
