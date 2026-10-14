"""Text installed into each board."""

MIGRATION_V1_TO_V2 = """## v1 -> v2

What changed: every entry gains a `supersedes` field (an entry id or null). `schema_version` becomes 2 on the entry and in `config.toml`. v1 boards have no `supersedes` key.

How to migrate: run `waybook migrate` (or `waybook migrate --to 2`). The migrator rewrites each entry to schema v2 with `supersedes: null` when the field is missing, appends a `migrate` line to `log/writes.jsonl`, and bumps `config.toml`.

Reversible? No. This tool does not downgrade a v2 board to v1.
"""

MIGRATIONS_MD = (
    "# Waybook schema migrations\n\n"
    "Schema v1 is the original entry format: frontmatter without `supersedes`.\n\n"
    + MIGRATION_V1_TO_V2
)

BOARD_README = """# Waybook board

This directory is the local board for one project.

Non-claims: it is not a memory of user preferences. It does not verify that an entry is true. It does not prove that selective loading is useful. The hidden usefulness number stored in each file is a heuristic, not a measurement. Version 1 commands never print it.

You may read files under `board/` directly. One file is one entry. Do not hand-edit them. `waybook verify` checks the write journal and fails if a file changed outside the CLI.

Writes go through the `waybook` command (`add`, `mark-resolved`, `prune`, `migrate`). To correct an entry, add a new one with `--supersedes <id>`.

Pending session notes dropped in `.pending/` are picked up by `waybook flush`.
"""

V1_MIGRATIONS_MD = """# Waybook schema migrations

Schema v1 is the original entry format: frontmatter without `supersedes`.
"""
