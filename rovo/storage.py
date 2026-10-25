"""Neustartfeste lokale Notizen und Timer; keine Rohaufnahmen."""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path


class Store:
    def __init__(self, path: str | Path = ":memory:") -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS notes(id TEXT PRIMARY KEY, text TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS timers(id TEXT PRIMARY KEY, label TEXT NOT NULL, due REAL NOT NULL,
                remaining REAL, state TEXT NOT NULL DEFAULT 'running');
        """)

    def note(self, text: str) -> str:
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            raise ValueError("Notiz muss 1 bis 2000 Zeichen enthalten.")
        ident = uuid.uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO notes VALUES(?,?,?)", (ident, text.strip(), time.time())
            )
        return ident

    def notes(self) -> list[dict]:
        return [
            dict(row) for row in self.db.execute("SELECT * FROM notes ORDER BY created")
        ]

    def delete_note(self, ident: str) -> bool:
        with self.db:
            return (
                self.db.execute("DELETE FROM notes WHERE id=?", (ident,)).rowcount == 1
            )

    def timer(self, seconds: float, label: str = "Timer") -> str:
        from .config import number

        number(seconds, 0.1, 365 * 86400)
        ident = uuid.uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO timers(id,label,due) VALUES(?,?,?)",
                (ident, label[:100], time.time() + seconds),
            )
        return ident

    def timers(self) -> list[dict]:
        now = time.time()
        return [
            {
                **dict(row),
                "remaining_s": max(
                    0,
                    row["remaining"] if row["state"] == "paused" else row["due"] - now,
                ),
            }
            for row in self.db.execute(
                "SELECT * FROM timers WHERE state IN ('running','paused') ORDER BY due"
            )
        ]

    def timer_action(self, ident: str, action: str) -> bool:
        row = self.db.execute("SELECT * FROM timers WHERE id=?", (ident,)).fetchone()
        if row is None:
            return False
        with self.db:
            if action == "pause" and row["state"] == "running":
                self.db.execute(
                    "UPDATE timers SET state='paused',remaining=? WHERE id=?",
                    (max(0, row["due"] - time.time()), ident),
                )
            elif action == "resume" and row["state"] == "paused":
                self.db.execute(
                    "UPDATE timers SET state='running',due=?,remaining=NULL WHERE id=?",
                    (time.time() + row["remaining"], ident),
                )
            elif action == "cancel":
                self.db.execute(
                    "UPDATE timers SET state='cancelled' WHERE id=?", (ident,)
                )
            else:
                return False
        return True

    def due(self) -> list[dict]:
        # Atomare Claim-Transaktion: erneuter Poll löst denselben Timer nicht doppelt aus.
        with self.db:
            rows = list(
                self.db.execute(
                    "SELECT * FROM timers WHERE state='running' AND due<=?",
                    (time.time(),),
                )
            )
            self.db.executemany(
                "UPDATE timers SET state='fired' WHERE id=?",
                [(row["id"],) for row in rows],
            )
        return [dict(row) for row in rows]

    def close(self) -> None:
        self.db.close()
