#!/usr/bin/env python3
"""Does weakening a typeclass change which lemma a proof ends on?

This is the measurement that justifies sweeping all 645 rows rather than the
eight the traversal already points at, and as far as a search on 3 September
2026 could tell, nothing else measures it.

The sibling keeps the proof text **byte for byte** and changes only a binder.
The elaborated term need not survive that: instance resolution can pick a
different lemma, so the same source can produce a different root. Two sources of
truth for the same theorems make the comparison possible:

  original  -- the root the library-wide traversal read, from Mathlib as shipped
  weakened  -- the root this sweep read, from the declaration recompiled at the
               sibling's weaker class

What the answer decides: whether Part 2's rung-2 join can be a lookup against
the traversal, or whether every joined row has to be compiled at the weaker
class first. A lookup is minutes. Compiling is hours, and only worth paying if
the roots actually move.

POPULATION: unused-assumptions survivors (Mathlib). Not a library rate.
"""

from __future__ import annotations

import argparse
import collections
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def real_name(theorem: str) -> str:
    """The declaration's actual name, as Lean knows it.

    The sibling records a theorem inside `namespace Prod` that was declared with
    `_root_.WCovBy.fst` as `Prod._root_.WCovBy.fst` -- the namespace it was
    written in, followed by the escape that leaves that namespace. Lean knows it
    as `WCovBy.fst`. Joining on the recorded string finds nothing, silently, for
    every such row.

    Six of the first 35 rows were dropped from the root-shift measurement this
    way, and a dropped row and a row with nothing to say produce the same
    absence. ENGINEERING.md 10.
    """
    marker = "._root_."
    return theorem.split(marker, 1)[1] if marker in theorem else theorem


AUX = ("match_", "_proof_", "_auxLemma", "eq_def", "eq_1", "_sunfold")


def normalise_root(root: str | None, decl: str) -> str | None:
    """Strip the parent declaration's name off an auxiliary root.

    Lean names a `match` auxiliary after the declaration it was lifted from. The
    sweep renames every declaration to `w<id>` so `#print axioms` names the right
    thing, so the SAME auxiliary is called
    `_private.Mathlib.Algebra.Order.Archimedean.Basic.0.exists_rat_lt.match_1_1`
    in the library and `w70947a3b59313356.match_1_1` in the sweep.

    Compared raw, that reads as the root having moved. Two of the first three
    "moves" were this, so the rate came out three times too high -- and it came
    out too high in the direction that makes the expensive Part 2 design look
    necessary. ENGINEERING.md 11.

    Only auxiliaries are normalised. A genuine change of root constant, which is
    the thing being measured, is left alone.
    """
    if root is None:
        return None
    for marker in AUX:
        index = root.find("." + marker)
        if index != -1:
            return "<aux>" + root[index:]
    return root


def traversal_roots(path: Path) -> dict[str, dict]:
    if not path.exists():
        raise SystemExit(f"{path}: no such file. An empty input is not an empty result.")
    out = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("ok"):
            out[row["decl"]] = row
    if not out:
        raise SystemExit(f"{path}: no readable rows")
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "part1.db")
    parser.add_argument("--traversal", type=Path,
                        default=ROOT / "data" / "scratch" / "roots-mathlib.jsonl")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    print(f"# read {args.db} and {args.traversal}", file=sys.stderr)
    original = traversal_roots(args.traversal)
    connection = sqlite3.connect(args.db)
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        "SELECT theorem, module, binder, stated_class, holds_over, root, verdict, area"
        " FROM candidate WHERE verdict IS NOT NULL").fetchall()
    if not rows:
        raise SystemExit("no decided rows yet")

    same, moved, unknown = [], [], []
    for row in rows:
        before = normalise_root(
            original.get(real_name(row["theorem"]), {}).get("root"), row["theorem"])
        after = normalise_root(row["root"], row["theorem"])
        if before is None or after is None:
            unknown.append((row, before, after))
        elif before == after:
            same.append((row, before, after))
        else:
            moved.append((row, before, after))

    comparable = len(same) + len(moved)
    report = {
        "population": "unused-assumptions survivors (Mathlib)",
        "decided_rows": len(rows),
        "comparable": comparable,
        "root_unchanged": len(same),
        "root_moved": len(moved),
        "not_comparable": len(unknown),
        "moved_fraction": round(len(moved) / comparable, 4) if comparable else None,
    }
    print(json.dumps(report, indent=1))

    if moved:
        print("\n# where the root moved (weakening changed the elaborated term)",
              file=sys.stderr)
        pairs = collections.Counter((b, a) for _, b, a in moved)
        for (before, after), count in pairs.most_common(25):
            print(f"{count:>5}  {before}  ->  {after}")

    if args.out:
        args.out.write_text(json.dumps(
            {**report,
             "moved": [{"theorem": r["theorem"], "module": r["module"],
                        "binder": r["binder"], "stated": r["stated_class"],
                        "weakened_to": r["holds_over"], "root_before": b,
                        "root_after": a, "verdict": r["verdict"], "area": r["area"]}
                       for r, b, a in moved]}, indent=1) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
