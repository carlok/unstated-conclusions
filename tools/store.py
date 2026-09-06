#!/usr/bin/env python3
"""The Part 1 store: resumable, and resumable in the only way that survives.

No marker file and no state outside the store. Completeness is a query, because
a marker can disagree with the data and a query cannot -- the sibling learned
that after a sprint whose marker said finished over an area whose prior-art
gate had never run, and reported that area as having zero findings.

Every row is committed as it is decided, and the work query selects only
undecided rows, so a kill costs at most one compile.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate (
    id              TEXT PRIMARY KEY,
    key             TEXT NOT NULL,
    corpus          TEXT NOT NULL,
    area            TEXT NOT NULL,
    module          TEXT NOT NULL,
    theorem         TEXT NOT NULL,
    namespace       TEXT,
    opens           TEXT,
    binder          TEXT,
    stated_class    TEXT,
    holds_over      TEXT,
    source          TEXT NOT NULL,
    -- filled by the sweep, one row at a time
    verdict         TEXT,
    shot            TEXT,
    layers          INTEGER,
    root            TEXT,
    explicit_index  INTEGER,
    stronger        TEXT,
    stated          TEXT,
    defeq_to_stated INTEGER,
    verify          TEXT,
    detail          TEXT,
    siblings        TEXT,
    seconds         REAL
);
CREATE INDEX IF NOT EXISTS candidate_verdict ON candidate(verdict);
"""

VERDICTS = ("strengthens", "witness", "duplicate", "root_not_weakening",
            "stripped_only", "unchained", "context")


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    connection.commit()
    return connection


def pending(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    """Undecided rows only. This is what makes a kill cost one compile."""
    return connection.execute(
        "SELECT * FROM candidate WHERE verdict IS NULL ORDER BY id").fetchall()


def record(connection: sqlite3.Connection, row_id: str, **fields) -> None:
    columns = ", ".join(f"{k} = ?" for k in fields)
    connection.execute(f"UPDATE candidate SET {columns} WHERE id = ?",
                       (*fields.values(), row_id))
    connection.commit()


def complete(connection: sqlite3.Connection) -> bool:
    """Every row decided. A query over the data, never a marker beside it."""
    total = connection.execute("SELECT COUNT(*) FROM candidate").fetchone()[0]
    if total == 0:
        return False  # an empty store is not a finished one
    undecided = connection.execute(
        "SELECT COUNT(*) FROM candidate WHERE verdict IS NULL").fetchone()[0]
    return undecided == 0


def tally(connection: sqlite3.Connection) -> dict[str, int]:
    return {r["verdict"] or "undecided": r["n"] for r in connection.execute(
        "SELECT verdict, COUNT(*) AS n FROM candidate GROUP BY verdict")}
