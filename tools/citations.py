#!/usr/bin/env python3
"""Answer the citation question: are the survivors classical results or plumbing?

`unused-assumptions` can show a weakening holds and cannot show anyone wants it.
Its three proxies -- a surname in the name, a docstring, a docstring naming a
classical result -- are all about naming, and naming is a convention. The count
of declarations that cite a lemma is a fact about the library.

The comparison is the whole point, and it is stated here before any number is
computed: **a median citation count for the survivors means nothing alone.** It
means something against the same figure for theorems generally. Both are
reported, or neither.

The baseline is every non-survivor theorem in the corpus, not a random sample of
them. A sample would need a seed, a size and a defence; the full set needs none
and costs the same, since the citation pass counts everything anyway.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rootshift  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def load_counts(path: Path) -> dict[str, int]:
    counts, header = {}, None
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "scanned_theorems" in row:
            header = row
            continue
        counts[row["decl"]] = row["cited_by"]
    if not counts:
        raise SystemExit(f"{path}: no counts. An empty input is not an empty result.")
    print(json.dumps({"header": header, "constants_with_a_citation": len(counts)}),
          file=sys.stderr)
    return counts


# Mathlib auto-generates a great many theorems -- `.injEq`, `.noConfusion`,
# `.eq_def`, match auxiliaries -- that nothing cites by name. They are 8% of the
# corpus and 83% of them are never cited, so leaving them in the baseline
# inflates its never-cited share and flatters any comparison against it.
GENERATED = re.compile(
    r"(\.injEq$|\.noConfusion|\.sizeOf_spec$|_eq_def$|\.eq_def$|\.eq_[0-9]+$"
    r"|\.mk\.injEq$|_proof_|\.below$|\.brecOn$|\.rec$|\.casesOn$|\.ndrec$"
    r"|\.ofNat_|\.toCtorIdx$|\.match_[0-9]|\.congr_|\.binductionOn$)")


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval. Written out rather than imported, so a reader with
    no dependencies can check it."""
    if n == 0:
        return (0.0, 0.0)
    p = hits / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def describe(values: list[int]) -> dict:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(values),
        "median": statistics.median(ordered),
        "mean": round(statistics.mean(ordered), 2),
        "cited_never": sum(1 for v in ordered if v == 0),
        "cited_once_or_less": sum(1 for v in ordered if v <= 1),
        "p25": ordered[len(ordered) // 4],
        "p75": ordered[3 * len(ordered) // 4],
        "p90": ordered[9 * len(ordered) // 10],
        "max": ordered[-1],
        "never_cited_share": round(sum(1 for v in ordered if v == 0) / len(ordered), 4),
        "never_cited_wilson95": [round(x, 4) for x in
                                 wilson(sum(1 for v in ordered if v == 0), len(ordered))],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--counts", type=Path,
                        default=ROOT / "data" / "scratch" / "citations.jsonl")
    parser.add_argument("--traversal", type=Path,
                        default=ROOT / "data" / "scratch" / "roots-mathlib.jsonl")
    parser.add_argument("--survivors", type=Path,
                        default=ROOT.parent / "unused-assumptions" / "data" / "survivors.jsonl")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--rows-out", type=Path)
    args = parser.parse_args()

    print(f"# read {args.counts}, {args.traversal}, {args.survivors}", file=sys.stderr)
    counts = load_counts(args.counts)

    # Every theorem the traversal saw, which is the corpus this is measured over.
    corpus, module_of = set(), {}
    for line in args.traversal.read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            if row.get("decl"):
                corpus.add(row["decl"])
                if row.get("module"):
                    module_of[row["decl"]] = row["module"]

    survivors = [json.loads(l) for l in args.survivors.read_text().splitlines() if l.strip()]
    # Their `theorem` field records the namespace a declaration was WRITTEN in,
    # so `Prod._root_.WCovBy.fst` is Lean's `WCovBy.fst`. Joining raw drops rows
    # silently, and a smaller denominator is what a rarer phenomenon looks like.
    named = {rootshift.real_name(r["theorem"]) for r in survivors}
    joined = named & corpus
    missed = named - corpus

    others = corpus - named
    survivor_counts = [counts.get(n, 0) for n in sorted(joined)]
    baseline_counts = [counts.get(n, 0) for n in sorted(others)]
    clean = [n for n in sorted(others) if not GENERATED.search(n)]
    clean_counts = [counts.get(n, 0) for n in clean]

    # Their challenge, and it is the right one: is the baseline theorems of the
    # same KIND? Mathlib carries a great deal of machinery that is genuinely
    # never cited, and if survivors are concentrated in hand-written areas the
    # gap could be entirely that.
    #
    # The control: non-survivor theorems in the SAME MODULES as the survivors.
    # Same files, same authors, same density of machinery. Cheap, and it does
    # not need a notion of "hand-written" that would have to be defended.
    survivor_modules = {r["module"] for r in survivors}
    same_module = [n for n in sorted(others)
                   if not GENERATED.search(n) and module_of.get(n) in survivor_modules]
    same_module_counts = [counts.get(n, 0) for n in same_module]

    report = {
        "population": "Mathlib at the pinned revision",
        "survivor_theorems": len(named),
        "joined_to_corpus": len(joined),
        "not_found_in_corpus": len(missed),
        "survivors": describe(survivor_counts),
        "baseline_all_other_theorems": describe(baseline_counts),
        "baseline_excluding_generated": describe(clean_counts),
        "baseline_same_modules_as_survivors": describe(same_module_counts),
        "survivor_modules": len(survivor_modules),
        "generated_excluded": len(baseline_counts) - len(clean_counts),
        "caveat": (
            "Survivors cluster by module and by author, so these are not "
            "independent trials and no p-value is quoted. The Wilson intervals "
            "are unclustered and are therefore narrower than the truth. The "
            "sibling's own density work makes the same correction and reports "
            "the clustered figure only; the same correction is owed here before "
            "anything is published."),
    }
    s, b = report["survivors"], report["baseline_all_other_theorems"]
    if s.get("n") and b.get("n"):
        report["median_ratio"] = (round(s["median"] / b["median"], 2)
                                  if b["median"] else None)
        c = report["baseline_excluding_generated"]
        report["headline"] = {
            "never_cited_survivors": s["never_cited_share"],
            "never_cited_baseline_clean": c["never_cited_share"],
            "mean_survivors": s["mean"],
            "mean_baseline_clean": c["mean"],
            "max_survivors": s["max"],
            "max_baseline_clean": c["max"],
        }
    print(json.dumps(report, indent=1))

    if args.rows_out:
        # `cited_by` is 0 when the theorem was measured and nothing cites it,
        # and null ONLY when it was not measured at all.
        #
        # The citation pass emits a constant only if something cites it, so a
        # zero-cited theorem is simply absent from the map. `describe` defaulted
        # the lookup to 0 and was right; this writer used a bare `.get()` and
        # collapsed "zero" and "not measured" into the same null. Every number
        # in our own report was correct and the file we shipped could not
        # reproduce them. ENGINEERING.md 22.
        rows = []
        for r in survivors:
            name = rootshift.real_name(r["theorem"])
            found = name in corpus
            rows.append({
                "id": r["id"], "key": r["key"], "theorem": r["theorem"],
                "module": r["module"], "binder": r["binder"], "area": r["area"],
                "cited_by": counts.get(name, 0) if found else None,
                "found_in_corpus": found,
                "cited_by_meaning": ("count" if found else "not measured"),
            })
        args.rows_out.write_text("".join(json.dumps(r) + "\n" for r in rows))
        print(f"wrote {args.rows_out}", file=sys.stderr)
    if args.out:
        args.out.write_text(json.dumps(report, indent=1) + "\n")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
