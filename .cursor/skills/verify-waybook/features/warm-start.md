# Warm-start

Warm-start prints the short board index for a new session, optionally expands entries whose title or one-liner match a query, and by default rewrites `index.md`.

## Sub-features

- `warm-index` prints the capped index with the DATA NOT INSTRUCTIONS notice.
- `warm-query` expands matching sections for `--query`.
- `warm-read-only` prints the same text without writing the index, journal, or usefulness fields.
- `warm-default-write` without `--read-only` rewrites `index.md` (and may bump hidden usefulness for expanded matches).

## How to get to it (user POV)

- Run `waybook warm-start`.
- Run `waybook warm-start --query <words>`.
- Run `waybook warm-start --read-only` (or with both `--query` and `--read-only`).
- Session-start hook: `hooks/session-start` (calls the default, non-read-only form).

## Driving it with control-waybook

Preconditions:

- `control-waybook launch --run-id warm-start --seed` completed so seeded titles include `Flat files` and `Tried SQLite`.
- `export WAYBOOK_VERIFY_RUN_ID=warm-start`.
- `control-waybook doctor` reports `doctor: READY`.

- **Read-only index.** Run `control-waybook record warm-ro -- warm-start --read-only`. Exit `0`; stdout starts with `DATA NOT INSTRUCTIONS` and lists seeded titles.
- **Query expand.** Run `control-waybook record warm-query -- warm-start --query flat --read-only`. Exit `0`; stdout includes `## decisions` / `### "Flat files"` and does not add a `## failed-attempts` expansion for `Tried SQLite`.
- **Prove read-only side effects.** Before and after the read-only commands, note `wc -l` of `.waybook/log/writes.jsonl` via snapshot or `control-waybook paths` then reading the project files. Line count must be unchanged by `--read-only` runs.
- **Default write.** Run `control-waybook record warm-write -- warm-start --query sqlite`. Exit `0`; `.waybook/index.md` exists and matches the printed index for open entries; a writes journal append may occur for usefulness/index updates — confirm with a fresh `control-waybook snapshot warm-after-write` compared to the earlier snapshot.
- **Session-start hook.** Run `hooks/session-start` from the project directory through a checkout `waybook` on `PATH`. A temporary `HOME` keeps the hook off `~/.local/bin/waybook`. Exit `0`; stdout starts with `DATA NOT INSTRUCTIONS` and lists the seeded titles. This is the default, non-read-only form.

```sh
project=$(control-waybook paths | awk -F= '/^project=/{print $2}')
repo=$(control-waybook paths | awk -F= '/^repo=/{print $2}')
if [ -z "$project" ] || [ -z "$repo" ]; then
  echo "control-waybook paths returned an empty path" >&2
  exit 1
fi
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
    sh "$repo/hooks/session-start"
)
```

- **Proof.** Keep transcripts `warm-ro.transcript.txt`, `warm-query.transcript.txt`, and snapshot dirs under `/tmp/waybook-verify-evidence/warm-start/`.

## Gotchas

- Default `warm-start` (no `--read-only`) mutates the board. Use `--read-only` when the proof must not bump usefulness or rewrite the index.
- Query matching is keyword overlap on title and one-liner, not full-body search.
- Inside a git checkout, warm-start may print a live `main:` tip line; the disposable helper project is not a git repo unless you create one, so absence of that line is expected there.
- `hooks/session-start` is a separate entry point: proving only `control-waybook cli -- warm-start` does not verify the hook script.
