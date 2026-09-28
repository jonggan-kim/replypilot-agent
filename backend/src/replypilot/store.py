from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RunStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                email_id TEXT NOT NULL,
                thread_id TEXT NOT NULL,
                sender TEXT NOT NULL,
                subject TEXT NOT NULL,
                status TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )

    @property
    def connection(self) -> sqlite3.Connection:
        return self._connection

    def save_run(self, run_id: str, data: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        payload = json.dumps(data, ensure_ascii=False, default=str)
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO runs (id, email_id, thread_id, sender, subject, status, payload, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  status=excluded.status, payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (
                    run_id,
                    data["email_id"],
                    data["thread_id"],
                    data["sender"],
                    data["subject"],
                    data["status"],
                    payload,
                    data.get("created_at", now),
                    now,
                ),
            )

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO audit_events (run_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (run_id, event_type, json.dumps(payload, ensure_ascii=False, default=str), now),
            )

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        row = self._connection.execute("SELECT payload FROM runs WHERE id = ?", (run_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def list_runs(self, *, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self._connection.execute(
                "SELECT payload FROM runs WHERE status = ? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = self._connection.execute("SELECT payload FROM runs ORDER BY updated_at DESC").fetchall()
        return [json.loads(row["payload"]) for row in rows]

