# Waybook board

This directory is the local board for one project.

Non-claims: it is not a memory of user preferences. It does not verify that an entry is true. It does not prove that selective loading is useful. The hidden usefulness number stored in each file is a heuristic, not a measurement. Version 1 commands never print it.

You may read files under `board/` directly. One file is one entry. Do not hand-edit them. `waybook verify` checks the write journal and fails if a file changed outside the CLI.

Writes go through the `waybook` command (`add`, `mark-resolved`, `prune`, `migrate`). To correct an entry, add a new one with `--supersedes <id>`.

Pending session notes dropped in `.pending/` are picked up by `waybook flush`.
