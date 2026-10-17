# Waybook verification map

This directory is the maintained source for verifying the user-facing behavior of Waybook. Read the index before driving the app, then use the matching feature file as the recipe.

## Baseline preconditions

- Launch an isolated board with `control-waybook launch --run-id <id> --seed` (or without `--seed` when a feature says so).
- Export `WAYBOOK_VERIFY_RUN_ID` to that id.
- Put `skills/verify-waybook/helpers` on `PATH`.
- Run `control-waybook doctor` and require `doctor: READY`.
- Never drive a `.waybook/` that this verification run did not create.
- Evidence goes under `/tmp/waybook-verify-evidence/<run-id>/` and must survive `control-waybook cleanup`.

## Driving conventions

- Start every recipe from the baseline state unless its preconditions say otherwise.
- Prefer `--json` for stable assertions on ids and lists; use human text when proving what a user/agent reads at session start.
- Treat every command as literal. Keep section names (`decisions`, `open-threads`, `failed-attempts`) and flags unchanged.
- Run all CLI actions through `control-waybook cli` or `control-waybook record`.
- Restore or relaunch after destructive proofs (`mark-resolved`, `flush`, real `prune`). Do not remove proof artifacts during cleanup.

## Proof and skip reporting

- Capture the user action and the resulting state, not only the final stdout line.
- CLI proof includes the command, stdout, stderr, and exit code (use `control-waybook record`).
- Mutation proof includes a second view: `list`/`show` and/or `control-waybook snapshot`.
- Record the feature file and entry point used with every artifact label.
- Report an unreachable path with the attempted command and the unmet precondition.
- Do not report a skipped entry point as verified through a different path.

## Feature entry contract

Each feature file starts with an H1 title and one paragraph describing the user-visible behavior. It then uses exactly four H2 sections in this order.

1. `Sub-features` lists short IDs with one line for each behavior.
2. `How to get to it (user POV)` lists every user entry point.
3. `Driving it with control-waybook` starts with `Preconditions:` and uses labeled bullets that pair each user action with an exact command and observable result.
4. `Gotchas` lists traps that can waste or invalidate a verification run.

Keep implementation details out of the map. Name only user paths, stable handles, required state, commands, and observable proof.

## Features

- [Initialize a board](./init-board.md) covers creating `.waybook/` from an empty project directory.
- [Add and inspect entries](./add-and-inspect.md) covers appending entries and reading them back with `list`/`show`.
- [Warm-start](./warm-start.md) covers the short index, query expansion, and read-only vs writing behavior.
- [Resolve and verify](./resolve-and-verify.md) covers explicit resolution, integrity checks, and dry-run prune of resolved entries.
- [Flush pending notes](./flush-pending.md) covers filing `.waybook/.pending/` notes into one open thread.
- [Silence watchdog](./watchdog.md) covers the one-shot silence check and the `hooks/watchdog` entry point.
