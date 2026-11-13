"""SQLite state: which procedures we know, and which alerts were already sent.

The procedure id (not the publication number) is the identity of a tender, so
a correction published as a new notice is recognised as a change of the same
procedure. Alerts are keyed, so running twice never alerts twice.
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from .models import Notice

NEW = "NEW"
DEADLINE_CHANGED = "DEADLINE_CHANGED"
AMENDED = "AMENDED"
UNCHANGED = "UNCHANGED"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS procedures (
    procedure_id TEXT PRIMARY KEY,
    publication_number TEXT NOT NULL,
    title TEXT NOT NULL,
    deadline TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS alerts_sent (
    key TEXT PRIMARY KEY
);
"""


class Store:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript(_SCHEMA)

    def upsert(self, n: Notice) -> tuple[str, Optional[str]]:
        """Record the notice. Returns (event, previous_deadline)."""
        row = self.db.execute(
            "SELECT publication_number, deadline FROM procedures WHERE procedure_id=?",
            (n.procedure_id,),
        ).fetchone()
        new_deadline = n.deadline_key()
        with self.db:
            if row is None:
                self.db.execute(
                    "INSERT INTO procedures VALUES (?,?,?,?)",
                    (n.procedure_id, n.publication_number, n.title, new_deadline),
                )
                return NEW, None
            old_pub, old_deadline = row
            if old_deadline != new_deadline:
                event = DEADLINE_CHANGED
            elif old_pub != n.publication_number:
                event = AMENDED
            else:
                return UNCHANGED, None
            self.db.execute(
                "UPDATE procedures SET publication_number=?, title=?, deadline=? WHERE procedure_id=?",
                (n.publication_number, n.title, new_deadline, n.procedure_id),
            )
            return event, old_deadline

    def was_sent(self, key: str) -> bool:
        return self.db.execute("SELECT 1 FROM alerts_sent WHERE key=?", (key,)).fetchone() is not None

    def mark_sent(self, keys: list[str]) -> None:
        with self.db:
            self.db.executemany("INSERT OR IGNORE INTO alerts_sent VALUES (?)", [(k,) for k in keys])

    def close(self) -> None:
        self.db.close()
