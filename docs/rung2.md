# Rung 2: weaker setting and stronger conclusion

**population: unused-assumptions survivors (Mathlib)**

A rung-2 row is a theorem whose setting `unused-assumptions` weakened and whose conclusion this project strengthens, at the same Mathlib pin. Two independent edits, and the composite compiles by construction: a subterm of a proof that typechecks under the weaker setting typechecks under it. The kernel is asked anyway.

**No number here is a library rate.** This set is theorems already known to carry hypothesis slack, so a rate over it says nothing about Mathlib. Part 2 measures library-wide, after the freeze.

> **Progress read.** 323 of 645 rows are still undecided. These counts will move.

## Verdicts

| verdict | rows | share of 322 decided | meaning |
|---|---:|---:|---|
| `root_not_weakening` | 314 | 97.5% | the proof's root is not in the table |
| `strengthens` | 6 | 1.9% | the subterm establishes a stronger statement, and no declaration in the theorem's own module already states it |
| `context` | 1 | 0.3% | this tool could not reproduce the declaration's setting. The tool's failure, counted apart |
| `unchained` | 1 | 0.3% | verified true, but wrapper stripping cut the chain, so that it implies the stated theorem is NOT established here |

### Degenerate categories, flagged

A verdict category at 0% or 100% is a bug until proven otherwise. Every defect in the sibling's pipeline failed the same way: something that resolved nothing looked exactly like something that contained nothing.

- `duplicate` never occurred in 322 decided rows
- `stripped_only` never occurred in 322 decided rows

## The rows

### `strengthens` -- 6 rows

_the subterm establishes a stronger statement, and no declaration in the theorem's own module already states it._

**`GroupSeminorm.mul_bddBelow_range_add`** (Analysis)  
setting weakened `CommGroup` → `Group`; root `Exists.intro`  

```lean
-- states
∀ {R : Type u_1} {R' : Type u_2} {E : Type u_3} {F : Type u_4} {G : Type u_5} [inst : Group E] [CommGroup F]
  (p q : GroupSeminorm E) (x : E) {p q : GroupSeminorm E} {x : E}, BddBelow (Set.range fun y => p y + q (x / y))

-- proves
∀ {R : Type u_1} {R' : Type u_2} {E : Type u_3} {F : Type u_4} {G : Type u_5} [inst : Group E] [CommGroup F]
  (p q : GroupSeminorm E) (x : E) {p q : GroupSeminorm E} {x : E} ⦃a : ℝ⦄,
  (a ∈ Set.range fun y => p y + q (x / y)) → 0 ≤ a
```

**`NonarchAddGroupSeminorm.add_bddBelow_range_add`** (Analysis)  
setting weakened `AddCommGroup` → `AddGroup`; root `Exists.intro`  

```lean
-- states
∀ {R : Type u_1} {R' : Type u_2} {E : Type u_3} {F : Type u_4} {G : Type u_5} [inst : AddGroup E]
  {p q : NonarchAddGroupSeminorm E} {x : E}, BddBelow (Set.range fun y => p y + q (x - y))

-- proves
∀ {R : Type u_1} {R' : Type u_2} {E : Type u_3} {F : Type u_4} {G : Type u_5} [inst : AddGroup E]
  {p q : NonarchAddGroupSeminorm E} {x : E} ⦃a : ℝ⦄, (a ∈ Set.range fun y => p y + q (x - y)) → 0 ≤ a
```

**`WeakDual.exists_countable_separating`** (Analysis)  
setting weakened `NontriviallyNormedField` → `NormedField`; root `Exists.intro`  

```lean
-- states
∀ {𝕜 : Type u_1} {M : Type u_2} {E : Type u_3} [inst : NormedField 𝕜] [inst_1 : AddCommGroup M] [TopologicalSpace M]
  [_root_.Module 𝕜 M] [inst_4 : SeminormedAddCommGroup E] [inst_5 : NormedSpace 𝕜 E]
  [TopologicalSpace.SeparableSpace E],
  ∃ gs, (∀ (n : ℕ), Continuous (gs n)) ∧ ∀ ⦃x y : WeakDual 𝕜 E⦄, x ≠ y → ∃ n, gs n x ≠ gs n y

-- proves
∀ {𝕜 : Type u_1} {M : Type u_2} {E : Type u_3} [inst : NormedField 𝕜] [inst_1 : AddCommGroup M] [TopologicalSpace M]
  [_root_.Module 𝕜 M] [inst_4 : SeminormedAddCommGroup E] [inst_5 : NormedSpace 𝕜 E]
  [inst_6 : TopologicalSpace.SeparableSpace E],
  (∀ (n : ℕ), Continuous fun φ => φ (TopologicalSpace.denseSeq E n)) ∧
    ∀ ⦃x y : WeakDual 𝕜 E⦄, x ≠ y → ∃ n, x (TopologicalSpace.denseSeq E n) ≠ y (TopologicalSpace.denseSeq E n)
```

**`Convexity.StdSimplex.restrict_ne_zero_aux`** (Geometry)  
setting weakened `LinearOrder` → `PartialOrder`; root `LT.lt.ne'`  

```lean
-- states
∀ {R : Type u_1} {X : Type u_2} {M : Type u_3} {N : Type u_4} {P : Type u_5} {I : Type u_6} {J : Type u_7}
  {K : Type u_8} [inst : Semifield K] [inst_1 : PartialOrder K] [IsStrictOrderedRing K] {w : Convexity.StdSimplex K X}
  {p : X → Prop} [inst_3 : DecidablePred p],
  (∃ a, p a ∧ w.weights a ≠ 0) → ((Finsupp.filter p w.weights).sum fun _x k => k) ≠ 0

-- proves
∀ {R : Type u_1} {X : Type u_2} {M : Type u_3} {N : Type u_4} {P : Type u_5} {I : Type u_6} {J : Type u_7}
  {K : Type u_8} [inst : Semifield K] [inst_1 : PartialOrder K] [IsStrictOrderedRing K] {w : Convexity.StdSimplex K X}
  {p : X → Prop} [inst_3 : DecidablePred p],
  (∃ a, p a ∧ w.weights a ≠ 0) → 0 < (Finsupp.filter p w.weights).sum fun _x k => k
```

**`Convexity.StdSimplex.restrict_ne_zero_aux`** (Geometry)  
setting weakened `Semifield` → `CommSemiring`; root `LT.lt.ne'`  

```lean
-- states
∀ {R : Type u_1} {X : Type u_2} {M : Type u_3} {N : Type u_4} {P : Type u_5} {I : Type u_6} {J : Type u_7}
  {K : Type u_8} [inst : CommSemiring K] [inst_1 : LinearOrder K] [IsStrictOrderedRing K] {w : Convexity.StdSimplex K X}
  {p : X → Prop} [inst_3 : DecidablePred p],
  (∃ a, p a ∧ w.weights a ≠ 0) → ((Finsupp.filter p w.weights).sum fun _x k => k) ≠ 0

-- proves
∀ {R : Type u_1} {X : Type u_2} {M : Type u_3} {N : Type u_4} {P : Type u_5} {I : Type u_6} {J : Type u_7}
  {K : Type u_8} [inst : CommSemiring K] [inst_1 : LinearOrder K] [IsStrictOrderedRing K] {w : Convexity.StdSimplex K X}
  {p : X → Prop} [inst_3 : DecidablePred p],
  (∃ a, p a ∧ w.weights a ≠ 0) → 0 < (Finsupp.filter p w.weights).sum fun _x k => k
```

**`edist_ne_top_of_mem_ball`** (Topology)  
setting weakened `EMetricSpace` → `PseudoEMetricSpace`; root `ne_of_lt`  

```lean
-- states
∀ {β : Type u_1} [inst : PseudoEMetricSpace β] {a : β} {r : ENNReal} (x y : ↑(Metric.eball a r)), edist ↑x ↑y ≠ ⊤

-- proves
∀ {β : Type u_1} [inst : PseudoEMetricSpace β] {a : β} {r : ENNReal} (x y : ↑(Metric.eball a r)), edist x y < ⊤
```

### `unchained` -- 1 rows

_verified true, but wrapper stripping cut the chain, so that it implies the stated theorem is NOT established here._

**`spectrum.eventually_isUnit_resolvent`** (Analysis)  
setting weakened `NontriviallyNormedField` → `NormedField`; root `Exists.intro`  

```lean
-- states
∀ {𝕜 : Type u_1} {A : Type u_2} [inst : NormedField 𝕜] [inst_1 : NormedRing A] [inst_2 : NormedAlgebra 𝕜 A]
  [CompleteSpace A] (a : A), ∀ᶠ (z : 𝕜) in Bornology.cobounded 𝕜, IsUnit (resolvent a z)

-- proves
∀ {𝕜 : Type u_1} {A : Type u_2} [inst : NormedField 𝕜] [inst_1 : NormedRing A] [inst_2 : NormedAlgebra 𝕜 A]
  [CompleteSpace A] (a : A), True ∧ ∀ ⦃x : 𝕜⦄, x ∈ norm ⁻¹' Set.Ioi (‖a‖ * ‖1‖) → IsUnit (resolvent a x)
```

## Areas

| area | rung-2 rows |
|---|---:|
| Analysis | 4 |
| Geometry | 2 |
| Topology | 1 |

