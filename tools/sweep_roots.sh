#!/bin/bash
# Phase A over Mathlib, one area per run, resumably.
#
# The whole-library traversal is one process and one file. That is the right
# shape when it fits in a timeout and the wrong shape when it does not: a
# timeout loses the whole pass, and there is nothing to resume from. This
# splits it by area, and an area whose file already exists is skipped -- the
# check derived from the data, never from a marker beside it.
#
# Usage: SWEEP_REPO=... tools/sweep_roots.sh [outdir]
set -u
D=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$D/data/scratch/roots}
: "${SWEEP_REPO:?set SWEEP_REPO from env.example}"
mkdir -p "$OUT"

AREAS="Algebra AlgebraicGeometry AlgebraicTopology Analysis CategoryTheory Combinatorics
Computability Condensed Control Data Deprecated Dynamics FieldTheory GroupTheory Geometry
InformationTheory Init Lean LinearAlgebra Logic MeasureTheory ModelTheory NumberTheory Order
Probability RepresentationTheory RingTheory SetTheory Std Tactic Testing Topology Util"

for area in $AREAS; do
  target="$OUT/$area.jsonl"
  if [ -s "$target" ]; then
    echo "{\"area\": \"$area\", \"stage\": \"skip\", \"reason\": \"already has rows\"}"
    continue
  fi
  echo "{\"area\": \"$area\", \"stage\": \"start\", \"at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
  # python3 -u and no pipe to tail anywhere: tail buffers its whole input, and
  # that made a run in the sibling look dead for three hours.
  python3 -u "$D/tools/traverse.py" roots-all \
      --module-prefix "Mathlib.$area" --timeout 3000 --out "$target" \
    || echo "{\"area\": \"$area\", \"stage\": \"failed\", \"at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
done
echo "{\"stage\": \"complete\", \"at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}"
