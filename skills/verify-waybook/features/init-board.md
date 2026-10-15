# Initialize a board

Initialize a board creates a usable `.waybook/` in an empty project so later commands can add and read entries.

## Sub-features

- `init-empty` creates schema v2 config, empty board sections, index, and logs.
- `init-project-id` records the given `project_id` for PR links.
- `init-already` refuses a second `init` on the same board with exit `2` and `already initialized`.

## How to get to it (user POV)

- Run `waybook init --project-id <owner/name>` from inside the project directory.
- Run `waybook --project <path> init --project-id <owner/name>` targeting a project path.

## Driving it with control-waybook

Preconditions:

- No prior run with the same `--run-id`, or it was cleaned up.
- `control-waybook` is on `PATH`.
- Launch **without** `--seed` so init is the feature under test.

- **Launch empty project + init.** Run `control-waybook launch --run-id init-board --project-id verify/demo` then `export WAYBOOK_VERIFY_RUN_ID=init-board`. Stdout includes `initialized` and paths; `.waybook/config.toml` exists.
- **Doctor.** Run `control-waybook doctor`. Output ends with `doctor: READY` and `schema_version=2`.
- **Confirm usable.** Run `control-waybook record list-empty -- list`. Exit `0`; human list has no entry rows (header only) or an empty entries payload with `--json`.
- **Confirm verify.** Run `control-waybook record verify-fresh -- verify`. Exit `0`; stdout is `ok`.
- **Refuse second init.** Run `control-waybook record init-again -- init --project-id verify/demo`. Exit `2`; stderr contains `already initialized`.
- **Init via `--project`.** Create an empty directory beside the launched project and run `waybook --project <path> init --project-id verify/other` from a cwd that has no board. Exit `0`; stdout contains `initialized`; `<path>/.waybook/config.toml` contains `project_id = "verify/other"`. Do not use `control-waybook cli` for this: that cwd is already a board, and init of a different path is denied.

```sh
project=$(control-waybook paths | awk -F= '/^project=/{print $2}')
repo=$(control-waybook paths | awk -F= '/^repo=/{print $2}')
if [ -z "$project" ] || [ -z "$repo" ]; then
  echo "control-waybook paths returned an empty path" >&2
  exit 1
fi
target=$(dirname "$project")/project-flag
mkdir -p "$target"
cwd=$(mktemp -d)
(
  cd "$cwd"
  PYTHONPATH="$repo${PYTHONPATH:+:$PYTHONPATH}" \
  WAYBOOK_AGENT=verifier \
  WAYBOOK_NOW=2026-10-13T12:00:00Z \
    python3 -m waybook --project "$target" init --project-id verify/other
)
```

- **Proof.** Run `control-waybook snapshot init-board`. Evidence under `/tmp/waybook-verify-evidence/init-board/` contains `cli-state.txt`, the refuse transcript, and a `dot-waybook/` copy with `config.toml`, `index.md`, and `log/writes.jsonl`.

## Gotchas

- Launch already runs `init`. To prove init itself, use `launch` without treating `--seed` adds as part of this feature.
- `--project` init of a different directory is denied when the cwd is already a Waybook project. Run that entry point from a directory with no board. `control-waybook cli` always starts in the launched board.
- `project_id` must look like a real `owner/name` if later proofs use `--link pr:N`.
- Do not initialize inside the waybook repo checkout's own tree for verification; use the helper's disposable project directory.
