#!/usr/bin/env python3
"""Part 1: the root-weakening sweep over `unused-assumptions`' Mathlib survivors.

POPULATION: unused-assumptions survivors (Mathlib). Every number this produces
is a rate among theorems already known to carry hypothesis slack. It is not a
library rate and must never be quoted as one.

One `lake env lean` per row, never batched. The sibling pays for that rule
already: a batch lets a parse error in one declaration corrupt its neighbours,
and lets a proof cite a sibling. Strictly serial and memory-gated, because this
runs beside that project's live sweep.

Each row's file compiles the weakened declaration and then asks three questions
of it in the same process: what is at the root, and what are the stronger
statements at explicit argument indices 0 and 1. Both indices always, because
the table lives in Python and Lean is not told what it is looking for -- asking
for both costs a little inference against an 85-second Mathlib import, and
asking Lean to consult the table would put the table in two places.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leanrun    # noqa: E402
import roots as rootsmod  # noqa: E402
import store      # noqa: E402
import traverse   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAX_INDEX = 2  # the table's largest stronger_arg is 1; ask for 0 and 1.


def seed(connection, survivors: Path, only: set[str] | None = None) -> int:
    rows = [json.loads(line) for line in survivors.read_text().splitlines() if line.strip()]
    if not rows:
        raise SystemExit(f"{survivors}: no rows")
    added = 0
    for row in rows:
        if row.get("corpus") != "Mathlib":
            continue
        if only is not None and row["id"] not in only:
            continue
        connection.execute(
            "INSERT OR IGNORE INTO candidate (id, key, corpus, area, module, theorem,"
            " namespace, opens, binder, stated_class, holds_over, source)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (row["id"], row["key"], row["corpus"], row["area"], row["module"],
             row["theorem"], row.get("namespace", ""), row.get("opens", ""),
             row.get("binder", ""), row.get("stated"), row.get("holds_over"),
             row["source"]))
        added += connection.total_changes and 1 or 0
    connection.commit()
    return connection.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]


def file_for(row, opens: str, wide: bool = False) -> str:
    """The candidate file: the weakened declaration, then the three questions.

    `opened` folds the directives and namespace prefixes into `open ... in`
    clauses bound to the declaration. Nothing is emitted raw: a bare `open` is a
    command, persists for the rest of the file, and lets one candidate elaborate
    on a neighbour's scope.
    """
    name = f"w{row['id']}"
    wide_flag = "true" if wide else "false"
    imports, body = traverse.metaprogram()
    head = "".join(f"import {n.strip()}\n" for n in leanrun.ROOT_IMPORT.split(",") if n.strip())
    head += "".join(f"{i}\n" for i in imports)
    head += "\nset_option maxHeartbeats 400000\n"
    scope = leanrun.opened({"opens": opens, "namespace": row["namespace"] or ""})
    questions = [f"#eval show Lean.Meta.MetaM Unit from do Unstated.emitLine "
                 f"(← Unstated.rootOf `{name})"]
    # The declaration is elaborated in this generated file, so it belongs to no
    # module and the sibling search has nothing to scan. Its module is passed
    # explicitly: the sibling lemma, when it exists, is in the file the theorem
    # came from -- often on the next line, which is precisely the outcome the
    # fifty-candidate gate is watching for.
    questions += [f"#eval show Lean.Meta.MetaM Unit from do Unstated.emitLine (← "
                  f"Unstated.detailOf `{name} {i} `strong{i} `{row['module']} {wide_flag})"
                  for i in range(MAX_INDEX)]
    return (head + "\n" + body + "\n\n" + scope + row["source"] + "\n\n"
            + "\n".join(questions) + "\n")


def parse(report: str) -> tuple[list[dict], list[str]]:
    rows, noise = [], []
    for line in report.splitlines():
        s = line.strip()
        if s.startswith("{") and s.endswith("}"):
            try:
                rows.append(json.loads(s))
                continue
            except json.JSONDecodeError:
                pass
        noise.append(line)
    return rows, noise


def decide(answers: list[dict], table: dict) -> dict:
    """Verdict from what Lean reported. The table decides; Lean never does.

    A fallback branch will be taken, and it returns the least interesting value
    rather than the most: anything unrecognised is `root_not_weakening`, never
    `strengthens`. The sibling scored every unlisted class at maximum depth and
    40 of its 64 deepest survivors were that default.
    """
    root_row = next((a for a in answers if "root_args" in a or "root_kind" in a), None)
    if root_row is None:
        # Fall back to a detail answer, which carries `root` and `layers` too.
        # One missing answer should cost precision, not the row -- and a row
        # recorded as `context` is recorded as a fact about the theorem.
        root_row = next((a for a in answers if a.get("ok") and a.get("root")), None)
    if root_row is None or not root_row.get("ok"):
        why = (root_row or {}).get("why", "no answer from the traversal")
        return {"verdict": "context", "detail": why[:400]}
    root = root_row.get("root")
    layers = root_row.get("layers")
    if any(a.get("has_sorry") for a in answers):
        # Lean inserts `sorryAx` when a tactic fails, so the declaration is still
        # added and `addDecl` on a subterm of it still succeeds. Nothing about
        # such a row is a finding, whatever its root. The sibling's rule --
        # success comes from `#print axioms`, never from the absence of an error
        # -- and the shot is accepted on positive evidence, so this is where that
        # relaxation has to be paid for.
        return {"verdict": "context", "root": root, "layers": layers,
                "detail": "proof rests on sorryAx: the weakened declaration did "
                          "not actually compile"}
    if root is None or root not in table:
        return {"verdict": "root_not_weakening", "root": root, "layers": layers,
                "detail": root_row.get("root_kind", "")}
    entry = table[root]
    want = entry["stronger_arg"]
    detail = next((a for a in answers
                   if a.get("explicit_index") == want and a.get("ok")), None)
    if detail is None:
        failed = next((a for a in answers if not a.get("ok") and "why" in a), {})
        return {"verdict": "context", "root": root, "layers": layers,
                "detail": failed.get("why", f"no detail at explicit index {want}")[:400]}
    siblings = detail.get("siblings") or []
    common = {"root": root, "layers": layers, "explicit_index": want,
              "siblings": ",".join(siblings),
              "stronger": detail.get("stronger"), "stated": detail.get("stated"),
              "defeq_to_stated": int(bool(detail.get("defeq_to_stated"))),
              "verify": detail.get("verify")}
    if not detail.get("peel_preserved_type", True):
        # Peeling a wrapper changed the type, so the table's guarantee -- the
        # selected argument implies the root's type -- no longer reaches the
        # stated conclusion. The statement is verified true; whether it implies
        # the theorem is unestablished.
        #
        # Its own verdict rather than a fold into `stripped_only`, because the
        # filter is CONSERVATIVE and the loss is real: in the first fifty, six
        # rows broke the chain and four of them look like genuine
        # strengthenings a person would want (`RatFunc.denom_inv_dvd` proves an
        # exact formula where the statement says divisibility). Discarding them
        # silently would hide that; counting them as findings would claim
        # something unproved. They ship in their own bucket, unpooled, and the
        # report says what is and is not established about them.
        return {"verdict": "unchained", **common,
                "detail": "wrapper stripping changed the type; the stronger "
                          "statement is verified but need not imply the stated one"}
    if detail.get("defeq_to_stated"):
        # The "stronger" statement is the stated one wearing different syntax.
        # Not a finding, and counted apart so it cannot inflate the yield.
        return {"verdict": "stripped_only", **common}
    if detail.get("verify") == "added as a definition":
        # The strengthened "statement" is a Type, not a Prop: the selected
        # argument is the object itself. The kernel accepted it as a `def`,
        # which is the right outcome and not a failure -- it is stage 2's
        # material, an object the library named in a proof and never wrote
        # down. Its own verdict, because calling it `strengthens` would put an
        # object in a table of statements. ENGINEERING.md 13.
        return {"verdict": "witness", **common}
    if detail.get("verify") != "added":
        return {"verdict": "context", **common,
                "detail": str(detail.get("verify"))[:400]}
    if siblings:
        # The library already states this. Not waste -- a measurement of API
        # design, and the pair is recorded so the rate can be read rather than
        # asserted.
        return {"verdict": "duplicate", **common}
    # `strengthens` from the defeq leg alone. The name-pattern and `exact?`
    # legs run afterwards on this much smaller set, and can only move a row
    # from `strengthens` to `duplicate`, never the other way.
    return {"verdict": "strengthens", **common}


def sweep(connection, repo: Path, table: dict, timeout: int, limit: int | None,
          wide: bool = False) -> None:
    todo = store.pending(connection)
    if limit:
        todo = todo[:limit]
    print(json.dumps({"stage": "start", "pending": len(todo),
                      "population": "unused-assumptions survivors (Mathlib)"}), flush=True)
    for n, row in enumerate(todo, 1):
        started = time.time()
        leanrun.wait_for_memory()
        # Two shots. The file's `open` directives cut both ways: without them a
        # name like `log` becomes an autoImplicit variable, and with them a
        # directive such as `open scoped zeta` names a notation namespace that
        # does not resolve outside its own file. Which shot won is recorded --
        # the sibling's verifier reproduced the result but not the procedure,
        # and 17 of its 18 apparent non-reproductions were that.
        answers, noise, shot = [], [], None
        for label, opens in (("opens", row["opens"] or ""), ("bare", "")):
            if label == "bare" and not (row["opens"] or "").strip():
                break  # a row with no directives is not retried
            ok, report = leanrun.run_lean(file_for(row, opens, wide), repo, timeout)
            if not ok:
                noise = ["timeout"]
                continue
            answers, noise = parse(report)
            errors = leanrun.errors_in("\n".join(noise))
            usable = any(a.get("ok") for a in answers)
            if usable:
                # Positive evidence, not the absence of an error: the kernel
                # said `added`, or the traversal read a root. The sibling's
                # lesson runs the other way -- never infer success FROM absence
                # of an error -- and is not weakened by accepting success when
                # there is a positive answer. Errors are still recorded.
                shot = label
                break
            answers, noise = [], errors or noise
        fields = (decide(answers, table) if shot
                  else {"verdict": "context",
                        "detail": ("; ".join(noise)[:400]) or "no output"})
        fields["shot"] = shot
        if noise:
            # Recorded even on a successful shot. A row that compiled while its
            # file emitted an error is a row someone should be able to look at.
            fields["detail"] = ((fields.get("detail") or "") + " | lean: "
                                + "; ".join(noise)[:300]).strip(" |")
        fields["seconds"] = round(time.time() - started, 1)
        store.record(connection, row["id"], **fields)
        print(json.dumps({"n": n, "of": len(todo), "theorem": row["theorem"],
                          "verdict": fields["verdict"], "root": fields.get("root"),
                          "shot": shot, "seconds": fields["seconds"]}), flush=True)
    print(json.dumps({"stage": "complete", "tally": store.tally(connection)}), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=os.environ.get("SWEEP_REPO"))
    parser.add_argument("--survivors", type=Path,
                        default=ROOT.parent / "unused-assumptions" / "data" / "survivors.jsonl")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "part1.db")
    parser.add_argument("--only", type=Path, help="file of ids, one per line")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--seed-only", action="store_true")
    parser.add_argument("--wide", action="store_true",
                        help="search the whole library for a duplicate, not "
                             "just the theorem's module. For the second pass "
                             "over rows that survived the first.")
    args = parser.parse_args()
    if not args.repo:
        parser.error("set SWEEP_REPO or pass --repo")
    repo = Path(args.repo)

    # Make the input list an output.
    print(json.dumps({"survivors": str(args.survivors), "db": str(args.db),
                      "repo": str(repo)}), flush=True)

    only = None
    if args.only:
        only = {line.strip() for line in args.only.read_text().splitlines() if line.strip()}

    connection = store.connect(args.db)
    total = seed(connection, args.survivors, only)
    print(json.dumps({"stage": "seeded", "rows": total}), flush=True)
    if args.seed_only:
        return 0

    ok, why = leanrun.preflight(repo)
    print(json.dumps({"preflight": ok, "detail": why}), flush=True)
    if not ok:
        return 1

    # Then the metaprogram, alone. Without this, an error in it is recorded as
    # `context` on every row -- the tool's own failure written into the store as
    # a fact about 645 theorems.
    ok, why = leanrun.metaprogram_check(
        lambda cmd: traverse.compose(cmd, None), repo)
    print(json.dumps({"metaprogram": ok, "detail": why}), flush=True)
    if not ok:
        return 1

    sweep(connection, repo, rootsmod.load_table(), args.timeout, args.limit,
          wide=args.wide)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
