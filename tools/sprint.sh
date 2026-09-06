#!/bin/bash
# The Part 1 sweep, driven so it survives the machine.
#
# POPULATION: unused-assumptions survivors (Mathlib). Nothing this produces is a
# library rate.
#
# Four choices, each copied from the sibling because it paid for them:
#
# 1. `exec caffeinate -i` re-exec, so the idle-sleep assertion covers the whole
#    run and dies with it. -i is idle sleep only: a closed lid or an explicit
#    sleep still suspends the machine, and that is fine -- see (4).
# 2. `python3 -u` everywhere and no `| tail` anywhere. tail buffers its whole
#    input, which made a run in the sibling look dead for three hours.
# 3. `set -u` but deliberately no `set -e`: a failed row costs its own row and
#    nothing else.
# 4. Resume from the store, never from a marker. A marker can disagree with the
#    data; a query cannot. So a sleep, a kill, a reboot or a fortnight costs at
#    most the one compile that was in flight.
set -u
D=$(cd "$(dirname "$0")/.." && pwd)
: "${SWEEP_REPO:?set SWEEP_REPO from env.example}"

if [ -z "${SPRINT_CAFFEINATED:-}" ] && command -v caffeinate >/dev/null 2>&1; then
  export SPRINT_CAFFEINATED=1
  exec caffeinate -i "$0" "$@"
fi

DB=${DB:-$D/data/part1.db}
LOG=${LOG:-$D/runs/part1.log}
mkdir -p "$(dirname "$LOG")"

stamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }
say() { echo "{\"at\": \"$(stamp)\", $1}" | tee -a "$LOG"; }

say "\"stage\": \"start\", \"db\": \"$DB\", \"repo\": \"$SWEEP_REPO\", \"caffeinated\": ${SPRINT_CAFFEINATED:-0}"

# One process of ours at a time, and the memory gate inside sweep1.py holds it
# there. The sibling's sweep may be running beside this one; its timeouts are
# recorded as verdicts in ITS store, so starving it corrupts its results and
# not ours, which is the worse way round.
python3 -u "$D/tools/sweep1.py" --db "$DB" --timeout 900 2>&1 | tee -a "$LOG"
status=${PIPESTATUS[0]}

say "\"stage\": \"exit\", \"status\": $status"
python3 -u - "$DB" <<'PY' | tee -a "$LOG"
import json, sqlite3, sys
c = sqlite3.connect(sys.argv[1]); c.row_factory = sqlite3.Row
tally = {r["verdict"] or "undecided": r["n"] for r in
         c.execute("SELECT verdict, COUNT(*) AS n FROM candidate GROUP BY verdict")}
total = sum(tally.values())
print(json.dumps({"stage": "tally", "rows": total, "verdicts": tally,
                  "complete": tally.get("undecided", 0) == 0 and total > 0}))
PY
exit "$status"
