#!/bin/sh
# Install waybook into a virtualenv and symlink it onto ~/.local/bin.
# Safe to re-run. A symlink that points into this install's venv is repaired.
# An existing directory is reused only when it has pyvenv.cfg, its interpreter
# is a virtualenv (sys.prefix != sys.base_prefix), and that interpreter's
# version matches the Python selected for this run. Otherwise a real venv is
# rebuilt, and a foreign directory is left alone unless --force is given.
#
# Interpreter order: --python or WAYBOOK_PYTHON, then python3.13, python3.12,
# and python3.11 on PATH, then python3 when it is 3.11 or newer.
set -eu

force=0
python_override=""
python_from_flag=0

while [ $# -gt 0 ]; do
  case "$1" in
    --force) force=1 ;;
    --python)
      shift
      if [ $# -eq 0 ] || [ -z "${1:-}" ]; then
        echo "--python requires a path" >&2
        exit 2
      fi
      python_override=$1
      python_from_flag=1
      ;;
    --python=*)
      python_override=${1#--python=}
      if [ -z "$python_override" ]; then
        echo "--python requires a path" >&2
        exit 2
      fi
      python_from_flag=1
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
  shift
done

if [ "$python_from_flag" -eq 0 ] && [ -n "${WAYBOOK_PYTHON:-}" ]; then
  python_override=$WAYBOOK_PYTHON
fi

if [ -z "${HOME:-}" ]; then
  echo "HOME is not set" >&2
  exit 1
fi

ROOT=$(CDPATH= cd -- "$(dirname "$0")" && pwd)
bin_dir="$HOME/.local/bin"
venv="$HOME/.local/share/waybook/venv"
link="$bin_dir/waybook"
target="$venv/bin/waybook"
python=""

warn_path() {
  case ":${PATH}:" in
    *":${bin_dir}:"*) ;;
    *)
      echo "warning: ${bin_dir} is not on PATH" >&2
      ;;
  esac
}

refuse() {
  echo "refusing to overwrite $1; pass --force" >&2
  warn_path
  exit 1
}

python_version() {
  "$1" -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null
}

meets_minimum() {
  local ver major rest minor
  ver=$(python_version "$1") || return 1
  case "$ver" in
    [0-9]*.[0-9]*.[0-9]*) ;;
    *) return 1 ;;
  esac
  major=${ver%%.*}
  rest=${ver#*.}
  minor=${rest%%.*}
  case "$major$minor" in
    *[!0-9]*) return 1 ;;
  esac
  if [ "$major" -gt 3 ]; then
    return 0
  fi
  [ "$major" -eq 3 ] && [ "$minor" -ge 11 ]
}

describe_found() {
  local label exe ver
  label=$1
  exe=$2
  if ver=$(python_version "$exe"); then
    echo "Found ${label}: ${ver}" >&2
  else
    echo "Found ${label}: could not read a version" >&2
  fi
}

explain_override_failure() {
  local ver
  echo "waybook requires Python 3.11 or newer." >&2
  if ver=$(python_version "$python_override"); then
    echo "Requested interpreter ${python_override} is ${ver}, which is not Python 3.11 or newer." >&2
  else
    echo "Requested interpreter ${python_override} could not be run." >&2
  fi
  echo "Re-run with --python /path/to/python3.11 (or set WAYBOOK_PYTHON) pointing at Python 3.11 or newer." >&2
  exit 1
}

explain_search_failure() {
  local found name resolved
  echo "waybook requires Python 3.11 or newer." >&2
  echo "No suitable interpreter was found." >&2
  found=0
  for name in python3.13 python3.12 python3.11 python3; do
    if resolved=$(command -v "$name" 2>/dev/null); then
      describe_found "${name} (${resolved})" "$resolved"
      found=1
    fi
  done
  if [ "$found" -eq 0 ]; then
    echo "No Python interpreter was found on PATH." >&2
  fi
  echo "Install Python 3.11 or newer, or re-run with --python /path/to/python3.11 (or set WAYBOOK_PYTHON)." >&2
  exit 1
}

select_python() {
  local name resolved
  if [ -n "$python_override" ]; then
    if meets_minimum "$python_override"; then
      python=$python_override
      return 0
    fi
    explain_override_failure
  fi
  for name in python3.13 python3.12 python3.11 python3; do
    if resolved=$(command -v "$name" 2>/dev/null) && meets_minimum "$resolved"; then
      python=$resolved
      return 0
    fi
  done
  explain_search_failure
}

link_inside_venv() {
  [ -L "$link" ] || return 1
  WAYBOOK_LINK="$link" WAYBOOK_VENV="$venv" "$python" - <<'PY'
import os
import sys

link = os.environ["WAYBOOK_LINK"]
dest = os.readlink(link)
if not os.path.isabs(dest):
    dest = os.path.join(os.path.dirname(link), dest)
dest = os.path.normpath(dest)
venv = os.path.normpath(os.environ["WAYBOOK_VENV"])
inside = dest == venv or dest.startswith(venv + os.sep)
sys.exit(0 if inside else 1)
PY
}

venv_python_runs() {
  [ -x "$venv/bin/python" ] || return 1
  "$venv/bin/python" -c 'import sys' >/dev/null 2>&1
}

# A directory with a runnable bin/python is not enough. pyvenv.cfg and an
# interpreter whose prefix differs from its base prefix are what make it a venv.
venv_is_isolated() {
  [ -d "$venv" ] || return 1
  [ -L "$venv" ] && return 1
  [ -f "$venv/pyvenv.cfg" ] || return 1
  venv_python_runs || return 1
  "$venv/bin/python" -c 'import sys; raise SystemExit(0 if sys.prefix != sys.base_prefix else 1)' >/dev/null 2>&1
}

venv_version_matches() {
  local want got
  want=$(python_version "$python") || return 1
  got=$(python_version "$venv/bin/python") || return 1
  [ "$want" = "$got" ]
}

select_python

if [ -L "$link" ]; then
  if link_inside_venv; then
    :
  elif [ "$force" -ne 1 ]; then
    refuse "$link"
  fi
elif [ -e "$link" ]; then
  if [ "$force" -ne 1 ]; then
    refuse "$link"
  fi
fi

if [ -e "$venv" ] || [ -L "$venv" ]; then
  if [ -d "$venv" ] && [ ! -L "$venv" ] && venv_is_isolated && venv_version_matches; then
    :
  elif [ -d "$venv" ] && [ ! -L "$venv" ] && [ -f "$venv/pyvenv.cfg" ]; then
    if venv_python_runs && venv_is_isolated; then
      got=$(python_version "$venv/bin/python" || true)
      echo "warning: rebuilding ${venv} because its Python ${got:-unknown} does not match $(python_version "$python")" >&2
    elif venv_python_runs; then
      echo "warning: rebuilding ${venv} because ${venv}/bin/python is not a virtualenv interpreter" >&2
    else
      echo "warning: rebuilding ${venv} because ${venv}/bin/python does not run" >&2
    fi
    rm -rf "$venv"
  elif [ "$force" -ne 1 ]; then
    refuse "$venv"
  else
    echo "warning: removing ${venv} because it is not a virtualenv" >&2
    rm -rf "$venv"
  fi
fi

mkdir -p "$bin_dir" "$(dirname "$venv")"

if [ ! -x "$venv/bin/python" ]; then
  "$python" -m venv "$venv"
fi

"$venv/bin/python" -m pip install --disable-pip-version-check --no-cache-dir "$ROOT"

if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
  warn_path
  exit 0
fi
if [ -e "$link" ] || [ -L "$link" ]; then
  rm -f "$link"
fi
ln -s "$target" "$link"
warn_path
