"""Minimal stdio MCP server. Write tools call waybook.board, same as the CLI."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from waybook import MCP_SERVER_NAME, __version__, errors
from waybook.board import (
    add_entry,
    coordinator_read,
    mark_resolved,
    prune,
    to_public,
    warm_start,
    write_index,
    show_entry,
    select_entries,
)

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
            "description": "Return the short warm-start index.",
            "inputSchema": {"type": "object", "properties": {}},
        },
        {
            "name": "board_warm_start",
            "description": "Return the short index, expanding sections that match query. read_only writes nothing.",
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
                    "body": {"type": "string"},
                    "links": {"type": "array"},
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


def parse_read_only(value: object) -> bool:
    """Boolean read_only flag. The strings false, 0, and no are false.

    Missing means false. true, 1, and yes are true. Any other value is rejected.
    """
    if value is None or value is False:
        return False
    if value is True:
        return True
    if isinstance(value, str):
        token = value.strip().lower()
        if token in {"false", "0", "no"}:
            return False
        if token in {"true", "1", "yes"}:
            return True
    if isinstance(value, int) and not isinstance(value, bool):
        if value == 0:
            return False
        if value == 1:
            return True
    raise errors.usage("read_only must be true or false")


def _call(name: str, args: dict, root: Path, role: str, agent: str):
    if name == "board_list":
        entries = select_entries(
            root,
            args.get("section"),
            args.get("status"),
            bool(args.get("archived", False)),
        )
        payload = {"entries": [to_public(entry, include_body=False) for entry in entries]}
        return _ok(json.dumps(payload, separators=(",", ":")))
    if name == "board_show":
        entry = show_entry(root, args.get("id") or "")
        return _ok(json.dumps(to_public(entry), separators=(",", ":")))
    if name == "board_index":
        return _ok(write_index(root))
    if name == "board_warm_start":
        return _ok(
            warm_start(
                root,
                args.get("query"),
                agent,
                read_only=parse_read_only(args.get("read_only", False)),
            )
        )
    if name == "board_add":
        entry = add_entry(
            root,
            args.get("section") or "",
            args.get("title"),
            args.get("one_liner"),
            args.get("body"),
            args.get("links") or [],
            agent,
            supersedes=args.get("supersedes"),
        )
        return _ok(json.dumps({"id": entry.id}, separators=(",", ":")))
    if name == "board_mark_resolved":
        entry = mark_resolved(
            root,
            args.get("id") or "",
            args.get("resolution"),
            args.get("note"),
            agent,
        )
        return _ok(json.dumps({"id": entry.id, "status": "resolved"}, separators=(",", ":")))
    if name == "board_prune":
        dry_run = True if "dry_run" not in args else bool(args.get("dry_run"))
        plan = prune(root, dry_run, agent)
        payload = {
            "dry_run": dry_run,
            "archive": [{"id": entry_id, "reason": reason} for entry_id, reason in plan],
        }
        return _ok(json.dumps(payload, separators=(",", ":")))
    if name == "coordinator_read":
        entries = coordinator_read(
            root,
            args.get("project_id") or "",
            args.get("reason"),
            args.get("section"),
            role,
            agent,
        )
        payload = {"entries": [to_public(entry) for entry in entries]}
        return _ok(json.dumps(payload, separators=(",", ":")))
    raise errors.usage(f"unknown tool {name}")


def handle(message: dict, root: Path, role: str, agent: str) -> dict | None:
    if "id" not in message:
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
            result = _call(params.get("name") or "", params.get("arguments") or {}, root, role, agent)
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except errors.WaybookError as err:
            return {"jsonrpc": "2.0", "id": msg_id, "result": _fail(err)}
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _read_message(stream) -> dict | None:
    while True:
        line = stream.readline()
        if line == b"":
            return None
        if not line.strip():
            continue
        return json.loads(line.decode("utf-8"))


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


def serve(root: Path, role: str, agent: str) -> None:
    stdin = sys.stdin.buffer
    stdout = sys.stdout.buffer
    while True:
        message = _read_message(stdin)
        if message is None:
            return
        response = handle(message, root, role, agent)
        if response is not None:
            _write_message(stdout, response)
