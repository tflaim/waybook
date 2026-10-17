# Warm-start

Warm-start prints the short board index for a new session, optionally expands entries whose title or one-liner match a query, and by default rewrites `index.md`.

## Sub-features

- `warm-index` prints the capped index with the DATA NOT INSTRUCTIONS notice.
- `warm-query` expands matching sections for `--query`.
- `warm-read-only` prints the same text without writing the index, journal, or usefulness fields.
- `warm-default-write` without `--read-only` rewrites `index.md` (and bumps hidden usefulness for each expanded match).
- `index-rewrite` runs `waybook index` and prints `updated index`.
- `index-print` runs `waybook index --print` and prints the same short index, including the DATA NOT INSTRUCTIONS notice.

## How to get to it (user POV)

- Run `waybook warm-start`.
- Run `waybook warm-start --query <words>`.
- Run `waybook warm-start --read-only` (or with both `--query` and `--read-only`).
- Run `waybook index` to rewrite `index.md`, or `waybook index --print` to print that index without a query expansion.
- Session-start hook: `hooks/session-start`. With `WAYBOOK_QUERY` unset it runs `waybook warm-start`. With `WAYBOOK_QUERY` set it runs `waybook warm-start --query` on that value. Both are the default, non-read-only form.

## Driving it with control-waybook

Preconditions:

- `control-waybook launch --run-id warm-start --seed` completed so seeded titles include `Flat files` and `Tried SQLite`.
- `export WAYBOOK_VERIFY_RUN_ID=warm-start`.
- `control-waybook doctor` reports `doctor: READY`.

- **Read-only index.** Run `control-waybook record warm-ro -- warm-start --read-only`. Exit `0`; stdout starts with `DATA NOT INSTRUCTIONS` and lists seeded titles.
- **Query expand.** Run `control-waybook record warm-query -- warm-start --query flat --read-only`. Exit `0`; stdout includes `## decisions` / `### "Flat files"` and does not add a `## failed-attempts` expansion for `Tried SQLite`.
- **Prove read-only side effects.** Before and after the read-only commands, note `wc -l` of `.waybook/log/writes.jsonl` via snapshot or `control-waybook paths` then reading the project files. Line count must be unchanged by `--read-only` runs.
- **Default write.** Run `control-waybook record warm-write -- warm-start --query sqlite`. Exit `0`; `.waybook/index.md` exists and matches the printed index for open entries. The expanded match's hidden usefulness becomes `0.1` and `log/writes.jsonl` grows by one line. Confirm with a fresh `control-waybook snapshot warm-after-write` compared to the earlier snapshot.
- **Rewrite index.** Run `control-waybook record index-update -- index`. Exit `0`; stdout is `updated index`.
- **Print index.** Run `control-waybook record index-print -- index --print`. Exit `0`; stdout starts with `DATA NOT INSTRUCTIONS` and lists the seeded titles.
- **Session-start hook.** Run `hooks/session-start` from the project directory through a checkout `waybook` on `PATH`. A temporary `HOME` keeps the hook off `~/.local/bin/waybook`. Leave `WAYBOOK_QUERY` unset. Exit `0`; stdout starts with `DATA NOT INSTRUCTIONS` and lists the seeded titles. This is the default, non-read-only form.
- **Session-start query.** Run the same hook with `WAYBOOK_QUERY=flat`. Exit `0`; stdout includes `### "Flat files"` and does not add a `## failed-attempts` expansion for `Tried SQLite`.

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
(
  cd "$project"
  HOME="$hook_home" PATH="$shim:$PATH" WAYBOOK_AGENT=verifier WAYBOOK_QUERY=flat \
    sh "$repo/hooks/session-start"
)
```

- **Proof.** Keep transcripts `warm-ro.transcript.txt`, `warm-query.transcript.txt`, `index-update.transcript.txt`, `index-print.transcript.txt`, and snapshot dirs under `/tmp/waybook-verify-evidence/warm-start/`.

## Gotchas

- Default `warm-start` (no `--read-only`) mutates the board. Use `--read-only` when the proof must not bump usefulness or rewrite the index.
- A query matches when every word is a case-insensitive substring of the title and one-liner together, so `flat` also matches `flatten`. It does not search the body. On a dormant board (`project_active = false`) the command still prints the index and does not expand the query.
- Inside a git checkout, warm-start may print a live `main:` tip line; the disposable helper project is not a git repo unless you create one, so absence of that line is expected there.
- `hooks/session-start` is a separate entry point: proving only `control-waybook cli -- warm-start` does not verify the hook script.
