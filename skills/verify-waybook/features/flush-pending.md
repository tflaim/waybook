# Flush pending notes

Flush turns notes left in `.waybook/.pending/` into one `open-threads` entry and deletes the pending files. The title is `Unfinished: <agent>` when an agent is set, and `Unfinished: session` when it is not. It is the session-end safety net.

## Sub-features

- `flush-empty` succeeds with no pending notes and does not invent an entry.
- `flush-file` creates one open thread from pending note text.
- `flush-clears-pending` removes the filed pending files after success.
- `flush-exit-zero` exits `0` even when used as a best-effort hook.
- `flush-no-agent` with no agent files `Unfinished: session` and records `source_agent: local`.

## How to get to it (user POV)

- Drop markdown/text notes into `.waybook/.pending/` during a session.
- Run `waybook flush` (or `hooks/session-end`, which calls flush).

## Driving it with control-waybook

Preconditions:

- `control-waybook launch --run-id flush-pending` completed (seed optional).
- `export WAYBOOK_VERIFY_RUN_ID=flush-pending`.
- `control-waybook doctor` reports `doctor: READY`.
- Resolve the project path with `control-waybook paths`.

- **Empty flush.** Run `control-waybook record flush-empty -- flush`. Exit `0`. Run `control-waybook cli -- list --section open-threads` and confirm no new `Unfinished: verifier` row if none existed.
- **Stage pending note.** Resolve the project path first. If `control-waybook paths` yields an empty project path, fail before writing anything:

```sh
project=$(control-waybook paths | awk -F= '/^project=/{print $2}')
if [ -z "$project" ]; then
  echo "control-waybook paths returned an empty project path" >&2
  exit 1
fi
echo "still wiring prune" > "$project/.waybook/.pending/note.txt"
```
- **Flush note.** Run `control-waybook record flush-note -- flush`. Exit `0`.
- **Inspect thread.** Run `control-waybook record list-unfinished -- list --section open-threads`. Exit `0`; a row titled `Unfinished: verifier` is present. `show` that id includes the pending note text in the body.
- **Pending cleared.** Confirm `.waybook/.pending/` no longer contains `note.txt` (only keep files like `.keep` if present).
- **Show quotes the title.** `show` of that id includes the pending note in the body. The title contains a colon, so the front-matter line is `title: "Unfinished: verifier"`, not an unquoted `title: Unfinished: verifier`. The list row stays unquoted.
- **No agent.** The helper always sets `WAYBOOK_AGENT=verifier`, so it cannot prove the unset-agent title. Stage a different note, then run `waybook flush` from the project with `WAYBOOK_AGENT` unset. Exit `0`. The new row is titled `Unfinished: session`, `show` has `source_agent: local` and `title: "Unfinished: session"`, and the pending file is gone.

```sh
project=$(control-waybook paths | awk -F= '/^project=/{print $2}')
repo=$(control-waybook paths | awk -F= '/^repo=/{print $2}')
if [ -z "$project" ] || [ -z "$repo" ]; then
  echo "control-waybook paths returned an empty path" >&2
  exit 1
fi
echo "no agent note" > "$project/.waybook/.pending/no-agent.txt"
(
  cd "$project"
  env -u WAYBOOK_AGENT WAYBOOK_NOW=2026-10-13T12:00:00Z PYTHONPATH="$repo${PYTHONPATH:+:$PYTHONPATH}" \
    python3 -m waybook flush
)
```
- **Session-end hook.** Stage a different note, then run `hooks/session-end` against this checkout (a temporary `HOME` avoids `~/.local/bin/waybook`). Exit `0`. A new `Unfinished: verifier` row contains the hook note, and the pending file is gone.

```sh
project=$(control-waybook paths | awk -F= '/^project=/{print $2}')
repo=$(control-waybook paths | awk -F= '/^repo=/{print $2}')
if [ -z "$project" ] || [ -z "$repo" ]; then
  echo "control-waybook paths returned an empty path" >&2
  exit 1
fi
echo "hook still wiring" > "$project/.waybook/.pending/hook-note.txt"
shim=$(mktemp -d)
cat > "$shim/waybook" <<EOF
#!/bin/sh
export PYTHONPATH="$repo\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m waybook "\$@"
EOF
chmod +x "$shim/waybook"
hook_home=$(mktemp -d)
(
  cd "$project"
  HOME="$hook_home" PATH="$shim:$PATH" WAYBOOK_AGENT=verifier \
    sh "$repo/hooks/session-end"
)
```

- **Proof.** Snapshots under `/tmp/waybook-verify-evidence/flush-pending/` include the flush transcript and a board copy whose `open-threads` entry matches the pending text.

## Gotchas

- `flush` always exits `0` by design (including many failure modes). Proof requires checking the board side effect, not only the exit code.
- With an agent set, the unfinished title uses that name (`Unfinished: verifier` under the helper). With no agent, the title is `Unfinished: session` and `source_agent` is `local`. The helper's default fills `WAYBOOK_AGENT`, so the no-agent path is the direct `python3 -m waybook flush` above.
- Proving `hooks/session-end` is a separate entry point from `waybook flush`; do not mark the hook verified by only running the CLI command.
- Secret-like text in pending notes is refused on write paths that scan content; use ordinary prose in fixtures.
