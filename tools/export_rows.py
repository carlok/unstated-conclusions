#!/usr/bin/env python3
"""Export the rows that ship, as `verify.py` will read them back.

The sibling's shape: stores are working data and are not published; what ships
is jsonl under `data/`, and the verifier reads the published files and never a
store. A result nobody can recompute from the artefact is a report, not a
result.

Two files. `part1-rows.jsonl` is every row the Part 1 sweep decided anything
about beyond `root_not_weakening` -- findings and the tool's own failures
together, because a run that ships only its successes is not reproducible.
`citations.jsonl` is the survivor citation counts.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POPULATION = "unused-assumptions survivors (Mathlib)"

INTERESTING = ("strengthens", "witness", "duplicate", "unchained", "context")

# Lean prints the filename it was handed, and we hand it a temp file. Those
# paths reach the `detail` column verbatim and would ship inside the artefact.
#
# This is the sibling's ENGINEERING #4 exactly: a temp path reached a published
# document there, and the source had been grepped for `/Users`, `/private` and
# `/tmp` -- macOS puts temp files under `/var/folders`. We inherited the story
# and reproduced the defect, in a file we generated ourselves. ENGINEERING.md 23.
TEMP_PATH = re.compile(r"(/private)?(/var/folders/[^\s:]+|/tmp/[^\s:]+)")


def redact(value):
    """Strip absolute temp paths out of anything that ships."""
    if isinstance(value, str):
        return TEMP_PATH.sub("<tempfile>", value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "part1.db")
    parser.add_argument("--citations", type=Path,
                        default=ROOT / "data" / "scratch" / "citations-rows.jsonl")
    parser.add_argument("--citations-report", type=Path,
                        default=ROOT / "data" / "scratch" / "citations-report.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data")
    args = parser.parse_args()

    print(f"# read {args.db}", file=sys.stderr)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    marks = ",".join("?" * len(INTERESTING))
    rows = [dict(r) for r in connection.execute(
        f"SELECT * FROM candidate WHERE verdict IN ({marks}) ORDER BY verdict, theorem",
        INTERESTING)]
    for row in rows:
        row["population"] = POPULATION
        for key, value in list(row.items()):
            row[key] = redact(value)
    (args.out / "part1-rows.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    print(f"wrote part1-rows.jsonl ({len(rows)} rows)")

    if args.citations.exists():
        shutil.copyfile(args.citations, args.out / "citations.jsonl")
        print("wrote citations.jsonl")
    if args.citations_report.exists():
        shutil.copyfile(args.citations_report, args.out / "citations-report.json")
        print("wrote citations-report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
