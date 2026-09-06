# Pre-registered: what the Part 1 sweep will find

Written 3 September 2026, with 12 of 645 rows decided and none of them matched.
Committed before the run finished, so it can be wrong in public.

## The prediction

**The Part 1 sweep will yield roughly 8 matched rows, not hundreds.**

It is not a guess. The library-wide traversal already holds the root of every
theorem in Mathlib at this pin, and 563 of the sibling's 595 survivor theorems
appear in it. Of those 563, **8** have a root in the weakening table:

| theorem | root |
|---|---|
| `Multipliable.sum` | `Exists.intro` |
| `Subalgebra.LinearDisjoint.exists_field_of_isDomain_of_injective` | `Exists.intro` |
| `NonarchAddGroupSeminorm.add_bddBelow_range_add` | `Exists.intro` |
| `GroupSeminorm.mul_bddBelow_range_add` | `Exists.intro` |
| `WeakDual.exists_countable_separating` | `Exists.intro` |
| `spectrum.eventually_isUnit_resolvent` | `Exists.intro` |
| `MulChar.mulEquiv_units` | `Nonempty.intro` |
| `edist_ne_top_of_mem_ball` | `ne_of_lt` |

That count is over the **original** declarations. The sweep compiles the
**weakened** ones, so the two can differ, and the size of that difference is the
thing the run actually measures (see below).

## Rates, and the wall

- Every theorem in Mathlib: 3,498 of 276,024 match. **1.27%.**
- The sibling's survivors: 8 of 563. **1.42%.**

Neither is reported as a result. The second is a rate among theorems already
known to carry hypothesis slack -- `population: unused-assumptions survivors
(Mathlib)` -- and the first comes from a pre-freeze run whose output built the
table it is measured against. Part 2 re-runs after the freeze and quotes that.

Stated anyway, as a prediction rather than a finding: **the two rates are close,
and that is mild evidence against a strong correlation between hypothesis slack
and conclusion slack.** The brief pre-registers that correlation as the cheapest
new question in the project. This is the crudest possible cut at it, on the
wrong population, with no clustering correction and no per-area breakdown. If
the properly computed Part 2 figure shows a strong correlation, this note is
evidence the crude cut was misleading, which is worth knowing either way.

## Why the run continues anyway

The eight rows could be swept in five minutes. Sweeping all 645 takes about
eight hours, and buys three things the eight cannot:

1. **The chain, exercised.** Part 1's stated purpose in `BRIEF.md` is to build
   and debug the whole mechanical chain on the smallest input that exercises all
   of it. Nine defects have already come out of that, four of them found only
   because a real row went through end to end.
2. **Does weakening change the root?** The 8 above are the roots of the
   *original* declarations. The sweep reads the roots of the *weakened* ones.
   Every row where those differ is a case where relaxing a typeclass changed
   which lemma the proof ends on -- through instance resolution, so the proof
   text is byte-identical and the term is not. Nothing else measures that, and
   it decides whether Part 2's library-wide traversal can be trusted to stand in
   for a rung-2 join or whether the join needs its own compile.
3. **A denominator.** A rung-2 table of eight rows means nothing without the 645
   it came from.

## What would falsify this

More than 20 matched rows, or fewer than 3. Either would mean weakening changes
proof roots far more often than expected, and that the library-wide traversal is
a poor proxy for what a weakened declaration proves.
