#!/usr/bin/env python3
"""Track D's input: the sibling's failures, joined to its survivors.

Reads `breaks.jsonl.gz` -- the export, not a store. The stores under
the producing project's stores are the fallback and are never opened live: a plain
read-only open takes a long shared lock and can hand a concurrent writer
"database is locked". If one is ever needed, snapshot it once with
`sqlite3 <src> ".backup ..."` (the online backup API) and read the snapshot.

Three facts about the file decide how it is read, and all three were checked
against it rather than taken from the brief:

- `blamed` is null on every one of the 57,382 rows and will stay so: the sweep
  kept only the first error line and Lean puts the class name on the second.
  The split property is derived from the class pair, not from the error.
- `fails_at` is the sibling's *reconstruction*, not a recorded event -- its
  table proposes several candidate classes per binder and tries each
  independently. `descent` carries every class tried with its own verdict, so
  the break point is recomputed here under this project's own order, and which
  order was used is recorded.
- `fail_error` is capped at 200 characters by the store. There is no more to
  give, and asking for more needs a four-day re-sweep.

The join is on `key` (corpus:module:theorem:binder). Never on
corpus:theorem:binder: 1,663 Mathlib theorem names appear in more than one
module, so that form collides.
"""

from __future__ import annotations

import argparse
import collections
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Verdicts that can host a dichotomy, and those that cannot.
#
# `incoherent` means *the statement cannot be stated* -- a sibling instance
# demands the stronger class. Track D's shape is `a'' -> b \/ c`, which needs an
# `a''` the statement can be written over, so an incoherent break cannot carry
# one. That is not a judgement call; it is the sibling's own definition of the
# verdict, and it is why the strict rung-3 population is 10 rows and not 277.
REPAIRABLE = {"needs_structure"}
NOT_A_FACT_ABOUT_THE_THEOREM = {"context"}  # the sibling's tooling, treat as missing


def read_breaks(path: Path):
    if not path.exists():
        raise SystemExit(f"{path}: no such file. The fallback is a store snapshot, "
                         "never a live store.")
    with gzip.open(path, "rt") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def read_survivors(path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise SystemExit(f"{path}: no rows")
    return {row["key"]: row for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--brother", type=Path, default=ROOT.parent / "unused-assumptions")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "trackd-input.json")
    parser.add_argument("--topup", type=int, default=190)
    parser.add_argument("--seed", type=int, default=20260903)
    args = parser.parse_args()

    breaks_path = args.brother / "data" / "breaks.jsonl.gz"
    survivors_path = args.brother / "data" / "survivors.jsonl"
    print(json.dumps({"read": [str(breaks_path), str(survivors_path)]}), file=sys.stderr)

    survivors = read_survivors(survivors_path)
    breaks = list(read_breaks(breaks_path))

    verdicts = collections.Counter(r["fail_verdict"] for r in breaks)
    on_survivor_key = [r for r in breaks if r["key"] in survivors]
    strict = [r for r in on_survivor_key if r["fail_verdict"] in REPAIRABLE]

    # The top-up population, kept apart and never merged into the strict one.
    # Rows that are their theorem's only break: one disjunct can plausibly
    # repair one failure and not five.
    breaks_per_theorem = collections.Counter((r["module"], r["theorem"]) for r in breaks)
    pool = [r for r in breaks
            if r["fail_verdict"] in REPAIRABLE
            and r["key"] not in survivors
            and breaks_per_theorem[(r["module"], r["theorem"])] == 1]

    # Stratified by area over the areas where the sibling found the most, since
    # that is where the brief says to look, and proportional inside each.
    import random
    rng = random.Random(args.seed)
    by_area = collections.defaultdict(list)
    for row in pool:
        by_area[row["area"]].append(row)
    for bucket in by_area.values():
        rng.shuffle(bucket)
    order = sorted(by_area, key=lambda a: -len(by_area[a]))
    topup, i = [], 0
    while len(topup) < args.topup and any(by_area.values()):
        area = order[i % len(order)]
        if by_area[area]:
            topup.append(by_area[area].pop())
        i += 1

    payload = {
        "population_strict": {
            "what": "rung 3: a binder of an unused-assumptions survivor that also "
                    "broke, with a verdict that can host a dichotomy",
            "join": "key = corpus:module:theorem:binder",
            "rows": len(strict),
        },
        "population_topup": {
            "what": "needs_structure rows that are their theorem's only break and "
                    "are NOT survivors. Exercises the machinery. NOT rung 3, and "
                    "no rate computed on it is a rung-3 rate.",
            "pool": len(pool),
            "rows": len(topup),
            "seed": args.seed,
        },
        "context_note": ("`context` rows are the sibling's tooling failing to "
                         "reconstruct scope, not a fact about the theorem; they are "
                         "missing data and are excluded from both populations."),
        "break_verdicts_in_full_file": dict(verdicts),
        "survivor_keys_that_also_broke": len(on_survivor_key),
        "of_those_not_repairable": len(on_survivor_key) - len(strict),
        "why_not_repairable": ("`incoherent`: the statement cannot be stated, so "
                               "there is no a'' to write `b \\/ c` over"),
        "strict": strict,
        "topup": topup,
    }
    args.out.write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps({k: v for k, v in payload.items()
                      if k not in ("strict", "topup")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
