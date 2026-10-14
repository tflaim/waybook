# Add and inspect entries

Add and inspect lets a user append one markdown entry to a section and read it back through `list` and `show` without seeing the hidden usefulness score.

## Sub-features

- `add-decision` appends a `decisions` entry and prints its id.
- `add-failed` appends a `failed-attempts` entry.
- `add-thread` appends an `open-threads` entry.
- `list-section` filters the table by `--section`.
- `show-entry` prints front matter and body without a usefulness field.
- `add-json` returns `{"id":"..."}` for scripting.

## How to get to it (user POV)

- Run `waybook --agent <name> add <section> --title <title> --one-liner <line>`.
- Run `waybook list [--section <section>]`.
- Run `waybook show <id>` with an id from `list` or `add`.

## Driving it with control-waybook

Preconditions:

- `control-waybook launch --run-id add-inspect` completed (no `--seed`).
- `export WAYBOOK_VERIFY_RUN_ID=add-inspect`.
- `control-waybook doctor` reports `doctor: READY`.

- **Add decision.** Run `control-waybook record add-decision -- --json add decisions --title "Flat files" --one-liner "No DB"`. Exit `0`; stdout is JSON with an `id` starting with `dec-`.
- **List section.** Run `control-waybook record list-decisions -- list --section decisions`. Exit `0`; stdout table includes `Flat files` and the new id.
- **Show entry.** Capture the id from the add transcript, then run `control-waybook record show-decision -- show <id>`. Exit `0`; output includes `title: Flat files`, `one_liner: No DB`, `source_agent: verifier`, and does **not** include a `usefulness` line.
- **Add other sections.** Run `control-waybook cli -- add failed-attempts --title "Tried SQLite" --one-liner "Locking issues"` and `control-waybook cli -- add open-threads --title "Wire prune to gh" --one-liner "Needs auth for PR lookup"`. Both exit `0`.
- **List all.** Run `control-waybook record list-all -- list`. Exit `0`; all three titles appear.
- **Proof.** Run `control-waybook snapshot after-add`. The snapshot's `dot-waybook/board/decisions/` contains a `0444` markdown file whose title is `Flat files`, and `cli-state.txt` lists the three entries.

## Gotchas

- Section names on the CLI use hyphens: `open-threads`, `failed-attempts` (not underscores).
- Identical title/one-liner/body/agent/clock input can collide on id (`E_APPEND_ONLY`). Change the title or unset `WAYBOOK_NOW` if you re-add the same text in one board.
- `show` and `--json` must never surface `usefulness`; treat any appearance as a failed proof.
- `--agent` / `WAYBOOK_AGENT` is what `source_agent` records; the helper defaults to `verifier`.
