# Sourced from githooks/test.sh. pass and fail are the caller's counters.
hooks=${hooks:-$(CDPATH= cd "$(dirname "$0")" && pwd)}
root=$(CDPATH= cd "$hooks/.." && pwd)
drop=$root/.cursor/drop-cursor-trailer.sh
same() {
  if cmp -s "$1" "$2"; then pass=$((pass+1)); else
    fail=$((fail+1)); printf 'FAIL %s\n' "$3"; diff -u "$1" "$2" || true; fi
}
co_script() {
  cat <<EOF
#!/bin/bash
CO_AUTHORS=(
'$1'
)
for CO_AUTHOR in "\${CO_AUTHORS[@]}"; do
echo "Co-authored-by: \$CO_AUTHOR"
done
EOF
}
run_drop() {
  wd=$(mktemp -d)
  printf '%s\n' "$1" > "$wd/commit-msg.cursor.co-author"
  ln -s "$drop" "$wd/commit-msg.cursor.z-house"
  cp "$2" "$wd/msg"
  sh "$wd/commit-msg.cursor.z-house" "$wd/msg"
  same "$3" "$wd/msg" "$4"
  rm -rf "$wd"
}

d=$(mktemp -d)
cursor='Cursor Agent <cursoragent@cursor.com>'
thomas='Thomas Flaim <tflaim@users.noreply.github.com>'
printf 'Line one.\n\nLine two keeps  trailing spaces.  \n' > "$d/body"
cp "$d/body" "$d/with-cursor"
printf '\nCo-authored-by: %s\n' "$cursor" >> "$d/with-cursor"
run_drop "$(co_script "$cursor")" "$d/with-cursor" "$d/body" strip-cursor-agent

printf 'Record the cloud hook install\n' > "$d/thomas-body"
cp "$d/thomas-body" "$d/with-thomas"
printf '\nCo-authored-by: %s\n' "$thomas" >> "$d/with-thomas"
run_drop "$(co_script "$thomas")" "$d/with-thomas" "$d/thomas-body" strip-thomas-flaim

printf 'Record the cloud hook install\n\nCo-authored-by: Pat <pat@example.com>\n' > "$d/other"
cp "$d/other" "$d/other-want"
run_drop "$(co_script "$thomas")" "$d/other" "$d/other-want" keep-unrelated

printf 'Record the cloud hook install\n\nCo-authored-by: %s\n' "$thomas" > "$d/unknown"
cp "$d/unknown" "$d/unknown-want"
run_drop '#!/bin/bash' "$d/unknown" "$d/unknown-want" unknown-trailer-unchanged

printf 'Line one.\n\nCo-authored-by: Pat <pat@example.com>\nCo-authored-by: %s\n' "$cursor" > "$d/mix"
printf 'Line one.\n\nCo-authored-by: Pat <pat@example.com>\n' > "$d/mix-want"
run_drop "$(co_script "$cursor")" "$d/mix" "$d/mix-want" strip-trailing-keep-other

both=$(printf '%s\n' '#!/bin/bash' 'CO_AUTHORS=(' "'$cursor'" "'$thomas'" ')')
printf 'Line one.\n\nCo-authored-by: %s\n\nCo-authored-by: %s\n' "$cursor" "$thomas" > "$d/both"
printf 'Line one.\n' > "$d/both-want"
run_drop "$both" "$d/both" "$d/both-want" strip-every-trailing-co-author

printf 'Line one.\n\nCo-authored-by: %s\nCo-authored-by: Pat <pat@example.com>\n' "$cursor" > "$d/mid"
cp "$d/mid" "$d/mid-want"
run_drop "$(co_script "$cursor")" "$d/mid" "$d/mid-want" keep-exact-not-trailing

printf 'Record the cloud hook install\n' > "$d/plain"
printf 'Record the cloud hook install\n\n\nCo-authored-by: %s\n' "$cursor" > "$d/cursor-in"
run_drop "$(co_script "$cursor")" "$d/cursor-in" "$d/plain" strip-cursor-agent-co-authors
printf 'Record the cloud hook install\n\n\nCo-authored-by: %s\n' "$thomas" > "$d/thomas-in"
run_drop "$(co_script "$thomas")" "$d/thomas-in" "$d/plain" strip-thomas-flaim-co-authors

printf 'Note the hook.\n\nCo-authored-by: Someone <x@y.z>\n' > "$d/someone"
cp "$d/someone" "$d/someone-want"
run_drop "$(co_script "$cursor")" "$d/someone" "$d/someone-want" keep-someone-with-cursor-agent
run_drop "$(co_script "$thomas")" "$d/someone" "$d/someone-want" keep-someone-with-thomas-flaim

printf 'Keep bytes.\n\nCo-authored-by: Someone <x@y.z>' > "$d/raw"
cp "$d/raw" "$d/raw-want"
wd=$(mktemp -d)
ln -s "$drop" "$wd/commit-msg.cursor.z-house"
cp "$d/raw" "$wd/msg"
sh "$wd/commit-msg.cursor.z-house" "$wd/msg"
same "$d/raw-want" "$wd/msg" missing-co-author-byte-identical
rm -rf "$wd"

wd=$(mktemp -d)
printf '%s\n' '#!/bin/bash' 'CO_AUTHORS=(' "'$thomas'" ')' > "$wd/commit-msg.cursor.co-author"
chmod 000 "$wd/commit-msg.cursor.co-author"
ln -s "$drop" "$wd/commit-msg.cursor.z-house"
cp "$d/raw" "$wd/msg"
sh "$wd/commit-msg.cursor.z-house" "$wd/msg"
same "$d/raw-want" "$wd/msg" unreadable-co-author-byte-identical
chmod u+r "$wd/commit-msg.cursor.co-author" 2>/dev/null || true
rm -rf "$wd"
rm -rf "$d"

mkdisp() {
  repo=$1
  co=$2
  git init -q -b main "$repo"
  mkdir -p "$repo/.cursor" "$repo/githooks" "$repo/dispatcher"
  cp "$root/.cursor/install-githooks.sh" "$root/.cursor/drop-cursor-trailer.sh" "$repo/.cursor/"
  cp "$root/githooks/commit-msg" "$root/githooks/pre-push" "$root/githooks/attribution.sh" "$repo/githooks/"
  chmod +x "$repo/.cursor/drop-cursor-trailer.sh" "$repo/githooks/commit-msg" "$repo/githooks/pre-push"
  printf '#!/bin/sh\nexit 0\n' > "$repo/dispatcher/.dispatcher"
  chmod +x "$repo/dispatcher/.dispatcher"
  ln -s .dispatcher "$repo/dispatcher/commit-msg"
  printf '#!/bin/sh\nexit 0\n' > "$repo/dispatcher/$co"
  chmod +x "$repo/dispatcher/$co"
  printf '%s\n' "$repo/.git/hooks" > "$repo/dispatcher/.cursor-original-hooks-path"
  git -C "$repo" config core.hooksPath "$repo/dispatcher"
}

sortdir=$(cd "$(mktemp -d)" && pwd -P)
mkdisp "$sortdir/bad" commit-msg.cursor.zz-co-author
err=$(cd "$sortdir/bad" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
want='install-githooks: commit-msg.cursor.z-house sorts before commit-msg.cursor.zz-co-author'
if [ "$code" -eq 1 ] && [ "$err" = "$want" ] && [ ! -e "$sortdir/bad/dispatcher/commit-msg.cursor.z-house" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL sort-before\n  want 1 %s\n  got  %s %s\n' "$want" "$code" "$err"
fi

mkdisp "$sortdir/ok" commit-msg.cursor.co-author
err=$(cd "$sortdir/ok" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
link=$(readlink "$sortdir/ok/dispatcher/commit-msg.cursor.z-house" 2>/dev/null || true)
if [ "$code" -eq 0 ] && [ "$err" = "" ] && [ "$link" = "$sortdir/ok/.cursor/drop-cursor-trailer.sh" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL sort-after\n  want 0 link %s\n  got  %s %s link %s\n' \
    "$sortdir/ok/.cursor/drop-cursor-trailer.sh" "$code" "$err" "$link"
fi
rm -rf "$sortdir"

late_top() {
  repo=$1
  git init -q -b main "$repo"
  mkdir -p "$repo/.cursor" "$repo/githooks"
  cp "$root/.cursor/install-githooks.sh" "$root/.cursor/drop-cursor-trailer.sh" "$repo/.cursor/"
  cp "$root/githooks/commit-msg" "$root/githooks/pre-push" "$root/githooks/attribution.sh" "$repo/githooks/"
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

latedir=$(mktemp -d)
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

late_top "$latedir/nosetsid"
git -C "$top" config core.hooksPath "$top/dispatcher"
bindir=$(mktemp -d)
for b in sh bash git nohup mkdir ln rm basename dirname date sleep cksum awk mktemp cat tr; do
  ln -s "$(command -v "$b")" "$bindir/$b"
done
want=$top/.cursor/drop-cursor-trailer.sh
found=$(PATH="$bindir" command -v setsid 2>/dev/null || true)
t0=$(date +%s)
err=$(cd "$top" && PATH="$bindir" sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
t1=$(date +%s)
elapsed=$((t1 - t0))
absent=0
[ ! -d "$top/dispatcher" ] && absent=1
sleep 1
mkdir -p "$top/dispatcher"
wait_link
if [ "$found" = "" ] && [ "$code" -eq 0 ] && [ "$err" = "" ] && [ "$absent" -eq 1 ] \
  && [ "$elapsed" -le 2 ] && [ "$link" = "$want" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL late-link-no-setsid\n  found [%s] code %s err [%s] absent %s elapsed %s link %s want %s\n' \
    "$found" "$code" "$err" "$absent" "$elapsed" "$link" "$want"
fi
late_stop

late_top "$latedir/term"
sh "$top/.cursor/install-githooks.sh" --wait-z-house "$top" "$lockdir" >>"$log" 2>&1 &
wpid=$!
i=0
pid=
state=
while [ "$i" -lt 25 ]; do
  if [ -f "$lockdir/pid" ]; then
    pid=$(cat "$lockdir/pid")
    break
  fi
  sleep 0.1
  i=$((i+1))
done
if [ -n "$pid" ]; then
  sleep 0.2
  kill -TERM "$pid" 2>/dev/null || true
  i=0
  while [ "$i" -lt 25 ]; do
    state=$(ps -p "$pid" -o state= 2>/dev/null | awk '{print substr($1,1,1)}')
    case $state in
      ""|Z) break ;;
    esac
    sleep 0.1
    i=$((i+1))
  done
  case $state in
    ""|Z) ;;
    *) kill -KILL "$pid" 2>/dev/null || true ;;
  esac
else
  kill -KILL "$wpid" 2>/dev/null || true
fi
wait "$wpid"
status=$?
lockgone=0
[ ! -e "$lockdir" ] && lockgone=1
if [ "$pid" = "$wpid" ] && [ "$status" -eq 0 ] && [ "$lockgone" -eq 1 ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL late-term-exit\n  pid %s wpid %s status %s lockgone %s state [%s]\n' \
    "$pid" "$wpid" "$status" "$lockgone" "$state"
  cat "$log" 2>/dev/null || true
fi
late_stop
rm -rf "$bindir"
rm -rf "$latedir"

disp_snap() {
  (cd "$1" && find . ! -type d -print | LC_ALL=C sort | while IFS= read -r f; do
    if [ -L "$f" ]; then
      printf 'L %s %s\n' "$f" "$(readlink "$f")"
    else
      printf 'F %s %s\n' "$f" "$(cksum "$f" | awk '{print $1,$2}')"
    fi
  done)
}
dispdir=$(mktemp -d)
git init -q --bare -b main "$dispdir/remote.git"
repo=$dispdir/w
git init -q -b main "$repo"
mkdir -p "$repo/.cursor" "$repo/githooks" "$repo/dispatcher"
cp "$root/.cursor/install-githooks.sh" "$root/.cursor/drop-cursor-trailer.sh" "$repo/.cursor/"
cp "$root/githooks/commit-msg" "$root/githooks/pre-push" "$root/githooks/attribution.sh" "$repo/githooks/"
chmod +x "$repo/.cursor/install-githooks.sh" "$repo/.cursor/drop-cursor-trailer.sh" \
  "$repo/githooks/commit-msg" "$repo/githooks/pre-push"
cat > "$repo/dispatcher/.dispatcher" << EOF
#!/bin/sh
exec "$repo/.git/hooks/\$(basename "\$0")" "\$@"
EOF
chmod +x "$repo/dispatcher/.dispatcher"
printf '#!/bin/sh\n# sample\n' > "$repo/dispatcher/pre-push.sample"
printf '#!/bin/sh\nexit 0\n' > "$repo/dispatcher/commit-msg"
chmod +x "$repo/dispatcher/commit-msg"
git -C "$repo" config user.name 'Thomas Flaim'
git -C "$repo" config user.email tflaim@gmail.com
git -C "$repo" config core.hooksPath "$repo/dispatcher"
git -C "$repo" remote add origin "$dispdir/remote.git"
echo a > "$repo/a"
git -C "$repo" add a
git -C "$repo" commit -qm 'Add a'
err=$(cd "$repo" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
link=$(readlink "$repo/dispatcher/pre-push" 2>/dev/null || true)
kept=$(cat "$repo/dispatcher/commit-msg")
perr=$(git -C "$repo" push --dry-run origin HEAD:main 2>&1 >/dev/null)
pcode=$?
want_keep='#!/bin/sh
exit 0'
if [ "$code" -eq 0 ] && [ "$err" = "" ] && [ "$link" = ".dispatcher" ] \
  && [ "$pcode" -ne 0 ] && printf '%s\n' "$perr" | grep -F "pre-push: refusing to push to 'main'" >/dev/null \
  && [ "$kept" = "$want_keep" ] && [ ! -L "$repo/dispatcher/commit-msg" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL dispatcher-pre-push\n  code %s err [%s] link %s pcode %s kept [%s]\n  %s\n' \
    "$code" "$err" "$link" "$pcode" "$kept" "$perr"
fi
before=$(disp_snap "$repo/dispatcher")
err2=$(cd "$repo" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code2=$?
after=$(disp_snap "$repo/dispatcher")
kept2=$(cat "$repo/dispatcher/commit-msg")
if [ "$code2" -eq 0 ] && [ "$err2" = "" ] && [ "$kept2" = "$want_keep" ] && [ "$before" = "$after" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL dispatcher-idempotent\n  code %s err [%s] kept [%s]\n' "$code2" "$err2" "$kept2"
  printf 'BEFORE\n%s\nAFTER\n%s\n' "$before" "$after"
fi
rm -rf "$dispdir"

latedisp=$(mktemp -d)
git init -q --bare -b main "$latedisp/remote.git"
late_top "$latedisp/w"
git -C "$top" config user.name 'Thomas Flaim'
git -C "$top" config user.email tflaim@gmail.com
git -C "$top" remote add origin "$latedisp/remote.git"
echo a > "$top/a"
git -C "$top" add a
git -C "$top" commit -qm 'Add a'
git -C "$top" config core.hooksPath "$top/dispatcher"
err=$(cd "$top" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
code=$?
mkdir -p "$top/stage"
cat > "$top/stage/.dispatcher" << EOF
#!/bin/sh
exec "$top/.git/hooks/\$(basename "\$0")" "\$@"
EOF
chmod +x "$top/stage/.dispatcher"
printf '#!/bin/sh\n# sample\n' > "$top/stage/pre-push.sample"
printf '#!/bin/sh\nexit 0\n' > "$top/stage/commit-msg"
chmod +x "$top/stage/commit-msg"
mv "$top/stage" "$top/dispatcher"
i=0
link=
while [ "$i" -lt 40 ]; do
  link=$(readlink "$top/dispatcher/pre-push" 2>/dev/null || true)
  if [ "$link" = ".dispatcher" ]; then
    break
  fi
  link=
  sleep 0.2
  i=$((i+1))
done
kept=$(cat "$top/dispatcher/commit-msg")
perr=$(git -C "$top" push --dry-run origin HEAD:main 2>&1 >/dev/null)
pcode=$?
want_keep='#!/bin/sh
exit 0'
if [ "$code" -eq 0 ] && [ "$err" = "" ] && [ "$link" = ".dispatcher" ] \
  && [ "$pcode" -ne 0 ] && printf '%s\n' "$perr" | grep -F "pre-push: refusing to push to 'main'" >/dev/null \
  && [ "$kept" = "$want_keep" ] && [ ! -L "$top/dispatcher/commit-msg" ]; then
  pass=$((pass+1))
else
  fail=$((fail+1))
  printf 'FAIL late-dispatcher-pre-push\n  code %s err [%s] link %s pcode %s kept [%s]\n  %s\n' \
    "$code" "$err" "$link" "$pcode" "$kept" "$perr"
  cat "$log" 2>/dev/null || true
fi
late_stop
rm -rf "$latedisp"

id_repo() {
  repo=$1
  git init -q -b main "$repo"
  mkdir -p "$repo/.cursor" "$repo/githooks" "$repo/dispatcher"
  cp "$root/.cursor/install-githooks.sh" "$root/.cursor/drop-cursor-trailer.sh" "$repo/.cursor/"
  cp "$root/githooks/commit-msg" "$root/githooks/pre-push" "$root/githooks/attribution.sh" "$repo/githooks/"
  chmod +x "$repo/.cursor/install-githooks.sh" "$repo/.cursor/drop-cursor-trailer.sh" \
    "$repo/githooks/commit-msg" "$repo/githooks/pre-push"
  git -C "$repo" config core.hooksPath "$repo/dispatcher"
}
id_check() {
  label=$1
  want_name=$2
  want_email=$3
  err=$(cd "$repo" && sh .cursor/install-githooks.sh 2>&1 >/dev/null)
  code=$?
  got_name=$(git -C "$repo" config --local --get user.name || true)
  got_email=$(git -C "$repo" config --local --get user.email || true)
  if [ "$code" -eq 0 ] && [ "$err" = "" ] && [ "$got_name" = "$want_name" ] && [ "$got_email" = "$want_email" ]; then
    pass=$((pass+1))
  else
    fail=$((fail+1))
    printf 'FAIL %s\n  want 0 %s %s\n  got  %s [%s] %s %s\n' \
      "$label" "$want_name" "$want_email" "$code" "$err" "$got_name" "$got_email"
  fi
}
iddir=$(mktemp -d)
id_repo "$iddir/unset"
id_check id-unset 'Thomas Flaim' tflaim@gmail.com
id_repo "$iddir/cursor"
git -C "$repo" config user.name 'Cursor Agent'
git -C "$repo" config user.email 'cursoragent@cursor.com'
id_check id-cursor 'Thomas Flaim' tflaim@gmail.com
id_repo "$iddir/other"
git -C "$repo" config user.name 'Pat Example'
git -C "$repo" config user.email 'pat@example.com'
id_check id-other 'Pat Example' pat@example.com
rm -rf "$iddir"
