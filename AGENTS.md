# Agent notes

These notes apply to any coding agent working in this repo.

To verify changes, read and follow `skills/verify-waybook/SKILL.md`.

Install the git hooks once per clone: `git config core.hooksPath githooks` (commit-msg blocks cursoragent@cursor.com; Co-authored-by/Generated-by/Made-with trailers; Key: lines with cursor.com/claude.ai/claude.com URLs; 'Docs: https://cursor.com/...'-style lines are rejected, so reword them; Markdown links to those; 'Generated with [Claude Code'; CURSOR_AGENT_PR_BODY; 🤖. pre-push allows tflaim/* branches and tags, refuses main/master, and re-checks pushed commits). Hook tests: `sh githooks/test.sh`.
