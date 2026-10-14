"""Command line for Waybook. Every write goes through waybook.board."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from waybook import BINARY_NAME, __version__, errors
from waybook.board import (
    add_entry,
    coordinator_read,
    flush,
    format_list,
    init_project,
    load_config_raw,
    locate,
    mark_resolved,
    migrate,
    prune,
    public_text,
    select_entries,
    show_entry,
    to_public,
    verify,
    warm_start,
    watchdog,
    write_index,
)
from waybook.mcp_server import serve


class Parser(argparse.ArgumentParser):
    def error(self, message: str):
        raise errors.usage(message)


def extract_globals(argv: list[str]):
    import os

    json_out = False
    project = None
    agent = os.environ.get("WAYBOOK_AGENT")
    role = os.environ.get("WAYBOOK_ROLE") or "project"
    rest: list[str] = []
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--json":
            json_out = True
        elif arg in ("--project", "--agent", "--role"):
            if index + 1 >= len(argv):
                raise errors.usage(f"{arg} needs a value")
            value = argv[index + 1]
            index += 1
            if arg == "--project":
                project = value
            elif arg == "--agent":
                agent = value
            else:
                role = value
        elif arg.startswith("--project="):
            project = arg.split("=", 1)[1]
        elif arg.startswith("--agent="):
            agent = arg.split("=", 1)[1]
        elif arg.startswith("--role="):
            role = arg.split("=", 1)[1]
        else:
            rest.append(arg)
        index += 1
    return json_out, project, agent, role, rest


def _parser() -> Parser:
    parser = Parser(prog=BINARY_NAME)
    commands = parser.add_subparsers(dest="cmd", required=True, parser_class=Parser)

    init = _sub(commands, "init")
    init.add_argument("--project-id", default=None)
    init.add_argument("--coordinator", action="store_true")

    add = _sub(commands, "add")
    add.add_argument("section")
    add.add_argument("--title", default=None)
    add.add_argument("--one-liner", default=None)
    add.add_argument("--body-file", default=None)
    add.add_argument("--link", action="append", default=[])
    add.add_argument("--supersedes", default=None)

    listing = _sub(commands, "list")
    listing.add_argument("--section", default=None)
    listing.add_argument("--status", default=None)
    listing.add_argument("--archived", action="store_true")

    show = _sub(commands, "show")
    show.add_argument("id")

    resolved = _sub(commands, "mark-resolved")
    resolved.add_argument("id")
    resolved.add_argument("--resolution", default="explicit")
    resolved.add_argument("--note", default=None)

    pruned = _sub(commands, "prune")
    pruned.add_argument("--dry-run", action="store_true")

    indexed = _sub(commands, "index")
    indexed.add_argument("--print", action="store_true")

    warm = _sub(commands, "warm-start")
    warm.add_argument("--query", default=None)
    warm.add_argument("--read-only", action="store_true")

    _sub(commands, "verify")

    migrated = _sub(commands, "migrate")
    migrated.add_argument("--to", type=int, default=None)

    coord = _sub(commands, "coordinator")
    coord_sub = coord.add_subparsers(dest="coordinator_cmd", required=True, parser_class=Parser)
    read = _sub(coord_sub, "read")
    read.add_argument("project_id")
    read.add_argument("--reason", default=None)
    read.add_argument("--section", default=None)

    _sub(commands, "flush")

    dog = _sub(commands, "watchdog")
    dog.add_argument("--silence", default=None)

    _sub(commands, "mcp")
    return parser


def _sub(parser, name: str) -> Parser:
    return parser.add_parser(name)


def _emit(payload, json_out: bool, human: str) -> None:
    if json_out:
        sys.stdout.write(json.dumps(payload, separators=(",", ":")) + "\n")
    else:
        sys.stdout.write(human)


def _project_active(root: Path) -> bool:
    return bool(load_config_raw(root).get("project_active", True))


def dispatch(rest: list[str], json_out: bool, project: str | None, agent: str | None, role: str) -> int:
    parser = _parser()
    args = parser.parse_args(rest)
    cwd = Path.cwd()
    if args.cmd == "flush":
        try:
            root = locate(cwd, project, role, agent or "")
            flush(root, agent or "session")
        except Exception:
            return 0
        return 0
    if args.cmd == "watchdog":
        try:
            root = locate(cwd, project, role, agent or "")
            fired = watchdog(root, args.silence, agent or "session")
        except Exception:
            return 0
        if fired:
            sys.stdout.write("notice: silence threshold exceeded; ran flush hook\n")
        return 0
    if args.cmd == "mcp":
        root = locate(cwd, project, role, agent or "")
        serve(root, role, agent or "local")
        return 0
    if args.cmd == "init":
        root = locate(cwd, project, role, agent or "", for_init=True)
        init_project(root, project_id=args.project_id, coordinator=args.coordinator)
        _emit({"result": "ok", "path": str(root)}, json_out, f"initialized {root}\n")
        return 0

    root = locate(cwd, project, role, agent or "")
    if args.cmd == "add":
        body = None
        if args.body_file:
            body = Path(args.body_file).read_text(encoding="utf-8")
        entry = add_entry(
            root,
            args.section,
            args.title,
            args.one_liner,
            body,
            args.link,
            agent or "local",
            supersedes=args.supersedes,
        )
        _emit({"id": entry.id}, json_out, f"added {entry.id}\n")
        return 0
    if args.cmd == "list":
        entries = select_entries(root, args.section, args.status, args.archived)
        payload = {
            "entries": [to_public(entry, include_body=False) for entry in entries]
        }
        _emit(payload, json_out, format_list(entries, _project_active(root)))
        return 0
    if args.cmd == "show":
        entry = show_entry(root, args.id)
        _emit(to_public(entry), json_out, public_text(entry))
        return 0
    if args.cmd == "mark-resolved":
        entry = mark_resolved(root, args.id, args.resolution, args.note, agent or "local")
        _emit({"id": entry.id, "status": "resolved"}, json_out, f"resolved {entry.id}\n")
        return 0
    if args.cmd == "prune":
        plan = prune(root, args.dry_run, agent or "local")
        if json_out:
            _emit(
                {
                    "dry_run": bool(args.dry_run),
                    "archive": [{"id": entry_id, "reason": reason} for entry_id, reason in plan],
                },
                True,
                "",
            )
        elif not plan:
            sys.stdout.write("nothing to archive\n")
        else:
            verb = "would archive" if args.dry_run else "archived"
            for entry_id, reason in plan:
                sys.stdout.write(f"{verb} {entry_id} ({reason})\n")
        return 0
    if args.cmd == "index":
        text = write_index(root)
        if args.print or json_out:
            if json_out:
                _emit({"index": text}, True, "")
            else:
                sys.stdout.write(text)
        else:
            sys.stdout.write("updated index\n")
        return 0
    if args.cmd == "warm-start":
        text = warm_start(root, args.query, agent or "local", read_only=args.read_only)
        if json_out:
            _emit({"text": text}, True, "")
        else:
            sys.stdout.write(text)
        return 0
    if args.cmd == "verify":
        verify(root)
        _emit({"result": "ok"}, json_out, "ok\n")
        return 0
    if args.cmd == "migrate":
        outcome = migrate(root, args.to, agent or "local")
        if outcome == "already":
            _emit({"result": "ok", "schema_version": 2}, json_out, "already schema v2\n")
        else:
            _emit({"result": "ok", "schema_version": 2}, json_out, "migrated to schema v2\n")
        return 0
    if args.cmd == "coordinator":
        entries = coordinator_read(
            root,
            args.project_id,
            args.reason,
            args.section,
            role,
            agent or "local",
        )
        payload = {"entries": [to_public(entry) for entry in entries]}
        _emit(payload, json_out, format_list(entries, True))
        return 0
    raise errors.usage(f"unknown command {args.cmd}")


def write_error(err: errors.WaybookError, json_out: bool) -> None:
    if json_out:
        payload = {"error": {"code": err.code, "message": err.message}}
        sys.stderr.write(json.dumps(payload, separators=(",", ":")) + "\n")
    else:
        sys.stderr.write(err.message + "\n")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--version" in argv:
        sys.stdout.write(__version__ + "\n")
        return 0
    json_out = False
    try:
        json_out, project, agent, role, rest = extract_globals(argv)
        return dispatch(rest, json_out, project, agent, role)
    except errors.WaybookError as err:
        write_error(err, json_out)
        return err.exit_code


if __name__ == "__main__":
    sys.exit(main())
