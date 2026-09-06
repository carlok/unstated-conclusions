#!/usr/bin/env python3
"""Ship `unused-assumptions` the three things it asked for.

Keyed by their `id` throughout, because that is what they asked for and because
`id` is stable across runs by their own scheme -- `sha256('module|theorem|
binder_index|to_class')[:16]`, containing no revision and no class table.

Their correction is honoured: `id` is per *target class*, so one (theorem,
binder) has several. Every row here also carries `key` so a join can be made on
either, and says which of the two it is unique on.

1. error_blocks -- the full multi-line Lean error for every pilot row we
   recompiled. Their store truncates at `errors[0][:200]` and Lean puts the
   class name on the line after; this is the thing they cannot recover without
   the re-sweep we talked them out of.
2. blamed -- the constant recovered from those blocks, where one exists.
3. roots -- the root of the proof term for their 645 survivors, before and
   after their own weakening, for the merge they proposed.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rootshift  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"wrote {path}  ({len(rows)} rows)")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--trackd", type=Path, default=ROOT / "data" / "trackd.db")
    parser.add_argument("--part1", type=Path, default=ROOT / "data" / "part1.db")
    parser.add_argument("--citations", type=Path,
                        default=ROOT / "data" / "scratch" / "citations-rows.jsonl")
    parser.add_argument("--citations-report", type=Path,
                        default=ROOT / "data" / "scratch" / "citations-report.json")
    parser.add_argument("--traversal", type=Path,
                        default=ROOT / "data" / "scratch" / "roots-mathlib.jsonl")
    args = parser.parse_args()

    td = sqlite3.connect(args.trackd); td.row_factory = sqlite3.Row
    p1 = sqlite3.connect(args.part1); p1.row_factory = sqlite3.Row
    original = rootshift.traversal_roots(args.traversal)

    # 1. the error blocks
    blocks = [{"id": r["id"], "key": r["key"], "theorem": r["theorem"],
               "module": r["module"], "binder": r["binder"],
               "fails_at": r["fails_at"], "population": r["population"],
               "provenance": r["provenance"], "verdict": r["verdict"],
               "full_error": r["full_error"]}
              for r in td.execute(
                  "SELECT * FROM repair WHERE verdict IN ('error_captured','parse_failed')"
                  " ORDER BY id")]
    write(args.out / "error-blocks.jsonl", blocks)

    # 2. the recovered blamed values
    blamed = [{"id": r["id"], "key": r["key"], "theorem": r["theorem"],
               "fails_at": r["fails_at"], "blamed": r["blamed"]}
              for r in td.execute(
                  "SELECT * FROM repair WHERE blamed IS NOT NULL ORDER BY id")]
    write(args.out / "blamed.jsonl", blamed)

    # 3. the root readings, before and after their weakening
    roots, moved = [], 0
    for r in p1.execute("SELECT * FROM candidate ORDER BY id"):
        before = rootshift.normalise_root(
            original.get(rootshift.real_name(r["theorem"]), {}).get("root"), r["theorem"])
        after = rootshift.normalise_root(r["root"], r["theorem"])
        comparable = before is not None and after is not None
        if comparable and before != after:
            moved += 1
        roots.append({
            "id": r["id"], "key": r["key"], "theorem": r["theorem"],
            "module": r["module"], "binder": r["binder"],
            "stated": r["stated_class"], "holds_over": r["holds_over"],
            # the root of the proof term as Mathlib ships it
            "root_before": original.get(
                rootshift.real_name(r["theorem"]), {}).get("root"),
            # the root after YOUR weakening, read from the recompiled declaration
            "root_after": r["root"],
            "comparable": comparable,
            "moved": (comparable and before != after),
            "our_verdict": r["verdict"],
        })
    write(args.out / "roots.jsonl", roots)

    # 4. the citation counts, their second ask
    cites = unmeasured = 0
    if args.citations.exists():
        rows = [json.loads(l) for l in args.citations.read_text().splitlines() if l.strip()]
        write(args.out / "citations.jsonl", rows)
        cites = len(rows)
        unmeasured = sum(1 for r in rows if not r.get("found_in_corpus"))
    if args.citations_report.exists():
        (args.out / "citations-report.json").write_text(args.citations_report.read_text())
        print(f"wrote {args.out / 'citations-report.json'}")

    readme = f"""# Data for `unused-assumptions`, {date.today().isoformat()}

Three files, all JSON lines, all keyed by **your** `id`, with `key` alongside so
either join works.

Your correction is honoured: `id` is per target class, so a (theorem, binder)
has several. `error-blocks.jsonl` and `blamed.jsonl` are unique on `id`.
`roots.jsonl` is one row per row of `survivors.jsonl`, so it is unique on `key`
and on `id` both, since that file is already one row per surviving
(module, theorem, binder).

## `error-blocks.jsonl` — {len(blocks)} rows

The full multi-line Lean error, recompiled by us at `fails_at`. Ask 1.

`verdict` is ours and separates two things you would otherwise pool:

- `error_captured` — the proof broke, and this is the whole error
- `parse_failed` — the generated file never parsed, so the row says nothing
  about the proof. These are the 22 from item 3 of our report; they are here so
  you can see whether the cause is your export or our preamble

`provenance` says where the source came from. After your fix every row is
`as_shipped`; it is kept so the field means the same thing in older data.

## `blamed.jsonl` — {len(blamed)} rows

Ask 2. The constant Lean names, recovered from the blocks above. Present only
where the error is an instance-synthesis failure, which is the finding from
item 1 of our report and is why the re-sweep is not worth running.

## `roots.jsonl` — {len(roots)} rows

Ask 3, and the input to your merge proposal.

- `root_before` — the head constant at the root of the proof term as Mathlib
  ships the theorem
- `root_after` — the same, read from the declaration recompiled under **your**
  weakened binder
- `comparable` — false when we could not read one of the two. Roughly
  {sum(1 for r in roots if not r['comparable'])} rows, mostly declarations the
  library-wide traversal skips as internal
- `moved` — {moved} rows, our 0.85%

Two things to know before joining:

**Auxiliary names are normalised in our comparison, not in these fields.** A
`match` auxiliary is named after its parent, and our sweep renames every parent
to `w<id>`, so `_private.…exists_rat_lt.match_1_1` and
`w70947a3b….match_1_1` are the same declaration under two names. `root_before`
and `root_after` are raw; `moved` already accounts for this. Comparing the two
strings yourself will show about three times too many moves. That cost us a
number before we noticed.

**`theorem` needs unescaping to join against a Lean name.** Your field records
the namespace a declaration was *written* in, so a theorem written
`_root_.WCovBy.fst` inside `namespace Prod` is `Prod._root_.WCovBy.fst`, which
Lean knows as `WCovBy.fst`. Not a complaint — it is the right thing for your
compiler and the wrong thing for a name lookup. It silently dropped rows from
our measurement until we printed the ones that failed to join.

## `citations.jsonl` — {cites} rows

Your second ask. One row per row of `survivors.jsonl`, carrying `cited_by`: the
number of Mathlib theorems whose proof term mentions that declaration.

`found_in_corpus` is false for {unmeasured} rows —
declarations the library-wide traversal skips as internal, or names that do not
resolve after unescaping. A `cited_by` of null means *not measured*, not zero,
and the two must not be pooled: a join failure and an uncited lemma leave the
same hole.

`citations-report.json` carries the comparison. The short version is in the
covering note; the number that matters is the never-cited share, and it goes the
opposite way to the hypothesis your naming proxies suggested.

## On the merge

Your framing is better than ours and we would like to take it. The nested pair
— same root {100 * (1 - moved / max(sum(1 for r in roots if r['comparable']), 1)):.2f}%,
same cited constants 87.5% — says something neither number says alone, and the
gap is the part worth reporting.

One thing to check in the join before either of us writes it down: a row where
the root moved but your constant set did not. You call it impossible. If it
appears, it is either a bug in one of us or a real thing about elaboration, and
we would want to know which before publishing the pair.
"""
    (args.out / "README.md").write_text(readme)
    print(f"wrote {args.out / 'README.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
