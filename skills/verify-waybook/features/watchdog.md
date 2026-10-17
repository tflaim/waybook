# Silence watchdog

The silence watchdog is a one-shot check. When the board has been quiet longer than the silence threshold, it files pending notes the same way `flush` does and prints a notice. When the board is still inside the threshold, it prints nothing and leaves the pending files where they are. It always exits 0.

## Sub-features

- `watchdog-quiet` with the default `20m` on a fresh board prints nothing and keeps pending notes.
- `watchdog-fire` with `--silence 0s` files those notes, prints the notice, and deletes the pending files.
- `watchdog-hook` is `hooks/watchdog`, which runs `waybook watchdog` and always exits 0.

## How to get to it (user POV)

- Run `waybook watchdog`.
- Run `waybook watchdog --silence 0s` (or another duration such as `20m`).
- Silence hook: `hooks/watchdog` (uses `WAYBOOK_SILENCE`, default `20m`).

## Driving it with control-waybook

Preconditions:

- `control-waybook launch --run-id watchdog-silence --seed` completed.
- `export WAYBOOK_VERIFY_RUN_ID=watchdog-silence`.
- `control-waybook doctor` reports `doctor: READY`.
- Resolve the project path with `control-waybook paths`.

- **Stage a pending note.** If `control-waybook paths` yields an empty project path, fail before writing anything:

```sh
project=$(control-waybook paths | awk -F= '/^project=/{print $2}')
repo=$(control-waybook paths | awk -F= '/^repo=/{print $2}')
if [ -z "$project" ] || [ -z "$repo" ]; then
  echo "control-waybook paths returned an empty path" >&2
  exit 1
fi
echo "watchdog still waiting" > "$project/.waybook/.pending/watch.txt"
```

- **Quiet check.** Run `control-waybook record watchdog-quiet -- watchdog`. Exit `0`. Stdout has no `notice:` line. `watch.txt` is still in `.waybook/.pending/`.
- **Fire.** Run `control-waybook record watchdog-fire -- watchdog --silence 0s`. Exit `0`. Stdout is `notice: silence threshold exceeded; ran flush hook`. `watch.txt` is gone. `list --section open-threads` has an `Unfinished: verifier` row, and `show` of that id includes `watchdog still waiting` in the body. The title line is `title: "Unfinished: verifier"` because of the colon.
- **Hook.** Stage a different note, then run `hooks/watchdog` through a checkout `waybook` on `PATH`. Export `WAYBOOK_NOW` to the harness clock and `WAYBOOK_SILENCE=0s`. A temporary `HOME` keeps the hook off `~/.local/bin/waybook`. Exit `0`. Stdout is the same notice. The new pending file is gone, and a `show` of the new `Unfinished: verifier` row includes the hook note.

```sh
echo "hook silence note" > "$project/.waybook/.pending/hook-watch.txt"
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
    WAYBOOK_NOW=2026-10-13T12:00:00Z WAYBOOK_SILENCE=0s \
    sh "$repo/hooks/watchdog"
)
```

- **Proof.** Transcripts `watchdog-quiet.transcript.txt` and `watchdog-fire.transcript.txt`, plus a snapshot, live under `/tmp/waybook-verify-evidence/watchdog-silence/`. The quiet transcript has no notice. The fire transcript has the notice, and the snapshot's open thread contains the pending text.

## Gotchas

- `watchdog` always exits `0`, including when it does not fire. Proof is the notice plus the pending file and the board, not the exit code.
- The helper sets `WAYBOOK_NOW=2026-10-13T12:00:00Z` and init stamps `.heartbeat` at that instant, so the default `20m` does not fire on a fresh launch. `--silence 0s` is the fire path.
- `hooks/watchdog` does not set `WAYBOOK_NOW`. Without that export, wall-clock time is later than the stamped heartbeat and the default `20m` fires immediately. Export the harness clock when the proof must choose quiet versus fire.
- The unfinished title follows flush: `Unfinished: verifier` when `WAYBOOK_AGENT` is set, `Unfinished: session` with `source_agent: local` when it is not. The helper sets the agent.
