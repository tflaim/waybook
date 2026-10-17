#!/bin/sh
set -eu

link_z_house() {
  d=$1
  td=$(mktemp -d)
  has_co=0
  for f in "$d"/commit-msg.cursor*; do
    [ -e "$f" ] || continue
    b=$(basename "$f")
    : > "$td/$b"
    case $b in
      *co-author*) has_co=1 ;;
    esac
  done
  if [ "$has_co" -eq 1 ]; then
    : > "$td/commit-msg.cursor.z-house"
    bad=$(bash -c '
      shopt -s nullglob
      z=0
      i=0
      last=0
      name=
      for h in "$1"/commit-msg.cursor*; do
        i=$((i + 1))
        b=${h##*/}
        case $b in
          *co-author*) last=$i; name=$b ;;
        esac
        if [ "$b" = commit-msg.cursor.z-house ]; then
          z=$i
        fi
      done
      if [ "$last" -gt 0 ] && [ "$z" -le "$last" ]; then
        printf "%s\n" "$name"
      fi
    ' bash "$td")
    if [ -n "$bad" ]; then
      rm -rf "$td"
      echo "install-githooks: commit-msg.cursor.z-house sorts before $bad" >&2
      return 1
    fi
  fi
  rm -rf "$td"
  ln -sfn "$top/.cursor/drop-cursor-trailer.sh" "$d/commit-msg.cursor.z-house"
}

if [ "${1:-}" = --wait-z-house ]; then
  top=$2
  lockdir=$3
  cd "$top"
  if ! mkdir "$lockdir" 2>/dev/null; then
    old=$(cat "$lockdir/pid" 2>/dev/null || true)
    if [ -z "$old" ] || kill -0 "$old" 2>/dev/null; then
      exit 0
    fi
    rm -rf "$lockdir"
    mkdir "$lockdir" 2>/dev/null || exit 0
  fi
  echo $$ > "$lockdir/pid"
  trap 'rm -rf "$lockdir"' EXIT INT TERM
  deadline=$(( $(date +%s) + 300 ))
  while :; do
    dispatcher=$(git config --get core.hooksPath || true)
    if [ -n "$dispatcher" ] && [ -d "$dispatcher" ]; then
      break
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
      echo "install-githooks: core.hooksPath did not name an existing directory within 300s" >&2
      exit 1
    fi
    sleep 0.2
  done
  link_z_house "$dispatcher"
  exit 0
fi

top=$(git rev-parse --show-toplevel)
cd "$top"
src=$(CDPATH= cd "$top/githooks" && pwd)
gitdir=$(git rev-parse --git-dir)
case $gitdir in
  /*) ;;
  *) gitdir=$top/$gitdir ;;
esac
dest=$gitdir/hooks

dispatcher=$(git config --get core.hooksPath || true)
if [ -n "$dispatcher" ] && [ -f "$dispatcher/.cursor-original-hooks-path" ]; then
  chained=$(tr -d '[:space:]' < "$dispatcher/.cursor-original-hooks-path")
  if [ -n "$chained" ]; then
    dest=$chained
  fi
fi
mkdir -p "$dest"
dest=$(CDPATH= cd "$dest" && pwd)

names='applypatch-msg pre-applypatch post-applypatch pre-commit pre-merge-commit prepare-commit-msg commit-msg post-commit pre-rebase post-checkout post-merge pre-push pre-receive update proc-receive post-receive post-update reference-transaction push-to-checkout pre-auto-gc post-rewrite sendemail-validate fsmonitor-watchman post-index-change'

for name in $names; do
  [ -f "$src/$name" ] || continue
  if [ "$src" != "$dest" ]; then
    ln -sfn "$src/$name" "$dest/$name"
  fi
  if [ -z "$dispatcher" ] || [ ! -d "$dispatcher" ] || [ -e "$dispatcher/$name" ]; then
    continue
  fi
  if [ -L "$dispatcher/commit-msg" ]; then
    ln -s "$(readlink "$dispatcher/commit-msg")" "$dispatcher/$name"
  elif [ -e "$dispatcher/.dispatcher" ]; then
    ln -s .dispatcher "$dispatcher/$name"
  fi
done

if [ -n "$dispatcher" ] && [ -d "$dispatcher" ]; then
  link_z_house "$dispatcher"
else
  key=$(printf '%s' "$top" | cksum | awk '{print $1}')
  lockdir=/tmp/install-githooks-z-house.$key.lock
  log=/tmp/install-githooks-z-house.$key.log
  self=$(CDPATH= cd "$(dirname "$0")" && pwd)/$(basename "$0")
  (nohup setsid sh "$self" --wait-z-house "$top" "$lockdir" >>"$log" 2>&1 </dev/null &)
fi
