"""The operations the CLI and the MCP server share.

Each operation names its arguments once: which are required, how a boolean
is read, and the default on each surface. Both front ends call run(), so an
argument means the same thing whichever way it arrives. The front ends keep
only their own parsing (argparse, JSON-RPC) and output (text, JSON).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from waybook import board, errors

SURFACES = ("cli", "mcp")
MISSING = object()


def agent_name(agent: str | None) -> str:
    """The name a write is recorded under. The one place "local" is filled in."""
    return agent or "local"


@dataclass(frozen=True)
class Context:
    root: Path
    role: str
    agent: str
    # Names the "Unfinished: <name>" entry a flush writes; "session" when no
    # agent was given. It is never the entry's source_agent.
    session_label: str

    @classmethod
    def build(cls, root: Path, role: str, agent: str | None) -> "Context":
        return cls(root, role, agent_name(agent), agent or "session")


def parse_bool(name: str, value: object) -> bool:
    """The one boolean parser. Missing is false.

    true/false, the strings true, 1, yes and false, 0, no (any case), and the
    integers 1 and 0 are accepted. Anything else is E_USAGE.
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
    raise errors.usage(f"{name} must be true or false")


@dataclass(frozen=True)
class Param:
    name: str
    kind: str = "str"  # "str", "bool" or "list"
    required: bool = False
    cli_default: Any = None
    mcp_default: Any = None

    def default_for(self, surface: str) -> Any:
        return self.cli_default if surface == "cli" else self.mcp_default

    def resolve(self, raw: object, surface: str) -> Any:
        if raw is MISSING or raw is None:
            if self.required:
                raise errors.usage(f"{self.name} is required")
            return self.default_for(surface)
        if self.kind == "bool":
            return parse_bool(self.name, raw)
        if self.kind == "str" and self.required and raw == "":
            raise errors.usage(f"{self.name} is required")
        return raw


@dataclass(frozen=True)
class Operation:
    name: str
    params: tuple[Param, ...]
    call: Callable[[Context, dict], Any]
    # Turns what call() returned into the JSON both surfaces send.
    payload: Callable[[Any, dict], dict]

    def param(self, name: str) -> Param:
        for param in self.params:
            if param.name == name:
                return param
        raise KeyError(name)


def _entries(entries, *, include_body: bool = True) -> dict:
    return {"entries": [board.to_public(entry, include_body=include_body) for entry in entries]}


OPERATIONS: dict[str, Operation] = {
    op.name: op
    for op in (
        Operation(
            "list",
            (Param("section"), Param("status"), Param("archived", "bool", cli_default=False, mcp_default=False)),
            lambda ctx, a: board.select_entries(ctx.root, a["section"], a["status"], a["archived"]),
            lambda entries, a: _entries(entries, include_body=False),
        ),
        Operation(
            "show",
            (Param("id", required=True),),
            lambda ctx, a: board.show_entry(ctx.root, a["id"]),
            lambda entry, a: board.to_public(entry),
        ),
        Operation(
            "index",
            (),
            lambda ctx, a: board.write_index(ctx.root),
            lambda text, a: {"index": text},
        ),
        Operation(
            "warm_start",
            (Param("query"), Param("read_only", "bool", cli_default=False, mcp_default=False)),
            lambda ctx, a: board.warm_start(ctx.root, a["query"], ctx.agent, read_only=a["read_only"]),
            lambda text, a: {"text": text},
        ),
        Operation(
            "add",
            (
                Param("section", required=True),
                Param("title", required=True),
                Param("one_liner", required=True),
                Param("body"),
                Param("links", "list", cli_default=[], mcp_default=[]),
                Param("supersedes"),
            ),
            lambda ctx, a: board.add_entry(
                ctx.root, a["section"], a["title"], a["one_liner"], a["body"], a["links"] or [],
                ctx.agent, supersedes=a["supersedes"],
            ),
            lambda entry, a: {"id": entry.id},
        ),
        Operation(
            "mark_resolved",
            (Param("id", required=True), Param("resolution", cli_default="explicit"), Param("note")),
            lambda ctx, a: board.mark_resolved(ctx.root, a["id"], a["resolution"], a["note"], ctx.agent),
            lambda entry, a: {"id": entry.id, "status": "resolved"},
        ),
        Operation(
            "prune",
            # The CLI archives unless told --dry-run; an MCP client has to ask
            # for a real prune with dry_run false.
            (Param("dry_run", "bool", cli_default=False, mcp_default=True),),
            lambda ctx, a: board.prune(ctx.root, a["dry_run"], ctx.agent),
            lambda plan, a: {
                "dry_run": a["dry_run"],
                "archive": [{"id": entry_id, "reason": reason} for entry_id, reason in plan],
            },
        ),
        Operation(
            "coordinator_read",
            # reason is checked by board.coordinator_read, which audits the
            # attempt and answers E_REASON_REQUIRED.
            (Param("project_id", required=True), Param("reason"), Param("section")),
            lambda ctx, a: board.coordinator_read(
                ctx.root, a["project_id"], a["reason"], a["section"], ctx.role, ctx.agent
            ),
            lambda entries, a: _entries(entries),
        ),
    )
}


def run(name: str, arguments: dict, ctx: Context, surface: str) -> tuple[Any, dict, dict]:
    """Runs one operation. Returns what it returned, its JSON payload, and the
    resolved arguments."""
    if surface not in SURFACES:
        raise ValueError(surface)
    op = OPERATIONS.get(name)
    if op is None:
        raise errors.usage(f"unknown operation {name}")
    if not isinstance(arguments, dict):
        raise errors.usage("arguments must be an object")
    resolved = {param.name: param.resolve(arguments.get(param.name, MISSING), surface) for param in op.params}
    value = op.call(ctx, resolved)
    return value, op.payload(value, resolved), resolved
