# What this project takes from `unused-assumptions`

Written from a read-only session over
`https://github.com/carlok/unused-assumptions` on 3 September 2026,
before any file of this project existed. Nothing there was modified, and nothing
here imports or symlinks it: what is reused is **copied**, and diverges from the
moment it is copied.

The brother is a reference, not a parent. After this document, this is an
autonomous project with its own pipeline, its own stages, and its own repository.

---

## The two projects are not the same shape

`unused-assumptions` weakens a hypothesis and asks the compiler. Its cost is one
compile per attempt, so its pipeline is built around making 116,265 compiles
survivable: collect, signatures, precheck, attempt, prior art, descent — six
stages, a resumable store, a sweep measured in days.

This project reads the root of a proof term. That is a single pass over the
environment, milliseconds per declaration. The strengthened statement does not
need recompiling to be believed, because its proof is a subterm of a term the
kernel already accepted. **So the stage list does not carry over.** Collect and
recompile are replaced by one traversal; verification moves from "compile it
again" to `inferType` plus `addDecl`; recompilation from source survives only as
the check on the shipped artefact.

What does carry over is everything the brother learned about not fooling itself.

---

## Reused as-is

| what | from | why |
|---|---|---|
| `run_bounded` | `tools/leanrun.py` | `lake env lean` spawns `lean` beneath it, so `subprocess.run`'s timeout kills the parent and leaves a grandchild holding a compiled Mathlib. Gigabytes per timeout, accumulating until the machine dies. That is what took the brother's first run down. Own process group, `killpg` on timeout. |
| `available_gb` / `wait_for_memory` | `tools/leanrun.py` | Starting a Mathlib process with no memory free is the other way to take the machine down. **Load-bearing here in a way it is not there** — see "Two bugs fixed at the copy". |
| `ERROR_RE` | `tools/leanrun.py`, `verify.py` | Lean writes tagged diagnostics as `error(lean.synthInstanceFailed):`, which does **not** contain the substring `error:`. A scan for the literal reads a file full of instance failures as clean. The regex makes the tag optional: `error(?:\([^)]*\))?:`. |
| `AXIOMS_RE` and the axiom rule | `verify.py` | Success comes from `#print axioms`, never from the absence of an error. Two relaxations, both scar tissue: the used set must be a **subset** of `{propext, Classical.choice, Quot.sound}`, never equal to it; and both spellings must match — `depends on axioms: [...]` *and* `does not depend on any axioms`. Missing the second failed 40 rows there for being cleaner than required. |
| `header_for` | `tools/leanrun.py` | Mathlib has an umbrella module, so `import Mathlib` suffices. TauCeti's root module is deliberately empty (verified: it is comments plus a bare `module`), so a candidate must import the module it came from. Imports must precede any command, hence the `replace` on `"\nset_option"`. |
| `opened` | `verify.py` — **not** `leanrun.py` | Scope belongs to the declaration, not the file: everything folds into one `open ... in`. A bare `open` is a command and persists, letting one candidate elaborate on a neighbour's scope. Every namespace **prefix** is opened, not only the leaf. |
| The preflight | `tools/sprint.sh:119`, `verify.preflight` | `#check @Nat.succ_le_succ` before anything. A toolchain bump leaves the dependency's oleans unreadable; `lake build` then exits 0 without fixing them, every `#check` resolves nothing, and every attempt scores the same verdict. The resulting store is indistinguishable from a finished sweep. It has fired twice. Three seconds against two days. |
| The revision guard | `verify.py:335` | It resolves **Mathlib's** revision under `.lake/packages/mathlib`, not the wrapper project's — comparing the project's HEAD reports a mismatch on every run. A missing revision does not trip the guard; a differing one does, and `--force` prefixes every output line with `OFF-REVISION`. |
| Store-derived resumability | `tools/sprint.sh:74` | No marker file. Completeness is a query over the store, because a marker can disagree with the data and a query cannot. `commit()` after every row; the work query selects only undecided rows; a kill costs one compile. |
| Generated numbers | `tools/note_tables.py`, `paper/tables/*.tex` | Every figure the prose quotes is a `\newcommand` generated from the data. Six numbers went stale in the brother before that rule was applied everywhere, and they went stale quietly, because nothing rereads a paragraph. |
| Tests as defects | `tests/test_pipeline.py` | One test per defect that shipped, written as the failing case, standard library only. |

Also copied, and adapted rather than reused verbatim: `tools/density.py` (its
tails, its Wilson intervals, its design-effect correction), `tools/export.py`
(the manifest-with-hashes shape), and the `tools/sprint.sh` skeleton.

## Two bugs fixed at the copy, not inherited

**`wait_for_memory` raises `NameError`.** It calls `json.dumps` and `time.sleep`;
`leanrun.py` imports neither. Six tools call it. It survives there only because
`available_gb()` normally clears its 4 GB threshold on the first poll, so the
loop is never entered.

That condition does not hold here. This project runs against a *live* sibling
sweep holding two Mathlib processes on a 36 GB machine — roughly 7 GB free — and
uses that function as its concurrency gate at 8 GB. The loop will be entered on
the first run. Fixed at the copy, with a test that forces the loop.

**`opened` emits `open scoped` before the plain clause.** `open scoped sigma`
resolves as `ArithmeticFunction.sigma` and is an unknown namespace until
`ArithmeticFunction` is open, so the dependency runs plain-then-scoped.
`verify.py` has the corrected order; `leanrun.py` still has the old one, masked
because the sweep also emits every directive raw a second time ahead of both.
The brother's own `ENGINEERING.md` records it as "still latent in the sweep".
This project takes `verify.py`'s order and does not carry the mask.

## Adapted — same lesson, different mechanism

**Prior art becomes the duplicate check.** `priorart.py` replaces the proof with
`exact?` and asks whether Mathlib closes the statement unaided. Three outcomes,
and the third is the important one: `not_a_weakening`, where the citation is the
theorem's **own** name. The first eight nominations there were all of this kind.

Here the same three outcomes appear as `duplicate` / `strengthens` /
`stripped_only`, and `exact?` is the strongest of four legs (the others: sibling
name pattern, by type, by alpha-equivalence). The self-citation trap transfers
unchanged, including its bug: the brother compared the citation's *last*
component against the theorem's *full* name, so any theorem with a dot in its own
name could never match and filed its self-citations as genuine prior art. Leaf
against leaf.

**Descent becomes strengthening descent.** `floor.py` exists because the sweep
reported the edge its table contained, which is a fact about the table rather
than about the theorem; its headline survivor was reported at `Field -> CommRing`
and actually held three steps lower. The same failure is available here: the
first weakening at the root is where *our* table stopped looking. So after a root
match, recurse into the selected subterm — its own root may be another weakening.

With the brother's correction attached. `floor` shipped as a class name with no
source behind it, because the store had no column for the source that proved it;
62 of 645 published rows claimed something the artefact could not check. Here
every recorded depth ships with the subterm that earned it, or it ships in a
column named `_unverified` and nothing quotes it. **A stage that computes
something must keep what proved it, or it has computed a rumour.**

**Two buckets become two buckets, differently drawn.** There: `structural` vs
`reusability`, split on magnitude and breadth. Here: *library value* (the
stronger form is a restatement, same proof, sharper statement, mathematically
inert) vs *the narrow bucket* (the stronger statement is a different theorem).
The reason is identical — reporting one number would overstate the result, and
the overstatement would be invisible afterwards.

**`magnitude` has no analogue and should not be invented one.** Its ordinals rank
distance within a class hierarchy. Conclusion strengthening has no hierarchy to
rank against, and a fabricated scale would be a guess wearing a measurement's
clothes — which is the exact shape of the brother's story #8. The stand-in is the
descent depth above, which is a count of actual peeled layers, not a score.

**Two shots become two shots.** The sweep compiles with the file's `open`
directives and retries without them, because a directive such as `open scoped
zeta` names a notation namespace that does not resolve outside its own file. The
brother's verifier reproduced the *result* but not the *procedure* — it always
included the directives, and so failed rows the sweep had passed. Seventeen of
eighteen apparent non-reproductions were the checker's own bugs, and the true
rate is one row in 645. Here the two-shot retry exists **and the artefact records
which shot won**, which the brother's rows still do not carry.

## Does not apply

| what | why not |
|---|---|
| `typeclass.py` (collect + attempt) | Replaced by the traversal. There is no per-attempt compile to schedule: the root of every proof term in the library is one pass. |
| `precheck.py` | It rejects impossible weakenings without compiling, by closing over what each class demands. Nothing here proposes a statement that might fail to elaborate — the strengthened statement is the type of a subterm that already typechecks. |
| `signatures.py` / `not_a_binder` | It exists because the brother had to guess which binders a declaration really takes. The traversal reads the actual `ConstantInfo`, so there is nothing to guess. |
| `derive_edges.py` and the two-table comparison | Its derived table comes from `class X extends Y`, a relation the library declares. Weakening lemmas are not declared as a relation anywhere; `WEAKENINGS` here can only be hand-written, so there is no second instrument to check it against. **This is a real loss** — the brother could cross-check one table against another and did, finding 89 missing classes that way. The substitute is weaker: the `root_not_weakening` histogram over the full traversal, read by hand before the freeze. |
| `jointly.py` | It asks whether several weakenings of one theorem hold at once. A theorem has one root; there is no subset question. |
| `triage.py`'s `STRENGTH` / `FAMILY` | See `magnitude` above. |
| `compare.py` | Cross-corpus comparison. Part 1 is Mathlib only, and TauCeti is not exported yet. |
| `perturb.py` | Perturbation is retired in the brother and named in `BRIEF.md` only as the failure mode this project exists to avoid. |

## The rules taken whole

- **A verdict category at 0% or 100% is a bug until proven otherwise.** Every
  defect in that pipeline failed the same way: something that resolved nothing
  looked exactly like something that contained nothing. Both print zero.
- **A fallback branch will be taken, and it should return the least interesting
  value rather than the most.** An unplaceable class scored maximum depth there,
  and 40 of 64 apparently-deep survivors were that default. Here: an unmatched
  root is `root_not_weakening`, never `strengthens`.
- **Read the built artefact, not the source that produces it.** A temp path
  reached a published document; the source had been grepped for `/Users`,
  `/private` and `/tmp`. macOS puts temp files under `/var/folders`.
- **Make the input list an output.** A glob written to mean two stores matched a
  third, and one instrument was compared against a union of both. The published
  correlation was +0.92; it is +0.73. Nothing in the data could have caught it.
- **One point is not a check. It is an anecdote with a number in it.** A Student
  t tail returned negative probabilities at every df above 1, and had been
  checked at df = 1.
- **Read individual cases, not summaries.** Every defect above was invisible in
  aggregate and obvious in one worked example.
- **A new instrument pointed at old results will find its own bugs first. Budget
  for that, and do not publish the first number it gives you.** Part 1 is exactly
  that: a new instrument pointed at the brother's 645 rows.

## What was checked rather than believed

`BRIEF.md` asks for three claims to be verified before they are relied on. Two
are settled here; the third is settled in `ENGINEERING.md` when the metaprogram
exists.

- **The export schemas.** Read, not assumed. `survivors.jsonl` is 645 rows over
  595 unique theorems, 16 fields. `breaks.jsonl.gz` is 57,382 rows, 17 fields,
  `blamed` null on every one of them, `descent` present. `id` is
  `sha256('module|theorem|binder_index|to_class')[:16]` — per *target class*, so
  one (theorem, binder) has several ids and `id` is the wrong join key. `key` is
  `corpus:module:theorem:binder`; the module is in there because 1,663 Mathlib
  theorem names appear in more than one module.
- **TauCeti's root module.** Still comments plus a bare `module` at
  `4fae4090…` — so `SWEEP_IMPORT` must name the row's own module there, and
  `header_for` already does.
- **`inferType` on the subterm plus a defeq check as sufficient verification.**
  Not yet settled. Universe levels, metavariables, and `_proof_n` auxiliaries
  whose type mentions local hypotheses are the three ways it could fail. The
  answer goes in `ENGINEERING.md` either way.

## One thing the brief assumed that the data does not support

Part 1's Track D pilot was budgeted at ~200 candidates drawn from the survivors'
own rows in `breaks.jsonl.gz`. Joining the two files on `key` gives 277 rows —
binders that both held somewhere and broke somewhere, which is the rung-3 shape.

But 267 of those 277 broke with verdict `incoherent`, which the brother's
`docs/pipeline.md` defines as *"the statement cannot be stated — a sibling
instance demands the stronger class"*. A dichotomy `a'' -> b ∨ c` needs an `a''`
the statement can be written over, so an incoherent break cannot host one.

**Ten rows remain.** Four of the ten are `IsDomain -> Nontrivial`, whose
exceptional case is `Subsingleton` — which `BRIEF.md` names in advance as the
outcome that means the track produced a linter rather than theorems.

The pilot therefore runs on two populations, tabled separately and never merged:
the 10 strict rung-3 rows, and a stratified top-up from the 2,551
`needs_structure` rows that are their theorem's only break, which exercises the
machinery but is not rung 3 and yields no rung-3 rate.
