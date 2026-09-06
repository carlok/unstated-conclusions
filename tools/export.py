#!/usr/bin/env python3
"""Generate data/MANIFEST.json and the published rows.

Every number this project quotes lives here and nowhere else. Prose quotes
generated macros. Six figures went stale in the sibling before that rule was
applied everywhere, and they went stale quietly, because nothing rereads a
paragraph.

The manifest also records what was consumed, by SHA-256: this project's inputs
are another project's outputs, and a row is relative to the exact bytes it was
computed from. When the sibling re-exports, the hashes change, the join is
re-run, and that is a visible event rather than a silent drift.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import store  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(repo: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(repo), *args],
                             capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip() or None


def corpus_pin(repo: Path) -> dict:
    """The revision that matters is Mathlib's, not the project depending on it.

    Comparing the wrapper project's HEAD reports a mismatch on every run; the
    sibling's verifier says so in a comment and this reads the same place.
    """
    mathlib = repo / ".lake" / "packages" / "mathlib"
    where = mathlib if mathlib.exists() else repo
    toolchain = (repo / "lean-toolchain")
    return {
        "corpus": "Mathlib",
        "revision": git(where, "rev-parse", "HEAD"),
        "describes": git(where, "log", "-1", "--format=%s"),
        "toolchain": toolchain.read_text().strip() if toolchain.exists() else None,
        "project_path": None,  # a local path, and this file is published
    }


def consumed(paths: list[Path]) -> list[dict]:
    rows = []
    for path in paths:
        if not path.exists():
            rows.append({"path": path.name, "present": False})
            continue
        rows.append({"path": path.name, "present": True, "bytes": path.stat().st_size,
                     "sha256": sha256(path)})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--brother", type=Path,
                        default=ROOT.parent / "unused-assumptions")
    parser.add_argument("--db", type=Path, default=ROOT / "data" / "part1.db")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "MANIFEST.json")
    args = parser.parse_args()

    # Make the input list an output.
    print(json.dumps({"repo": str(args.repo), "brother": str(args.brother),
                      "db": str(args.db)}), file=sys.stderr)

    brother_data = args.brother / "data"
    brother_manifest = brother_data / "MANIFEST.json"
    upstream = json.loads(brother_manifest.read_text()) if brother_manifest.exists() else {}

    counts = {}
    if args.db.exists():
        connection = store.connect(args.db)
        counts = {
            "part1_population": "unused-assumptions survivors (Mathlib)",
            "part1_rows": connection.execute(
                "SELECT COUNT(*) FROM candidate").fetchone()[0],
            "part1_theorems": connection.execute(
                "SELECT COUNT(DISTINCT module || '|' || theorem) FROM candidate").fetchone()[0],
            "part1_complete": store.complete(connection),
            "part1_verdicts": store.tally(connection),
        }

    manifest = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "unstated-conclusions",
        "note": ("Every number this project quotes lives in this file. A row is "
                 "relative to the corpus revision below; a row that fails to "
                 "verify against a different revision says nothing about this "
                 "export."),
        "corpora": [corpus_pin(args.repo)],
        "tauceti": "not yet exported (gated): the sibling's census and prior-art "
                   "gate have not caught up, and exporting now would divide a "
                   "gated numerator by an ungated denominator",
        "consumed": {
            "from": "unused-assumptions",
            "upstream_manifest_generated": upstream.get("generated"),
            "upstream_revision": (upstream.get("corpora") or [{}])[0].get("revision"),
            "id_scheme": upstream.get("id_scheme"),
            "key_scheme": upstream.get("key_scheme"),
            "files": consumed([brother_data / "survivors.jsonl",
                               brother_data / "breaks.jsonl.gz"]),
        },
        "table": {
            "path": "weakenings.json",
            "sha256": sha256(ROOT / "weakenings.json"),
            "entries": len(json.loads((ROOT / "weakenings.json").read_text())["entries"]),
        },
        "metaprogram": {
            "path": "lean/Traverse.lean",
            "sha256": sha256(ROOT / "lean" / "Traverse.lean"),
        },
        **counts,
    }
    args.out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
