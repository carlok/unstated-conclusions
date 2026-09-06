#!/usr/bin/env python3
"""What the table did not match, read by hand before the freeze.

This is the weakest part of the project's design and saying so is the point.

The sibling could check its hand-written class table against one derived
mechanically from `class X extends Y`, and that comparison found 89 classes the
hand table had missed -- including `DivisionRing`. Weakening lemmas are not
declared as a relation anywhere in Mathlib, so no second instrument exists here.
The substitute is this: a histogram of every root the table did not match, most
common first, annotated by hand. It catches a miss only if a person reads far
enough down, and it cannot catch one that is rare.

Counts are generated. The annotations are hand-written and are marked as such,
because a judgement that looks like a measurement is the thing this project's
sibling lost a published number to.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Hand-written. "add" means a real conclusion weakening the table is missing;
# "no" means the root is not one, with the reason. Anything unannotated has not
# been read yet, and the document says so rather than implying it was cleared.
READING = {
    "Eq.refl": ("no", "reflexivity; the proof establishes nothing beyond the statement"),
    "rfl": ("no", "as above"),
    "Eq.trans": ("no", "transitivity; neither argument is stronger than the conclusion"),
    "Iff.intro": ("no", "builds the iff, does not discard half of one"),
    "Iff.rfl": ("no", "reflexivity"),
    "Iff.symm": ("no", "same content, other orientation"),
    "Iff.trans": ("no", "transitivity"),
    "Exists.rec": ("no", "eliminator: consumes an existential rather than producing one"),
    "Or.rec": ("no", "eliminator"),
    "And.rec": ("no", "eliminator"),
    "List.rec": ("no", "eliminator"),
    "Nonempty.rec": ("no", "eliminator"),
    "Iff.mp": ("add", "the theorem states `a -> b` and the proof holds `a <-> b`. "
                      "Genuinely stronger. Expect a high duplicate rate, since the "
                      "iff is usually a library lemma already stated -- and that "
                      "rate is itself the API-discipline measurement"),
    "Iff.mpr": ("add", "as `Iff.mp`, other direction. Very common as the root of a "
                       "`simp`-shaped proof"),
    "Equiv.injective": ("add", "the proof has an equivalence, the statement asks for "
                               "injectivity. Same family as the two "
                               "`Function.Bijective` entries already in the table"),
    "Eq.symm": ("no", "same content"),
    "And.intro": ("no", "builds the conjunction"),
    "le_antisymm": ("no", "produces `=` from two `<=`: the proof is doing MORE work "
                          "than either argument, which is the opposite shape"),
    "LE.le.antisymm": ("no", "as `le_antisymm`"),
    "Set.Subset.antisymm": ("no", "as `le_antisymm`, for sets"),
    "le_trans": ("no", "transitivity. The sharper-intermediate-bound case is Track C, "
                       "which BRIEF.md drops for having no finite table"),
    "LE.le.trans": ("no", "as `le_trans`"),
    "Set.ext": ("no", "produces `=` from a pointwise iff"),
    "Finset.ext": ("no", "as `Set.ext`"),
    "funext": ("no", "as `Set.ext`"),
    "congrArg": ("no", "congruence"),
    "congr_arg": ("no", "congruence"),
    "Classical.byContradiction": ("no", "proof technique, not a weakening"),
    "Subsingleton.elim": ("no", "consumes a subsingleton"),
    "Or.elim": ("no", "eliminator"),
    "mt": ("no", "modus tollens"),
    "Subsingleton.intro": ("no", "wraps a proposition in a structure carrying the same "
                                 "content; would report as defeq and land in "
                                 "`stripped_only`"),
    "Function.Injective.eq_iff": ("no", "uses injectivity, does not discard it"),
    "Filter.Tendsto.comp": ("no", "composition"),
    "Continuous.comp": ("no", "composition"),
    "Measurable.comp": ("no", "composition"),
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--histogram", type=Path, default=ROOT / "data/scratch/missed.tsv")
    parser.add_argument("--candidates", type=Path, default=ROOT / "data/scratch/candidates.jsonl")
    parser.add_argument("--depth", type=int, default=75)
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "table-misses.md")
    args = parser.parse_args()

    print(f"# read {args.histogram}", file=sys.stderr)
    missed = []
    for line in args.histogram.read_text().splitlines():
        if not line.strip():
            continue
        count, root = line.split("\t", 1)
        missed.append((int(count), root))
    if not missed:
        raise SystemExit(f"{args.histogram}: empty")

    total_missed = sum(c for c, _ in missed)
    read = missed[:args.depth]
    covered = sum(c for c, _ in read)
    annotated = [(c, r) for c, r in read if r in READING]
    to_add = [(c, r) for c, r in read if READING.get(r, ("", ""))[0] == "add"]

    out = [
        "# What the table did not match\n",
        "Counts generated by `tools/misses_report.py`. **The annotations are "
        "hand-written**, and are marked so, because a judgement that looks like a "
        "measurement is what cost the sibling a published correlation.\n",
        "## Why this document is the weak point\n",
        "The sibling checked its hand-written class table against one derived "
        "mechanically from `class X extends Y`, and the comparison found 89 classes "
        "the hand table had missed, `DivisionRing` among them. That check was worth "
        "more than the fix.\n",
        "Weakening lemmas are not declared as a relation anywhere in Mathlib, so this "
        "project has no second instrument. What replaces it is a person reading a "
        "histogram, which catches a miss only if they read far enough down and cannot "
        "catch one that is rare. Calling that weaker than the sibling's check is the "
        "honest description, and it goes in the paper.\n",
        "## Coverage of this reading\n",
        f"- distinct roots not matched: **{len(missed):,}**",
        f"- occurrences not matched: **{total_missed:,}**",
        f"- read here (top {args.depth}): **{covered:,}** occurrences, "
        f"{100 * covered / total_missed:.0f}% of them",
        f"- annotated: **{len(annotated)}** of the {len(read)} read",
        f"- judged a real miss: **{len(to_add)}**\n",
        "Everything below the read depth, and anything in it left unannotated, has "
        "**not** been cleared. It is unread, which is not the same as clean.\n",
    ]
    if to_add:
        out.append("## Judged real misses\n")
        out.append("| root | occurrences | why it belongs in the table |")
        out.append("|---|---:|---|")
        for count, root in to_add:
            out.append(f"| `{root}` | {count:,} | {READING[root][1]} |")
        out.append("")
    out.append("## The reading\n")
    out.append("| root | occurrences | verdict | note |")
    out.append("|---|---:|---|---|")
    for count, root in read:
        verdict, why = READING.get(root, ("unread", ""))
        mark = {"add": "**miss**", "no": "not a weakening", "unread": "_unread_"}[verdict]
        out.append(f"| `{root}` | {count:,} | {mark} | {why} |")
    args.out.write_text("\n".join(out) + "\n")
    print(f"wrote {args.out}", file=sys.stderr)
    print(json.dumps({"distinct_missed": len(missed), "occurrences": total_missed,
                      "read": len(read), "annotated": len(annotated),
                      "real_misses": len(to_add)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
