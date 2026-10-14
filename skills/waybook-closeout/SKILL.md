---
name: waybook-closeout
description: Close out a session by recording decisions, open threads, and failed attempts on the local Waybook board.
---

# Waybook closeout

At the end of a session, leave the next session a warm board.

1. From the project root, add one entry per decision, open thread, and failed attempt. Link the commit or PR when there is one.

   waybook add decisions --title "..." --one-liner "..." --body-file note.md --link pr:N
   waybook add open-threads --title "..." --one-liner "..."
   waybook add failed-attempts --title "..." --one-liner "..."

2. Mark work that actually finished:

   waybook mark-resolved <id> --resolution explicit --note "what finished"

3. Check the board:

   waybook verify

4. If notes are still in flux, drop them in `.waybook/.pending/`. The flush hook files one open thread from those notes if the session dies.

Do not hand-edit files under `.waybook/board/`. To correct an entry, add a new one with `--supersedes <id>`.
