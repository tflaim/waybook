"""Acceptance tests from SPEC.md section 10."""

from __future__ import annotations

import json
import os
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def _base_env(now: str | None = "2026-10-11T14:02:33Z", extra: dict | None = None) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env.pop("WAYBOOK_ROLE", None)
    env.pop("WAYBOOK_AGENT", None)
    if now is None:
        env.pop("WAYBOOK_NOW", None)
    else:
        env["WAYBOOK_NOW"] = now
    if extra:
        env.update(extra)
    return env


def run(args, cwd, now="2026-10-11T14:02:33Z", extra=None):
    return subprocess.run(
        [sys.executable, "-m", "waybook", *args],
        cwd=cwd,
        env=_base_env(now, extra),
        capture_output=True,
        text=True,
    )


def init(cwd, now="2026-10-11T14:02:33Z", project_id="demo", coordinator=False):
    args = ["init", "--project-id", project_id]
    if coordinator:
        args.append("--coordinator")
    result = run(args, cwd, now=now)
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return result


def shift(stamp: str, days: int = 0, minutes: int = 0) -> str:
    moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    moment += timedelta(days=days, minutes=minutes)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


class McpClient:
    def __init__(self, project: Path, role: str = "project", agent: str = "tester", now: str | None = "2026-10-11T14:02:33Z"):
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "waybook",
                "--project",
                str(project),
                "--role",
                role,
                "--agent",
                agent,
                "mcp",
            ],
            cwd=str(project),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=_base_env(now, {"WAYBOOK_AGENT": agent}),
        )
        self._n = 0
        try:
            self._handshake()
        except Exception:
            self.close()
            raise

    def _handshake(self):
        self.request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "0"},
            },
        )
        self.notify("notifications/initialized")

    def close(self):
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except Exception:
                    pass
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.proc.kill()

    def _send(self, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        self.proc.stdin.write(data)
        self.proc.stdin.flush()

    def _recv(self, timeout: float = 10) -> dict:
        deadline = time.time() + timeout
        buf = getattr(self, "_buf", b"")
        while b"\n" not in buf:
            if time.time() > deadline:
                raise TimeoutError("timed out waiting for mcp response")
            ready, _, _ = select.select([self.proc.stdout], [], [], 0.2)
            if not ready:
                if self.proc.poll() is not None:
                    raise RuntimeError("mcp server exited during handshake")
                continue
            chunk = os.read(self.proc.stdout.fileno(), 65536)
            if not chunk:
                raise EOFError("mcp stdout closed")
            buf += chunk
        line, _, rest = buf.partition(b"\n")
        self._buf = rest
        return json.loads(line.decode("utf-8"))

    def request(self, method: str, params: dict) -> dict:
        self._n += 1
        self._send({"jsonrpc": "2.0", "id": self._n, "method": method, "params": params})
        return self._recv()

    def notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def call(self, name: str, arguments: dict | None = None) -> dict:
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})


def _tool_text(response: dict) -> str:
    result = response.get("result") or {}
    content = result.get("content") or []
    return "\n".join(item.get("text", "") for item in content)


def _error_code(response: dict) -> str | None:
    text = _tool_text(response)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    return (payload.get("error") or {}).get("code")


def _snapshot(root: Path) -> dict:
    base = root / ".waybook"
    found = {}
    for path in sorted(base.rglob("*")):
        if path.is_file():
            found[str(path.relative_to(base))] = path.read_bytes()
    return found


def _fake_gh(directory: Path) -> None:
    script = directory / "gh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, sys\n"
        "args = sys.argv[1:]\n"
        "if len(args) >= 3 and args[0] == 'pr' and args[1] == 'view':\n"
        "    states = json.loads(os.environ.get('WAYBOOK_FAKE_PRS', '{}'))\n"
        "    number = args[2]\n"
        "    if number not in states:\n"
        "        sys.stderr.write('missing\\n')\n"
        "        sys.exit(1)\n"
        "    json.dump({'state': states[number]}, sys.stdout)\n"
        "    sys.exit(0)\n"
        "sys.stderr.write('unsupported\\n')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_01_append_only(self):
        project = self.root / "proj"
        project.mkdir()
        init(project)
        args = [
            "add",
            "decisions",
            "--title",
            "Flat files",
            "--one-liner",
            "No DB",
            "--link",
            "pr:97",
        ]
        first = run(args, project)
        self.assertEqual(first.returncode, 0, first.stderr)
        entry_id = first.stdout.strip().split()[-1]
        second = run(args, project)
        self.assertEqual(second.returncode, 7, second.stderr)
        self.assertIn("immutable except via mark-resolved", second.stderr)
        self.assertIn(entry_id, second.stderr)

        client = McpClient(project, agent="local")
        try:
            response = client.call(
                "board_add",
                {
                    "section": "decisions",
                    "title": "Flat files",
                    "one_liner": "No DB",
                    "links": ["pr:97"],
                },
            )
        finally:
            client.close()
        self.assertTrue(response["result"]["isError"])
        self.assertEqual(_error_code(response), "E_APPEND_ONLY")

        checked = run(["verify"], project)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        path = next((project / ".waybook" / "board").rglob("*.md"))
        path.chmod(0o644)
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace("No DB", "No DB hand edit"), encoding="utf-8")
        broken = run(["verify"], project)
        self.assertEqual(broken.returncode, 11, broken.stderr)
        self.assertIn("Hash chain broken", broken.stderr)
        self.assertIn(entry_id, broken.stderr)

    def test_02_schema_validation(self):
        project = self.root / "proj"
        project.mkdir()
        init(project)
        bad_section = run(
            ["add", "notes", "--title", "T", "--one-liner", "L"],
            project,
        )
        self.assertEqual(bad_section.returncode, 4, bad_section.stderr)
        self.assertIn("schema v2: section", bad_section.stderr)
        # A missing argument is a usage error, checked before the schema.
        missing = run(["add", "decisions", "--title", "Only a title"], project)
        self.assertEqual(missing.returncode, 2, missing.stderr)
        self.assertIn("one_liner is required", missing.stderr)
        self.assertEqual(list((project / ".waybook" / "board").rglob("*.md")), [])

    def test_03_schema_migration(self):
        project = self.root / "v1proj"
        shutil.copytree(FIXTURES / "v1", project)
        refused = run(
            ["add", "decisions", "--title", "New", "--one-liner", "Blocked"],
            project,
            now="2026-02-01T00:00:00Z",
        )
        self.assertEqual(refused.returncode, 5, refused.stderr)
        self.assertIn("schema v1", refused.stderr)
        self.assertIn("tool supports v2", refused.stderr)
        self.assertIn("waybook migrate", refused.stderr)
        listed = run(["list"], project)
        self.assertEqual(listed.returncode, 0, listed.stderr)
        self.assertIn("Keep the ledger flat", listed.stdout)
        shown = run(["show", _entry_id(project)], project)
        self.assertEqual(shown.returncode, 0, shown.stderr)
        migrated = run(["migrate"], project, now="2026-02-01T00:00:00Z")
        self.assertEqual(migrated.returncode, 0, migrated.stderr)
        note = (project / ".waybook" / "MIGRATIONS.md").read_text(encoding="utf-8")
        self.assertIn("v1 -> v2", note)
        self.assertIn("Reversible?", note)
        checked = run(["verify"], project)
        self.assertEqual(checked.returncode, 0, checked.stderr)
        added = run(
            ["add", "open-threads", "--title", "After migrate", "--one-liner", "Writes work"],
            project,
            now="2026-02-01T00:00:00Z",
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        v2 = self.root / "v2proj"
        shutil.copytree(FIXTURES / "v2", v2)
        v2_ok = run(["verify"], v2)
        self.assertEqual(v2_ok.returncode, 0, v2_ok.stderr)

    def test_04_prune_by_resolution(self):
        project = self.root / "proj"
        project.mkdir()
        bindir = self.root / "bin"
        bindir.mkdir()
        _fake_gh(bindir)
        init(project, project_id="demo")
        old = "2026-06-01T00:00:00Z"
        new = "2026-10-11T14:02:33Z"
        open_pr = run(
            [
                "add",
                "open-threads",
                "--title",
                "Old open PR",
                "--one-liner",
                "Still open",
                "--link",
                "pr:98",
            ],
            project,
            now=old,
            extra={"PATH": f"{bindir}:{os.environ.get('PATH', '')}", "WAYBOOK_FAKE_PRS": json.dumps({"97": "MERGED", "98": "OPEN"})},
        )
        self.assertEqual(open_pr.returncode, 0, open_pr.stderr)
        merged = run(
            [
                "add",
                "decisions",
                "--title",
                "Merged PR",
                "--one-liner",
                "Ship it",
                "--link",
                "pr:97",
            ],
            project,
            now=new,
            extra={"PATH": f"{bindir}:{os.environ.get('PATH', '')}", "WAYBOOK_FAKE_PRS": json.dumps({"97": "MERGED", "98": "OPEN"})},
        )
        self.assertEqual(merged.returncode, 0, merged.stderr)
        extra = {
            "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
            "WAYBOOK_FAKE_PRS": json.dumps({"97": "MERGED", "98": "OPEN"}),
        }
        before = _snapshot(project)
        dry = run(["prune", "--dry-run"], project, now=new, extra=extra)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn("would archive", dry.stdout)
        self.assertEqual(_snapshot(project), before)
        done = run(["prune"], project, now=new, extra=extra)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("archived", done.stdout)
        listed = run(["list"], project, now=new)
        self.assertIn("Old open PR", listed.stdout)
        self.assertNotIn("Merged PR", listed.stdout)
        offline = run(
            [
                "add",
                "decisions",
                "--title",
                "Unknown PR",
                "--one-liner",
                "Cannot look up",
                "--link",
                "pr:99",
            ],
            project,
            now=new,
            extra=extra,
        )
        self.assertEqual(offline.returncode, 0, offline.stderr)
        failed = run(["prune"], project, now=new, extra=extra)
        self.assertEqual(failed.returncode, 12, failed.stderr)
        self.assertIn("nothing pruned", failed.stderr)
        still = run(["list"], project, now=new)
        self.assertIn("Unknown PR", still.stdout)
        self.assertIn("Old open PR", still.stdout)

    def test_05_archive_listing(self):
        project = self.root / "proj"
        project.mkdir()
        init(project)
        added = run(
            ["add", "decisions", "--title", "Done work", "--one-liner", "Finished"],
            project,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        entry_id = added.stdout.strip().split()[-1]
        resolved = run(["mark-resolved", entry_id, "--resolution", "explicit"], project)
        self.assertEqual(resolved.returncode, 0, resolved.stderr)
        pruned = run(["prune"], project)
        self.assertEqual(pruned.returncode, 0, pruned.stderr)
        active = run(["list"], project)
        self.assertNotIn(entry_id, active.stdout)
        archived = run(["list", "--archived"], project)
        self.assertIn(entry_id, archived.stdout)
        files = list((project / ".waybook" / "archive").rglob("*.md"))
        self.assertEqual(len(files), 1)
        text = files[0].read_text(encoding="utf-8")
        self.assertIn("archived_at:", text)
        self.assertNotIn(str(files[0]), str(project / ".waybook" / "board"))
        self.assertFalse((project / ".waybook" / "board" / "decisions" / files[0].name).exists())

    def test_06_dormant_project(self):
        project = self.root / "proj"
        project.mkdir()
        bindir = self.root / "bin"
        bindir.mkdir()
        _fake_gh(bindir)
        init(project, now="2026-10-11T14:02:33Z")
        extra = {
            "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
            "WAYBOOK_FAKE_PRS": json.dumps({"97": "MERGED"}),
        }
        old = run(
            [
                "add",
                "open-threads",
                "--title",
                "Ancient thread",
                "--one-liner",
                "Left open on purpose",
                "--link",
                "pr:97",
            ],
            project,
            now="2026-08-01T00:00:00Z",
            extra=extra,
        )
        self.assertEqual(old.returncode, 0, old.stderr)
        recent = run(
            ["add", "decisions", "--title", "Recent decision", "--one-liner", "Keeps the project warm"],
            project,
            now="2026-10-11T14:02:33Z",
        )
        self.assertEqual(recent.returncode, 0, recent.stderr)
        flagged = run(["list"], project, now="2026-10-11T14:02:33Z")
        self.assertIn("[stale]", flagged.stdout)
        self.assertIn("Ancient thread", flagged.stdout)
        config = project / ".waybook" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                "project_active = true", "project_active = false"
            ),
            encoding="utf-8",
        )
        quiet = run(["list"], project, now="2026-10-11T14:02:33Z")
        self.assertNotIn("[stale]", quiet.stdout)
        self.assertIn("Ancient thread", quiet.stdout)
        pruned = run(["prune"], project, now="2026-10-11T14:02:33Z", extra=extra)
        self.assertEqual(pruned.returncode, 0, pruned.stderr)
        remain = run(["list"], project, now="2026-10-11T14:02:33Z")
        self.assertIn("Ancient thread", remain.stdout)
        self.assertNotIn("[stale]", remain.stdout)
        self.assertEqual(list((project / ".waybook" / "archive").rglob("*.md")), [])

    def test_07_hidden_score(self):
        project = self.root / "proj"
        project.mkdir()
        init(project)
        added = run(
            ["add", "decisions", "--title", "Score me", "--one-liner", "zebra token"],
            project,
        )
        self.assertEqual(added.returncode, 0, added.stderr)
        warmed = run(["warm-start", "--query", "zebra"], project)
        self.assertEqual(warmed.returncode, 0, warmed.stderr)
        stored = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (project / ".waybook" / "board").rglob("*.md")
        )
        self.assertIn("usefulness:", stored)
        outputs = [warmed.stdout, warmed.stderr]
        for args in (
            ["list"],
            ["list", "--json"],
            ["show", added.stdout.strip().split()[-1]],
            ["show", "--json", added.stdout.strip().split()[-1]],
        ):
            result = run(args, project)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
            outputs.append(result.stderr)
        client = McpClient(project)
        try:
            responses = [
                client.call("board_list"),
                client.call("board_show", {"id": added.stdout.strip().split()[-1]}),
                client.call("board_index"),
                client.call("board_warm_start", {"query": "zebra"}),
                client.call(
                    "board_add",
                    {
                        "section": "open-threads",
                        "title": "Another",
                        "one_liner": "no score here",
                    },
                ),
            ]
        finally:
            client.close()
        for response in responses:
            outputs.append(json.dumps(response))
        blob = "\n".join(outputs)
        self.assertNotIn("usefulness", blob)

    def test_08_cross_project_denied(self):
        coord = self.root / "coord"
        other = self.root / "other"
        coord.mkdir()
        other.mkdir()
        init(coord, project_id="coord", coordinator=True)
        init(other, project_id="other")
        run(
            ["add", "open-threads", "--title", "Secret thread", "--one-liner", "Stay home"],
            other,
        )
        denied = run(
            ["coordinator", "read", "other", "--reason", "Need the status before planning"],
            coord,
        )
        self.assertEqual(denied.returncode, 9, denied.stderr)
        self.assertIn("coordinator role", denied.stderr)
        self.assertNotIn("Secret thread", denied.stdout)
        audit_text = (coord / ".waybook" / "log" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertIn("E_ACCESS_DENIED", audit_text)
        self.assertIn("denied", audit_text)
        client = McpClient(coord, role="project")
        try:
            response = client.call(
                "coordinator_read",
                {"project_id": "other", "reason": "Need the status before planning"},
            )
        finally:
            client.close()
        self.assertEqual(_error_code(response), "E_ACCESS_DENIED")
        audit_text = (coord / ".waybook" / "log" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertGreaterEqual(audit_text.count("E_ACCESS_DENIED"), 2)

    def test_09_coordinator_reason_and_audit(self):
        coord = self.root / "coord"
        other = self.root / "other"
        coord.mkdir()
        other.mkdir()
        init(coord, project_id="coord", coordinator=True)
        init(other, project_id="other")
        added = run(
            ["add", "open-threads", "--title", "PR follow-up", "--one-liner", "Check the build"],
            other,
        )
        entry_id = added.stdout.strip().split()[-1]
        _append_route(coord, "other", other)
        missing = run(
            ["--role", "coordinator", "coordinator", "read", "other"],
            coord,
            extra={"WAYBOOK_AGENT": "coordinator/main"},
        )
        self.assertEqual(missing.returncode, 10, missing.stderr)
        self.assertIn("--reason is required", missing.stderr)
        target_audit = (other / ".waybook" / "log" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertNotIn("cross_read_notice", target_audit)
        reason = "Check PR 12 status before planning"
        allowed = run(
            [
                "--role",
                "coordinator",
                "--agent",
                "coordinator/main",
                "coordinator",
                "read",
                "other",
                "--reason",
                reason,
                "--section",
                "open-threads",
            ],
            coord,
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)
        self.assertIn(entry_id, allowed.stdout)
        self.assertNotIn("usefulness", allowed.stdout)
        coord_audit = (coord / ".waybook" / "log" / "audit.jsonl").read_text(encoding="utf-8")
        target_audit = (other / ".waybook" / "log" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertIn(reason, coord_audit)
        self.assertIn(reason, target_audit)
        self.assertIn(entry_id, coord_audit)
        self.assertIn(entry_id, target_audit)
        self.assertIn("cross_read_notice", target_audit)
        self.assertIn('"result":"ok"', coord_audit)
        client = McpClient(coord, role="coordinator", agent="coordinator/main")
        try:
            bad = client.call("coordinator_read", {"project_id": "other", "reason": "short"})
            good = client.call(
                "coordinator_read",
                {"project_id": "other", "reason": reason, "section": "open-threads"},
            )
        finally:
            client.close()
        self.assertEqual(_error_code(bad), "E_REASON_REQUIRED")
        self.assertFalse(good["result"]["isError"])
        self.assertNotIn("usefulness", _tool_text(good))
        self.assertIn(entry_id, _tool_text(good))

    def test_10_project_path_escape(self):
        first = self.root / "alpha"
        second = self.root / "beta"
        first.mkdir()
        second.mkdir()
        init(first, project_id="alpha")
        init(second, project_id="beta")
        run(
            ["add", "decisions", "--title", "Beta only", "--one-liner", "Not for alpha"],
            second,
        )
        escaped = run(["--project", str(second), "list"], first)
        self.assertEqual(escaped.returncode, 9, escaped.stderr)
        self.assertIn("coordinator role", escaped.stderr)
        self.assertNotIn("Beta only", escaped.stdout)
        audit_text = (first / ".waybook" / "log" / "audit.jsonl").read_text(encoding="utf-8")
        self.assertIn("E_ACCESS_DENIED", audit_text)
        self.assertIn("denied", audit_text)

    def test_11_warm_start_cap_and_query(self):
        project = self.root / "proj"
        project.mkdir()
        init(project)
        for number in range(45):
            result = run(
                [
                    "add",
                    "open-threads",
                    "--title",
                    f"Topic {number}",
                    "--one-liner",
                    f"note {number}",
                ],
                project,
                now=shift("2026-10-11T14:02:33Z", minutes=number),
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        body = project / "body.md"
        body.write_text("UNIQUEBODY\n", encoding="utf-8")
        matched = run(
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
            project,
            now="2026-10-11T16:00:00Z",
        )
        self.assertEqual(matched.returncode, 0, matched.stderr)
        other = project / "other.md"
        other.write_text("SHOULDNOTSHOW\n", encoding="utf-8")
        skipped = run(
            [
                "add",
                "failed-attempts",
                "--title",
                "Unrelated",
                "--one-liner",
                "nothing similar",
                "--body-file",
                str(other),
            ],
            project,
            now="2026-10-11T16:05:00Z",
        )
        self.assertEqual(skipped.returncode, 0, skipped.stderr)
        plain = run(["warm-start"], project, now="2026-10-11T16:05:00Z")
        self.assertEqual(plain.returncode, 0, plain.stderr)
        self.assertLessEqual(len(plain.stdout.splitlines()), 40)
        self.assertGreater(len(plain.stdout.splitlines()), 0)
        queried = run(
            ["warm-start", "--query", "zebra"],
            project,
            now="2026-10-11T16:05:00Z",
        )
        self.assertEqual(queried.returncode, 0, queried.stderr)
        self.assertIn("UNIQUEBODY", queried.stdout)
        self.assertNotIn("SHOULDNOTSHOW", queried.stdout)
        self.assertIn("## decisions", queried.stdout)
        self.assertNotIn("## failed-attempts", queried.stdout)
        index_part = []
        for line in queried.stdout.splitlines():
            if line.startswith("## "):
                break
            index_part.append(line)
        self.assertLessEqual(len(index_part), 40)
        config = project / ".waybook" / "config.toml"
        config.write_text(
            config.read_text(encoding="utf-8").replace(
                "project_active = true", "project_active = false"
            ),
            encoding="utf-8",
        )
        dormant = run(
            ["warm-start", "--query", "zebra"],
            project,
            now="2026-10-11T16:05:00Z",
        )
        self.assertEqual(dormant.returncode, 0, dormant.stderr)
        self.assertNotIn("UNIQUEBODY", dormant.stdout)
        self.assertNotIn("## decisions", dormant.stdout)
        self.assertLessEqual(len(dormant.stdout.splitlines()), 40)

    def test_12_flush_and_watchdog(self):
        project = self.root / "proj"
        project.mkdir()
        start = "2026-10-11T14:02:33Z"
        init(project, now=start)
        pending = project / ".waybook" / ".pending" / "notes.txt"
        pending.write_text("left off in the parser\n", encoding="utf-8")
        early = run(["watchdog", "--silence", "20m"], project, now=shift(start, minutes=5))
        self.assertEqual(early.returncode, 0, early.stderr)
        self.assertNotIn("notice", early.stdout)
        self.assertTrue(pending.exists())
        fired = run(["watchdog", "--silence", "20m"], project, now=shift(start, minutes=21))
        self.assertEqual(fired.returncode, 0, fired.stderr)
        self.assertIn("notice", fired.stdout)
        self.assertFalse(pending.exists())
        listed = run(["list", "--section", "open-threads"], project, now=shift(start, minutes=21))
        self.assertIn("Unfinished:", listed.stdout)
        again = run(["flush"], project, now=shift(start, minutes=21))
        self.assertEqual(again.returncode, 0, again.stderr)
        missing = run(["--project", str(self.root / "missing"), "flush"], project)
        self.assertEqual(missing.returncode, 0, missing.stderr)
        config = project / ".waybook" / "config.toml"
        config.write_text("this is not toml\n", encoding="utf-8")
        broken = run(["flush"], project)
        self.assertEqual(broken.returncode, 0, broken.stderr)
        hook = subprocess.run(
            ["sh", str(ROOT / "hooks" / "session-end")],
            cwd=self.root,
            env=_base_env(None),
            capture_output=True,
            text=True,
        )
        self.assertEqual(hook.returncode, 0, hook.stderr)

    def test_hooks_call_the_installed_entry_point(self):
        home = self.root / "hook-home"
        installed = home / ".local/bin/waybook"
        installed.parent.mkdir(parents=True)
        log = self.root / "hook-calls"
        recorder = "#!/bin/sh\nprintf '%s\\n' \"$@\" >> \"$WAYBOOK_CALL_LOG\"\nexit 0\n"
        installed.write_text(recorder, encoding="utf-8")
        installed.chmod(0o755)
        decoy_dir = self.root / "decoy-bin"
        decoy_dir.mkdir()
        decoy = decoy_dir / "waybook"
        decoy.write_text(
            "#!/bin/sh\nprintf '%s\\n' decoy >> \"$WAYBOOK_CALL_LOG\"\nexit 1\n",
            encoding="utf-8",
        )
        decoy.chmod(0o755)
        env = _base_env(None)
        env["HOME"] = str(home)
        env["PATH"] = str(decoy_dir) + os.pathsep + "/usr/bin:/bin"
        env["WAYBOOK_CALL_LOG"] = str(log)
        env["WAYBOOK_QUERY"] = "sqlite"
        env.pop("WAYBOOK_SILENCE", None)
        for name in ("session-start", "session-end", "watchdog"):
            text = (ROOT / "hooks" / name).read_text(encoding="utf-8")
            self.assertNotIn("python3", text)
            result = subprocess.run(
                ["sh", str(ROOT / "hooks" / name)],
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            log.read_text(encoding="utf-8").splitlines(),
            ["warm-start", "--query", "sqlite", "flush", "watchdog", "--silence", "20m"],
        )
        installed.unlink()
        decoy.write_text(recorder, encoding="utf-8")
        decoy.chmod(0o755)
        log.write_text("", encoding="utf-8")
        fallback = subprocess.run(
            ["sh", str(ROOT / "hooks" / "session-end")],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(fallback.returncode, 0, fallback.stderr)
        self.assertEqual(log.read_text(encoding="utf-8").splitlines(), ["flush"])

    def test_13_mcp_and_cli_same_bytes(self):
        stamp = "2026-10-11T14:02:33Z"
        agent = "agent-a"
        body = "Because flat files diff cleanly.\n"
        cli_root = self.root / "cli"
        mcp_root = self.root / "mcp"
        cli_root.mkdir()
        mcp_root.mkdir()
        init(cli_root, now=stamp, project_id="demo")
        init(mcp_root, now=stamp, project_id="demo")
        body_path = self.root / "body.md"
        body_path.write_text(body, encoding="utf-8")
        cli_add = run(
            [
                "--agent",
                agent,
                "add",
                "decisions",
                "--title",
                "Flat files",
                "--one-liner",
                "No DB",
                "--body-file",
                str(body_path),
                "--link",
                "pr:97",
                "--link",
                "commit:abc123",
            ],
            cli_root,
            now=stamp,
        )
        self.assertEqual(cli_add.returncode, 0, cli_add.stderr)
        client = McpClient(mcp_root, agent=agent, now=stamp)
        try:
            response = client.call(
                "board_add",
                {
                    "section": "decisions",
                    "title": "Flat files",
                    "one_liner": "No DB",
                    "body": body,
                    "links": ["pr:97", "commit:abc123"],
                },
            )
        finally:
            client.close()
        self.assertFalse(response["result"]["isError"], _tool_text(response))
        cli_file = next((cli_root / ".waybook" / "board").rglob("*.md")).read_bytes()
        mcp_file = next((mcp_root / ".waybook" / "board").rglob("*.md")).read_bytes()
        self.assertEqual(cli_file, mcp_file)
        cli_journal = (cli_root / ".waybook" / "log" / "writes.jsonl").read_bytes()
        mcp_journal = (mcp_root / ".waybook" / "log" / "writes.jsonl").read_bytes()
        self.assertEqual(cli_journal, mcp_journal)


def _entry_id(project: Path) -> str:
    text = next((project / ".waybook" / "board").rglob("*.md")).read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("id:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError("no id")


def _append_route(project: Path, project_id: str, path: Path) -> None:
    config = project / ".waybook" / "config.toml"
    with config.open("a", encoding="utf-8") as handle:
        handle.write("\n[[routes]]\n")
        handle.write(f'project_id = "{project_id}"\n')
        handle.write(f'path = "{path}"\n')


if __name__ == "__main__":
    unittest.main()
