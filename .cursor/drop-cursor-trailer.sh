#!/bin/sh
f=$1
tmp=$1.drop
dir=$(CDPATH= cd "$(dirname "$0")" && pwd)
lines=
for c in "$dir"/commit-msg.cursor*co-author*; do
  [ -f "$c" ] || continue
  got=$(awk '
    function take(s,   v) {
      while (1) {
        if (match(s, /\047[^\047]*\047/)) {
          v = substr(s, RSTART + 1, RLENGTH - 2)
          if (v != "") print "Co-authored-by: " v
          s = substr(s, RSTART + RLENGTH)
          continue
        }
        if (match(s, /"[^"]*"/)) {
          v = substr(s, RSTART + 1, RLENGTH - 2)
          if (v != "") print "Co-authored-by: " v
          s = substr(s, RSTART + RLENGTH)
          continue
        }
        break
      }
    }
    index($0, "CO_AUTHORS=(") { grab = 1 }
    grab {
      s = $0
      if (index(s, "CO_AUTHORS=(")) sub(/.*CO_AUTHORS=\(/, "", s)
      cut = index(s, ")")
      if (cut > 0) s = substr(s, 1, cut - 1)
      take(s)
      if (cut > 0) exit
    }
  ' "$c")
  if [ -n "$got" ]; then
    lines=${lines:+$lines
}$got
  fi
done
if [ -z "$lines" ]; then
  exit 0
fi
printf '%s\n' "$lines" > "$tmp.list"
awk '
  function blank(s) { return s ~ /^[[:space:]]*$/ }
  NR == FNR { if ($0 != "") exact[$0] = 1; next }
  { line[++n] = $0 }
  END {
    if (n == 0) exit 2
    last = n
    while (last > 0 && blank(line[last])) last--
    if (last == 0 || !exact[line[last]]) exit 2
    endat = last - 1
    while (endat >= 1 && blank(line[endat])) endat--
    for (i = 1; i <= endat; i++) print line[i]
  }
' "$tmp.list" "$f" > "$tmp"
st=$?
rm -f "$tmp.list"
if [ "$st" -eq 2 ]; then
  rm -f "$tmp"
  exit 0
fi
if [ "$st" -ne 0 ]; then
  rm -f "$tmp"
  exit "$st"
fi
mv "$tmp" "$f"
