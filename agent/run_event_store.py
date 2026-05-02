from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from agent.run_events import RunEventRecord, RunNodeRecord, RunRecord
from hermes_constants import get_hermes_home

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    started_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS run_nodes (
    node_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    started_at REAL NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE TABLE IF NOT EXISTS run_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node_id TEXT,
    event_type TEXT NOT NULL,
    sequence INTEGER,
    timestamp REAL NOT NULL,
    payload TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_run_nodes_run_id ON run_nodes(run_id);
CREATE INDEX IF NOT EXISTS idx_run_events_run_id_order
    ON run_events(run_id, COALESCE(sequence, 9223372036854775807), timestamp, event_id);
CREATE INDEX IF NOT EXISTS idx_run_events_type ON run_events(event_type);
"""


class RunEventStore:
    """Small SQLite store for append-only RunGraph evidence.

    This is intentionally separate from ``SessionDB`` for the first P0 slice:
    message transcripts remain unchanged while run lifecycle events can be
    replayed and projected by Agent Board / CEO ledger consumers.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else get_hermes_home() / "run_events.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "RunEventStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def append_run(self, run: RunRecord) -> None:
        payload = run.to_dict()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO runs (run_id, payload, started_at)
            VALUES (?, ?, ?)
            """,
            (run.run_id, json.dumps(payload, ensure_ascii=False), run.started_at),
        )

    def append_node(self, node: RunNodeRecord) -> None:
        payload = node.to_dict()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO run_nodes (node_id, run_id, payload, started_at)
            VALUES (?, ?, ?, ?)
            """,
            (node.node_id, node.run_id, json.dumps(payload, ensure_ascii=False), node.started_at),
        )

    def append_event(self, event: RunEventRecord) -> None:
        payload = event.to_dict()
        self._conn.execute(
            """
            INSERT OR REPLACE INTO run_events
                (event_id, run_id, node_id, event_type, sequence, timestamp, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.run_id,
                event.node_id,
                event.event_type.value,
                event.sequence,
                event.timestamp,
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def append_graph(self, run: RunRecord, nodes: Iterable[RunNodeRecord], events: Iterable[RunEventRecord]) -> None:
        self.append_run(run)
        for node in nodes:
            self.append_node(node)
        for event in events:
            self.append_event(event)

    def get_run(self, run_id: str) -> RunRecord | None:
        row = self._conn.execute("SELECT payload FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            return None
        return RunRecord.from_dict(json.loads(row["payload"]))

    def list_nodes(self, run_id: str) -> list[RunNodeRecord]:
        rows = self._conn.execute(
            "SELECT payload FROM run_nodes WHERE run_id = ? ORDER BY started_at, node_id",
            (run_id,),
        ).fetchall()
        return [RunNodeRecord.from_dict(json.loads(row["payload"])) for row in rows]

    def list_events(self, run_id: str) -> list[RunEventRecord]:
        rows = self._conn.execute(
            """
            SELECT payload FROM run_events
            WHERE run_id = ?
            ORDER BY COALESCE(sequence, 9223372036854775807), timestamp, event_id
            """,
            (run_id,),
        ).fetchall()
        return [RunEventRecord.from_dict(json.loads(row["payload"])) for row in rows]
