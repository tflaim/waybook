# Waybook: build spec (V1)

The binary and the MCP server share one name, `waybook`. Keep Waybook distinct from any other agent ledger: separate repo, store, schema, and CLI. A later bridge (attestations from another ledger referenced from a Waybook entry's `links`) is possible but out of scope.

## Build rules (read first)
- The repository may be published. **Do not create it as part of this spec task.**
- Use short, descriptive branch names.
- No tool attribution footers and no `Co-authored-by` trailers in commits, PR bodies, code or docs.
- **No global store.** Nothing under `~`, `/etc`, or a shared dir is read or written by default.
- V1 is single-operator and local. No network service, no accounts.

## 1. Purpose and non-claims
A per-project board where agent sessions record **decisions**, **open threads** and **failed attempts**, so the next session starts warm. Non-claims: it is not a memory of user preferences; it does not verify that an entry is true; it does not prove usefulness of selective loading (see section 12); the hidden score is a heuristic, not a measurement.

## 2. Locked decisions (encoded)
1. Versioned markdown schema from day one: `schema_version` field; every bump ships a migration note and a migrator.
2. Sections: `decisions`, `open-threads`, `failed-attempts`. Each entry: timestamp, source agent, linked commit/PR, and a **hidden** `usefulness` score. V1 output (CLI text, JSON, MCP) never shows it.
3. Per-project install by default; no global store. A root-folder board (one board above several project folders) is possible but **not recommended**: it mixes projects' entries, breaks the only-own-project visibility rule (5), makes `project` ambiguous for links to commits/PRs, and lets one noisy project crowd the cold-start index. If used, it is just a project whose root is the parent folder; no special code.
4. Writes are CLI-only: `add`, `mark-resolved`, plus `list`, `show` (and `prune`, `init`, `migrate`, `index`). The CLI enforces schema and append-only semantics. Direct read-only file access is allowed (files are `0444`-style by convention; the validator flags hand edits).
5. A project agent sees only its own project's board. Cross-project read is coordinator-only, explicitly routed, and audit-logged with what was read/changed and why.
6. Pruning is by resolution (linked commit/PR merged or closed, or explicit resolve), never by age. Pruned entries move to the archive. `last_useful_at` is paired with a `project_active` flag so dormant projects are not pruned by neglect.
7. Cold start: auto-load a short index (titles, statuses, one-liners); expand sections on match; deprioritize by project rhythm.
8. Closeout: a skill for clean closeout, a hook for best-effort partial flush on session death, a watchdog that fires after a silence threshold.
9. V1 single-operator, local. Multiplayer approvals and visible scoring are V2.
10. Later, not V1: MemoType ideas (section 12).

## 3. Directory layout
```
<project>/.waybook/
  config.toml            # schema_version, project_id, project_active, coordinator settings, silence_threshold
  board/
    decisions/        2026-10-11T14-02-33Z_a1b2c3.md   # one file per entry
    open-threads/     ...
    failed-attempts/  ...
  index.md               # generated short index (titles, status, one-liners)
  archive/               # pruned entries, same file format, + archived_at, archive_reason
  log/audit.jsonl        # audit log (section 8)
  log/writes.jsonl       # append-only write journal (hash chain)
  MIGRATIONS.md          # migration note per schema version
  README.md              # non-claims + how to read files directly
```
Coordinator-level config lives in the coordinator project's own `.waybook/config.toml` (`coordinator = true`, `routes = [{project_id, path}]`). Never a global file.

## 4. Entry format
```markdown
---
schema_version: 2
id: dec-20261011-a1b2c3
section: decisions            # decisions | open-threads | failed-attempts
title: Use SQLite-free flat files for the ledger
one_liner: Flat markdown, one file per entry, no DB, so humans can read it.
status: open                  # open | resolved   (failed-attempts: recorded | resolved)
created_at: 2026-10-11T14:02:33Z
source_agent: agent/session-8f3a
links:
  - {type: commit, repo: example-org/example-app, ref: 3fa91c2}
  - {type: pr, repo: example-org/example-app, ref: 12}
resolved_at: null
resolution: null              # merged | closed | explicit
last_useful_at: null
usefulness: 0.0               # HIDDEN in V1 output; 0..1; updated by CLI only
---
Body: free markdown. Up to 20000 characters are stored. A longer body is truncated automatically (there is no `--truncate` flag) and ends with a pointer line (`[truncated: omitted N characters]`). The cut backs up to the last newline before the cap when one fits, and an open triple-backtick fence is closed. Why, alternatives, what to check first. There is no cap on the number of links. A link is given as `commit:<sha>` or `pr:<number>` (MCP also takes a `{type, ref}` object) and is stored with this project's id as `repo`. A link can't name another repo: an object with `repo` is rejected E_SCHEMA_INVALID.
```
Append-only semantics: an entry file is never rewritten except through `mark-resolved` (sets `status`, `resolved_at`, `resolution`) and internal `usefulness`/`last_useful_at` bumps. Every mutation appends a line to `writes.jsonl` (`{ts, op, id, prev_hash, hash, digest, content_root}`). `hash` chains the previous hash with `ts`, `op`, `id`, and `digest`. `digest` is the sha256 of the entry file. `content_root` on the latest line is the sha256 of the sorted `id digest` lines for every entry file on the board or in the archive. `waybook verify` recomputes the chain, compares digests to those files, and fails if the tip `content_root` does not match. Corrections are new entries with `supersedes: <id>`.

## 5. CLI
Global flags: `--json`, `--project <path>` (default: nearest ancestor with `.waybook/`), `--agent <name>` (or env `WAYBOOK_AGENT`).

| Command | Purpose |
|---|---|
| `init` | create `.waybook/`, config, README |
| `add <section> --title --one-liner [--body-file] [--link commit:SHA\|pr:N]...` | append an entry |
| `list [--section] [--status] [--json]` | list entries (no score) |
| `show <id>` | full entry (no score) |
| `mark-resolved <id> [--resolution explicit] [--note]` | resolve an entry |
| `prune [--dry-run]` | archive entries whose linked commit/PR is merged/closed or that are resolved |
| `index` | regenerate `index.md`; `index --print` emits the warm-start text |
| `warm-start [--query TEXT] [--read-only]` | print the short index + expanded matching sections. Default rewrites `index.md` and bumps usefulness for each expanded match. `--read-only` writes nothing |
| `verify` | schema + hash-chain check |
| `migrate [--to N]` | run migrations, write a migration-note entry check |
| `coordinator read <project_id> --reason TEXT` | cross-project read (coordinator role only) |

Example:
```
$ waybook list --section open-threads
ID                   STATUS  CREATED               TITLE
thr-20261011-9e41d0  open    2026-10-11T14:20Z     PRs #12 #13 never compiled
$ waybook add decisions --title "Flat files" --one-liner "No DB" --link pr:12
added dec-20261011-a1b2c3
$ echo $?
0
```
Exit codes (stderr human message; with `--json`, stderr is `{"error":{"code":"E_...","message":"..."}}`):

| Exit | Code | Human message |
|---|---|---|
| 0 | OK | - |
| 2 | E_USAGE | Bad arguments: <detail> |
| 3 | E_NOT_INITIALIZED | No .waybook/ found; run `waybook init` |
| 4 | E_SCHEMA_INVALID | Entry fails schema v<N>: <field> |
| 5 | E_SCHEMA_VERSION | Board is schema v<A>, tool supports v<B>; run `waybook migrate` |
| 6 | E_NOT_FOUND | No entry with id <id> |
| 7 | E_APPEND_ONLY | Entry <id> is immutable except via mark-resolved |
| 8 | E_ALREADY_RESOLVED | Entry <id> already resolved |
| 9 | E_ACCESS_DENIED | Cross-project read requires the coordinator role |
| 10 | E_REASON_REQUIRED | `--reason` is required for cross-project access |
| 11 | E_INTEGRITY | Hash chain broken at <id>; board modified outside the CLI |
| 12 | E_LINK_LOOKUP | Could not check PR/commit state (offline or no auth); nothing pruned |
| 13 | E_SECRET | Refused write: secret pattern <class> |
| 1 | E_INTERNAL | Internal error: <exception type> (any unexpected failure; the MCP server keeps running) |

## 6. MCP wrapper
Thin stdio server; **every write tool shells to / imports the same validation as the CLI** (no second code path). Responses never contain `usefulness`.
- Read: `board_list`, `board_show`, `board_index` (regenerates `index.md`, returns `{index}`), `board_warm_start(query, read_only?)` (returns `{text}`). These are the same JSON shapes as `index --json` and `warm-start --json`.
- Write: `board_add` (body up to 20000 characters, longer is truncated), `board_mark_resolved`, `board_prune` (dry_run default true; the CLI's `prune` defaults to a real prune).
- Arguments: a missing required argument is E_USAGE. Every boolean takes true/false, "true"/"false", "yes"/"no", "1"/"0" or 1/0; anything else is E_USAGE.
- Coordinator: `coordinator_read(project_id, reason, section?)`. `reason` is a required non-empty string (min 10 chars). Role comes from the server's launch config (`--role coordinator`), not from tool arguments. Every call appends to the **coordinator's** audit log and a notice line to the target project's audit log.
- Errors return the same `code` + `message` as the CLI.

## 7. Pruning, archive, project rhythm
- Prune candidates: entry `resolved`, or any linked PR `merged`/`closed` (looked up via `gh`; commit links count as resolved only if reachable from the default branch). The default branch is `origin/HEAD`, else `main`, else `master`. `HEAD` alone is not a default branch. Age is never a criterion.
- One failed lookup does not cancel the others. Entries that are resolved, or whose links have a known state, are archived. If a lookup failed and nothing was archived, prune exits `E_LINK_LOOKUP` and writes nothing (`nothing pruned`). If a lookup failed after some entries were archived, prune still exits `E_LINK_LOOKUP` (`entries with a known state were still archived`).
- `prune` moves files to `archive/` (adds `archived_at`, `archive_reason`), appends to `writes.jsonl`, regenerates the index. Archive is readable (`list --archived`), never auto-deleted.
- `last_useful_at` updates when an entry is expanded by warm-start on a match, unless `--read-only` is set. `project_active` (config, set by hand; reads do not change it) gates any "stale" hint: dormant projects get no stale flags and no auto-prune of unresolved entries.
- Rhythm: warm-start orders and trims index lines by project activity (recent writes/commits first); dormant projects load the index only.

## 8. Cold start, closeout, audit log
- **Cold start**: a session-start hook runs `waybook warm-start`. Output is the index only (title, status, one-liner, ~150 chars/line, cap ~40 lines), plus expanded sections for entries matching `--query` (title/one-liner keyword match in V1).
- **Closeout skill**: instructs the agent to add decisions, open threads, failed attempts with links, then `mark-resolved` what finished and run `verify`.
- **Flush hook**: on session end/death, best-effort: writes one `open-threads` entry titled "Unfinished: <session>" from whatever pending notes exist in `.waybook/.pending/` (agents drop notes there during work). Must never block or exit nonzero.
- **Watchdog**: `waybook watchdog --silence 20m` fires when no CLI write or heartbeat touches `.waybook/.heartbeat` for the threshold; action = run the flush hook once and print a notice. Single local process, no daemon install in V1.
- **Audit log** (`log/audit.jsonl`, append-only, one JSON per line):
```json
{"ts":"2026-10-11T15:00:00Z","actor":"coordinator/main","role":"coordinator","op":"cross_read","target_project":"example-app","sections":["open-threads"],"entry_ids":["thr-20261011-9e41d0"],"reason":"Check PR #12 status before planning","changed":false,"result":"ok"}
```
Fields for any op that changes state: `op`, `entry_ids`, `changed` (true), `changes` (short summary), `reason` (required for cross-project ops, optional otherwise). Denials are logged too (`result:"denied"`, code E_ACCESS_DENIED).

## 9. Schema versioning
`schema_version` in config and every entry. A bump requires: a `MIGRATIONS.md` section ("v1 -> v2: what changed, how to migrate, reversible?"), a migrator function, a fixture board for each version. Tool refuses writes to an older board (E_SCHEMA_VERSION) until `migrate`; reads of older versions work read-only.

## 10. Acceptance tests
1. Append-only enforced: editing an entry via the CLI/MCP fails E_APPEND_ONLY; a hand edit makes `verify` fail E_INTEGRITY.
2. Schema validation: bad section or field rejected E_SCHEMA_INVALID; a missing required argument fails E_USAGE (CLI and MCP).
3. Schema version migration: v1 fixture -> `migrate` -> v2 passes verify; migration note exists; old board refuses writes before migrating.
4. Prune by resolution: entry with merged PR is archived; entry with open PR and old timestamp is NOT; dry-run changes nothing.
5. Archive: pruned entry present in `archive/` with `archived_at`, absent from `list`, appears in `list --archived`.
6. Dormant project: `project_active=false` and unresolved entries are never pruned or flagged stale.
7. Hidden score: absent from CLI text, `--json` and every MCP response.
8. Cross-project access denied without coordinator role (CLI and MCP), and the denial is logged.
9. Coordinator read without `--reason` fails E_REASON_REQUIRED; with reason, audit line written in both projects.
10. Project agent cannot read another project's board via `--project` path escape.
11. Warm-start output stays under the line cap; a query expands only matching sections.
12. Flush hook never exits nonzero; watchdog fires after threshold (fake clock).
13. MCP write tools and CLI produce byte-identical files for identical input.

## 11. Milestones
- M0: repo + CI skeleton, schema v1, `init`, `add`, `list`, `show`, `verify` (tests 1, 2, 7).
- M1: `mark-resolved`, `prune`, archive, `project_active` (4-6).
- M2: `warm-start`/`index`, closeout skill, flush hook, watchdog (11, 12).
- M3: MCP wrapper, coordinator role + audit log (8-10, 13).
- M4: `migrate` with a real v1->v2 dry run; docs, non-claims README.

## 12. Later, not V1: MemoType ideas
From arXiv 2610.11573: learned memory-type router, hypothetical queries, rank fusion, relevance judge. Note: the paper only **weakly** supports typed selective loading, and it studies chat-dialogue memory, not agent experience memory. Treat as hypotheses to test on our own boards. V1 uses plain keyword match.

## 13. Open questions (visible)
1. Implementation language/runtime (Python vs Swift vs Node)? Suggest Python 3.11+, stdlib only for the CLI; confirm.
2. Which agent hosts get the hook/skill/watchdog (Cursor, Claude Code, Hermes)? Hook APIs differ.
3. Who defines the coordinator role locally? In V1 it is a launch flag, not a security boundary; is that enough?
4. How is the hidden score computed in V1 (expansion count? manual?) and when does it become visible (V2)?
5. PR/commit state lookup needs `gh` auth; behavior offline is "prune nothing" (E_LINK_LOOKUP). Acceptable?
6. Should `.waybook/` be committed to git or ignored? Committing leaks nothing outward only if the repo is private.
7. Entry size cap and secret hygiene: should `add` scan for secrets?
8. Does a bridge to another ledger need reserved fields now (e.g. `external_refs`)?
