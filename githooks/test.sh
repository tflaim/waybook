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
check no-verify-author 1 "pre-push: commit $h has author '$CA', must be '$W'." 'git push -q origin HEAD:tflaim/seal-module'
git tag v2
check tag-bad-commit 1 "pre-push: commit $h has author '$CA', must be '$W'." 'git push -q origin v2'
git reset -q --hard "$good"
h=$(bad -m x -m "Co-authored-by: $W")
check no-verify-trailer 1 "pre-push: commit $h carries AI attribution. Fix: git rebase -i and reword it." 'git push -q origin HEAD:tflaim/seal-module'
git reset -q --hard "$good"

# Regression: remote tip unknown locally (force-push over someone else's commit) must not fail open.
git clone -q "$tmp/remote.git" "$tmp/other"
(cd "$tmp/other" && git checkout -q -b w origin/tflaim/seal-module && git -c user.name=Other -c user.email=o@x commit -q --allow-empty -m other &&
  git push -q --no-verify origin HEAD:tflaim/seal-module)
h=$(bad -m x --author='Bad <b@x>')
check force-unknown-remote 1 "pre-push: commit $h has author 'Bad <b@x>', must be '$W'." \
  'git push -q -f origin HEAD:tflaim/seal-module'
check unknown-remote-sha 1 "pre-push: commit $h has author 'Bad <b@x>', must be '$W'." \
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
check republish-agent 1 "pre-push: commit $h has author '$CA', must be '$W'." \
  'git push -q origin origin/cursor/agent-1:refs/heads/tflaim/agent'
h=$(git rev-parse --short origin/scratch/junk)
check scratch-only-bad 1 "pre-push: commit $h has author 'Bad <b@x>', must be '$W'." \
  'git push -q origin origin/scratch/junk:refs/heads/tflaim/junk'
check could-not-list 1 'pre-push: could not list commits for refs/heads/tflaim/x. Fix: git fetch origin, then push again.' \
  "echo 'refs/heads/x 2222222222222222222222222222222222222222 refs/heads/tflaim/x 0000000000000000000000000000000000000000' | sh '$hooks/pre-push' origin '$tmp/remote.git'"
h=$(git rev-parse --short origin/main)
check no-main-ref-checks-all 1 "pre-push: commit $h has author 'Thomas Flaim <84033778+tflaim@users.noreply.github.com>', must be '$W'." \
  "git push -q '$tmp/remote.git' HEAD:tflaim/fresh"

# drop-cursor-trailer.sh runs from the dispatcher directory, beside the co-author hook.
drive_strip() {
  d=$(mktemp -d "$tmp/strip.XXXXXX")
  ln -s "$hooks/../.cursor/drop-cursor-trailer.sh" "$d/commit-msg.cursor.z-house"
  if [ "$2" != missing ]; then
    printf '%s\n' '#!/bin/bash' 'CO_AUTHORS=(' \
      "'Cursor Agent <cursoragent@cursor.com>'" \
      "'Thomas Flaim <tflaim@gmail.com>'" ')' > "$d/commit-msg.cursor.co-author"
    if [ "$2" = unreadable ]; then chmod 000 "$d/commit-msg.cursor.co-author"; fi
  fi
  cp "$3" "$d/msg"
  "$d/commit-msg.cursor.z-house" "$d/msg" 2>"$d/err"
  code=$?
  if [ "$code" -eq 0 ] && cmp -s "$d/msg" "$4"; then pass=$((pass+1)); else
    fail=$((fail+1)); printf 'FAIL %s\n  exit %s\n' "$1" "$code"; fi
}
cursor_line='Co-authored-by: Cursor Agent <cursoragent@cursor.com>'
thomas_line='Co-authored-by: Thomas Flaim <tflaim@gmail.com>'
printf 'Add a\n\n\n%s\n' "$cursor_line" > "$tmp/cursor-in"
printf 'Add a\n' > "$tmp/stripped"
drive_strip strip-cursor-agent-co-authors present "$tmp/cursor-in" "$tmp/stripped"
printf 'Add a\n\n\n%s\n' "$thomas_line" > "$tmp/thomas-in"
drive_strip strip-thomas-flaim-co-authors present "$tmp/thomas-in" "$tmp/stripped"
printf 'Add a\n\n\n%s\n' 'Co-authored-by: Pat Cursor Agent <pat@example.com>' > "$tmp/keep-cursor"
drive_strip keep-someone-with-cursor-agent present "$tmp/keep-cursor" "$tmp/keep-cursor"
printf 'Add a\n\n\n%s\n' 'Co-authored-by: Pat Thomas Flaim <pat@example.com>' > "$tmp/keep-thomas"
drive_strip keep-someone-with-thomas-flaim present "$tmp/keep-thomas" "$tmp/keep-thomas"
drive_strip missing-co-author-byte-identical missing "$tmp/cursor-in" "$tmp/cursor-in"
drive_strip unreadable-co-author-byte-identical unreadable "$tmp/cursor-in" "$tmp/cursor-in"

# start runs before the dispatcher directory exists; a detached waiter links z-house later.
root=$(CDPATH= cd "$hooks/.." && pwd)
late_top() {
  repo=$1
  git init -q -b main "$repo"
  mkdir -p "$repo/.cursor" "$repo/githooks"
  cp "$root/.cursor/install-githooks.sh" "$root/.cursor/drop-cursor-trailer.sh" "$repo/.cursor/"
  cp "$root/githooks/commit-msg" "$root/githooks/pre-push" "$repo/githooks/"
  chmod +x "$repo/.cursor/install-githooks.sh" "$repo/.cursor/drop-cursor-trailer.sh" \
    "$repo/githooks/commit-msg" "$repo/githooks/pre-push"
  top=$(git -C "$repo" rev-parse --show-toplevel)
  key=$(printf '%s' "$top" | cksum | awk '{print $1}')
  log=/tmp/install-githooks-z-house.$key.log
  lockdir=/tmp/install-githooks-z-house.$key.lock
  rm -rf "$lockdir"
  rm -f "$log"
}
late_stop() {
  if [ -f "$lockdir/pid" ]; then
    kill "$(cat "$lockdir/pid")" 2>/dev/null || true
  fi
  rm -rf "$lockdir"
  rm -f "$log"
}
wait_link() {
  i=0
  link=
  while [ "$i" -lt 40 ]; do
    link=$(readlink "$top/dispatcher/commit-msg.cursor.z-house" 2>/dev/null || true)
    if [ "$link" = "$top/.cursor/drop-cursor-trailer.sh" ]; then
      return
    fi
    link=
    sleep 0.2
    i=$((i+1))
  done
}

latedir=$(mktemp -d "$tmp/late.XXXXXX")
late_top "$latedir/unset"
t0=$(date +%s)
err=$(cd "$top" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
err2=$(cd "$top" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code2=$?
t1=$(date +%s)
elapsed=$((t1 - t0))
absent=0
[ ! -d "$top/dispatcher" ] && absent=1
sleep 1
git -C "$top" config core.hooksPath "$top/dispatcher"
mkdir -p "$top/stage"
printf '#!/bin/sh\nexit 0\n' > "$top/stage/commit-msg.cursor.co-author"
chmod +x "$top/stage/commit-msg.cursor.co-author"
mv "$top/stage" "$top/dispatcher"
wait_link
if [ "$code" -eq 0 ] && [ "$code2" -eq 0 ] && [ "$err" = "" ] && [ "$err2" = "" ] \
  && [ "$absent" -eq 1 ] && [ "$elapsed" -le 3 ] \
  && [ "$link" = "$top/.cursor/drop-cursor-trailer.sh" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL late-link-unset\n  code %s %s err [%s] [%s] absent %s elapsed %s link %s\n' \
    "$code" "$code2" "$err" "$err2" "$absent" "$elapsed" "$link"
fi
late_stop

late_top "$latedir/missing"
git -C "$top" config core.hooksPath "$top/dispatcher"
t0=$(date +%s)
err=$(cd "$top" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
t1=$(date +%s)
elapsed=$((t1 - t0))
absent=0
[ ! -d "$top/dispatcher" ] && absent=1
sleep 1
mkdir -p "$top/stage"
printf '#!/bin/sh\nexit 0\n' > "$top/stage/commit-msg.cursor.co-author"
chmod +x "$top/stage/commit-msg.cursor.co-author"
mv "$top/stage" "$top/dispatcher"
wait_link
if [ "$code" -eq 0 ] && [ "$err" = "" ] && [ "$absent" -eq 1 ] && [ "$elapsed" -le 2 ] \
  && [ "$link" = "$top/.cursor/drop-cursor-trailer.sh" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL late-link-missing-dir\n  code %s err [%s] absent %s elapsed %s link %s\n' \
    "$code" "$err" "$absent" "$elapsed" "$link"
fi
late_stop

late_top "$latedir/bad"
git -C "$top" config core.hooksPath "$top/dispatcher"
err=$(cd "$top" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
sleep 1
mkdir -p "$top/stage"
printf '#!/bin/sh\nexit 0\n' > "$top/stage/commit-msg.cursor.zz-co-author"
chmod +x "$top/stage/commit-msg.cursor.zz-co-author"
mv "$top/stage" "$top/dispatcher"
want='install-githooks: commit-msg.cursor.z-house sorts before commit-msg.cursor.zz-co-author'
i=0
logged=0
while [ "$i" -lt 40 ]; do
  if [ -f "$log" ] && grep -qx "$want" "$log"; then
    logged=1
    break
  fi
  sleep 0.2
  i=$((i+1))
done
if [ "$code" -eq 0 ] && [ "$err" = "" ] && [ "$logged" -eq 1 ] \
  && [ ! -e "$top/dispatcher/commit-msg.cursor.z-house" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL late-sort-fail\n  code %s err [%s] logged %s\n' "$code" "$err" "$logged"
  cat "$log" 2>/dev/null || true
fi
late_stop

echo "githooks: $pass passed, $fail failed"
[ "$fail" = 0 ]
