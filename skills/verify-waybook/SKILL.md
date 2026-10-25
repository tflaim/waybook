---
name: verify-waybook
description: "Verify Waybook (CLI board for decisions, open threads, failed attempts) by launching an isolated project board, driving real CLI commands, and capturing transcripts plus on-disk board state. Use when proving Waybook behavior, regression-checking CLI/MCP-adjacent flows, or after changing init/add/list/show/index/warm-start/resolve/verify/flush/watchdog."
---

# Verify Waybook

Waybook is a **short-lived CLI** (plus an optional stdio MCP server). There is no HTTP port and no long-running app process for normal verification. Each drive is one or more `python3 -m waybook` invocations against an isolated project directory that owns its own `.waybook/`.

`sh githooks/test.sh` must print `githooks: 270 passed, 0 failed`, exit 0, and write no stderr, under sh, dash, and bash, each plain and with `LC_ALL=C.UTF-8` and `LC_ALL=C` (the bash 3.2 and BSD tool run is Mac-only). The group-kill test needs perl on PATH (`POSIX::setsid`).

Secondary surfaces (do not use as the primary proof path unless the change is MCP/hooks-specific): `waybook mcp` (stdio JSON-RPC), and the POSIX hooks under `hooks/` that shell out to the same CLI.

## Launch

From the repo root:

```sh
chmod +x skills/verify-waybook/helpers/control-waybook
# Doctor requires python3 3.11+. On this Mac, /usr/bin/python3 is 3.9 and fails
# that check, so Homebrew's python3 has to come first. Do not install a runtime
# when this check already passes.
export PATH="$PWD/skills/verify-waybook/helpers:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'

control-waybook launch --run-id "prove-warm-start" --seed
export WAYBOOK_VERIFY_RUN_ID=prove-warm-start
```

If you omit `--run-id`, launch invents one and prints `export WAYBOOK_VERIFY_RUN_ID=...`; run that export before doctor/cli.
What launch does:

1. Sets `PYTHONPATH` to this repo (documented checkout path; does **not** require `./install.sh` or a venv).
2. Creates `/tmp/waybook-verify/<run-id>/project` with an empty data dir.
3. Runs `waybook init --project-id verify/demo` so the board is usable (schema v2, `index.md`, logs).
4. With `--seed`, adds three open entries: decision `Flat files`, failed attempt `Tried SQLite`, open thread `Wire prune to gh`.
5. Creates evidence dir `/tmp/waybook-verify-evidence/<run-id>/` (empty until you capture).

**Ready means:** `control-waybook doctor` prints `doctor: READY`, `waybook verify` is ok, and `waybook list` succeeds inside the project.

**Teardown:** `control-waybook cleanup` (see Cleanup). Never leave `/tmp/waybook-verify/<run-id>` behind after a failed attempt.

**Isolation:** Every run uses its own project directory. Concurrent runs are safe if they use different `WAYBOOK_VERIFY_RUN_ID` values. Do **not** drive the developer's real project `.waybook/` or any board you did not launch. Refusing a shared instance is correct.

**Clean shell.** Start from `env -i PATH="$PATH" HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}"`. Pass `TMPDIR` through so `mktemp` in the feature recipes has a directory. The one `WAYBOOK_*` you export yourself is `WAYBOOK_VERIFY_RUN_ID`: launch prints it, and the launch block above exports that line before doctor and the feature recipes. Do not export any other `WAYBOOK_*` or any `HANKO_*`. The helper sets `WAYBOOK_AGENT` and `WAYBOOK_NOW`.

**State paths stay on `/tmp`.** Instances live at `/tmp/waybook-verify/<run-id>/` and evidence at `/tmp/waybook-verify-evidence/<run-id>/`. Do not point `WAYBOOK_VERIFY_STATE_ROOT` or `WAYBOOK_VERIFY_EVIDENCE_ROOT` at `$TMPDIR`. On macOS `$TMPDIR` is a per-user directory, not `/tmp`. `/tmp` is a symlink to `/private/tmp`, so the `initialized` line can show `/private/tmp/...` while `project=` shows `/tmp/...`. Those strings name the same directory.

**Install note:** `./install.sh` needs `python3-venv`/`ensurepip`. Verification does not use it; it uses `python3 -m waybook` with `PYTHONPATH=<repo>` as documented in the README.

## Doctor

```sh
control-waybook doctor --run-id "$WAYBOOK_VERIFY_RUN_ID"
```

Read-only checks:

- `python3` is 3.11+ (a `Python 3.9` failure means `/usr/bin` is ahead of `/opt/homebrew/bin`; fix `PATH` and run doctor again)
- `waybook` imports from this checkout and version matches the launch record
- the run's `.waybook/` exists with `schema_version = 2`
- `waybook verify` exits 0 in that project
- the evidence directory for the run exists

If anything looks off, run doctor before re-driving. Exit nonzero means do not continue.

## Drive

Put the helper on `PATH`, export `WAYBOOK_VERIFY_RUN_ID`, then drive only through the helper:

```sh
control-waybook cli -- list --section decisions
control-waybook cli -- --json list --section decisions
control-waybook cli -- add decisions --title "T" --one-liner "L"
control-waybook cli -- show <id>
control-waybook cli -- warm-start --query flat --read-only
control-waybook cli -- index
control-waybook cli -- mark-resolved <id> --resolution explicit
control-waybook cli -- verify
control-waybook cli -- flush
control-waybook cli -- watchdog --silence 0s
```

Stable handles (prefer these over scraping markdown files first):

| Handle | Meaning |
| --- | --- |
| Exit code `0` | success |
| Exit codes `1`–`13` | documented `E_*` failures (see README). `1` is `E_INTERNAL` |
| `--json` stdout | machine-readable payloads (`{"id":...}`, `{"entries":[...]}`, `{"result":"ok"}`) |
| Human stdout | `added <id>`, `resolved <id>`, `ok`, list table, warm-start index text |
| `.waybook/board/<section>/*.md` | persisted entry files (mode `0444`) |
| `.waybook/log/writes.jsonl` | append-only hash chain |
| `.waybook/index.md` | generated short index |

Default harness env: `WAYBOOK_AGENT=verifier`, `WAYBOOK_NOW=2026-10-13T12:00:00Z` (unset `WAYBOOK_NOW` in the environment before `cli` if you need wall-clock time). Global flags go before the subcommand: `control-waybook cli -- --json --agent alice list`.

Feature recipes live in [`features/`](./features/). Read the map index, then the feature file, then drive that path. A proof that uses a different entry point than the map lists is incomplete for that entry point.

## Evidence

Evidence root (survives cleanup): `/tmp/waybook-verify-evidence/<run-id>/`.

Capture both the action and the resulting state:

```sh
# Action transcript (command + stdout/stderr + exit)
control-waybook record add-decision -- add decisions --title "Evidence sample" --one-liner "Unique for this proof"

# Resulting board state (list, verify, index.md, full .waybook/ copy)
control-waybook snapshot after-add
```

Proof standards:

- Exercise the **real CLI** (`python3 -m waybook` via the helper). Do not call `waybook.board` Python APIs as a substitute for a user path.
- Capture the **command transcript** and a **second view** of persistence (`list`/`show` or the copied `.waybook/` files).
- For mutations, confirm side effects on disk (new file under `board/`, new line in `log/writes.jsonl`, index rewrite when not `--read-only`).
- `warm-start --read-only` must leave `writes.jsonl` length and entry `last_useful_at` unchanged; prove that by snapshotting before/after, not by trusting the flag name alone.
- `prune` without network/`gh` still archives **explicitly resolved** entries; PR/commit resolution needs `gh`/`git` and is a separate gotcha in the feature map.
- Mocks are not used. External boundaries (`gh` for PR state) are either exercised for real or marked unmet in Gotchas — never silently skipped as “verified”.

## Cleanup

```sh
control-waybook cleanup --run-id "$WAYBOOK_VERIFY_RUN_ID"
```

Removes only `/tmp/waybook-verify/<run-id>/` (the instance this run created). Does **not** delete `/tmp/waybook-verify-evidence/<run-id>/`. Does not kill by process name (no daemon to kill for CLI drives). If you started `waybook mcp` for an MCP-specific check, terminate that specific process you spawned (PID you recorded), not every `waybook` on the machine.

## Helpers

Executable: `skills/verify-waybook/helpers/control-waybook`

```sh
control-waybook launch [--run-id ID] [--project-id ID] [--seed]
control-waybook doctor [--run-id ID]
control-waybook cli [--run-id ID] -- <waybook args>
control-waybook record [--run-id ID] <label> -- <waybook args>
control-waybook snapshot [--run-id ID] [label]
control-waybook paths [--run-id ID]
control-waybook cleanup [--run-id ID]
```
