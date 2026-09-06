# Defects that shipped, and how they were found

One section per defect, numbered, one defect per number. Each becomes a test in
`tests/`, written as the failing case.

The sibling project's version of this file is the reason this one exists: fifteen
stories there, and every one of them failed the same way — *something that
resolved nothing looked exactly like something that contained nothing*. Both
print zero. The rule that follows is at the top of this page and not at the
bottom:

> **A verdict category at 0% or 100% is a bug until proven otherwise.**

Three practices, each bought with someone else's defect:

- **Read individual cases, not summaries.** Every defect in the sibling was
  invisible in aggregate and obvious in one worked example.
- **Distrust round numbers** — 0%, 100%, and exactly the value you hoped for.
- **Verify the artefact you ship, not the pipeline that produced it.** That is
  why `verify.py` reads only the published data and never a store.

And one more, which applies to this project's entire Part 1: **a new instrument
pointed at old results will find its own bugs first. Budget for that, and do not
publish the first number it gives you.**

---

## Inherited before they could ship

Two defects were found in the sibling's code while copying it, and fixed at the
copy rather than inherited. They are recorded here because the copies are in this
repository and a reader comparing the two files deserves the reason.

### I-1. `wait_for_memory` raises `NameError` on the path that matters

`tools/leanrun.py` in `unused-assumptions` defines `wait_for_memory`, which
polls free memory before launching a Lean process. It calls `json.dumps` and
`time.sleep`; the module imports neither. Six tools call it.

It has never fired there, because `available_gb()` normally clears the 4 GB
threshold on the first poll and the loop is never entered.

That condition does not hold in this project. Part 1 runs against a live sibling
sweep holding two Mathlib processes on a 36 GB machine — roughly 7 GB free — and
uses this function as its concurrency gate at 8 GB. The loop is entered on the
first run. Fixed at the copy; the test forces the loop rather than trusting that
memory is scarce when the suite runs.

*Found:* reading the function before copying it, because this plan made it
load-bearing.

### I-2. `open scoped` emitted before the plain clause

`leanrun.opened` emits `open scoped ... in` ahead of `open ... in`.
`verify.opened` emits them the other way round. The dependency runs
plain-then-scoped: `open scoped sigma` resolves as `ArithmeticFunction.sigma`
and is an unknown namespace until `ArithmeticFunction` is open.

The sibling's own notes record this as "still latent in the sweep, masked
there" — masked because the sweep also emits every directive raw a second time,
ahead of both. This project takes `verify.py`'s order and does not carry the
mask, so the masking duplicate is not copied either.

*Found:* the same read-through.

---

## Defects that shipped here

### 1. A memory gate set above the memory that exists

The plan for Part 1 set `wait_for_memory`'s threshold at 8 GB, reasoning that
this project runs beside a sibling sweep holding two Mathlib processes and
should therefore wait for plenty of room.

Measured, the machine has 36 GB and had **7.0 GB free with both of those
processes running**. A gate at 8 GB never opens. It would not have protected
anything; it would have hung the first run forever, printing a JSON line every
thirty seconds — and, worse, it would have looked like a slow sweep rather than
a stuck one, because that is exactly what a legitimate wait looks like.

The number was a guess written in prose. The measurement: a Mathlib-importing
`lean` holds about 3.4 GB resident, so one more process fits inside 7.0 GB.
The floor is now 5 GB — one process plus margin — and it is a named constant
with the measurement in the comment beside it, so the next person to change it
has to disagree with a number rather than with a habit.

*Found:* before the first run, by measuring `available_gb()` instead of quoting
the plan. The general form is the sibling's rule turned around: **a threshold
that never fires and a threshold that always fires look identical from the
outside.** Both produce a run that does nothing, quietly.

### 2. `ConstantInfo.value?` returns nothing for a theorem

The traversal reads a proof term with `ConstantInfo.value?`, which `BRIEF.md`
names as the way to get one. Run over Mathlib, it returned `ok: false, "no
value"` on **100% of rows**.

That number is the whole story. A library where no theorem has a proof and a
tool that cannot read proofs produce the same output, and the second is
overwhelmingly more likely. The rule at the top of this page exists for exactly
this shape, and it fired on the first real run of the first stage.

The diagnosis took one Lean file and did not involve guessing: define a theorem
locally, in the same file, and ask the same question of it. `value?` returned
`none` for that one too. So it was not about imported modules, `.olean` loading,
or the async environment — `ConstantInfo.value?` simply does not return a
theorem's proof at this toolchain, whatever the brief assumed. The proof is
reached by matching `.thmInfo v => v.value`.

Two things this cost nothing only because the rule caught it. Had the histogram
been read first, every root would have been absent and the obvious conclusion
would have been *the weakening table matches nothing* — a false negative about
the library, produced by a tool that never read a single proof. And the shape is
the sibling's story #1 exactly: a stage that resolved nothing, reported as a
corpus that contained nothing.

*Found:* by the 0%-or-100% rule, on the first traversal.
*Fixed:* `Unstated.proofOf` matches the constructor. `value?` is not used
anywhere in this project, and the docstring on `proofOf` says why.
*Test:* the traversal over a known declaration must return a root; a run whose
rows are 100% one verdict fails the report tool before it prints a rate.

### 3. A gate document that rendered without its evidence

`detailOf` returns `MetaM Json`. The generated command invoked it as
`MetaM Unit`, discarding the result. Fifty type errors, no rows.

The type error is not the defect. Lean caught that in seconds and said exactly
what was wrong, which is what a compiler is for. The defect is what happened
next: the renderer wrote `docs/gate-fifty.md` anyway, with **"no detail
computed" fifty times**, and exited 0.

That document is the fifty-candidate gate — the point where a person reads real
candidates and decides whether Part 1 continues. A reader opening it would have
found fifty theorem names, fifty root constants, and no statements. The
available conclusions are all wrong: that the candidates are empty, that the
tool found nothing, that the gate failed. The true state — that a Lean
invocation had the wrong type — is the one thing the document does not say.

This is the sibling's shape once more, in the reporting layer rather than the
pipeline: a stage that computed nothing produced a document indistinguishable
from a stage that found nothing.

*Found:* by reading the run's log rather than its output. The guard added two
commits earlier — refuse to overwrite an output file with zero rows — did work,
and is why there was a log to read instead of an empty details file silently
standing in for a good one.

*Fixed:* three ways, because one of them is the compile error and the other two
are the reason it mattered.
1. The call is wrapped in `emitLine`, and a test asserts every generated
   `#eval` line that mentions `detailOf` also mentions `emitLine`.
2. `gate.py` refuses to render when the details file is missing, rather than
   treating absent evidence as absent findings.
3. It also refuses when no sampled row has a statement, because an empty gate
   and a gate over candidates that are all artefacts print the same document.

### 4. A duplicate search that scanned the library once per candidate

`defeqSiblings` restricts its search to the theorem's own module, which is
correct and was the point. It found that module by walking every constant in
the environment and asking `getModuleFor?` of each one.

A quarter of a million constants, per call. Fifty calls to render one gate
document. The run hit its forty-minute timeout with nothing to show, and the
sweep it was rehearsing for would have carried the same cost into all 645 rows.

Nothing about the *result* was wrong, which is why this one is worth writing
down: a correct answer computed the expensive way looks exactly like a correct
answer, right up until it does not finish. The sibling's version of this lesson
is about wrong numbers; this is the same discipline applied to a number that
never arrives.

*Fixed:* `moduleConsts` reads the module's own `constNames` off the environment
header, so the scan is the few hundred declarations the module actually
contains. The library-wide variant keeps its full scan, because it genuinely
needs one, and it runs only on the rows that survive everything else.

*Found:* by reading the timeout in the log rather than raising the timeout.
The distinction matters. Raising it would have worked, and would have hidden a
factor of a thousand.

### 5. A script that announced a write it had not done

`gate.sh` ended with `echo "wrote docs/gate-fifty.md"`, unconditionally. When
defect 3's guard correctly refused to render, the log still said the document
had been written -- directly above the refusal that said it had not.

Two lines apart and contradicting each other. The one that reads like a result
is the one a person believes.

*Fixed:* the echo is inside the `if`, and the failure branch says what is true:
the document on disk is unchanged, which is correct, because a stale document
is at least honestly dated and one rendered without its evidence is not. The
draft render now goes to `data/scratch/`; only a render that has the statements
is allowed to land in `docs/`.

### 6. The kernel verified the statement, not the claim

The first fifty candidates came back with 48 of 50 accepted by the kernel. Two
of the 48 were nonsense. `Nat.sInf_empty` states `sInf ∅ = 0` and its
"stronger" statement was `∅ = ∅`. A Euclidean geometry row stated an equality
of distances and offered an equality of angles.

The kernel was not wrong. It was asked the wrong question. `addDecl` establishes
that a statement is **proved**; it establishes nothing about whether that
statement **implies** the theorem the row is about.

The implication was supposed to come from the table. Each entry's guarantee is
that the selected argument's type implies the *root application's* type -- for
`Or.inl h : a ∨ b`, that `h : a` gives `a ∨ b`. That chain reaches the
theorem's conclusion only if the root's type still **is** the conclusion. Peeling
an elaboration wrapper breaks exactly that: `Eq.mpr h x` and `x` have different
types by construction. With `layers > 0` the chain can be cut, and what comes
out the far end is a statement that is true, verified, and unrelated.

This is the sibling's `claims_what_it_proves` in another costume -- a pure guard
that a row's claim appears in its own source, run before spending a compile,
because *"a green recompile of the wrong statement is worse than a red one,
because it is quiet."* Here the green came from the kernel itself, which makes
it quieter still.

*Found:* by reading the fifty candidates rather than the counter above them.
`48/50 verified` is exactly the number that invites nobody to look. The two bad
rows were obvious on sight and invisible in aggregate, which is the sibling's
first practice word for word.

*Fixed, but conservatively, and the conservatism is the interesting part.*
`peel_preserved_type` records whether peeling changed the type. Six of the fifty
broke the chain -- and **four of those six look like genuine strengthenings a
person would want**. `RatFunc.denom_inv_dvd` states that a denominator divides a
numerator and its proof gives the exact formula for the inverse;
`Cardinal.natCast_lt_aleph0` states `↑n < ℵ₀` and its proof builds
`Fin (n+1) ↪ ℕ`. Both are real. Neither is established *by this chain*.

So they do not become `stripped_only` and they are not discarded. `unchained` is
its own verdict, shipped in its own bucket, never pooled with findings and never
dropped. The report says what is established about those rows (the statement is
true) and what is not (that it implies the theorem). A filter that quietly ate
four good rows in fifty would have been the more damaging fix.

### 7. A witness is not a proposition, and the kernel said so

`LTSeries.nonempty_of_infiniteDimensionalOrder` states `Nonempty α`. Its proof
carries an element of `α`. The strengthened "statement" is therefore
`(α : Type) → [Preorder α] → [InfiniteDimensionalOrder α] → α`, which is a
Type, not a Prop, and `addDecl` refused it: *type of theorem 'strengthened46' is
not a proposition*.

Read as a verification failure, that row is a tool error. It is the opposite. It
is **stage 2's entire subject** -- a statement that says a thing exists whose
proof names it, where the named thing is an object the library never gave a
name. The brief calls these "a new declaration on the library: an explicit bound
function, an explicit inverse, an explicit index."

The declaration was being emitted as a theorem because every other row is one.
It is now emitted as a `def` when the strengthened type is not a Prop, and the
row carries `is_prop` so stage 2 can find these rather than reconstruct them.

*Found:* by reading a kernel error in a log instead of a verdict in a table.
*Worth noting:* this failure mode would have hidden `Exists.intro`, the single
most common matched root in the library at 1,775 occurrences, behind an error
message -- for the subset where the witness is data rather than a proof.

### 8. The tool's own error, written into the store as a fact about 645 theorems

An edit to `Traverse.lean` left a doc comment with no declaration under it:
`-/` on one line, `/--` on the next. A parse error, and an obvious one.

It did not look like one. **Lean recovers from a parse error and elaborates the
commands after it**, so the traversal and the gate's detail run both kept
working and both emitted every row they were asked for. Fifty candidates were
detailed, read, and written up while the file they ran in did not parse.

The sweep is the only stage that scans for errors, and it did its job: it saw
them and recorded the verdict `context` -- *this tool could not reproduce the
declaration's setting*. Correct verdict, wrong subject. The error was in the
metaprogram, identical on every row, so a full run would have produced a store
saying the setting could not be reproduced for **any** of 645 theorems.

That store is not obviously broken. `context` is a legitimate verdict with a
legitimate meaning, and a column of them reads as a hard corpus rather than a
stray comment. It is the sibling's failure shape once more, and this time it had
somewhere worse to hide: not in a zero, but in a plausible non-zero verdict.

*Found:* by trialling two rows before committing sixteen hours. Both came back
`context`, which is 100% of a two-row sample, and the rule at the top of this
page does not care that the sample was small.

*Fixed:* `metaprogram_check` compiles the metaprogram **alone** before the sweep
starts, and the sweep refuses to run if it does not. That is the distinction the
`context` verdict depends on: a row's setting failing to reproduce is a fact
about the row, and it can only be recorded as one if the tool has already proved
it can compile itself. `traverse.py` also prints Lean's errors now rather than
folding them into unparsed noise.

*And a second time, in the fix.* The repair deleted one line too many, taking
the next declaration's docstring opener with it. The new check caught that
immediately, on its first run, before anything else saw it -- which is the
argument for the check, made by the check.

### 9. The same defect, in the place the test did not look

Defect 3 was `detailOf` invoked as `MetaM Unit` when it returns `MetaM Json`.
The fix wrapped the call in `emitLine` and added a test asserting that every
generated `#eval` line **mentioning `detailOf`** also mentions `emitLine`.

`rootOf` returns `MetaM Json` for the same reason and was not wrapped. The test
was written around the defect that had been seen rather than around the shape it
belonged to, so it passed while the bug it was meant to prevent sat two lines
above the code it checked.

The cost was the whole sweep reading as `context` again -- the second distinct
cause of that same symptom in one afternoon, which is its own small warning
about how much a verdict can absorb.

*Fixed:* the call is wrapped, and the test now covers **every** generated
`#eval`, not the ones matching the name that broke first.

*Second fix, and the more useful one.* A shot was counted successful only if
Lean emitted no error at all. That is stricter than the sibling's rule and
strict in the wrong direction: the rule is *never infer success from the absence
of an error*, and accepting success on positive evidence -- the kernel said
`added`, or the traversal returned a root -- does not weaken it. A row now
succeeds on an answer, and any Lean output is recorded on the row either way, so
a row that compiled while its file emitted a warning is one a person can still
go and look at.

`decide` also falls back to a detail answer when `rootOf`'s row is missing, since
the detail rows carry `root` and `layers` too. One absent answer should cost
precision, not the row -- a row written off as `context` is written into the
store as a fact about a theorem.

### 10. A name that could never match, dropping rows from a measurement

The root-shift measurement joins the sweep's rows against the library-wide
traversal on the theorem's name. Six of the first 35 rows did not join.

The sibling records a theorem written as `_root_.WCovBy.fst` inside
`namespace Prod` as **`Prod._root_.WCovBy.fst`** -- the namespace it was written
in, followed by the escape that leaves that namespace. Lean knows the
declaration as `WCovBy.fst`. The recorded string is not a name and matches
nothing, for every such row, silently.

The measurement did not fail. It reported a smaller denominator, and a smaller
denominator is exactly what a genuinely rarer phenomenon looks like. Six rows
absent because the join could not see them and six rows absent because they had
nothing to say leave the same hole.

Worth being plain about: this is not the sibling's defect. Its field records the
namespace context a declaration was written in, which is what its own compiler
needs. It is this project's defect for treating that field as a Lean name.

*Found:* by printing the rows that failed to compare instead of reading only the
comparable count. The count was 29 of 35 and looked unremarkable.
*Fixed:* `real_name` splits on `._root_.` and keeps what follows. Comparable
rows went from 29 to 33 of 36 immediately.

### 11. A measurement inflated three-fold by a renaming

The root-shift measurement asks whether weakening a typeclass changes which
lemma a proof ends on. At 310 decided rows it said three had moved.

Two of the three had not. Lean names a `match` auxiliary after the declaration
it was lifted from, and the sweep renames every declaration to `w<id>` so that
`#print axioms` names the right thing. So the same auxiliary is
`_private.Mathlib.Algebra.Order.Archimedean.Basic.0.exists_rat_lt.match_1_1` in
the library and `w70947a3b59313356.match_1_1` in the sweep. Compared as strings,
it moved. Compared as declarations, it did not.

The rate was 1.08% and is 0.36%. Three times too high.

The direction is the part worth recording. This measurement exists to decide
whether Part 2's rung-2 join can be a lookup against the traversal, taking
minutes, or must compile every joined row at the weaker class, taking hours. An
inflated move rate argues for the expensive design. A number that is wrong in
the direction of *more work, more caution, more apparent rigour* is the hardest
kind to distrust, because being talked out of it feels like cutting a corner.

*Found:* by printing the three rows rather than the count of them. The count was
3 of 278 and looked like a small honest number.
*Fixed:* `normalise_root` strips the parent's name off an auxiliary before
comparing. Genuine changes of root constant survive the normalisation, and a
test asserts that, because a fix that makes a measurement measurable must not
also make it blind.

### 12. A proof that proves nothing, one relaxation away from being a finding

Defect 9's second fix loosened the rule for accepting a compile shot: from *no
error at all* to *positive evidence* -- the kernel said `added`, or the
traversal returned a root. The reasoning still stands. The sibling's rule is
*never infer success FROM the absence of an error*, and accepting success on a
positive answer does not weaken it.

What it did weaken was something the sibling had guarded elsewhere and this
project had not copied. **Lean inserts `sorryAx` when a tactic fails.** The
declaration is still added, the proof term still exists, and `addDecl` on a
subterm of it still succeeds. Every piece of positive evidence is present and
the proof proves nothing.

One row in 645 does exactly this: `MulChar.restrictHom_surjective`. Its root came
back as `sorryAx`, so it landed in `root_not_weakening` and nothing false was
reported. With a table entry at the root it would have been `strengthens`.

That row is **also the single row the sibling itself ships as unreproduced**.
Two projects, two unrelated mechanisms -- their verifier gets a rewrite failure
recompiling from source, this one gets a `sorry` from the elaborator -- and the
same theorem. Neither could make that check alone.

*Found:* by reading the five moved roots rather than the rate they summed to.
The rate, 0.85%, was the number worth quoting and the rows were where the defect
was.
*Fixed:* `hasSorry` on both phases, and any row carrying one becomes `context`,
whatever its root. The test asserts the guard does not swallow a clean row of
the same shape.

### 13. The fix that rescued a row, and the branch that threw it away again

Defect 7 taught the kernel to accept a non-Prop strengthening as a `def`, so
that a `Nonempty` witness -- an object the library never named, and stage 2's
entire subject -- stopped reading as a verification failure. It reports
`added as a definition`.

`decide()` still tested `verify != "added"`. So the row that fix existed to
rescue was recorded as `context`: the tool's own failure.

The row is `MulChar.mulEquiv_units`, and it is one of the eight named in
`prereg/part1-yield.md` before the sweep ran. It was the single predicted row
that did not appear, and the pre-registration was right: the sweep was wrong.

There is a general shape here worth naming, because this is the third time it
has happened in this project. A fix that adds a new **success** value has to be
followed into every place that tests for the old one. Defect 3 added `emitLine`
to one call and not the other; defect 9 was the same omission a second time;
this is the third, on a return value rather than a call.

*Found:* by checking the sweep's output against a prediction committed
beforehand. Nothing else would have flagged it -- `context` on one row in 645 is
invisible, and the row would simply have been absent from the results.
*Fixed:* `witness` is its own verdict. Not `strengthens`, because that table is
statements and this is an object.

### 14. A false zero on exactly the category the brief expects to dominate

`BRIEF.md` predicts stage 2 will be a footnote: *expect most existentials in
Mathlib to be proved by `Classical.choose` or by an inherited exists from
another lemma, so that the witness is not new.*

The first run said `noncomputable_choice` was **0 of 8**. The brief's prediction
contradicted, on the first measurement.

It was not. `choiceConstants` listed the `Classical.*` family and stopped there.
**`Nonempty.some` is the idiomatic way to pull a value out of a proof in
Mathlib**, and it is `Classical.choice` underneath; so is `Exists.choose`, so is
`Trunc.out`. A witness reading `MulChar.mulEquivToUnitHom.trans ⋯.some` was
classified without anyone noticing the `.some`.

Two things make this one worth its own entry. The zero was on the category a
pre-existing prediction says should be *largest*, so the error pointed at a
publishable-looking result -- *the brief was wrong about Mathlib* -- when the
truth was that the classifier could not see. And it is the same shape as the
weakening table: a hand-written list where a missing entry reports the
flattering answer and nothing catches it. That was written in
`weakenings.json`'s own header and then not applied to the second list in the
project.

*Found:* by reading the eight witnesses instead of the four counts.
`⋯.some` is visible on the line.
*Fixed:* the list now carries `Nonempty.some`, `Exists.choose`, `Trunc.out`,
`Quot.out` and the decidability constants. `noncomputable_choice` went from 0 to
1 of 8 immediately.

### 15. An instance is not a hypothesis

The classifier flagged a witness as `depends_on_hypothesis_proof` when it
mentioned any binder whose type is a Prop. Two of eight rows landed there,
including `WeakDual.exists_countable_separating`, whose witness --
`fun n φ => φ (denseSeq E n)` -- is one of the better objects the sweep found.

The binder it depended on was `[SeparableSpace E]`. A Prop-valued typeclass is a
proof, so `Meta.isProof` was right. It is not a *hypothesis*. The brief asks for
the hypothesis case to be flagged because a witness computed from an assumption
someone made is a different kind of object; an instance argument is part of the
setting, and every witness in an algebraic statement mentions several.

Counting the two together overstates how often a witness rests on an assumption,
and it does so on the rows most worth looking at.

*Fixed:* `instance_deps` is reported separately from `proof_deps`, split on
`BinderInfo.instImplicit`, and only the latter drives the classification.

### 16. A guard that checked the class but not the variable

`claims_what_it_fails_at` asked whether a row's recorded `fails_at` class
appeared anywhere in its source. `Ne.isUnit_C` has binder `[Field k]` and a
source carrying `[CommRing R]` -- a different variable. The guard passed, the
row compiled cleanly, and it was recorded as **`compiles_anyway`**: a theorem
the sibling says fails and this project says compiles, at the same pin.

That is a publishable-looking sentence. It was false. The row compiled because
its source was still at the class where it *succeeded*, and the guard had
matched a class name attached to something else entirely.

*Fixed:* the guard reads the variable out of the binder and requires
`[<fails_at> <variable>]`. `compiles_anyway` went from 1 to 0, which is the
correct count.

*The data finding underneath.* Chasing that row showed why so many were
mismatching: the sibling's export ships **one** source per row, and for a binder
that both held somewhere and broke somewhere it ships the source that **held**.
Seven of seven strict rows with a non-null `holds_over` carry `holds_over`, and
none carries `fails_at`. For exactly the rows Track D needs, the failing compile
has no source attached.

That is the sibling's ENGINEERING #12 in a new place, and its own sentence fits:
*a stage that computes something must keep what proved it, or it has computed a
rumour.* Rebuilding the source by rewriting the binder is possible and is not
free -- the sibling rebuilt six that way and all six stopped compiling -- so a
reconstructed row is marked `reconstructed`, kept in its own bucket, and never
pooled with rows whose source arrived as shipped. All ten strict rows now yield
an error: three as shipped, seven reconstructed.

### 17. A file that does not parse is not a theorem that fails

174 rows came back `error_captured`, which is the verdict meaning *the proof
broke here and this is where*. Twenty-two of them had the error
`unexpected identifier; expected command`.

A parse failure. The file never got as far as the theorem, so the row says
nothing about the proof, the class, or the break. All 22 were sources shipped
as-is, so this is not the reconstruction's doing; a standalone file built from
that source simply does not parse.

Counted as breaks, they would have been fed to dichotomy repair as rows with a
known failure point, and the repair would have been reasoning about a syntax
error.

*Fixed:* `parse_failed` is its own verdict. The 22 were reclassified from the
stored error text with no recompile, which is what keeping the whole error block
was for.

### 18. The field the exchange asked for is the wrong field for the verdict

`docs/exchange-format-request.md` asked the sibling for `blamed`: *the constant
name Lean names as needing the structure*. The response explained it is null on
all 57,382 rows and offered a four-day re-sweep to recover it.

Recovered here on the pilot slice, the answer is **23 of 152 usable breaks, 15%**
-- and those 23 are exactly the rows whose error is an instance-synthesis
failure. Every row where the concept applies gave it up; the rest do not have
one to give.

The reason is structural and was visible in the sibling's own verdict
definitions all along. `incoherent` means *the statement cannot be stated*,
which is what an instance-synthesis failure looks like, and it is 44,979 of the
57,382 rows -- so on the file as a whole, `failed to synthesize instance of type
class` really is the dominant error, exactly as the response said.
`needs_structure` means *the statement elaborates and the proof fails*, and a
proof fails with a type mismatch, an unsolved goal, or a timeout. On this slice:
48 application type mismatches, 19 type mismatches, 12 unsolved goals, 10 whnf
timeouts, and 23 synthesis failures.

Track D consumes `needs_structure` rows only. So **the four-day re-sweep would
have recovered `blamed` for about 15% of the rows this project can use**, and
the request that prompted the offer was written against the wrong half of the
file. Worth sending back, since the offer is presumably still open.

## Upstream fixes, verified rather than trusted

`unused-assumptions` regenerated `breaks.jsonl.gz` after our report. The
manifest's recorded SHA-256 changed from `5a6cb24e…` to `c35b959b…`, which is
the visible event that recording input hashes exists to produce.

Checked before use, and it holds: 285 of 285 rows where a binder both held and
broke now carry the **failing** source, `source_class` equals `fails_at` on
every one, and `source_at_hold` carries the holding declaration separately.

The effect on Track D, re-run against the corrected export:

| | before | after |
|---|---:|---:|
| strict rows yielding an error | 10 (7 reconstructed) | **10, all as shipped** |
| `mismatch` | 26 | **0** |
| `blamed` recovered | 23 | **28** |
| rows needing binder reconstruction | 7 | **0** |

Every reconstruction is gone, and with it the caveat that those rows could not
be pooled with the rest. The reconstruction code stays, marked, because older
data still needs it and because a field that means one thing in one export and
another thing in the next is worse than a field that is always explicit.

Two numbers in the report we sent are now stale in our favour and are corrected
when the data ships: `blamed` recovery is 28 of 176, **16%**, not 15%.

### 19. A timeout that threw away what the run had produced

`run_bounded` killed the process group on timeout and then discarded everything
the child had written. That is the right behaviour for a candidate compile: a
Lean run cut off partway says nothing about the theorem in it, and half an
error is worse than none.

It is the wrong behaviour for a pass that emits one row per declaration. The
citation count over Mathlib runs for hours and prints as it goes; a timeout at
ninety percent yielded **nothing at all**, and there was no way to tell ninety
percent from five.

The general shape: a rule sound for one kind of run was applied to a different
kind without anyone asking whether it still held. The rule was inherited from
the sibling, where every Lean run is a candidate compile and the rule is simply
correct.

*Fixed:* `PartialTimeout` carries the child's output, and `traverse.py` parses
those rows rather than dropping them. The report still begins with `timeout`,
because a partial pass must not be mistakable for a complete one.

*Not fixed, and worth stating:* there is still no progress signal during a long
run. Output is captured at exit, so "running for two hours" and "wedged for two
hours" look identical from outside. That is the same shape as everything else on
this page and it is currently unaddressed.

### 20. Two hours spent on a data structure

`citationCounts` accumulated into a `NameMap`, which is a persistent red-black
tree. It does one insert per (theorem, cited constant) pair -- on the order of
tens of millions across Mathlib -- and every insert rebalances and allocates a
new path. The root traversal never paid this, because it stops at the head of
each term and never builds a map.

The run went past its timeout without finishing. `Std.HashMap` is O(1)
amortised.

The fix was written before the run was killed and deliberately **not** applied
while it was alive: swapping a data structure mid-flight to chase a guess is how
a run that was about to succeed gets thrown away for a faster one that has never
been tested. Once the run was dead the fix cost nothing, and it was compiled
alone before relaunching -- `Std.HashMap` uses `get?` where `NameMap` uses
`find?`, and that typo alone would have cost another two hours.

### 21. A hand-rolled term walk, on a graph that is not a tree

`constsIn` collected the constants a term mentions by structural recursion:
descend into the function and the argument, the binder type and the body, union
the results.

A Lean proof term is a **DAG**, not a tree. Subterms are shared aggressively --
the same instance, the same type, the same lemma application reached by many
paths -- and a recursion with no memo visits each shared subterm once per path
into it. On small proofs that is invisible. On large ones it is exponential.

The shape of the evidence: `Mathlib.Order`, 17,632 theorems, finished in about
forty seconds. The full library, sixteen times the theorems, did not finish in
two and a half hours. Twice. Both times the conclusion drawn was about the
accumulator -- first `NameMap`, then, after that was fixed and the numbers
barely moved, nothing at all -- because a sixteen-fold input taking twenty-fold
longer still looks like slowness rather than like a different complexity class.

`Expr.getUsedConstants` is in Lean core and does this properly, because the
compiler needs it. Replacing the walk: **identical output** on `Mathlib.Order`
-- 14,564 rows, not one count different -- at forty-four seconds instead of
seventy-nine.

*The lesson worth keeping is not "use the library function".* It is that two
successive fixes to the wrong component both looked plausible and both produced
a small improvement, which is exactly what a real fix looks like from the
outside. The thing that finally separated them was measuring one area and
extrapolating: 16x the input for >20x the time is not slowness, it is a
different curve, and that comparison was available before either fix.

*Defect 20's fix stands on its own merits* -- `Std.HashMap` over `NameMap` is
right regardless -- but it was not the reason the run did not finish, and this
page said it was.

### 22. Zero and not-measured, shipped to another project as the same null

The citation pass emits a constant **only if something cites it**, so a theorem
nothing cites is absent from the map rather than present with a zero.

`describe`, which computes the report, looked it up with `counts.get(n, 0)` and
was right. The writer that produced the file for `unused-assumptions` used a
bare `counts.get(n)` and got `None`. So *cited zero times* and *not measured at
all* left the file as the same `null`, distinguishable only by a separate
`found_in_corpus` column — for a field whose zeros carry the entire claim.

Every number in our own report was correct. The file shipped beside it could not
reproduce a single one of them.

They found it from arithmetic, without running anything: 198 nulls per theorem,
24 rows marked not-found, and our report claiming 174 never cited. 174 + 24 =
198. Three counts and a subtraction.

This is the failure this project has a rule about, a tool that exits non-zero
on, and nine entries on this page about. It went out the door anyway, in the one
artefact another project was going to compute on. The rule was applied
everywhere the numbers were consumed internally and nowhere on the boundary.

*Fixed:* `cited_by` is `0` when measured and uncited, `null` only when not
measured, and every row carries `cited_by_meaning` saying which in words. The
re-exported file reconciles to the report exactly: 571 measured, 174 never
cited, 24 not measured.

*Second thing, from the same exchange.* They asked whether the baseline was
theorems of the same kind. It was not entirely: restricted to the survivors'
own 325 modules, the baseline's never-cited share falls from 42.9% to 37.7%
against the survivors' 30.5%. The gap goes from 12.4 points to 7.2 and the
intervals still do not overlap. A reviewer's question, answered by a control
that should have been in the first table.

### 23. The sibling's temp-path defect, reproduced in our own artefact

`data/part1-rows.jsonl` shipped with `/var/folders/ck/…/T/tmpXXXX.lean` inside
its `detail` column. Lean prints the filename it is handed and we hand it a temp
file, so the path arrives in the error text we record verbatim.

The sibling's ENGINEERING #4 is this defect. A temp path reached a published
document there; the source had been grepped for `/Users`, `/private` and `/tmp`,
and macOS puts temp files under `/var/folders`. Their lesson, which
`docs/from-the-brother.md` in this repository quotes: **read the built artefact,
not the source that produces it.**

We wrote that down in the first session and shipped the defect anyway, in a file
we generated ourselves, four sessions later.

*Found:* by grepping the tracked files before creating a remote, which is the
lesson applied at the one moment it was going to matter. Not by any test.

*Fixed:* `redact` strips absolute temp paths from every field on export, and the
test does two things — checks the function, and then greps the **shipped files
in `data/`** for `/var/folders`, `/private/var` and `/tmp/`. The second is the
one that would have caught it, and it fails today if any artefact regresses.

*Also fixed in passing:* `data/scratch/` was tracked, 57 MB of intermediate
traversal dumps in a repository whose actual artefacts are under 300 KB. Those
regenerate in about forty minutes and nothing reads them. What ships is now the
rows themselves, generated by `tools/export_rows.py`, in the sibling's shape:
stores are working data, the verifier reads the published files and never a
store.
