#!/bin/sh
# Exercises the hooks with real git in a temp repo. Run: sh githooks/test.sh
set -u
unset GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
hooks=${HOOKS:-$(cd "$(dirname "$0")" && pwd)}
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
git init -q --bare -b main "$tmp/remote.git"
git init -q -b main "$tmp/w" && cd "$tmp/w"
git config core.hooksPath "$hooks"
git config user.name 'Thomas Flaim'; git config user.email tflaim@gmail.com
git remote add origin "$tmp/remote.git"
printf '#!/bin/sh\nsed "1s/^/$1/" "$2" > "$2.new" && mv "$2.new" "$2"\n' > "$tmp/editor"; chmod +x "$tmp/editor"
pass=0; fail=0
check() { # check <name> <expected-exit> <expected-first-stderr-line> <cmd>
  err=$(sh -c "$4" 2>&1 >/dev/null); code=$?; first=$(printf '%s\n' "$err" | head -n1)
  if [ "$code" = "$2" ] && [ "$first" = "$3" ]; then pass=$((pass+1)); else
    fail=$((fail+1)); printf 'FAIL %s\n  want %s %s\n  got  %s %s\n' "$1" "$2" "$3" "$code" "$first"; fi
}
W='Thomas Flaim <tflaim@gmail.com>'
AI='commit-msg: AI attribution found:'
CA='Cursor Agent <cursoragent@cursor.com>'
IDFIX="Fix: git rebase -x 'git commit --amend --no-edit --reset-author' <base>"
bad() { git commit -q --no-verify --allow-empty "$@"; git rev-parse --short HEAD; }

echo a > a; git add a
check good-commit 0 '' 'git commit -qm "Add a"'
git push -q --no-verify origin HEAD:main
check bad-author 1 "commit-msg: AUTHOR is '$CA', must be '$W'." "git commit -q --allow-empty -m x --author='$CA'"
check bad-committer 1 "commit-msg: COMMITTER is 'Thomas Flaim <taco@box.local>', must be '$W'." \
  'GIT_COMMITTER_EMAIL=taco@box.local git commit -q --allow-empty -m x'
check co-authored-by 1 "$AI" "git commit -q --allow-empty -m x -m 'Co-authored-by: $CA'"
check generated-by 1 "$AI" 'git commit -q --allow-empty -m x -m "Generated-by: Cursor"'
check made-with 1 "$AI" 'git commit -q --allow-empty -m x -m "Made-with: Cursor"'
check cursoragent-email 1 "$AI" 'git commit -q --allow-empty -m "x" -m "Thanks cursoragent@cursor.com"'
check trailer-url 1 "$AI" 'git commit -q --allow-empty -m x -m "Agent-Session: https://cursor.com/agents?id=bc-1"'
check footer-link 1 "$AI" 'git commit -q --allow-empty -m x -m "Made with [Cursor](https://cursor.com)"'
check claude-footer 1 "$AI" 'git commit -q --allow-empty -m x -m "Generated with [Claude Code](https://claude.com/claude-code)"'
check pr-body-marker 1 "$AI" 'git commit -q --allow-empty -m x -m "<!-- CURSOR_AGENT_PR_BODY_BEGIN -->"'
check robot 1 "$AI" 'git commit -q --allow-empty -m x -m "🤖 done"'
check prose-cursor-com 0 '' 'git commit -q --allow-empty -m "Document cursor.com and claude.com hook docs"'
check claude-md 0 '' 'git commit -q --allow-empty -m "Link CLAUDE.md to AGENTS.md"'
check comment-line 0 '' "printf 'Add x\n# Co-authored-by: $CA\n' > ../m && git commit -q --allow-empty --cleanup=strip -F ../m"
check comment-char 0 '' "printf 'Add y\n; Co-authored-by: $CA\n' > ../m && git -c core.commentChar=';' commit -q --allow-empty --cleanup=strip -F ../m"
echo 'x: cursoragent@cursor.com' > g; git add g
check commit-v-comment-char 0 '' "GIT_EDITOR='$tmp/editor Add-g' git -c core.commentChar=';' commit -q -v"
echo 'author: cursoragent@cursor.com' > f; git add f
check commit-v-diff 0 '' "GIT_EDITOR='$tmp/editor Add-f' git commit -q -v"

check push-tflaim 0 '' 'git push -q origin HEAD:tflaim/seal-module'
check push-main 1 "pre-push: refusing to push to 'main'. Fix: push a tflaim/<slug> branch and open a PR." 'git push -q origin HEAD:main'
check push-master 1 "pre-push: refusing to push to 'master'. Fix: push a tflaim/<slug> branch and open a PR." 'git push -q origin HEAD:master'
check push-cursor 1 "pre-push: branch 'cursor/seal-7f3a' must be tflaim/<slug>. Fix: git push origin HEAD:tflaim/seal-7f3a" \
  'git push -q origin HEAD:cursor/seal-7f3a'
check push-nested 1 "pre-push: branch 'claude/Fix/thing' must be tflaim/<slug>. Fix: git push origin HEAD:tflaim/fix-thing" \
  'git push -q origin HEAD:claude/Fix/thing'
check multi-ref-bad 1 "pre-push: branch 'cursor/b' must be tflaim/<slug>. Fix: git push origin HEAD:tflaim/b" \
  'git push -q origin HEAD:tflaim/a HEAD:cursor/b'
check multi-ref-good 0 '' 'git push -q origin HEAD:tflaim/a HEAD:tflaim/b'
check delete-tflaim 0 '' 'git push -q origin :tflaim/b'
check delete-main 1 "pre-push: refusing to push to 'main'. Fix: push a tflaim/<slug> branch and open a PR." 'git push -q origin :main'
git tag v1
check tag-good 0 '' 'git push -q origin v1'

good=$(git rev-parse HEAD)
h=$(bad -m x --author="$CA")
check no-verify-author 1 "pre-push: commit $h has author '$CA', must be '$W'. $IDFIX" 'git push -q origin HEAD:tflaim/seal-module'
z=0000000000000000000000000000000000000000
check delete-cursor-branch 0 '' \
  "echo '(delete) $z refs/heads/cursor/some-branch $(git rev-parse HEAD)' | sh '$hooks/pre-push' origin '$tmp/remote.git'"
check delete-main-line 1 "pre-push: refusing to push to 'main'. Fix: push a tflaim/<slug> branch and open a PR." \
  "echo '(delete) $z refs/heads/main $(git rev-parse HEAD)' | sh '$hooks/pre-push' origin '$tmp/remote.git'"
check push-cursor-line 1 "pre-push: branch 'cursor/some-branch' must be tflaim/<slug>. Fix: git push origin HEAD:tflaim/some-branch" \
  "echo 'refs/heads/cursor/some-branch $(git rev-parse HEAD) refs/heads/cursor/some-branch $z' | sh '$hooks/pre-push' origin '$tmp/remote.git'"
check push-bad-author-line 1 "pre-push: commit $h has author '$CA', must be '$W'. $IDFIX" \
  "echo 'refs/heads/tflaim/bad-author $(git rev-parse HEAD) refs/heads/tflaim/bad-author $z' | sh '$hooks/pre-push' origin '$tmp/remote.git'"
git tag v2
check tag-bad-commit 1 "pre-push: commit $h has author '$CA', must be '$W'. $IDFIX" 'git push -q origin v2'
git reset -q --hard "$good"
h=$(bad -m x -m "Co-authored-by: $W")
check no-verify-trailer 1 "pre-push: commit $h carries AI attribution. Fix: git rebase -i and reword it." 'git push -q origin HEAD:tflaim/seal-module'
git reset -q --hard "$good"
h=$(GIT_COMMITTER_NAME='Cursor Agent' GIT_COMMITTER_EMAIL=cursoragent@cursor.com git commit -q --no-verify --allow-empty -m x && git rev-parse --short HEAD)
check cursor-committer 1 "pre-push: commit $h has committer '$CA', must be '$W'. $IDFIX" 'git push -q origin HEAD:tflaim/seal-module'
git reset -q --hard "$good"
GIT_AUTHOR_NAME='Thomas Flaim' GIT_AUTHOR_EMAIL=tflaim@gmail.com \
  GIT_COMMITTER_NAME='Thomas Flaim' GIT_COMMITTER_EMAIL=tflaim@gmail.com \
  git commit -q --allow-empty -m thomas
ha=$(git log -1 --format='%an <%ae>')
hc=$(git log -1 --format='%cn <%ce>')
err=$(git push -q origin HEAD:tflaim/thomas-ok 2>&1 >/dev/null); code=$?
if [ "$code" = 0 ] && [ "$err" = "" ] && [ "$ha" = "$W" ] && [ "$hc" = "$W" ]; then pass=$((pass+1)); else
  fail=$((fail+1)); printf 'FAIL thomas-thomas\n  want 0 %s %s\n  got  %s [%s] %s %s\n' "$W" "$W" "$code" "$err" "$ha" "$hc"; fi
git reset -q --hard "$good"

# Regression: remote tip unknown locally (force-push over someone else's commit) must not fail open.
git clone -q "$tmp/remote.git" "$tmp/other"
(cd "$tmp/other" && git checkout -q -b w origin/tflaim/seal-module && git -c user.name=Other -c user.email=o@x commit -q --allow-empty -m other &&
  git push -q --no-verify origin HEAD:tflaim/seal-module)
h=$(bad -m x --author='Bad <b@x>')
check force-unknown-remote 1 "pre-push: commit $h has author 'Bad <b@x>', must be '$W'. $IDFIX" \
  'git push -q -f origin HEAD:tflaim/seal-module'
check unknown-remote-sha 1 "pre-push: commit $h has author 'Bad <b@x>', must be '$W'. $IDFIX" \
  "echo 'refs/heads/x $(git rev-parse HEAD) refs/heads/tflaim/x 1111111111111111111111111111111111111111' | sh '$hooks/pre-push' origin '$tmp/remote.git'"
git reset -q --hard "$good"
git push -q -f origin HEAD:tflaim/seal-module

# Regression: merging main (with a GitHub squash commit) into a pushed tflaim branch.
(cd "$tmp/other" && git fetch -q && git checkout -q -B main "$good" &&
  GIT_COMMITTER_NAME=GitHub GIT_COMMITTER_EMAIL=noreply@github.com git -c user.name='Thomas Flaim' \
    -c user.email=84033778+tflaim@users.noreply.github.com commit -q --allow-empty -m 'Squash (#9)' &&
  git push -q --no-verify origin main)
git fetch -q origin
echo m > m; git add m; git commit -qm "Add m"
check merge-main 0 '' 'git merge -q --no-edit origin/main && git push -q origin HEAD:tflaim/seal-module'

# Regression: commits already on another remote branch are still checked when republished.
(cd "$tmp/other" && git checkout -q -B agent "$good" &&
  git -c user.name='Cursor Agent' -c user.email=cursoragent@cursor.com commit -q --allow-empty -m agent -m "Co-authored-by: $CA" &&
  git push -q --no-verify origin HEAD:cursor/agent-1 &&
  git checkout -q -B junk "$good" && git -c user.name=Bad -c user.email=b@x commit -q --allow-empty -m junk &&
  git push -q --no-verify origin HEAD:scratch/junk)
git fetch -q origin
h=$(git rev-parse --short origin/cursor/agent-1)
check republish-agent 1 "pre-push: commit $h has author '$CA', must be '$W'. $IDFIX" \
  'git push -q origin origin/cursor/agent-1:refs/heads/tflaim/agent'
h=$(git rev-parse --short origin/scratch/junk)
check scratch-only-bad 1 "pre-push: commit $h has author 'Bad <b@x>', must be '$W'. $IDFIX" \
  'git push -q origin origin/scratch/junk:refs/heads/tflaim/junk'
check could-not-list 1 'pre-push: could not list commits for refs/heads/tflaim/x. Fix: git fetch origin, then push again.' \
  "echo 'refs/heads/x 2222222222222222222222222222222222222222 refs/heads/tflaim/x 0000000000000000000000000000000000000000' | sh '$hooks/pre-push' origin '$tmp/remote.git'"
h=$(git rev-parse --short origin/main)
check no-main-ref-checks-all 1 "pre-push: commit $h has author 'Thomas Flaim <84033778+tflaim@users.noreply.github.com>', must be '$W'. $IDFIX" \
  "git push -q '$tmp/remote.git' HEAD:tflaim/fresh"

. "$hooks/test-cursor-hooks.sh"

echo "githooks: $pass passed, $fail failed"
[ "$fail" = 0 ]
