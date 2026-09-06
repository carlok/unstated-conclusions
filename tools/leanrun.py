#!/usr/bin/env python3
"""Running Lean, safely, and reconstructing a declaration's setting.

Copied from `unused-assumptions/tools/leanrun.py` and diverged at the copy.
Four things here were paid for rather than designed, and each has a comment
saying what it cost. Two further things are fixed relative to the original and
are written up as I-1 and I-2 in ENGINEERING.md; both fixes are marked below.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path


class PartialTimeout(subprocess.TimeoutExpired):
    """A timeout that still carries what the child managed to write."""

    def __init__(self, timeout: float, out: str, err: str):
        super().__init__(cmd="lake env lean", timeout=timeout, output=out, stderr=err)
        self.partial = out + err


def run_bounded(command: list[str], cwd: Path, timeout: int,
                env: dict[str, str] | None = None) -> tuple[str, str]:
    """Run a child in its own process group and kill the group on timeout.

    `lake env lean` spawns `lean` beneath it. subprocess.run kills only the
    direct child, so a timeout leaves a grandchild holding a compiled Mathlib
    -- gigabytes that nothing reclaims, accumulating one per timeout until the
    machine dies. That is what took the sibling's first run down.
    """
    process = subprocess.Popen(command, cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=True)
    try:
        return process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()
        # Keep what the child had already written. Discarding it is right for a
        # candidate compile -- a partial Lean run says nothing about a theorem --
        # and wrong for a pass that emits one row per declaration, where a
        # two-hour run timing out at 90% currently yields nothing at all.
        out, err = process.communicate()
        raise PartialTimeout(timeout, out or "", err or "")


def available_gb() -> float:
    """Memory the system could hand a new Lean process, in gigabytes.

    Returns infinity where `vm_stat` does not exist, i.e. this fails open off
    macOS. A gate that blocks forever on a machine it cannot measure is worse
    than no gate.
    """
    try:
        out = subprocess.run(["vm_stat"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return float("inf")
    size = 4096
    first = out.splitlines()[0] if out else ""
    if "page size of" in first:
        size = int(re.search(r"page size of (\d+)", first).group(1))
    pages = 0
    for name in ("Pages free", "Pages inactive", "Pages speculative"):
        match = re.search(rf"{name}:\s+(\d+)", out)
        if match:
            pages += int(match.group(1))
    return pages * size / (1024 ** 3)


# The threshold is measured, not chosen. A Mathlib-importing `lean` on this
# machine holds about 3.4 GB resident (observed on the sibling sweep's own
# processes). With its two running, 7.0 GB was free on a 36 GB machine -- so
# one more process fits, and a gate set above that free figure is a deadlock
# rather than a safety measure. 5 GB clears one process with margin and still
# refuses when memory is genuinely gone. ENGINEERING.md 1.
MEMORY_FLOOR_GB = 5.0


# ENGINEERING.md I-1. The original calls json.dumps and time.sleep and imports
# neither, so any call that actually enters the loop raises NameError. It never
# fired there because available_gb() cleared the threshold on the first poll.
# This project runs beside a live sibling sweep holding two Mathlib processes,
# so the loop is entered on the first run. tests/ forces it.
def wait_for_memory(minimum_gb: float = MEMORY_FLOOR_GB, poll: int = 30,
                    limit: int | None = None) -> float:
    """Block until enough memory is free to start a Lean process.

    A Lean process with Mathlib wants gigabytes. Starting one with none free is
    how a previous run took the machine down with it.

    Returns the free figure it finally saw. `limit` caps the wait in seconds
    and is for tests.
    """
    waited = 0
    free = available_gb()
    while free < minimum_gb:
        print(json.dumps({"waiting_for_memory_gb": round(free, 1),
                          "want_gb": minimum_gb, "waited_seconds": waited}),
              flush=True)
        if limit is not None and waited >= limit:
            break
        time.sleep(poll)
        waited += poll
        free = available_gb()
    return free


# Lean writes tagged diagnostics as `error(lean.synthInstanceFailed):`, which
# does not contain the substring `error:`. A scan for the literal reads a file
# full of instance failures as clean. That mistake was made once in the sibling
# and cost a run. Warnings are deliberately not matched: linter noise about
# shadowed binders is inherited from the original declaration and must not fail
# a row.
ERROR_RE = re.compile(r"error(?:\([^)]*\))?:\s*(.*)")


def errors_in(report: str) -> list[str]:
    return ERROR_RE.findall(report)


# Two spellings, because `#print axioms` writes `does not depend on any axioms`
# for a proof that needs none and `depends on axioms: [...]` for one that does.
# Matching only the bracketed form failed 40 rows in the sibling for being
# cleaner than required.
AXIOMS_RE = re.compile(
    r"'(?P<name>[^']+)' (?:depends on axioms: \[(?P<axioms>[^\]]*)\]"
    r"|(?P<none>does not depend on any axioms))")

STANDARD_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}


def axioms_clean(report: str, declaration: str) -> tuple[bool, str]:
    """Did `#print axioms <declaration>` rest on nothing beyond the standard three?

    Subset, never equality: demanding all three fails a proof that uses two.
    The record must also *name* the declaration we asked about, or we are
    reading someone else's axioms.
    """
    for match in AXIOMS_RE.finditer(report):
        if match.group("name") != declaration:
            continue
        if match.group("none") is not None:
            return True, "no axioms"
        used = {a.strip() for a in (match.group("axioms") or "").split(",") if a.strip()}
        extra = used - STANDARD_AXIOMS
        if extra:
            return False, "non-standard axioms: " + ", ".join(sorted(extra))
        return True, "axioms ok"
    return False, f"no axiom record for {declaration}"


ROOT_IMPORT = os.environ.get("SWEEP_IMPORT", "Mathlib")

HEADER = ("".join(f"import {name.strip()}\n" for name in ROOT_IMPORT.split(",")
                  if name.strip())
          + "\nset_option maxHeartbeats 400000\n")


def header_for(row: dict) -> str:
    """What a standalone candidate must import to stand up.

    Mathlib has an umbrella, so importing it is enough. Another corpus need not:
    TauCeti's root module is deliberately empty, its lakefile building by glob
    instead, so there is nothing to import that brings the corpus with it. A
    candidate from such a library has to import the module it came from, which
    is the only thing that supplies its namespace and its own file's imports.

    Doing so also puts the original theorem in scope, so a tactic can close the
    goal by citing it. That is not new -- importing Mathlib has the same effect
    for a Mathlib candidate -- and it is what the duplicate check exists to
    catch.

    The replace keeps imports ahead of any command; an `import` after a command
    is a syntax error.
    """
    module = (row.get("module") or "").strip()
    if not module or module.split(".")[0] == "Mathlib":
        return HEADER
    return HEADER.replace("\nset_option", f"import {module}\n\nset_option")


def opened(row: dict) -> str:
    """Put a candidate back in the scope its source declaration had.

    Three things, all learned by losing candidates to them.

    The namespace, with every prefix. `open A.B` brings in what lives in `A.B`;
    sitting inside `namespace A` then `namespace B` also gives you `A`, so
    opening only the leaf loses everything declared at the outer level.

    The file's own `open` directives. A declaration is elaborated with whatever
    its file had opened. Without them a name like `log` is not unknown -- it
    becomes an autoImplicit variable, and the statement fails as "Function
    expected", which is indistinguishable from an ill-typed candidate.

    Everything is folded into `open ... in` clauses, so each binds to this
    declaration and nothing after it. A bare `open` is a command and would
    persist for the rest of the file, letting one candidate elaborate on a
    neighbour's scope.

    ENGINEERING.md I-2. Plain names first, scoped second. A scoped notation
    namespace is often reachable only *through* one of the plain ones: `open
    scoped sigma` resolves as `ArithmeticFunction.sigma` and is an unknown
    namespace until `ArithmeticFunction` is open. The sibling's sweep emits the
    scoped clause first and gets away with it only because it also emits every
    directive a second time, raw, ahead of both. That duplicate is load-bearing
    by accident, and it is not copied here.
    """
    plain: list[str] = []
    scoped: list[str] = []
    for line in (row.get("opens") or "").splitlines():
        body = line.strip().removeprefix("open ").strip()
        if not body:
            continue
        (scoped if body.startswith("scoped") else plain).append(body)
    namespace = (row.get("namespace") or "").strip()
    if namespace:
        parts = namespace.split(".")
        plain.extend(".".join(parts[: i + 1]) for i in range(len(parts)))
    names = list(dict.fromkeys(" ".join(plain).split()))
    prefix = f"open {' '.join(names)} in\n" if names else ""
    prefix += "".join(f"open {directive} in\n" for directive in dict.fromkeys(scoped))
    return prefix


PREFLIGHT = "#check @Nat.succ_le_succ"


def metaprogram_check(compose, repo: Path, timeout: int = 900) -> tuple[bool, str]:
    """Compile the metaprogram alone, before blaming any row for its errors.

    The `context` verdict means *this tool could not reproduce the
    declaration's setting*. It is the tool's failure, counted apart, and it is
    about the row. An error in the metaprogram itself produces exactly the same
    verdict on every row -- a store saying the setting could not be reproduced
    anywhere, which reads as a fact about the corpus.

    A stray doc comment did this once. Lean recovers from a parse error and
    still runs the commands after it, so the traversal kept working and only
    the sweep, which checks for errors, noticed -- and attributed them to the
    first row it tried. ENGINEERING.md 8.
    """
    ok, report = run_lean(compose("#check @Nat.succ_le_succ"), repo, timeout)
    if not ok:
        return False, "metaprogram check timed out"
    errors = errors_in(report)
    if errors:
        return False, "metaprogram does not compile: " + errors[0][:200]
    return True, "ok"


def preflight(repo: Path, timeout: int = 600) -> tuple[bool, str]:
    """Compile one trivial file before spending days on the real ones.

    A toolchain bump leaves the Mathlib dependency's compiled artefacts
    unreadable. `lake build` on the root project then exits 0 without fixing
    them, every `#check` resolves nothing, and every attempt comes back with
    the same verdict -- a store that looks exactly like a finished sweep. It
    has happened twice in the sibling. Three seconds against days.

    The fix there is `lake exe cache get`, which this project is not allowed to
    run: whoever owns the installation runs it. So this reports and stops.
    """
    import tempfile
    body = HEADER + "\n" + PREFLIGHT + "\n"
    handle = tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False)
    try:
        handle.write(body)
        handle.close()
        env = dict(os.environ)
        env.pop("LEAN_PATH", None)
        out, err = run_bounded(["lake", "env", "lean", handle.name], repo, timeout, env)
    except subprocess.TimeoutExpired:
        return False, "preflight timed out"
    finally:
        os.unlink(handle.name)
    report = out + err
    if "Nat.succ_le_succ :" in report:
        return True, "ok"
    first = report.strip().splitlines()[0] if report.strip() else "(no output)"
    return False, f"preflight failed: {first}"


def run_lean(body: str, repo: Path, timeout: int) -> tuple[bool, str]:
    """Compile one file in the sweep environment. The file lives in *our* temp
    directory, never inside the installation: nothing may be created there.
    """
    import tempfile
    handle = tempfile.NamedTemporaryFile("w", suffix=".lean", delete=False)
    try:
        handle.write(body)
        handle.close()
        env = dict(os.environ)
        env.pop("LEAN_PATH", None)
        try:
            out, err = run_bounded(["lake", "env", "lean", handle.name], repo, timeout, env)
        except PartialTimeout as expired:
            return False, "timeout\n" + expired.partial
        except subprocess.TimeoutExpired:
            return False, "timeout"
        return True, out + err
    finally:
        os.unlink(handle.name)
