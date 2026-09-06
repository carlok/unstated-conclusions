#!/usr/bin/env python3
"""The name-pattern leg of the duplicate check.

Three legs run in total and they are not equal evidence, so they are recorded
apart rather than merged into one flag:

  defeq      -- a declaration in the theorem's own module whose type IS the
                stronger statement. Runs inside the sweep; the strongest leg.
  name       -- this file. A guess at what the sharper sibling would be called,
                confirmed only by that name existing. Cheap, needs no Lean, and
                is a NOMINATION rather than a verdict.
  exact?     -- the library closes the stronger statement unaided. Runs last,
                on the few rows that survive the other two.

The sibling's prior-art stage has the trap this leg inherits: its first eight
nominations were all the theorem citing *itself*. It compared the citation's
last component against the theorem's full name, so any theorem with a dot in
its own name could never match and filed its self-citations as genuine prior
art -- 23 rows in one corpus and 63 in another, in the wrong bucket. Here the
equivalent is a substitution that changes nothing, and it is discarded.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roots as rootsmod  # noqa: E402


def known_names(path: Path) -> set[str]:
    """Every declaration the traversal saw, including ones it could not read.

    Deliberately including the unreadable ones: this leg asks whether a NAME
    exists, and a declaration whose proof could not be walked still exists.
    """
    names = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("decl"):
            names.add(row["decl"])
    if not names:
        raise SystemExit(f"{path}: no declarations. An empty input is not an empty result.")
    return names


def nominations(decl: str, patterns: list[list[str]], names: set[str]) -> list[str]:
    found = []
    for stated, stronger in patterns:
        if stated not in decl:
            continue
        guess = decl.replace(stated, stronger)
        if guess == decl:
            # The substitution changed nothing, so the "sibling" is the theorem
            # itself. That is the sibling's own defect, and it is an artefact of
            # this tool rather than a fact about the library.
            continue
        if guess in names:
            found.append(guess)
    return list(dict.fromkeys(found))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--names", type=Path, required=True,
                        help="traversal output, used only as the set of declaration names")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    print(f"# read {args.candidates} and {args.names}", file=sys.stderr)
    table = rootsmod.load_table()
    names = known_names(args.names)
    rows = [json.loads(line) for line in args.candidates.read_text().splitlines() if line.strip()]
    if not rows:
        raise SystemExit(f"{args.candidates}: no rows")

    tally = collections.Counter()
    out = []
    for row in rows:
        entry = table.get(row["root"], {})
        nominated = nominations(row["decl"], entry.get("sibling_patterns", []), names)
        tally["nominated" if nominated else "no_name_sibling"] += 1
        out.append({**row, "name_siblings": nominated})

    print(json.dumps({"rows": len(rows), **tally,
                      "declarations_known": len(names)}))
    for note in rootsmod.suspicious(tally, len(rows)):
        print(f"# SUSPICIOUS: {note}", file=sys.stderr)
    if args.out:
        args.out.write_text("".join(json.dumps(r) + "\n" for r in out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
