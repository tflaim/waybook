# Resolve and verify

Resolve and verify lets a user mark an entry resolved, check the board hash chain, and see that prune would archive resolved entries.

## Sub-features

- `mark-resolved` sets status to resolved and prints `resolved <id>`.
- `verify-ok` reports `ok` on an intact board.
- `verify-integrity` fails after a hand edit of an entry file (`E_INTEGRITY`).
- `prune-dry-run` lists resolved entries as `would archive` without moving files.

## How to get to it (user POV)

- Run `waybook mark-resolved <id> --resolution explicit`.
- Run `waybook verify`.
- Run `waybook prune --dry-run`.

## Driving it with control-waybook

Preconditions:

- `control-waybook launch --run-id resolve-verify --seed` completed.
- `export WAYBOOK_VERIFY_RUN_ID=resolve-verify`.
- `control-waybook doctor` reports `doctor: READY`.
- Note the decision id for `Flat files` from `control-waybook cli -- --json list --section decisions`.

- **Resolve.** Run `control-waybook record resolve -- mark-resolved <id> --resolution explicit`. Exit `0`; stdout is `resolved <id>`.
- **Show resolved.** Run `control-waybook cli -- show <id>`. Output has `status: resolved` and `resolution: explicit`.
- **Verify intact.** Run `control-waybook record verify-ok -- verify`. Exit `0`; stdout `ok`.
- **Prune dry-run.** Run `control-waybook record prune-dry -- prune --dry-run`. Exit `0`; stdout includes `would archive <id> (resolved)`. Confirm with `control-waybook cli -- list --section decisions` that the entry is still present (not yet archived).
- **Integrity failure (optional destructive proof).** Make the entry file writable, append one character to the body, and run `control-waybook record verify-broken -- verify`. The record command exits `11`. The transcript's stderr line is `Hash chain broken at <id>; board modified outside the CLI`, where `<id>` is that entry's id. Relaunch a fresh run afterward; do not continue other features on the broken board.
- **Proof.** Snapshots and transcripts under `/tmp/waybook-verify-evidence/resolve-verify/` show the resolve command, `status: resolved` via show/list, and dry-run prune output. Board files for the dry-run path remain under `board/`, not `archive/`.

## Gotchas

- Real `prune` (without `--dry-run`) moves files to `archive/`. Prefer `--dry-run` unless the feature under test is archival itself.
- PR/commit-based prune needs `gh` and git history; if those are missing, do not claim that path verified — record the unmet precondition.
- Hand-editing entry files is only for the integrity proof; always cleanup/relaunch after.
- `mark-resolved` on an already resolved id exits `8` (`E_ALREADY_RESOLVED`).
