#!/usr/bin/env python3
"""The rung-2 table: what the two projects find together and neither finds alone.

A rung-2 row is a theorem whose *setting* the sibling weakened and whose
*conclusion* this project strengthens, at the same Mathlib pin. The composite
`a' -> b'` compiles by construction -- a subterm of a proof that typechecks
under `a'` typechecks under `a'` -- and the kernel is asked anyway.

**POPULATION: unused-assumptions survivors (Mathlib).** This is printed in the
caption of every table here and is not optional. A rate computed on this set is
a rate among theorems already known to carry hypothesis slack, so it cannot feed
the per-area correlation, the rung-1 baseline, or the ladder curve. Part 2
measures those, library-wide, after the freeze.

Two buckets, never one, and the reason is the sibling's: reporting a single
number would overstate the result and the overstatement would be invisible
afterwards.
"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POPULATION = "unused-assumptions survivors (Mathlib)"

# What each verdict is, in one line, for the report's own table. `context` and
# `unchained` are the tool's own limits and are never pooled with findings.
MEANING = {
    "strengthens": "the subterm establishes a stronger statement, and no "
                   "declaration in the theorem's own module already states it",
    "witness": "the selected argument is the OBJECT the statement quantifies "
               "away, not a proof about it. Accepted by the kernel as a "
               "definition. Stage 2's material",
    "duplicate": "the stronger statement is already in the library. A "
                 "measurement of API discipline, not waste",
    "unchained": "verified true, but wrapper stripping cut the chain, so that it "
                 "implies the stated theorem is NOT established here",
    "root_not_weakening": "the proof's root is not in the table",
    "stripped_only": "the only slack was an elaboration wrapper",
    "context": "this tool could not reproduce the declaration's setting. The "
               "tool's failure, counted apart",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "part1.db")
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "rung2.md")
    parser.add_argument("--allow-incomplete", action="store_true",
                        help="report over a store that still has undecided rows")
    args = parser.parse_args()

    print(f"# read {args.db}", file=sys.stderr)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    tally = {r["verdict"] or "undecided": r["n"] for r in connection.execute(
        "SELECT verdict, COUNT(*) n FROM candidate GROUP BY verdict")}
    total = sum(tally.values())
    undecided = tally.pop("undecided", 0)

    if undecided and not args.allow_incomplete:
        raise SystemExit(
            f"{undecided} of {total} rows are undecided. Refusing to print rates over "
            "a partial store: the sibling reported an area as having zero findings by "
            "counting a stage that had not run. Pass --allow-incomplete for a progress "
            "read, which is labelled as one.")

    decided = total - undecided
    rows = connection.execute(
        "SELECT * FROM candidate WHERE verdict IN"
        " ('strengthens', 'witness', 'duplicate', 'unchained')"
        " ORDER BY verdict, area, theorem").fetchall()

    out = [f"# Rung 2: weaker setting and stronger conclusion\n",
           f"**population: {POPULATION}**\n",
           "A rung-2 row is a theorem whose setting `unused-assumptions` weakened and "
           "whose conclusion this project strengthens, at the same Mathlib pin. Two "
           "independent edits, and the composite compiles by construction: a subterm "
           "of a proof that typechecks under the weaker setting typechecks under it. "
           "The kernel is asked anyway.\n",
           "**No number here is a library rate.** This set is theorems already known "
           "to carry hypothesis slack, so a rate over it says nothing about Mathlib. "
           "Part 2 measures library-wide, after the freeze.\n"]
    if undecided:
        out.append(f"> **Progress read.** {undecided} of {total} rows are still "
                   f"undecided. These counts will move.\n")

    out.append("## Verdicts\n")
    out.append(f"| verdict | rows | share of {decided} decided | meaning |")
    out.append("|---|---:|---:|---|")
    for verdict, count in sorted(tally.items(), key=lambda kv: -kv[1]):
        out.append(f"| `{verdict}` | {count} | {100 * count / decided:.1f}% | "
                   f"{MEANING.get(verdict, '')} |")
    out.append("")

    # A verdict category at 0% or 100% is a bug until proven otherwise.
    notes = [f"`{v}` is {100 * c / decided:.0f}% of {decided} decided rows"
             for v, c in tally.items() if c in (0, decided)]
    for verdict in MEANING:
        if verdict not in tally:
            notes.append(f"`{verdict}` never occurred in {decided} decided rows")
    if notes:
        out.append("### Degenerate categories, flagged\n")
        out.append("A verdict category at 0% or 100% is a bug until proven otherwise. "
                   "Every defect in the sibling's pipeline failed the same way: "
                   "something that resolved nothing looked exactly like something that "
                   "contained nothing.\n")
        for note in notes:
            out.append(f"- {note}")
        out.append("")

    if rows:
        out.append("## The rows\n")
        for verdict in ("strengthens", "witness", "duplicate", "unchained"):
            group = [r for r in rows if r["verdict"] == verdict]
            if not group:
                continue
            out.append(f"### `{verdict}` -- {len(group)} rows\n")
            out.append(f"_{MEANING[verdict]}._\n")
            for row in group:
                out.append(f"**`{row['theorem']}`** ({row['area']})  ")
                out.append(f"setting weakened `{row['stated_class']}` → "
                           f"`{row['holds_over']}`; root `{row['root']}`  ")
                if row["siblings"]:
                    out.append(f"already stated as: `{row['siblings']}`  ")
                out.append(f"\n```lean\n-- states\n{(row['stated'] or '').strip()}\n"
                           f"\n-- proves\n{(row['stronger'] or '').strip()}\n```\n")

    areas = collections.Counter(r["area"] for r in rows)
    if areas:
        out.append("## Areas\n")
        out.append("| area | rung-2 rows |")
        out.append("|---|---:|")
        for area, count in areas.most_common():
            out.append(f"| {area} | {count} |")
        out.append("")

    args.out.write_text("\n".join(out) + "\n")
    print(json.dumps({"decided": decided, "undecided": undecided,
                      "rung2_rows": len(rows), **tally}))
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
