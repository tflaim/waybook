# Flush pending notes

Flush turns notes left in `.waybook/.pending/` into one `open-threads` entry titled `Unfinished: <agent>` and deletes the pending files. It is the session-end safety net.

## Sub-features

- `flush-empty` succeeds with no pending notes and does not invent an entry.
- `flush-file` creates one open thread from pending note text.
- `flush-clears-pending` removes the filed pending files after success.
- `flush-exit-zero` exits `0` even when used as a best-effort hook.

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
- The unfinished title uses the agent name (`WAYBOOK_AGENT` / `--agent`); the helper default is `verifier`.
- Proving `hooks/session-end` is a separate entry point from `waybook flush`; do not mark the hook verified by only running the CLI command.
- Secret-like text in pending notes is refused on write paths that scan content; use ordinary prose in fixtures.
