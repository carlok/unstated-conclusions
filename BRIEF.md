# Project brief: unstated-conclusions

Working name: `unstated-conclusions`, the dual of `unused-assumptions`. Rename freely.

Folder and its own local git repository: `.`. Standalone — related to nothing but its brother `unused-assumptions`, whose way of reaching Mathlib and TauCeti it copies exactly (same two installations already on disk, reached by path through `SWEEP_REPO`; nothing new installed). See "Environment" below before creating anything.

Use this brief to start the project from scratch. It states the question, the method, the verdicts, what is measured, the prior art to cite, the build order with its gates, and what would make the result fail honestly. Everything numeric is to be generated, never typed into prose.

If you were asked to "read this and make a plan": plan **Part 1 only** (see "Two parts, and the wall between them"). Its first item is the read-only study of the brother project described below, with output `docs/from-the-brother.md`; its last items are the Track D pilot gate and the freeze. Part 2 gets its own plan after the freeze, from the same document. Ask one question before planning if it is not stated: whether the brother's sweep is currently running on this machine, since that decides the concurrency limits in the rules below.

## Instructions for the agent building this

You are creating a new project in the folder above, from this document, on a machine where a sibling project (`unused-assumptions`) may be running a multi-day sweep at the same time. Read the whole brief before writing a file. Then:

**Before anything else: study the brother.** Spend the first session reading `https://github.com/carlok/unused-assumptions`, read-only, before writing a single file here — its `README.md`, `ENGINEERING.md` (every defect that shipped and how it was found; most of them will try to ship here too), `tools/` (the pipeline stages and their order: collect → signatures → precheck → compile → prior art → floor; the SQLite store schema; how `sprint.sh` makes a sweep resumable and how the status runner reports it), `tests/` (one test per shipped defect, written as the failing case), `verify.py` (the revision guard, the axiom check, the `synthInstanceFailed` lesson), `paper/` (numbers as generated macros, never typed), and `data/MANIFEST.json`. Write down, in `docs/from-the-brother.md`, what you will reuse as-is, what you will adapt, and what does not apply here and why — the root-of-proof-term traversal replaces the collect-and-recompile stages, for instance, so the stage list is not the same. The point is to inherit the hard-won discipline (resumable stores, verdicts kept apart, two-bucket reporting, generated counts, tests as defects, honest failure rows shipped rather than dropped) and to avoid re-shipping the brother's mistakes, not to fork it. After that first session this is an autonomous project: its own pipeline, its own stages, its own decisions, its own repository; the brother is a reference, not a parent.

**Start here, in this order.** (0) The study session above, ending in `docs/from-the-brother.md`. (1) `git init` in the project folder; README stating the question in one paragraph and the "does not produce new mathematics in stages 1–2" sentence up front; Apache-2.0; `env.example` with the two `SWEEP_REPO` paths from the Environment section. (2) Copy — do not import, symlink or modify in place — the listed tools from the brother. (3) The `WEAKENINGS` table with one worked example per entry. (4) The metaprogram, tested on ten hand-picked survivors in the Mathlib installation. (5) The fifty-candidate gate, by hand, reported in `docs/`. Nothing beyond step 5 until the gate is read. This is the start of Part 1; the full sequence is under "Two parts, and the wall between them".

**Verify, do not trust, these claims of the brief.** They were written from reading, not from running:
- that `inferType` on the proof subterm plus a defeq check is sufficient verification for a strengthened statement (check universe levels, metavariables, and auxiliary `_proof_n` lemmas whose type mentions local hypotheses);
- the actual fields of `breaks.jsonl.gz` and `survivors.jsonl` and the `id_scheme` / `key_scheme` entries of the brother's `MANIFEST.json` — read the first rows and the manifest before writing the importer; fall back to `.schema` on a store snapshot only if the export is missing;
- that TauCeti's root module is still empty at its current pin and that `SWEEP_IMPORT` still resolves names there.
If any of these is false, record it in `ENGINEERING.md` and adjust; do not silently work around it.

**Off limits — hard rules, no exceptions, do not ask for one.** These exist so the sibling's running sweep is not disturbed:
- Inside the two `SWEEP_REPO` directories the only permitted command is `lake env lean <file>` where `<file>` lives in *this* project's temp directory. No `lake build`, `lake update`, `lake exe cache get`, no `elan` commands, no editing, no creating files there. A rebuild or a toolchain move under a running sweep invalidates its compiled artefacts mid-run.
- Prefer the brother's exported files (`data/survivors.jsonl`, `data/breaks.jsonl.gz`) over its stores; they exist for this purpose. If a store must be read anyway, do not open it live. Snapshot each once with `sqlite3 <src> ".backup <this-project>/data/snapshots/<name>.db"` (the online backup API, safe against a concurrent writer), read the snapshot, record the source path and SHA-256 in `MANIFEST.json`. Never write to a store under the producing project's stores.
- Do not run more than two `lean` processes concurrently unless told the sibling's sweep is finished. Each Mathlib-importing `lean` takes gigabytes; if the sibling's candidates hit their timeouts under load, a timeout is recorded there as a verdict and its results, not yours, are the ones corrupted. Stage 1 is cheap and may run anytime; the Track D pilot waits for a quiet machine.
- Do not modify anything under `unused-assumptions/`, `the sweep project/`, `formal-corpora/`, or the producing project, and do not edit shell rc files to export `SWEEP_REPO`; set it per invocation from `env.example`.
- Do not install a Lean toolchain or a Mathlib checkout anywhere. If something appears to require one, stop and report why.

**Report** in `ENGINEERING.md` every defect you ship and how it was found, as the brother does; each becomes a test written as the failing case.

---

## The question

`unused-assumptions` asks: which theorems in Mathlib are stated over a stronger *setting* than their own proof requires? Weaken one binder, keep the proof byte for byte, recompile.

This project asks the dual: which theorems in Mathlib state a *weaker conclusion* than their own proof establishes? Not by generating stronger conclusions — that space is not enumerable — but by reading the root of the proof term. If the last step of a proof is a weakening lemma (`le_of_lt`, `le_of_eq`, `Or.inl`, `Exists.intro w _`, `ne_of_gt`, `Nonempty.intro`, `Filter.Eventually.of_forall`, `Set.Subset.trans` into a superset, `And.left`, ...), the proof has already proved the stronger statement and discarded it in its final line. The stronger statement is a subterm. It comes with its own proof, and it compiles by construction.

That restores exactly what made `unused-assumptions` clean: a finite hand-written table, a mechanical verdict, no judgement in the loop.

Three stages, each a gate for the next:

1. **The sweep.** Root-weakening detection over Mathlib. Output: a table of theorems whose proof proves more than they state, with the stronger statement and the proof subterm that establishes it.
2. **Witness materialisation.** For the existential rows, turn the hidden witness into a `def` with a `_spec` theorem. This is where the project can produce objects rather than restatements.
3. **The bet on new mathematics.** Feed the strengthened statements and materialised witnesses to a judgement stage (the the producing project, if it exists by then) as candidates that are *already true and already proved*. This removes the failure mode that killed perturbation as a candidate source: every candidate there was one edit from a known theorem and nearly always false or folklore. Here every candidate is true by construction; the only remaining question is interest. Whether that is enough is the thing being tested.

Be explicit from the first line of the README: stages 1 and 2 do not produce new mathematics, in the same sense that `unused-assumptions` does not. Every row of stage 1 is a statement a competent reader grants on sight once shown the proof. The claim of stage 1 is the map — where in the library conclusions carry slack, and whether that correlates with where hypotheses carry slack — and the claim of stage 3 is a bet whose outcome is reported either way.

## Method

### Stage 1 — the sweep

For each `theorem` declaration in the pinned Mathlib revision:

- Obtain the proof term (`ConstantInfo.value?`), including for tactic proofs; descend through `_proof_n` auxiliaries and `Eq.mpr`/`id`/`cast` wrappers that elaboration inserts, and record how many layers were stripped.
- Reduce the head to weak head normal form only as far as needed to expose the root application. Do not unfold definitions — a proof whose root is `le_of_lt` after unfolding user definitions is a different, weaker claim; record it separately if at all.
- Match the root head constant against `WEAKENINGS.lean`/`weakenings.json`: a hand-written table mapping each weakening lemma to (a) which argument carries the stronger fact, (b) the shape of the stronger statement. Hand-written and reviewable for the same reason the class table was: a wrong entry silently reports "no slack" and nothing catches it.
- Emit the candidate: the original declaration, the stronger statement (the type of the selected argument, with the theorem's binders re-abstracted), and the proof subterm.
- Recompile the strengthened declaration in isolation with the file's open directives, exactly as `verify.py` does. Success is `no error` *and* `#print axioms` resting on nothing beyond `propext`, `Classical.choice`, `Quot.sound`. Never infer success from the absence of an error string; the `lean.synthInstanceFailed` lesson applies here unchanged.

Verdicts, kept apart so the tool's own failures cannot inflate the yield:

| verdict | meaning |
|---|---|
| `strengthens` | stronger statement compiles with the subterm as proof and is not already in the library |
| `duplicate` | the stronger statement already exists (by name pattern `foo_lt`/`foo_le`, by type, or alpha-equivalent); record the pair — this is a measurement of API design, not waste |
| `root_not_weakening` | root head not in the table |
| `stripped_only` | the only slack is an elaboration wrapper; not a finding |
| `context` | the tool failed to reproduce the declaration's setting; the tool's failure, counted separately |

Two buckets in every report, never one:

- **Library value.** The stronger form is a restatement; same proof, sharper statement, mathematically inert. Most rows will be here, and most of *those* are deliberate: the `≤` form is the one downstream uses. That is not a defect of the library; say so.
- **The narrow bucket.** Rows where the stronger statement is not a sibling of the stated one but a different theorem: a witness that is a named object nobody named, a strict bound where the literature has only the weak one, a disjunct that is always the left one. This is the bucket the paper is about, and collapsing the two would overstate what was found.

### Stage 2 — witness materialisation

For every `strengthens` row whose root is `Exists.intro w h` (or `Nonempty.intro`, `Subtype.mk`, `Sigma.mk` inside a `Prop`-valued wrapper):

- Extract `w` with the theorem's binders re-abstracted. Emit `def foo_witness ... := w` and `theorem foo_witness_spec ... : P foo_witness := h`.
- Classify the witness: `computable`, `noncomputable_choice` (goes through `Classical.choose`), `noncomputable_other`, `depends_on_hypothesis_proof` (the witness term mentions a proof of a hypothesis — legitimate in DTT, but flag it), `not_closed` (tool failure).
- Where the witness is a function of the theorem's parameters, it is a *new declaration on the library*: an explicit bound function, an explicit inverse, an explicit index. Its properties beyond `_spec` are not proved by anything in the sweep. Record it as an object, not a theorem.

Expect most existentials in Mathlib to be proved by `Classical.choose` or by an inherited `∃` from another lemma, so that the witness is not new. Measure the computable fraction and report it before claiming anything; if it is small, stage 2 is a footnote and the report says so.

### Stage 3 — the bet

Hand the narrow bucket of stage 1 plus the computable witnesses of stage 2 to the judgement stage. Two things distinguish these candidates from every source the the producing project has had so far, and both must be stated in advance:

- They are **true with proof**. No prover in the loop, no timeout misread as success.
- They are **not perturbations**. A witness function is an object the library uses implicitly in a proof and never names; asking what else is true of it is a question about a new object, not a one-edit restatement.

What the judgement stage does: rank, record the reason and the expected proof needs *before* any campaign, then work on the top of the ranking. Calibration first, on rows whose interest can be settled cheaply. If the ranking has no predictive power there, that is published and stage 3 stops.

An optional Track C, riskier and explicitly separate: **mid-proof slack**. A `le_trans` chain where an intermediate bound is strictly sharper than the stated one, a `Nat.le_of_lt_succ` in the middle of a counting argument. This is the quantitative content proof mining extracts by hand, and it is the one place where the literature shows that "the proof proves more" has yielded theorems nobody had (rates of convergence, effective bounds). Mechanising it over a library is unexplored. It is also not root-only, so it loses the finite-table guarantee. Design it only after stage 1 has a number; do not let it delay the sweep.

### Track D — dichotomy repair (the route to statements that are not restatements)

This track mechanises what a human does when generalising a theorem: push the hypothesis until the proof breaks, then characterise the break. The push is `unused-assumptions`; the break is its `needs_structure` verdict; the characterisation is the new work.

Fed not by the strengthening sweep but by the *failures* of `unused-assumptions`: every `needs_structure` verdict is a theorem `a → b` whose proof breaks at a known location under a known weakening `a'` of its setting. The compiler names the lemma that needed the structure. That is the hint — the same hint a mathematician reads off a proof when they notice which step used the hypothesis, except here it is recorded for every theorem in the library at once.

Shape of the target:

    a  → b          (stated, proved)
    a' → b ∨ c      (candidate; a' weaker than a; c describes a' ∧ ¬a better than ¬a does)

Note the logic carefully, because it is easy to get backwards. With `a` fixed, `a → b ∨ c` is *weaker* than `a → b` and follows by `Or.inl` for any `c`; there is nothing there. With `a` weakened to `a'`, the disjunction has content only when `c` is sharper than `¬a` — a named degenerate case, not the negation of the hypothesis. `a' → b ∨ ¬a` is `a → b` rewritten and is filtered as a restatement.

Construction:

1. From the `needs_structure` record, identify the property `p` of the weakened binder that the failing lemma required (`p` is what separates `a` from `a'`).
2. Split on `p`. On the `p` branch, the original proof runs byte for byte; that branch is guaranteed and needs no prover.
3. On the `¬p` branch, the goal is `c`, drawn from a small hand-written family of exceptional shapes Mathlib already names: `Subsingleton`, `ringChar = 2`, `Nontrivial` failing, `n ≤ 1`, `Fintype.card ≤ 2`, `IsEmpty`, `x = 0`, and so on. A candidate `c` is admitted only if it is *not* provably equivalent to `¬p` in the weakened setting — otherwise it is the restatement again.
4. Attempt the `¬p` branch with `decide`, `simp`, `aesop`, then a prover, in that order, with a fixed budget. Record which closed it.
5. Emit the candidate in one of three states: `closed` (both branches proved; a theorem, submit it), `half-open` (the `p` branch proved by construction, the `¬p` branch an unresolved `Prop`, kept in this project's own ledger with its proved half attached), `restatement` (the only admissible `c` collapsed to `¬p`; discard).

Report `closed` and `half-open` separately and never merge them. A `closed` row whose `¬p` branch fell to `decide` on a finite exceptional set is real but small mathematics — the same one step of structure the `unused-assumptions` catalogue admits, and it is reported in that bucket. The rows worth a paper are the ones where the exceptional region turned out to have a description nobody had stated; those are found by reading the survivors, not by a filter.

What Track D gives up: the binary verdict. Only the `p` branch is mechanical; the `¬p` branch needs a prover, so a prover that is too weak reads as "half-open" and inflates that count. Keep the prover budget fixed and recorded, and treat the half-open rate as an upper bound on what is actually open.

What Track D does not need: a new sweep. As of 3 September 2026 the brother exports its failures: `unused-assumptions/data/breaks.jsonl.gz` (57,382 rows, one per (module, theorem, binder) with a failing attempt; see `docs/exchange-format-request.md` and `docs/exchange-format-response.md` in this folder). That file is Track D's input; the read-only store snapshot described under Environment is the fallback if it is ever missing. Three facts about it decide how it is read:

- `blamed` is `null` on every row and will stay so: the sweep kept only the first error line and Lean puts the class name on the second. It is not needed. The split property `p` is derived from the class pair (`stated` → `fails_at` along the hierarchy), not from the error. Every row that reaches repair is recompiled at `fails_at` by this project anyway, to construct the split; capture the full multi-line error then, for the pilot slice only, and store it in this project's data. Do not ask the brother to re-sweep for it.
- `fails_at` is the brother's *reconstruction*, not a recorded event: its table proposes several candidate classes per binder and tries each independently. Use the `descent` field (every class tried, with its verdict) and compute this project's own break point under the hand table's order; record which order was used.
- `fail_error` is capped at 200 characters by the store. Do not ask for more.

Join key, shared with the brother: `key = corpus:module:theorem:binder`. `corpus:theorem:binder` collides — 1,663 theorem names in Mathlib appear in more than one module — so never join on it. The brother's `MANIFEST.json` documents `id_scheme` and `key_scheme`; read them rather than assuming.

TauCeti rows are not in the brother's export yet, deliberately: its census and prior-art gate have not caught up, and exporting now would divide a gated numerator by an ungated denominator. Record `TauCeti: not yet exported (gated)` in this project's MANIFEST and consume it when it arrives. Nothing here pools across corpora, so nothing waits on it.

## The distance ladder

The whole project, both brothers included, is one measurement: how far a true, proved statement can be moved from what the library writes down, and at what distance it stops being folklore. State it as rungs of edit distance and report every rung the same way.

| rung | statement | how obtained | cost | what "new" means here |
|---|---|---|---|---|
| 0 | `a → b` | the library | — | — |
| 1 | `a' → b` or `a → b'` | one brother alone | free (same proof / subterm) | one edit; expected almost always duplicate or granted on sight |
| 2 | `a' → b'` | both brothers, joined by name at the same pin | free by construction | two independent edits; the joint bucket above |
| 3 | `a'' → b' ∨ c` | Track D on a rung-2 row: push `a'` past the break to `a''`, repair with `c` | not free: falsifier, tactic ladder, prover budget | first rung whose proof is not a rearrangement of the original; the `c` branch is new work about a region the original proof never touched |
| 4+ | iterate 3 on the repaired statement | the "push until it breaks, characterise the break" loop, repeated | a prover per step | decided by the rung-3 pilot; not built before |

**Rung 3 is a dichotomy, not a further strengthening.** `b' ∨ c` is a weaker conclusion than `b'`, under a weaker hypothesis. Do not draw the ladder as monotone improvement; a reader who assumes it will misread the table.

**Pre-register one prediction for the ladder before any count exists:** the duplicate rate falls with the rung, and the fraction surviving the triviality filters rises with it. That is the claim "one edit from the library is folklore" turned into a curve. If the curve is flat, edit distance is not the proxy for non-folklore that the the producing project design assumed, and that gets published as a result about the proxy.

**Rung 3 needs a load-bearing test the lower rungs do not.** Iterated weakening drifts into vacuity: `a''` so weak and `c` so broad that `b' ∨ c` is trivially true. Before any prover runs on a rung-3 candidate, require two finite models of `a''` (the parsimagma machinery): one where `¬c` holds, so `b'` is doing work, and one where `¬b'` holds, so `c` is doing work. A candidate missing either model is discarded as `vacuous`, its own verdict, counted and reported.

**Report per rung:** candidates, duplicates, vacuous, survivors, and the areas they came from. One table; no pooling across rungs.

## Cost, and the shape that respects it

The cost is lopsided and the design should follow it.

**Stages 1 and 2 are one traversal, not a sweep.** Reading the root of a proof term is a single pass over the environment: milliseconds per declaration, minutes for the library. The strengthened statement does not need recompiling to be verified — its proof is a subterm of a kernel-checked term, so `inferType` on the subterm and a defeq check against the candidate statement is the verification. Recompilation from source is for the shipped artefact only, and runs on survivors, not candidates. The same traversal records, per proof, which instance fields it actually touches (Best 2021); that is the cheap predictor for the hypothesis side and costs nothing extra once the term is in hand. One walk, three detectors, verify only what survives.

**Track D is the only expensive part and the only part that can produce mathematics.** Keep it small three ways:

- No new sweep. Inputs are the existing `needs_structure` rows with the failing declaration named.
- Falsify before proving. Test `a' → b ∨ c` on small finite instances first (the finite-model machinery from parsimagma; the scrutiny's "not trivially false" pass). A finite counterexample ends the candidate without a prover, and that will be most of them.
- A tactic ladder before the prover: `decide`, `simp`, `aesop`, seconds each; the prover with a fixed budget only for what survives the ladder.

Run it as a **pilot on a stratified slice**, not the library: the areas where `unused-assumptions` found high rates, and within them the rows where a single lemma failed under weakening, since one disjunct can plausibly repair one failure and not five. Two hundred candidates at a fixed sixty-second budget is a few hours of one machine. The pilot's `closed` and `half-open` rates decide whether to scale; if `closed` is dominated by `Subsingleton` under `decide`, do not scale.

**Track C is dropped**, not deferred. It has no finite table and needs a prover on every candidate. It stays in this document as a named direction so nobody rediscovers it as new.

## What is measured

- Rate of `strengthens` per thousand declarations, by area, with the clustered correction: a weakening idiom belongs to a file or an author at least as much as to a theorem, so declarations are not independent trials. Report the clustered figure and quote only that.
- Rate of `duplicate`: how often the library already states the stronger sibling. A high duplicate rate is itself a result about Mathlib's API discipline.
- **Correlation with `unused-assumptions`**, per area: is slack in hypotheses correlated with slack in conclusions? This is the cheapest new question in the project, it reuses the per-area counts that already exist, and it has no literature. Pre-register the direction before looking.
- **The joint set**, its own bucket. Rows present in both survivors tables at the same Mathlib pin: `a → b` weakens to `a' → b` (brother) and its proof root yields `b'` (here). The composite `a' → b'` compiles by construction — a subterm of a proof that typechecks under `a'` typechecks under `a'` — so emit it, verify it the same way, and run the duplicate check on it. A composite is two edits from what the library states, not one; the rows where no sibling exists are the ones where the proof was about a different theorem than the one written, in setting and in conclusion at once. Report the joint count, the fraction of composites with no duplicate, and their areas. This is the strongest claim the two projects can make together and neither can make alone; it is still a claim about distance from the library, not about interest, and the README says so. Joint rows are also the preferred input to Track D: repairing `a' → b'` past the break asks whether the exceptional case costs exactly the strengthening — "strict over a field, non-strict over a division ring, and here is the counterexample" — which is a theorem shape people state.
- Existential rows: computable-witness fraction; fraction where the witness is a closed term in the parameters versus inherited from another lemma.
- Stage 3: whether ranked candidates produced dependent lemma chains of depth ≥ 3, against the ranking recorded at selection time.

Every number lives in a generated `MANIFEST.json`; prose quotes macros. Six numbers drifted in the previous project before that lesson took.

## Prior art, to cite and to distinguish

- **Kohlenbach, proof mining** (monograph 2008; surveys since). The informal, by-hand, per-theorem version of "the proof proves more". It is the reason to believe stage 3 and Track C can produce mathematics; it is also the reason to be clear that nothing in stage 1 is proof mining.
- **Program extraction / realisability** (Coq extraction, Minlog, Agda). The witness question in constructive systems. Mathlib is classical, which is why the computable fraction in stage 2 is a measurement rather than a given.
- **Best 2021**, *Automatically Generalizing Theorems Using Typeclasses*; **Alama 2013**, *Eliciting Implicit Assumptions of Mizar Proofs by Property Omission*; **Gandhi 2025** (ITP), *Automatically Generalizing Proofs and Statements* — all on the hypothesis side. Gandhi generalises constants by discovering which of their properties the proof uses; cite it in `unused-assumptions` too, it is missing there.
- Mathlib's own linters. Check whether any existing linter flags a weakening lemma at proof root; none is known at the time of writing. If one exists, this project's stage 1 is partly a linter and the README says so.
- No library-scale audit of hidden witnesses or root-weakened conclusions exists for any proof assistant, as far as a search on 2 September 2026 could find.

## Two parts, and the wall between them

The project runs in two parts. Part 1 is a pilot on a set where `a'` is already known; Part 2 is the measurement. The wall between them is statistical, not organisational: **no number from Part 1 is a library rate.** A rate computed on the brother's survivors is a rate among theorems that already had hypothesis slack, so it cannot feed the per-area correlation, the rung-1 baseline, or the ladder curve. Part 1 tables say `population: unused-assumptions survivors (Mathlib)` in their caption, and the README says the same sentence once, near the top.

### Part 1 — pilot on the brother's Mathlib survivors

Input: `unused-assumptions/data/survivors.jsonl`, Mathlib rows only, plus their matching rows in `breaks.jsonl.gz`. One environment: the Mathlib installation. No TauCeti.

Four counts describe this input at the 3 September export, and all four are correct; know which one you are using. The shipped file is the **union** of the brother's two weakening tables: **645 rows over 595 unique theorems** (a theorem can carry more than one weakenable binder). The brother's paper quotes the **hand-written table alone**: **431 theorems, 462 rows**, because that is the population its pre-registered tests were run on; the derived table alone gives 357 theorems, 382 rows. Use *rows* for the join — `key` includes the binder — and *unique theorems* for anything reported as "theorems". Re-read the brother's `MANIFEST.json` for the numbers rather than these; they move when it re-exports.

Denominators, for later: the brother's per-area `decls` (29,261 across 25 areas in `areas-hand.csv` at this export) counts declarations *for which some weakening was proposed*, not the area's size — its own README calls this "density among theorems the method can ask about". The root-reading sweep asks its question of every theorem, so its natural denominator is the full declaration count per area at the pin. Part 2's correlation therefore computes both projects' rates over the **common** denominator (per-area declaration counts, which the traversal yields for free) as the primary figure, and over each project's own askable population only as a secondary one. Dividing each by its own denominator would make the correlation partly an artefact of how far the brother's class table reaches.

What it is for: to build and debug the entire mechanical chain on the smallest input that exercises all of it, and to see rung 2 — the composite `a' → b'` — on day one, because on this set `a'` comes for free from the brother.

1. The study session (`docs/from-the-brother.md`), `git init`, README, licence, `env.example`.
2. `WEAKENINGS` table, hand-written, one worked example per entry. Twenty entries to start. It is expected to change during Part 1; every change is a commit with the reason.
3. The metaprogram: for each survivor, compile the brother's `source` (weakened declaration, original proof) in the sweep environment, read its proof term, strip elaboration wrappers with a layer count, match the root against the table, `inferType` the selected subterm, `addDecl` the strengthened declaration from it, `#print axioms`. Test first on ten hand-picked survivors, including two whose root is *not* a weakening after stripping.
4. **Gate: read fifty candidates by hand.** If they are all `le_of_lt` closing a `calc` block with the `_lt` sibling on the next line of the file, stop here, having cost an afternoon, and write down why.
5. `verify.py`, copied, revision guard and `synthInstanceFailed` handling intact, on the rows that ship.
6. Duplicate check for every composite: by sibling name pattern, by type, by alpha-equivalence, against the pin. Report rung 2 on this set as its own table, population stated in the caption.
7. Stage 2 (witness materialisation) on the existential rows of this set; measure the computable fraction.
8. Track D pilot, on this set, with the finite-model falsifier, the load-bearing two-model test, and the tactic ladder wired in before the prover. Inputs: the survivors' own `descent` rows from `breaks.jsonl.gz`, break point recomputed under the hand table's order. **Gate:** `closed` / `half-open` / `vacuous` / `restatement` rates and what closed them.
9. **Freeze.** Commit the final `WEAKENINGS` table, the wrapper-stripping rules, and the duplicate-check rules; record their SHA-256 in `MANIFEST.json` under `frozen_for_part2`. From here they do not change without a new freeze entry and a stated reason. Pre-register the Part 2 predictions (correlation direction; duplicate rate falling with the rung) in `prereg/` and commit before any Part 2 count exists.

Part 1 ends with three things: a working chain, a rung-2 table on a stated population, and a frozen table. It does not end with a claim about Mathlib.

### Part 2 — the measurement, library-wide

Input: every theorem in the corpus, not the brother's rows. Two corpora, each at its own pin, never pooled: Mathlib now; TauCeti when the brother's gated export arrives (the traversal can run on TauCeti before that — it needs only the installation — but rung 2 and Track D on TauCeti wait for the export).

1. The traversal over the pinned revision, both installations: root head, witness term, touched instance fields, one pass. Minutes. Verification by `inferType` on the subterm; source recompilation only for rows that ship. The metaprogram must compile unchanged under both toolchains; test that before the first run.
2. Rung 1 for `b'` alone, library-wide: rates per thousand declarations, by area, clustered by module. This is the baseline the ladder is measured against; it does not exist in Part 1.
3. The rung-2 join, library-wide: this project's rung-1 rows against the brother's `survivors.jsonl`, on `key`. Rung-2 rows found here that Part 1 also found are the same rows; report the overlap as a consistency check on the chain, not as a result.
4. `tools/density.py` with this table and the brother's per-area counts: the correlation, against the pre-registered direction, over the common denominator first (see the denominators note under Part 1), each project's own askable population second.
5. The ladder table: rungs 1, 2, 3 with candidates / duplicates / vacuous / survivors per rung, against the pre-registered prediction.
6. Stage 2 library-wide; the computable fraction decides whether it is a section or a sentence.
7. Track D at scale only if the Part 1 pilot's gate said so; on the stratified slice first (areas with high brother rates, single-failure rows).
8. **Gate: pre-register stage 3** — the ranking protocol, the calibration set, the depth metric, the stopping rule — and commit it before any candidate is shown to any agent.
9. Stage 3.

Nothing in Part 2 re-tunes the frozen table on what it finds. A row the table misses is recorded as `root_not_weakening` and, if it looks like a real miss, goes on a list for the *next* freeze; it does not change this sweep.

## What would make this fail honestly

- Nearly every root weakening is deliberate API shape, and the stronger sibling already exists: the duplicate rate is above ninety percent. Then the contribution is a linter and a number, and the paper is short.
- The existential witnesses are `Classical.choose` almost everywhere. Stage 2 is then empty and stage 3 has only the narrow bucket of stage 1 to work with.
- The correlation with hypothesis slack is null at the clustered level. Report it as null; the per-theorem p-value is not the one to quote.
- The judgement stage ranks "true and already proved" candidates no better than it ranked perturbations. That would mean truth-by-construction did not address the interest problem, which is worth knowing and gets published as such.
- Track C cannot be given a finite table, and every attempt at it needs a prover. Then it is left as the open direction, named, not built.
- Track D's admissible `c` collapses to `¬p` in nearly every case, or the `¬p` branch is closed by `decide` on `Subsingleton` every time. Then the dichotomies are real and uniformly dull, and the track produced a linter for degenerate-case clauses rather than theorems. Say so.
- The ladder's duplicate-rate curve is flat: rung-2 and rung-3 statements are already in the library, or granted on sight, as often as rung-1 ones. Then edit distance does not measure distance from folklore, the the producing project's premise was wrong, and the honest paper is about the proxy failing.

## Environment: paths, pins, and what not to install

Everything below was read from the machine on 2 September 2026. Re-check `lean-toolchain` files and `git rev-parse HEAD` before trusting a revision; do not type revisions into prose.

**This is a standalone project.** Its own local git repository, its own folder: `.`. It holds Python (standard library only, as before), one small Lean metaprogram file, data, docs, paper, tests. It holds **no Lean toolchain and no Mathlib checkout**, and it does not depend on, feed, or import any other project. In particular it has no relationship with the sweep project or with formal-corpora; those names appear below only because two directories that happen to belong to them are where Mathlib and TauCeti are already installed on this disk. The relationship is to the *installations*, by path, through one environment variable — nothing more.

**The brother project.** `https://github.com/carlok/unused-assumptions`, the same shape, one level up in the same `lean4` folder. Copy — do not import or symlink — `verify.py`, `tools/leanrun.py` (the `SWEEP_IMPORT` header logic and the `AXIOMS_RE` / `synthInstanceFailed` handling), `tools/density.py`, `tools/export.py`, the `tools/sprint.sh` structure and the test layout. Its published rows are relative to the Mathlib pin in its `data/MANIFEST.json` (`0df444a360eaa60ab8c11dca51a86af692955474`, "chore: bump toolchain to v4.33.1"), and this project's Mathlib rows must be swept at that same pin for the per-area correlation to mean anything.

**How the brother reaches Mathlib and TauCeti, and how this project does the same.** `unused-assumptions` owns no Lean installation either. Its `sprint.sh` requires `SWEEP_REPO`, "a Lean project with Mathlib as a dependency", and runs `lake env lean` inside it; `SWEEP_IMPORT` says what a standalone candidate file imports. This project uses the identical mechanism and the identical two directories, so no gigabyte is added to the disk:

| corpus | `SWEEP_REPO` (an installation, not a collaborator) | toolchain | Mathlib pin | on disk |
|---|---|---|---|---|
| Mathlib | `/path/to/your/lean-project` | `leanprover/lean4:v4.33.1` | `0df444a3…` — the brother's MANIFEST pin | `.lake` ≈ 7.6 GB, already there |
| TauCeti | `/path/to/another/corpus` | `leanprover/lean4:v4.34.0-rc1` | `4fae4090…` — TauCeti's own pin | ≈ 13 GB, already there |

Put both paths in one file, `env.example` (or the top of `sprint.sh`), read from the environment, never hard-coded in a tool. If either installation moves, one line changes. If the Mathlib installation is ever upgraded by whoever owns it, do not follow: pin this project's `MANIFEST.json` to the revision it was swept at and let the copied `verify.py` revision guard refuse anything else, as it does in the brother. Never run `lake update` in either directory from this project.

**TauCeti is swept at its own pin, inside its own checkout.** It pins a different Mathlib under a different toolchain than the Mathlib installation above, and that pin *is* the corpus: moving it would change the object being measured. So the two corpora cannot share one environment, and they do not need to; each is swept where it already is. For TauCeti, `SWEEP_IMPORT` must make candidates import the module they came from — TauCeti's root module is deliberately empty — or every name fails to resolve and the corpus scores as pathologically over-constrained. The brother's `leanrun.py` docstring and its ENGINEERING.md story "the imports the signature pass did not make" record that failure; copy the fix with the file.

**Where the brother's failures live, for Track D.** Primary source: `unused-assumptions/data/breaks.jsonl.gz` (exported 3 September 2026; see the Track D section). Fallback only: the SQLite stores from which `unused-assumptions` exported its tables are on this disk under `the producing project's stores` — `sprint-1.db`, `sprint-2.db`, `sprint-3.db`, `sweep-wide.db`, `sweep-wide-b.db`, `typeclass.db` for Mathlib, `tauceti-before-priorart.db`, `tauceti-before-census.db` for TauCeti. Track D reads `needs_structure` rows from a **snapshot** of them, never from the live files: `sqlite3 <src> ".backup data/snapshots/<name>.db"` once per store (the online backup API is safe against a concurrent writer; a plain read-only open is not, since a long shared lock can hand the sibling's writer "database is locked"), then a one-time `tools/import_failures.py` over the snapshot, with the source store's path and SHA-256 recorded in `MANIFEST.json`. That is the whole relationship; nothing here depends on that folder afterwards, and nothing ever writes to it.

**Serial in data, not in time.** The brother's outputs — `data/survivors.jsonl` for the rung-2 join, `data/breaks.jsonl.gz` for Track D — are *inputs* to this project, recorded in `MANIFEST.json` with the brother's MANIFEST revision and the SHA-256 of each file or snapshot consumed. They are not a reason to wait: the nineteen swept areas are final at the pin, and the areas still running are the ones with few or no survivors. When the brother's MANIFEST changes, re-run `tools/import_failures.py` and the join (seconds) and bump the recorded hashes. **The Part 2 sweep is library-wide, never restricted to the brother's survivors** (Part 1 restricts to them on purpose, as a pilot, and reports no library rate). Restricting the measurement would lose the `b'`-only class of rung 1, would build the per-area correlation into the sample (conclusion slack measured only among theorems that already had hypothesis slack), and would remove the rung-1 baseline the ladder's curve is measured against. The sweep is minutes; there is no cost reason to narrow it.

**Consequence for the metaprogram.** The one Lean file that walks proof terms must compile unchanged under both `v4.33.1` and `v4.34.0-rc1`. Keep it to the stable `Lean.Meta` surface (`getConstInfo`, `ConstantInfo.value?`, `whnfR`/`whnfCore`, `inferType`, `isDefEq`, `Expr.getAppFn`), no Mathlib imports inside the metaprogram itself, and test it in both environments before the first sweep. If the two toolchains ever diverge on that surface, fork the file per toolchain rather than moving a pin.

**Results are reported per corpus at that corpus's pin, never pooled.** A Mathlib row and a TauCeti row are relative to different Mathlibs; the comparison between them is a comparison of rates, not of statements.

## Repository conventions, carried over

Apache-2.0, matching Mathlib. Standard library only for anything a reader runs without Lean. Tests written as the defect that shipped, one per defect. `ENGINEERING.md` for the stories. `CITATION.cff`. Counts in `MANIFEST.json`, never in this file. Revision pinned, verifier refuses to run against another one. One row that does not reproduce ships with its error rather than being dropped.
