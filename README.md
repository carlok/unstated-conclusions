# unstated-conclusions

Which theorems in Mathlib state a **weaker conclusion** than their own proof
establishes? Not by generating stronger statements — that space is not
enumerable — but by reading the root of the proof term. If the last step of a
proof is a weakening lemma (`le_of_lt`, `le_of_eq`, `Or.inl`, `Exists.intro w _`,
`ne_of_gt`, `Nonempty.intro`, `And.left`, ...), then the proof has already
established the stronger statement and discarded it in its final line. The
stronger statement is a subterm, it arrives with its own proof, and it typechecks
by construction. A finite hand-written table decides what counts as a weakening;
nothing else is judgement.

This is the dual of [`unused-assumptions`](https://github.com/carlok/unused-assumptions), which asks the
same question about hypotheses: there you weaken a binder and keep the proof
byte for byte, here you keep the setting and read what the proof actually
delivered.

## No new mathematics in stages 1 and 2

Every row this produces is a statement a competent reader grants on sight once
shown the proof. The claim is the **map** — where in a library conclusions carry
slack, and whether that is the same place hypotheses carry slack — not any
individual row. Stage 3 bets that candidates which are *true with proof* rank
better than the perturbations that failed before it; that bet is reported either
way, and it has not been run.

## Part 1 reports no rate about Mathlib

The project runs in two parts and the wall between them is statistical, not
organisational. **Part 1 is a pilot on `unused-assumptions`' own survivors** — a
population of theorems already known to carry hypothesis slack. A rate computed
there is a rate among those theorems and nothing more, so it cannot feed the
per-area correlation, the rung-1 baseline, or the ladder curve. Every Part 1
table names its population in its caption: `population: unused-assumptions
survivors (Mathlib)`. Part 2 is the library-wide measurement and it begins after
Part 1's table is frozen.

## Status

Part 1, at the fifty-candidate gate. The chain runs end to end: the metaprogram
reads proof roots, the table's 22 entries all resolve at the pinned revision,
and the traversal covers the library in one process. **No mathematical finding
exists yet**, and this section says so rather than leaving the question open.

Three defects have shipped and are written up in `ENGINEERING.md`, each with a
test written as the failing case. The one worth reading is defect 2: the first
traversal reported "no value" on 100% of rows, because `ConstantInfo.value?`
does not return a theorem's proof at this toolchain. A library with no proofs
and a tool that cannot read proofs print the same thing.

## Counts live in `data/MANIFEST.json`

Not in this file, and not in any prose. A number typed into a paragraph goes
stale the moment the next run lands, and it goes stale quietly, because nothing
rereads a paragraph. Six of them did in the sibling project before that rule
took. Prose quotes generated macros; the manifest is generated; this sentence is
not a number.

## Verdicts are kept apart

The tool's own failures must not inflate the yield, so they are counted
separately and never merged into it.

| verdict | meaning |
|---|---|
| `strengthens` | the stronger statement is established by the subterm and is not already in the library |
| `duplicate` | the stronger statement already exists, by sibling name pattern, by type, or up to alpha-equivalence. Recorded as a pair — this is a measurement of API design, not waste |
| `root_not_weakening` | the root head is not in the table |
| `stripped_only` | the only slack was an elaboration wrapper. Not a finding |
| `context` | the tool failed to reproduce the declaration's setting. **The tool's failure**, not a fact about the theorem |

And two buckets in every report, never one:

- **Library value** — the stronger form is a restatement: same proof, sharper
  statement, mathematically inert. Most rows will be here, and most of *those*
  are deliberate, because the `≤` form is the one downstream uses. That is not a
  defect of the library and the report says so.
- **The narrow bucket** — the stronger statement is not a sibling of the stated
  one but a different theorem. This is the bucket worth writing about, and
  collapsing the two would overstate what was found.

## Requirements

Python 3, standard library only, for everything a reader runs without Lean.

This repository contains **no Lean toolchain and no Mathlib checkout**, and adds
no gigabyte to the disk. It reaches Mathlib through `SWEEP_REPO`, an installation
that already exists; see `env.example`. The only command it runs inside that
directory is `lake env lean <file>` on a file in its own temp directory.

## Licence

Apache-2.0, matching Mathlib.
