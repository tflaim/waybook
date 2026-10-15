"""Minimal stdio MCP server. Write tools call waybook.board, same as the CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from waybook import MCP_SERVER_NAME, __version__, errors, operations
from waybook.board import BODY_MAX
from waybook.operations import Context

PROTOCOL = "2024-11-05"


def _tools() -> list[dict]:
    return [
        {
            "name": "board_list",
            "description": "List board entries. Hidden heuristic fields are omitted.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "status": {"type": "string"},
                    "archived": {"type": "boolean"},
                },
            },
        },
        {
            "name": "board_show",
            "description": "Show one entry without hidden heuristic fields.",
            "inputSchema": {
                "type": "object",
                "properties": {"id": {"type": "string"}},
                "required": ["id"],
            },
        },
        {
            "name": "board_index",
            "description": "Regenerate index.md and return the short warm-start index as {index}.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "board_warm_start",
            "description": (
                "Return the short index as {text}, expanding sections that match query. "
                "By default rewrites index.md and bumps usefulness for each match; read_only writes nothing."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "read_only": {"type": "boolean"},
                },
            },
        },
        {
            "name": "board_add",
            "description": "Append one entry. Uses the same validation as the CLI.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "title": {"type": "string"},
                    "one_liner": {"type": "string"},
                    "body": {
                        "type": "string",
                        "description": (
                            f"Free markdown. Up to {BODY_MAX} characters are stored; a longer body is "
                            "truncated and ends with a [truncated: omitted N characters] line."
                        ),
                    },
                    "links": {
                        "type": "array",
                        "description": (
                            "commit:<sha> or pr:<number> strings, or {type, ref} objects. "
                            "Links always point at this project; an object with repo is rejected."
                        ),
                    },
                    "supersedes": {"type": "string"},
                },
                "required": ["section", "title", "one_liner"],
            },
        },
        {
            "name": "board_mark_resolved",
            "description": "Resolve an entry. Uses the same validation as the CLI.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "resolution": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["id"],
            },
        },
        {
            "name": "board_prune",
            "description": "Archive resolved entries. dry_run defaults to true.",
            "inputSchema": {
                "type": "object",
                "properties": {"dry_run": {"type": "boolean"}},
            },
        },
        {
            "name": "coordinator_read",
            "description": "Coordinator-only cross-project read. reason is required.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "project_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "section": {"type": "string"},
                },
                "required": ["project_id", "reason"],
            },
        },
    ]


def _ok(text: str) -> dict:
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _fail(err: errors.WaybookError) -> dict:
    payload = {"error": {"code": err.code, "message": err.message}}
    return {
        "content": [{"type": "text", "text": json.dumps(payload, separators=(",", ":"))}],
        "isError": True,
    }


# MCP tool name -> shared operation.
TOOLS = {
    "board_list": "list",
    "board_show": "show",
    "board_index": "index",
    "board_warm_start": "warm_start",
    "board_add": "add",
    "board_mark_resolved": "mark_resolved",
    "board_prune": "prune",
    "coordinator_read": "coordinator_read",
}


def parse_read_only(value: object) -> bool:
    """Kept for callers of the old name; every MCP boolean uses parse_bool."""
    return operations.parse_bool("read_only", value)


def _call(name: str, args: dict, ctx: Context):
    operation = TOOLS.get(name)
    if operation is None:
        raise errors.usage(f"unknown tool {name}")
    _, payload, _ = operations.run(operation, args, ctx, "mcp")
    return _ok(json.dumps(payload, separators=(",", ":")))


def handle(message: dict, root: Path, role: str, agent: str | None) -> dict | None:
    if not isinstance(message, dict) or "id" not in message:
        return None
    method = message.get("method")
    msg_id = message["id"]
    params = message.get("params") or {}
    if method == "initialize":
        version = params.get("protocolVersion") or PROTOCOL
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": version,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": MCP_SERVER_NAME, "version": __version__},
            },
        }
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": _tools()}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if method == "tools/call":
        try:
            ctx = Context.build(root, role, agent)
            result = _call(params.get("name") or "", params.get("arguments") or {}, ctx)
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except errors.WaybookError as err:
            return {"jsonrpc": "2.0", "id": msg_id, "result": _fail(err)}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": msg_id, "result": _fail(errors.internal(exc))}
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _read_message(stream) -> dict | None:
    """The next JSON message. A line that isn't JSON is skipped."""
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if not line.strip():
            continue
        try:
            return json.loads(line.decode("utf-8"))
        except ValueError:
            continue


def _write_message(stream, payload: dict) -> None:
    data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    if b"\n" in data or b"\r" in data:
        raise ValueError("json-rpc message must be one line")
    blob = data + b"\n"
    fd = stream.fileno()
    view = memoryview(blob)
    while view:
        written = os.write(fd, view)
        view = view[written:]


def serve(root: Path, role: str, agent: str | None) -> None:
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        message = _read_message(stdin)
        if message is None:
            return
        try:
            response = handle(message, root, role, agent)
        except Exception:
            # Keep serving: one bad request must not end the session.
            msg_id = message.get("id") if isinstance(message, dict) else None
            response = None if msg_id is None else {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32603, "message": "Internal error"},
            }
        if response is not None:
            _write_message(stdout, response)
