# Changelog

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
