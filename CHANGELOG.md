# Changelog

## Unreleased

The CLI and the MCP server now run every operation through one table (`waybook/operations.py`).

- MCP booleans (`archived`, `dry_run`, `read_only`) all take true/false, "true"/"false", "yes"/"no", "1"/"0" or 1/0. Anything else is `E_USAGE`. Before, `"false"` counted as true for `archived` and `dry_run`.
- A missing required argument is `E_USAGE` on both surfaces. For example, `add` without `--one-liner` used to be `E_SCHEMA_INVALID`, and `board_show` without `id` used to be `E_NOT_FOUND`.
- A link object that names a `repo` is rejected with `E_SCHEMA_INVALID`. Links always point at this project.
- `board_index` returns `{"index": ...}` and `board_warm_start` returns `{"text": ...}`, the same JSON as `index --json` and `warm-start --json`. Before, both returned bare text.
- An unexpected failure is `E_INTERNAL` (exit 1) on the CLI and in MCP. The MCP server keeps running, and skips a line that isn't JSON.
- `flush` with no agent records the entry as `local`. It is still titled `Unfinished: session`.
- The `board_add` schema documents the 20000-character body cap.

## 0.1.0 - 2026-10-13

First public cut of the local board.

- A per-project `.waybook/` directory of markdown entries in three sections: `decisions`, `open-threads`, and `failed-attempts`.
- Schema v2, with a migrator from v1. Each entry is written through the CLI, stored read-only (`0444`), and covered by a hash chain that `waybook verify` checks.
- Commands: `init`, `add`, `list`, `show`, `mark-resolved`, `prune`, `index`, `warm-start`, `verify`, `migrate`, `flush`, `watchdog`, and `mcp`. The MCP server uses the same write path as the CLI.
- `warm-start` prints a short index. In a git checkout it shows the live default-branch tip and flags an open entry that names a commit already behind that tip. `--read-only` prints the same text and writes nothing.
- `prune` archives by resolution: an entry you marked resolved, a linked pull request that is merged or closed, or a linked commit on the default branch. It does not archive by age.
- Session hooks for warm-start, a flush of notes left in `.pending/`, and a one-shot silence watchdog, plus a closeout skill.
- A coordinator role for an audited cross-project read.
- Writes refuse text that looks like a cloud key, a private-key header, or a common API token.
- A one-command installer. Python 3.11 or newer, with no third-party runtime dependencies. MIT license.
