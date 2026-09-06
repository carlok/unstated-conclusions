# Where this project is, and what to do next

Written for a session with no memory of the conversation that produced it. Read
`BRIEF.md` first for what the project is; this file is only the state.

Everything below was verified, not remembered: the counts come from the stores,
the commits are in git, and anything unfinished says so.

---

## Done

**Part 1 steps 0 through 9 of `BRIEF.md`, plus Track D phase 1.** 33 commits,
58 tests, 20 defects written up in `ENGINEERING.md`.

| store | rows | state |
|---|---:|---|
| `data/part1.db` | 645 / 645 | complete, integrity ok |
| `data/trackd.db` | 200 / 200 | complete, integrity ok |

### The results, such as they are

**The sweep** (population: `unused-assumptions` survivors (Mathlib) — *not* a
library rate, and every table says so):

- 9 `strengthens`, 1 `witness`, 1 `unchained`, 1 `context`, 633 `root_not_weakening`
- **0 duplicates**, and that zero was positive-controlled rather than believed:
  three known duplicates from the gate are found by the same library-wide search
- Against `prereg/part1-yield.md`, written before the run: predicted 8, found 9
  theorems. Seven of the eight named confirmed. Well inside the 3–20 band.

**The fifty-candidate gate passed** (`docs/gate-fifty.md`): 19 narrow, 9
restatement, 6 witness, 4 artefact, of 38 read. `BRIEF.md`'s stop condition is
not met.

**Root shift: 5 of 585 comparable rows, 0.85%.** Weakening a typeclass
essentially never changes which lemma a proof ends on. This decides that Part 2's
rung-2 join can be a lookup against the traversal rather than a compile per row.

**Stage 2:** computable fraction 0.5 on 8 witnesses.

**Track D phase 1:** all 10 strict rows yield an error from sources shipped
as-is, 0 mismatches, 28 `blamed` recovered of 176 usable (**16%**).

---

## Running right now, detached

The **citation pass** — `unused-assumptions`' second ask. One `lake env lean`
under `caffeinate -i`, launched with `nohup`, so it survives a terminal or an
editor closing. It does **not** survive a reboot or an OS update.

```bash
ps -ax -o pid=,etime=,command= | grep "[t]raverse.py citations"
ls -l data/scratch/citations.jsonl
tail -3 data/scratch/citations.log
```

Three outcomes:

- **File exists, non-empty, log has no `timeout`** — it finished. Go to
  "What to do next".
- **File exists and the log begins with `timeout`** — it is *partial*, and
  deliberately so: `PartialTimeout` now keeps what the run wrote
  (ENGINEERING.md 19). Usable, but every number from it must say it is partial.
- **Nothing** — relaunch:

```bash
source env.example
caffeinate -i python3 -u tools/traverse.py citations --timeout 9000 \
    --out data/scratch/citations.jsonl
```

Before any long Lean run, compile the metaprogram **alone**. This has caught two
defects, one where Lean's own message suggested `#eval!`, which would have run a
function containing a type error rather than reporting it:

```bash
python3 -c "
import sys, os; sys.path.insert(0,'tools')
import leanrun, traverse
from pathlib import Path
print(leanrun.metaprogram_check(lambda c: traverse.compose(c, None),
                                Path(os.environ['SWEEP_REPO'])))"
```

**Known and unfixed:** there is no progress signal during a long run. Output is
captured at exit, so "running for two hours" and "wedged for two hours" look
identical from outside.

---

## What to do next

### 1. Finish the citation answer

```bash
python3 tools/citations.py --out data/scratch/citations-report.json \
    --rows-out data/scratch/citations-rows.jsonl
```

The question is whether the sibling's survivors are classical results or working
lemmas. Their own proxies are about naming; a citation count is about the
library. The tool enforces their framing: a survivor median alone means nothing,
so it reports the baseline over every non-survivor theorem or it reports
neither.

### 2. Ship the four files owed to `unused-assumptions`

```bash
python3 tools/exchange_export.py --out ../exchange/to-unused-assumptions
```

Writes `error-blocks.jsonl` (176 rows), `blamed.jsonl` (28), `roots.jsonl` (645,
for their merge) and a README. Add the citation results to the same directory
when they exist.

**One correction is owed regardless.** The report already sent —
`../exchange/from-unstated-conclusions-2026-09-04.md` — quotes **15%** for
`blamed` recovery. Their export fix raised it to **16%** (28 of 176). Stale in
our favour, which is the direction that gets corrected rather than left alone.

### 3. Their merge proposal, which is worth taking

They measured "every lemma the proof cites" unchanged at 87.5%; we measured "the
root of the proof term" unchanged at 99.15%. Nested claims, two implementations
sharing no code. The gap — roughly one weakening in eight keeps the destination
and changes the route — is the reportable part and neither project can state it
alone.

Before either side publishes the pair, check the join for a row where the root
moved but their constant set did not. They call it impossible. If it appears it
is a bug in one of us or a real fact about elaboration, and which one matters.

### 4. Part 1's remaining steps

- **Track D phase 2**: the dichotomy split and tactic ladder. Needs a prover and
  a quiet machine. Phase 1's data is in `data/trackd.db`.
- **The freeze** (`BRIEF.md` step 11): commit `weakenings.json`, the
  wrapper-stripping rules and the duplicate-check rules; record their SHA-256 in
  `MANIFEST.json` under `frozen_for_part2`; pre-register the Part 2 predictions
  in `prereg/` **before any Part 2 count exists**.

Two table changes are known-wanted and deliberately **not** made yet, because
the gate ran against the table as it stands: `Iff.mp` and `Iff.mpr` (the
statement is `a → b` and the proof holds `a ↔ b`; about 8,000 occurrences) and
`Equiv.injective`. See `docs/table-misses.md`, which also says plainly that
reading a histogram by hand is a weaker check than the sibling's second table
and cannot catch a rare miss.

---

## Rules that are not negotiable

Inside either `SWEEP_REPO` the only permitted command is `lake env lean <file>`
on a file in this project's own temp directory. No `lake build`, no `lake
update`, no `lake exe cache get`, no `elan`, no editing, no creating files there.
Never modify anything under `unused-assumptions/`, `the sweep project/`,
`formal-corpora/` or the producing project. Install no toolchain and no Mathlib.

**A verdict category at 0% or 100% is a bug until proven otherwise.** Six of the
twenty defects on this project failed the same way: something that computed
nothing was indistinguishable from something that found nothing. `tools/roots.py`
exits non-zero on a degenerate distribution for that reason.

## Why nothing is lost

Every row commits to its store as it is decided, and completeness is a query
over the data rather than a marker beside it. An interruption costs the one
compile in flight. `caffeinate -i` blocks idle sleep only; an explicit sleep or
an update suspends the machine as normal.
