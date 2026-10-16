#!/bin/sh
set -eu

top=$(git rev-parse --show-toplevel)
cd "$top"
src=$(CDPATH= cd "$top/githooks" && pwd)
dest=$(git rev-parse --git-path hooks)
case $dest in
  /*) ;;
  *) dest=$top/$dest ;;
esac

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
  td=$(mktemp -d)
  has_co=0
  for f in "$dispatcher"/commit-msg.cursor*; do
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
      exit 1
    fi
  fi
  rm -rf "$td"
  ln -sfn "$top/.cursor/drop-cursor-trailer.sh" "$dispatcher/commit-msg.cursor.z-house"
fi
