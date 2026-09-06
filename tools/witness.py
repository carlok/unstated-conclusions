#!/usr/bin/env python3
"""Stage 2: the objects the library names in a proof and never writes down.

For every row whose root hides a witness -- `Exists.intro w h`, `Nonempty.intro
a` -- extract `w` and classify it. `BRIEF.md` is explicit that the answer is a
measurement and not a premise:

  *Expect most existentials in Mathlib to be proved by `Classical.choose` or by
  an inherited exists from another lemma, so that the witness is not new.
  Measure the computable fraction and report it before claiming anything; if it
  is small, stage 2 is a footnote and the report says so.*

So this tool's job is to be able to report that stage 2 is a footnote. The
classification runs in Lean (`Unstated.witnessOf`); this composes the run and
counts what comes back.

Every witness is detailed in ONE Lean process. They are declarations that
already exist in the imported environment, so nothing has to be elaborated
first.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leanrun    # noqa: E402
import roots as rootsmod  # noqa: E402
import traverse   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

KINDS = ("computable", "noncomputable_choice", "noncomputable_other",
         "depends_on_hypothesis_proof", "not_closed")


def witness_entries(table: dict) -> dict[str, int]:
    """Table entries that carry an object, and which argument holds it."""
    out = {}
    for root, entry in table.items():
        if "witness_arg" in entry:
            out[root] = entry["witness_arg"]
        elif entry.get("produces") == "witness":
            out[root] = entry["stronger_arg"]
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=os.environ.get("SWEEP_REPO"))
    parser.add_argument("--source", choices=["db", "traversal"], default="traversal",
                        help="db: the Part 1 sweep's rows, population "
                             "'unused-assumptions survivors (Mathlib)'. "
                             "traversal: every matched row in the library, which is "
                             "a Part 2 population and reports no rate in Part 1")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "part1.db")
    parser.add_argument("--candidates", type=Path,
                        default=ROOT / "data" / "scratch" / "candidates.jsonl")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=2400)
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "scratch" / "witnesses.jsonl")
    args = parser.parse_args()
    if not args.repo:
        parser.error("set SWEEP_REPO or pass --repo")
    repo = Path(args.repo)

    table = rootsmod.load_table()
    carriers = witness_entries(table)
    print(json.dumps({"witness_roots": carriers}), file=sys.stderr)

    pairs = []
    if args.source == "db":
        connection = sqlite3.connect(args.db)
        connection.row_factory = sqlite3.Row
        for row in connection.execute(
                "SELECT theorem, root FROM candidate WHERE root IS NOT NULL"):
            if row["root"] in carriers:
                pairs.append({"decl": row["theorem"], "which": carriers[row["root"]]})
    else:
        print(f"# read {args.candidates}", file=sys.stderr)
        for line in args.candidates.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row["root"] in carriers:
                pairs.append({"decl": row["decl"], "which": carriers[row["root"]]})

    if not pairs:
        raise SystemExit("no rows carry a witness. An empty input is not an empty result.")
    if args.limit:
        pairs = pairs[:args.limit]
    print(json.dumps({"witness_rows": len(pairs), "source": args.source}), flush=True)

    ok, why = leanrun.metaprogram_check(lambda c: traverse.compose(c, None), repo)
    print(json.dumps({"metaprogram": ok, "detail": why}), flush=True)
    if not ok:
        return 1

    command = "\n".join(
        f'#eval show Lean.Meta.MetaM Unit from do Unstated.emitLine '
        f'(← Unstated.witnessOf `{p["decl"]} {p["which"]})'
        for p in pairs)
    rows, noise = traverse.run(command, repo, args.timeout)
    errors = leanrun.errors_in(noise)
    if errors:
        print(f"--- {len(errors)} error(s) from Lean ---", file=sys.stderr)
        for error in errors[:6]:
            print("  " + error[:200], file=sys.stderr)
    if not rows:
        print("# refusing to write: no rows", file=sys.stderr)
        return 1

    kinds = collections.Counter(
        (r.get("classification") or {}).get("kind", "unreadable") for r in rows)
    computable = kinds.get("computable", 0)
    report = {"rows": len(rows), "kinds": dict(kinds),
              "computable_fraction": round(computable / len(rows), 4)}
    print(json.dumps(report, indent=1))
    for note in rootsmod.suspicious(dict(kinds), len(rows)):
        print(f"# SUSPICIOUS: {note}", file=sys.stderr)
    if computable == 0:
        print("# Stage 2 is a footnote, and the report says so.", file=sys.stderr)

    args.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
