#!/usr/bin/env python3
"""Match traversal output against the weakening table, and report what missed.

Two outputs, and the second matters as much as the first:

  candidates  -- rows whose root head is in the table
  histogram   -- root heads that are NOT in the table, most common first

The histogram is this project's substitute for the sibling's second weakening
table. There, a hand-written table could be cross-checked against one derived
from `class X extends Y`, and that comparison found 89 classes the hand table
had missed. Weakening lemmas are not declared as a relation anywhere, so there
is no second instrument here. Reading the histogram by hand before the freeze is
the weaker substitute, and calling it weaker is the honest description.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_table(path: Path | None = None) -> dict:
    table = json.loads((path or ROOT / "weakenings.json").read_text())
    by_root = {}
    for entry in table["entries"]:
        if entry["root"] in by_root:
            raise SystemExit(f"weakenings.json: {entry['root']} listed twice")
        by_root[entry["root"]] = entry
    return by_root


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"{path}: no such file. An empty input is not an empty result.")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise SystemExit(f"{path}: no rows. Something that resolved nothing looks "
                         "exactly like something that contained nothing.")
    return rows


def area_of(module: str | None) -> str:
    """`Mathlib.Order.Basic` -> `Order`. Matches the sibling's `area_of` so the
    per-area join is on the same coordinate."""
    if not module:
        return "?"
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else parts[0]


def classify(rows: list[dict], table: dict) -> tuple[list[dict], collections.Counter, dict]:
    candidates, missed = [], collections.Counter()
    tally = collections.Counter()
    for row in rows:
        if not row.get("ok"):
            tally["unreadable"] += 1
            continue
        root = row.get("root")
        if root is None:
            tally["root_not_constant"] += 1
            missed[f"<{row.get('root_kind', 'unknown')}>"] += 1
            continue
        if root in table:
            tally["matched"] += 1
            candidates.append({**row, "entry": table[root], "area": area_of(row.get("module"))})
        else:
            tally["root_not_weakening"] += 1
            missed[root] += 1
    return candidates, missed, tally


def suspicious(tally: dict, total: int) -> list[str]:
    """A verdict category at 0% or 100% is a bug until proven otherwise.

    Every defect in the sibling's pipeline failed the same way: something that
    resolved nothing looked exactly like something that contained nothing. Both
    print zero. This does not stop the run; it says so loudly.
    """
    notes = []
    if total == 0:
        return ["no rows at all"]
    for name, count in tally.items():
        share = count / total
        if share == 0.0:
            notes.append(f"{name} is 0% of {total} rows")
        elif share == 1.0:
            notes.append(f"{name} is 100% of {total} rows")
    return notes


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("roots", type=Path)
    parser.add_argument("--table", type=Path)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--histogram", type=Path)
    parser.add_argument("--top", type=int, default=40)
    parser.add_argument("--anyway", action="store_true",
                        help="print a degenerate distribution anyway, having read a case")
    args = parser.parse_args()

    # Make the input list an output. A glob that matches too much looks exactly
    # like a glob that matches right, and no check over the data can tell them
    # apart -- that cost the sibling a published correlation of +0.92 that is
    # actually +0.73.
    print(f"# read {args.roots}", file=sys.stderr)

    table = load_table(args.table)
    rows = read_rows(args.roots)
    candidates, missed, tally = classify(rows, table)

    total = sum(tally.values())
    print(json.dumps({"rows": total, **tally,
                      "distinct_roots_missed": len(missed),
                      "table_entries": len(table)}))
    notes = suspicious(tally, total)
    for note in notes:
        print(f"# SUSPICIOUS: {note}", file=sys.stderr)

    if args.candidates:
        args.candidates.write_text("".join(json.dumps(c) + "\n" for c in candidates))
    if args.histogram:
        args.histogram.write_text("".join(
            f"{count}\t{root}\n" for root, count in missed.most_common()))
    for root, count in missed.most_common(args.top):
        print(f"{count:>7}  {root}")
    # A verdict category at 0% or 100% is a bug until proven otherwise, so this
    # exits non-zero rather than printing a warning into a scrollback nobody
    # rereads. Defect 2 was found because a 100% category was treated as a
    # result for exactly as long as it took to read the line. `--anyway` is for
    # the case where the degenerate distribution has been looked at and is real.
    if notes and not args.anyway:
        print("# refusing: pass --anyway once you have opened a case and read it",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
