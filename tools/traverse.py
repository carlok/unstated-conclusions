#!/usr/bin/env python3
"""Compose and run the traversal metaprogram in a sweep environment.

`lean/Traverse.lean` is included textually, because this project owns no Lean
package and may not create a file inside either installation. Its own `import`
lines are hoisted to the top of the generated file, since an `import` after a
command is a syntax error -- the same rule `header_for` obeys.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import leanrun  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
METAPROGRAM = ROOT / "lean" / "Traverse.lean"


def metaprogram() -> tuple[list[str], str]:
    """Return (imports, body) for the metaprogram, imports hoisted out."""
    imports, body = [], []
    for line in METAPROGRAM.read_text().splitlines():
        (imports if line.startswith("import ") else body).append(line)
    return imports, "\n".join(body)


def compose(command: str, row: dict | None = None) -> str:
    imports, body = metaprogram()
    header = leanrun.header_for(row or {})
    extra = "".join(f"{i}\n" for i in imports if i.split()[1] not in header)
    # Imports first, always: the header already ends with a `set_option`
    # command, and an import after a command does not parse.
    head = "".join(f"import {n.strip()}\n" for n in leanrun.ROOT_IMPORT.split(",") if n.strip())
    head += extra + "\nset_option maxHeartbeats 1000000\n"
    if row is not None and (row.get("module") or "").split(".")[0] not in ("", "Mathlib"):
        head = f"import {row['module']}\n" + head
    return head + "\n" + body + "\n\n" + command + "\n"


def run(command: str, repo: Path, timeout: int = 1800,
        row: dict | None = None) -> tuple[list[dict], str]:
    """Run a composed file and split its stdout into JSON rows and the rest.

    Lines that are not JSON are returned as the report rather than discarded:
    a Lean error is the most useful thing in the output and dropping it is how
    a stage comes to report on itself.
    """
    body = compose(command, row)
    leanrun.wait_for_memory()
    ok, report = leanrun.run_lean(body, repo, timeout)
    # A timed-out run now carries what it managed to write, so its rows are
    # parsed rather than dropped. The caller is told via the report, which
    # begins with "timeout" -- a partial pass is a partial pass and must not be
    # mistaken for a complete one.
    rows, noise = [], []
    for line in report.splitlines():
        stripped = line.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                rows.append(json.loads(stripped))
                continue
            except json.JSONDecodeError:
                pass
        noise.append(line)
    return rows, "\n".join(noise)


def name_list(names) -> str:
    """A Lean list of *unchecked* name literals.

    Single backtick, not double: a double-backtick literal is checked at
    elaboration, so a table entry naming a constant that does not exist would
    fail to compile instead of being reported as missing. Reporting it is the
    entire point of the check.
    """
    return "[" + ", ".join("`" + str(n) for n in names) + "]"


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["check-table", "roots", "roots-all",
                                        "detail", "citations"])
    parser.add_argument("--repo", type=Path, default=os.environ.get("SWEEP_REPO"))
    parser.add_argument("--names", nargs="*", default=[])
    parser.add_argument("--module-prefix", default="Mathlib")
    parser.add_argument("--which", type=int, default=0)
    parser.add_argument("--pairs", type=Path,
                        help="jsonl of {decl, which, module} to detail in one run")
    parser.add_argument("--wide", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    if not args.repo:
        parser.error("set SWEEP_REPO or pass --repo")
    repo = Path(args.repo)

    ok, why = leanrun.preflight(repo)
    print(json.dumps({"preflight": ok, "detail": why, "repo": str(repo)}), flush=True)
    if not ok:
        return 1

    if args.mode == "check-table":
        table = json.loads((ROOT / "weakenings.json").read_text())
        names = [e["root"] for e in table["entries"]]
        command = f"#eval show Lean.Meta.MetaM Unit from Unstated.checkTable {name_list(names)}"
    elif args.mode == "roots":
        command = f"#eval show Lean.Meta.MetaM Unit from Unstated.roots {name_list(args.names)}"
    elif args.mode == "citations":
        command = ('#eval show Lean.Meta.MetaM Unit from Unstated.citationCounts '
                   f'"{args.module_prefix}"')
    elif args.mode == "roots-all":
        command = ('#eval show Lean.Meta.MetaM Unit from Unstated.rootsAll '
                   f'"{args.module_prefix}"')
    else:
        # A list of (declaration, explicit index) pairs, detailed in ONE
        # process. These are declarations that already exist in the imported
        # environment, so nothing has to be compiled first -- fifty of them cost
        # one Mathlib import between them rather than fifty. The per-row sweep
        # pays the import fifty times only because it must elaborate a
        # declaration that does not exist yet.
        if args.pairs:
            pairs = [json.loads(line) for line in
                     args.pairs.read_text().splitlines() if line.strip()]
        else:
            pairs = [{"decl": n, "which": args.which} for n in args.names]
        command = "\n".join(
            f'#eval show Lean.Meta.MetaM Unit from do Unstated.emitLine (← '
            f'Unstated.detailOf `{p["decl"]} {p["which"]} `strengthened{i} '
            f'`{p.get("module", "")} {"true" if args.wide else "false"})'
            for i, p in enumerate(pairs))

    rows, noise = run(command, repo, args.timeout)
    errors = leanrun.errors_in(noise)
    if errors:
        # Lean recovers from a parse error and runs the commands after it, so a
        # broken metaprogram still emits rows and the run looks fine. Those rows
        # may be perfectly good; the point is that nobody was told. Print the
        # errors loudly and, if nothing came back at all, refuse.
        print(f"--- {len(errors)} error(s) from Lean ---", file=sys.stderr)
        for error in errors[:10]:
            print("  " + error[:200], file=sys.stderr)
    if noise.strip():
        print("--- lean output that was not a row ---", file=sys.stderr)
        print(noise.strip()[:2000], file=sys.stderr)
    if args.out:
        if not rows:
            # Never overwrite a good file with an empty one. A run that timed
            # out and a corpus that contained nothing produce the same zero,
            # and the second is what an empty file would go on to mean to
            # everything downstream.
            print(f"# refusing to write {args.out}: no rows", file=sys.stderr)
            return 1
        args.out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    else:
        for r in rows:
            print(json.dumps(r))
    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
