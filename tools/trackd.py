#!/usr/bin/env python3
"""Track D, phase 1: recover what the sibling's export could not carry.

`blamed` is null on all 57,382 rows of `breaks.jsonl.gz`, and will stay so. The
sibling's sweep kept `errors[0][:200]` and Lean puts the class name on the
*second* line of `failed to synthesize instance of type class`. The constant
that dichotomy repair needs was discarded at collection time, and recovering it
there costs a four-day re-sweep.

The brief's instruction is not to ask for that. *Every row that reaches repair
is recompiled at `fails_at` by this project anyway, to construct the split;
capture the full multi-line error then, for the pilot slice only, and store it
in this project's data.*

So this recompiles 200 rows and keeps the whole error block. Two populations,
never merged: 10 strict rung-3 rows, and 190 top-up rows that exercise the
machinery and yield no rung-3 rate.

Before spending a compile, a Lean-free guard checks the row's recorded
`fails_at` actually appears in its own source. The sibling's `claims_what_it_proves`
exists for the same reason and states it best: a green result on the wrong
statement is worse than a red one, because it is quiet.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leanrun  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SCHEMA = """
CREATE TABLE IF NOT EXISTS repair (
    id          TEXT PRIMARY KEY,
    key         TEXT NOT NULL,
    population  TEXT NOT NULL,
    area        TEXT NOT NULL,
    module      TEXT NOT NULL,
    theorem     TEXT NOT NULL,
    namespace   TEXT,
    opens       TEXT,
    binder      TEXT,
    stated      TEXT,
    holds_over  TEXT,
    fails_at    TEXT,
    fail_error  TEXT,
    source      TEXT NOT NULL,
    provenance  TEXT,
    verdict     TEXT,
    full_error  TEXT,
    blamed      TEXT,
    shot        TEXT,
    seconds     REAL
);
CREATE INDEX IF NOT EXISTS repair_verdict ON repair(verdict);
"""

# Lean writes the class on the line after the header, which is exactly what the
# sibling's 200-character first-line capture threw away.
BLAMED = [
    re.compile(r"failed to synthesize instance of type class\s*\n\s*(.+)", re.M),
    re.compile(r"failed to synthesize\s*\n\s*(.+)", re.M),
    re.compile(r"unknown identifier '([^']+)'"),
    re.compile(r"unknown constant '([^']+)'"),
]


def error_block(report: str) -> str:
    """The whole error, not its first line.

    Lines are kept from the first `error` marker to the next file:line:col
    header or the end. This is the entire point of the stage.
    """
    lines = report.splitlines()
    start = next((i for i, l in enumerate(lines) if leanrun.ERROR_RE.search(l)), None)
    if start is None:
        return ""
    out = [lines[start]]
    for line in lines[start + 1:]:
        if re.match(r"^\S*:\d+:\d+: ", line):
            break
        out.append(line)
    return "\n".join(out).strip()


def blamed_from(block: str) -> str | None:
    for pattern in BLAMED:
        match = pattern.search(block)
        if match:
            return match.group(1).strip()[:200]
    return None


def binder_variable(binder: str) -> str | None:
    """`[IsDomain R]` -> `R`. The class alone is not enough to check against.

    A source can carry `[CommRing R]` while the binder under test is
    `[Field k]`, and a check for the bare class name passes on the wrong
    variable. `Ne.isUnit_C` did exactly that and was recorded as compiling at a
    class it was never rebuilt at. ENGINEERING.md 16.
    """
    inner = binder.strip().strip("[]").split()
    return inner[-1] if len(inner) >= 2 else None


def source_at(row) -> tuple[str | None, str, str]:
    """The row's source rebuilt at `fails_at`, and how it was obtained.

    The sibling's export ships ONE source per row, and for a binder that both
    held somewhere and broke somewhere it ships the source that **held**. Seven
    of seven strict rows with a non-null `holds_over` carry `holds_over`, and
    none carries `fails_at`. So for exactly the rows Track D needs, the failing
    compile has no source attached.

    That is the sibling's own ENGINEERING #12 in a new place: a stage that
    computes something must keep what proved it, or it has computed a rumour.
    Its descent shipped a class with no source behind it; its breaks export
    ships a source belonging to a different class than the row's `fails_at`.

    Reconstruction is possible and is not free. The sibling tried rebuilding a
    source by rewriting a binder and **six rows that had compiled stopped
    compiling**. So a reconstructed row is marked as one, kept in its own
    bucket, and never pooled with rows whose source arrived as shipped.
    """
    fails_at = (row["fails_at"] or "").strip()
    variable = binder_variable(row["binder"] or "")
    if not fails_at:
        return None, "mismatch", "no fails_at recorded"
    if not variable:
        return None, "mismatch", f"cannot read a variable out of {row['binder']!r}"
    wanted = f"[{fails_at} {variable}]"
    if wanted in row["source"]:
        return row["source"], "as_shipped", "ok"
    holds_over = (row["holds_over"] or "").strip()
    if holds_over:
        have = f"[{holds_over} {variable}]"
        if have in row["source"]:
            return row["source"].replace(have, wanted, 1), "reconstructed", \
                   f"rewrote {have} to {wanted}"
        return None, "mismatch", f"source carries neither {wanted} nor {have}"
    return None, "mismatch", f"source does not carry {wanted}"


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    connection.commit()
    return connection


def seed(connection, payload: dict) -> int:
    for population in ("strict", "topup"):
        for row in payload[population]:
            connection.execute(
                "INSERT OR IGNORE INTO repair (id, key, population, area, module,"
                " theorem, namespace, opens, binder, stated, holds_over, fails_at,"
                " fail_error, source) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (row["id"], row["key"], population, row["area"], row["module"],
                 row["theorem"], row.get("namespace", ""), row.get("opens", ""),
                 row.get("binder", ""), row.get("stated"), row.get("holds_over"),
                 row.get("fails_at"), row.get("fail_error"), row["source"]))
    connection.commit()
    return connection.execute("SELECT COUNT(*) FROM repair").fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=os.environ.get("SWEEP_REPO"))
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "trackd-input.json")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "trackd.db")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if not args.repo:
        parser.error("set SWEEP_REPO or pass --repo")
    repo = Path(args.repo)

    print(json.dumps({"input": str(args.input), "db": str(args.db),
                      "repo": str(repo)}), flush=True)
    connection = connect(args.db)
    total = seed(connection, json.loads(args.input.read_text()))
    print(json.dumps({"stage": "seeded", "rows": total}), flush=True)

    ok, why = leanrun.preflight(repo)
    print(json.dumps({"preflight": ok, "detail": why}), flush=True)
    if not ok:
        return 1

    todo = connection.execute(
        "SELECT * FROM repair WHERE verdict IS NULL ORDER BY population DESC, id").fetchall()
    if args.limit:
        todo = todo[:args.limit]
    print(json.dumps({"stage": "start", "pending": len(todo)}), flush=True)

    for n, row in enumerate(todo, 1):
        started = time.time()
        source, provenance, why = source_at(row)
        if source is None:
            connection.execute(
                "UPDATE repair SET verdict=?, provenance=?, full_error=?, seconds=?"
                " WHERE id=?",
                ("mismatch", provenance, why, round(time.time() - started, 1), row["id"]))
            connection.commit()
            print(json.dumps({"n": n, "of": len(todo), "theorem": row["theorem"],
                              "verdict": "mismatch", "why": why}), flush=True)
            continue

        leanrun.wait_for_memory()
        verdict, block, blamed, shot = "context", "", None, None
        for label, opens in (("opens", row["opens"] or ""), ("bare", "")):
            if label == "bare" and not (row["opens"] or "").strip():
                break
            body = (leanrun.header_for(dict(row)) + "\n"
                    + leanrun.opened({"opens": opens, "namespace": row["namespace"] or ""})
                    + source + "\n")
            ran, report = leanrun.run_lean(body, repo, args.timeout)
            if not ran:
                verdict, block = "timeout", "timeout"
                continue
            errors = leanrun.errors_in(report)
            if not errors:
                # The sibling recorded this row as failing and it compiles here.
                # A real discrepancy, recorded rather than smoothed over.
                verdict, block, shot = "compiles_anyway", "", label
                break
            block = error_block(report)
            blamed = blamed_from(block)
            shot = label
            # A file that does not parse says nothing about the theorem in it.
            # 22 of the first 174 captured "errors" were this, all on sources
            # shipped as-is, and every one would have been counted as a break
            # the sweep could analyse. ENGINEERING.md 17.
            verdict = ("parse_failed"
                       if ("expected command" in block or "unexpected token" in block)
                       else "error_captured")
            break

        connection.execute(
            "UPDATE repair SET verdict=?, provenance=?, full_error=?, blamed=?,"
            " shot=?, seconds=? WHERE id=?",
            (verdict, provenance, block[:4000], blamed, shot,
             round(time.time() - started, 1), row["id"]))
        connection.commit()
        print(json.dumps({"n": n, "of": len(todo), "population": row["population"],
                          "theorem": row["theorem"], "verdict": verdict,
                          "provenance": provenance, "blamed": blamed,
                          "seconds": round(time.time() - started, 1)}),
              flush=True)

    tally = {r["verdict"] or "undecided": r["n"] for r in connection.execute(
        "SELECT verdict, COUNT(*) n FROM repair GROUP BY verdict")}
    recovered = connection.execute(
        "SELECT COUNT(*) FROM repair WHERE blamed IS NOT NULL").fetchone()[0]
    print(json.dumps({"stage": "complete", "tally": tally,
                      "blamed_recovered": recovered}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
