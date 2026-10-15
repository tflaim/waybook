"""The CLI and the MCP server run every operation through one table.

Each test pins one place where the two surfaces used to disagree.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from test_acceptance import McpClient, _error_code, _tool_text, init, run

STAMP = "2026-10-11T14:02:33Z"


def _payload(response: dict) -> dict:
    return json.loads(_tool_text(response))


class OperationTableTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.project.mkdir()
        init(self.project)

    def _add(self, title="Parser choice", one_liner="zebra habitat"):
        added = run(["add", "decisions", "--title", title, "--one-liner", one_liner], self.project)
        self.assertEqual(added.returncode, 0, added.stderr)
        return added.stdout.strip().split()[-1]

    def _resolve(self, entry_id):
        done = run(["mark-resolved", entry_id], self.project)
        self.assertEqual(done.returncode, 0, done.stderr)

    def _mcp(self, *calls, agent="tester"):
        client = McpClient(self.project, agent=agent)
        try:
            return [client.call(name, arguments) for name, arguments in calls]
        finally:
            client.close()

    # (a) prune defaults are declared once: real on the CLI, dry run on MCP.

    def test_a_prune_defaults_are_declared_once(self):
        from waybook.operations import OPERATIONS

        dry_run = OPERATIONS["prune"].param("dry_run")
        self.assertEqual(dry_run.default_for("cli"), False)
        self.assertEqual(dry_run.default_for("mcp"), True)

    # (c) every MCP boolean goes through the same strict parser.

    def test_c_mcp_dry_run_false_string_really_prunes(self):
        self._resolve(self._add())
        (response,) = self._mcp(("board_prune", {"dry_run": "false"}))
        self.assertFalse(response["result"]["isError"], _tool_text(response))
        self.assertEqual(_payload(response)["dry_run"], False)
        self.assertEqual(len(list((self.project / ".waybook" / "archive").rglob("*.md"))), 1)

    def test_c_mcp_archived_false_string_lists_the_board(self):
        entry_id = self._add()
        (response,) = self._mcp(("board_list", {"archived": "false"}))
        self.assertFalse(response["result"]["isError"], _tool_text(response))
        self.assertEqual([e["id"] for e in _payload(response)["entries"]], [entry_id])

    def test_c_non_bool_values_are_usage_errors(self):
        responses = self._mcp(
            ("board_list", {"archived": "maybe"}),
            ("board_prune", {"dry_run": "maybe"}),
            ("board_prune", {"dry_run": 2}),
            ("board_warm_start", {"read_only": "maybe"}),
        )
        for response in responses:
            self.assertTrue(response["result"]["isError"])
            self.assertEqual(_error_code(response), "E_USAGE", _tool_text(response))

    # (b) the agent falls back to "local" once; "session" only names the flush.

    def test_b_flush_without_agent_is_written_by_local(self):
        pending = self.project / ".waybook" / ".pending" / "notes.txt"
        pending.write_text("left off in the parser\n", encoding="utf-8")
        flushed = run(["flush"], self.project)
        self.assertEqual(flushed.returncode, 0, flushed.stderr)
        listed = run(["--json", "list", "--section", "open-threads"], self.project)
        (entry,) = json.loads(listed.stdout)["entries"]
        self.assertEqual(entry["title"], "Unfinished: session")
        self.assertEqual(entry["source_agent"], "local")

    # (d) required arguments are checked in the shared layer.

    def test_d_missing_required_mcp_arguments_are_usage_errors(self):
        responses = self._mcp(
            ("board_show", {}),
            ("board_add", {"section": "decisions", "one_liner": "no title"}),
            ("board_add", {"title": "No section", "one_liner": "x"}),
            ("board_mark_resolved", {}),
            ("coordinator_read", {"reason": "a long enough reason"}),
        )
        for response in responses:
            self.assertTrue(response["result"]["isError"])
            self.assertEqual(_error_code(response), "E_USAGE", _tool_text(response))

    def test_d_missing_required_cli_arguments_are_usage_errors(self):
        for args in (
            ["--json", "add", "decisions", "--one-liner", "no title"],
            ["--json", "add", "decisions", "--title", "No one-liner"],
        ):
            result = run(args, self.project)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stderr)["error"]["code"], "E_USAGE")

    # (e) no cross-repo links.

    def test_e_link_object_with_a_repo_is_rejected(self):
        (response,) = self._mcp(
            (
                "board_add",
                {
                    "section": "decisions",
                    "title": "Elsewhere",
                    "one_liner": "points at another repo",
                    "links": [{"type": "pr", "repo": "someone/else", "ref": "1"}],
                },
            )
        )
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(_error_code(response), "E_SCHEMA_INVALID")
        self.assertEqual(list((self.project / ".waybook" / "board").rglob("*.md")), [])

    def test_e_link_object_without_a_repo_still_works(self):
        (response,) = self._mcp(
            (
                "board_add",
                {
                    "section": "decisions",
                    "title": "Here",
                    "one_liner": "points at this repo",
                    "links": [{"type": "pr", "ref": "1"}],
                },
            )
        )
        self.assertFalse(response["result"]["isError"], _tool_text(response))

    # (f) one response shape for board_index and warm_start.

    def test_f_index_and_warm_start_have_one_shape(self):
        self._add()
        index = run(["--json", "index"], self.project)
        warm = run(["--json", "warm-start", "--query", "zebra", "--read-only"], self.project)
        mcp_index, mcp_warm = self._mcp(
            ("board_index", {}),
            ("board_warm_start", {"query": "zebra", "read_only": True}),
        )
        self.assertEqual(_payload(mcp_index), json.loads(index.stdout))
        self.assertEqual(_payload(mcp_warm), json.loads(warm.stdout))

    def test_f_board_index_says_it_writes_index_md(self):
        from waybook.mcp_server import _tools

        (tool,) = [t for t in _tools() if t["name"] == "board_index"]
        self.assertIn("index.md", tool["description"])

    # (g) unexpected exceptions become one internal error; the MCP loop survives.

    def test_g_cli_reports_an_unexpected_exception_as_internal(self):
        from waybook import cli

        entry_id = self._add()
        err = io.StringIO()
        with mock.patch("waybook.board._show_entry_unlocked", side_effect=RuntimeError("boom")), \
                mock.patch.dict(os.environ, {"WAYBOOK_NOW": STAMP}), \
                contextlib.chdir(self.project), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["--json", "show", entry_id])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(err.getvalue())["error"]["code"], "E_INTERNAL")

    def test_g_mcp_reports_an_unexpected_exception_as_internal(self):
        from waybook.mcp_server import handle

        entry_id = self._add()
        message = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "board_show", "arguments": {"id": entry_id}},
        }
        with mock.patch("waybook.board._show_entry_unlocked", side_effect=RuntimeError("boom")), \
                mock.patch.dict(os.environ, {"WAYBOOK_NOW": STAMP}):
            response = handle(message, self.project, "project", "tester")
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(_error_code(response), "E_INTERNAL")

    def test_g_mcp_loop_keeps_running_after_a_bad_line(self):
        client = McpClient(self.project)
        try:
            client.proc.stdin.write(b"this is not json\n")
            client.proc.stdin.flush()
            response = client.request("ping", {})
            self.assertEqual(response.get("result"), {})
        finally:
            client.close()

    # (h) the body cap is in the tool schema.

    def test_h_board_add_documents_the_body_cap(self):
        from waybook.mcp_server import _tools

        (tool,) = [t for t in _tools() if t["name"] == "board_add"]
        self.assertIn("20000", tool["inputSchema"]["properties"]["body"].get("description", ""))


if __name__ == "__main__":
    unittest.main()
