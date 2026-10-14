# Waybook schema migrations

Schema v1 is the original entry format: frontmatter without `supersedes`.

## v1 -> v2

What changed: every entry gains a `supersedes` field (an entry id or null). `schema_version` becomes 2 on the entry and in `config.toml`. v1 boards have no `supersedes` key.

How to migrate: run `waybook migrate` (or `waybook migrate --to 2`). The migrator rewrites each entry to schema v2 with `supersedes: null` when the field is missing, appends a `migrate` line to `log/writes.jsonl`, and bumps `config.toml`.

Reversible? No. This tool does not downgrade a v2 board to v1.
