"""Write the checked-in v1 and v2 fixture boards."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from waybook.board import add_entry, init_project, verify  # noqa: E402


def build(dest: Path, schema_version: int) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    os.environ["WAYBOOK_NOW"] = "2026-01-15T12:00:00Z"
    init_project(dest, project_id="fixture", schema_version=schema_version)
    add_entry(
        dest,
        "decisions",
        "Keep the ledger flat",
        "One markdown file per entry",
        "Humans can read the board without a database.",
        ["pr:97"],
        "fixture",
        legacy_ok=schema_version < 2,
    )
    verify(dest)


def main() -> None:
    fixtures = ROOT / "tests" / "fixtures"
    build(fixtures / "v1", 1)
    build(fixtures / "v2", 2)


if __name__ == "__main__":
    main()
