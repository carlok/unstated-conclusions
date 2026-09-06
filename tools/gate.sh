#!/bin/bash
# The fifty-candidate gate, end to end.
#
#   1. match the traversal against the table          (no Lean)
#   2. sample fifty, stratified by root               (no Lean)
#   3. detail all fifty in ONE Lean process           (one Mathlib import)
#   4. render the document a person reads
#
# Step 3 is one process rather than fifty because these candidates are
# declarations that already exist in the imported environment. The per-row sweep
# pays the import once per row only because it must elaborate a declaration that
# does not exist yet.
set -u
D=$(cd "$(dirname "$0")/.." && pwd)
S=$D/data/scratch
: "${SWEEP_REPO:?set SWEEP_REPO from env.example}"
ROOTS=${1:-$S/roots-mathlib.jsonl}

python3 -u "$D/tools/roots.py" "$ROOTS" \
    --candidates "$S/candidates.jsonl" --histogram "$S/missed.tsv" --top 40 \
  || { echo "roots.py refused; read a case before passing --anyway" >&2; exit 2; }

python3 -u "$D/tools/gate.py" "$S/candidates.jsonl" \
    --population "unused-assumptions survivors are NOT the population here: this is \
every theorem in Mathlib at the pinned revision. No rate is reported from it in \
Part 1; the table is built from this run and Part 2 re-runs after the freeze." \
    --pairs-out "$S/gate-pairs.jsonl" --out "$S/gate-draft.md"

python3 -u "$D/tools/traverse.py" detail --pairs "$S/gate-pairs.jsonl" \
    --timeout 2400 --out "$S/gate-details.jsonl"

# The draft above is written to scratch, never to docs/. Only a render that has
# the statements is allowed to land where a person will read it.
if python3 -u "$D/tools/gate.py" "$S/candidates.jsonl" \
    --population "every theorem in Mathlib at the pinned revision (traversal run, \
pre-freeze; no rate from it is reported in Part 1)" \
    --details "$S/gate-details.jsonl" --verdicts "$D/docs/gate-verdicts.json" \
    --out "$D/docs/gate-fifty.md"; then
  echo "wrote docs/gate-fifty.md"
else
  echo "gate NOT written: the detail run produced nothing. docs/gate-fifty.md is" >&2
  echo "unchanged, which is correct -- a stale document is at least honestly dated," >&2
  echo "and one rendered without its evidence is not." >&2
  exit 1
fi
