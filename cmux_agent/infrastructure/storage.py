"""SQLite 기반 상태 저장소 (Repository)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cmux_agent.domain.models import (
    Agent,
    AgentRole,
    Artifact,
    Message,
    MessageStatus,
    MessageType,
    Part,
    Run,
    RunStatus,
    Task,
    TaskState,
)

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS runs (
    run_id      TEXT PRIMARY KEY,
    status      TEXT NOT NULL DEFAULT 'CREATED',
    workspace_id TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agents (
    agent_id    TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES runs(run_id),
    role        TEXT NOT NULL,
    name        TEXT NOT NULL,
    surface_id  TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
    task_id     TEXT PRIMARY KEY,
    context_id  TEXT NOT NULL,
    run_id      TEXT NOT NULL REFERENCES runs(run_id),
    state       TEXT NOT NULL DEFAULT 'SUBMITTED',
    history_message_ids TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artifacts (
    artifact_id TEXT PRIMARY KEY,
    task_id     TEXT NOT NULL REFERENCES tasks(task_id),
    parts       TEXT NOT NULL DEFAULT '[]',
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    message_id    TEXT PRIMARY KEY,
    run_id        TEXT NOT NULL REFERENCES runs(run_id),
    sender        TEXT NOT NULL,
    recipient     TEXT NOT NULL,
    type          TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'PENDING',
    payload       TEXT NOT NULL,
    artifact_path TEXT,
    task_id       TEXT,
    context_id    TEXT,
    created_at    TEXT NOT NULL,
    delivered_at  TEXT
);
"""


def _ts(dt: datetime) -> str:
    return dt.isoformat()


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


class StateStore:
    """SQLite 기반 상태 저장소."""

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._migrate_schema()
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _migrate_schema(self) -> None:
        self._ensure_column("messages", "task_id", "TEXT")
        self._ensure_column("messages", "context_id", "TEXT")

    def _ensure_column(self, table: str, column: str, ddl: str) -> None:
        cols = {
            row["name"]
            for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in cols:
            self._conn.execute(
                f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
            )

    # -- Run ----------------------------------------------------------------

    def save_run(self, run: Run) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO runs (run_id, status, workspace_id, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (run.run_id, run.status.value, run.workspace_id,
             _ts(run.created_at), _ts(run.updated_at)),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> Run | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,),
        ).fetchone()
        return self._row_to_run(row) if row else None

    def get_latest_run(self) -> Run | None:
        row = self._conn.execute(
            "SELECT * FROM runs ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        return self._row_to_run(row) if row else None

    def get_active_run(self) -> Run | None:
        row = self._conn.execute(
            "SELECT * FROM runs WHERE status IN ('CREATED', 'RUNNING')"
            " ORDER BY created_at DESC LIMIT 1",
        ).fetchone()
        return self._row_to_run(row) if row else None

    def update_run_status(self, run_id: str, status: RunStatus) -> None:
        self._conn.execute(
            "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
            (status.value, _ts(datetime.now(UTC)), run_id),
        )
        self._conn.commit()

    @staticmethod
    def _row_to_run(row: sqlite3.Row) -> Run:
        return Run(
            run_id=row["run_id"],
            status=RunStatus(row["status"]),
            workspace_id=row["workspace_id"],
            created_at=_parse_ts(row["created_at"]),
            updated_at=_parse_ts(row["updated_at"]),
        )

    # -- Agent --------------------------------------------------------------

    def save_agent(self, agent: Agent) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO agents"
            " (agent_id, run_id, role, name, surface_id, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (agent.agent_id, agent.run_id, agent.role.value, agent.name,
             agent.surface_id, _ts(agent.created_at)),
        )
        self._conn.commit()

    def get_agents(self, run_id: str) -> list[Agent]:
        rows = self._conn.execute(
            "SELECT * FROM agents WHERE run_id = ? ORDER BY created_at", (run_id,),
        ).fetchall()
        return [self._row_to_agent(r) for r in rows]

    def get_agent_by_name(self, run_id: str, name: str) -> Agent | None:
        row = self._conn.execute(
            "SELECT * FROM agents WHERE run_id = ? AND name = ?", (run_id, name),
        ).fetchone()
        return self._row_to_agent(row) if row else None

    @staticmethod
    def _row_to_agent(row: sqlite3.Row) -> Agent:
        return Agent(
            agent_id=row["agent_id"],
            run_id=row["run_id"],
            role=AgentRole(row["role"]),
            name=row["name"],
            surface_id=row["surface_id"],
            created_at=_parse_ts(row["created_at"]),
        )

    # -- Message ------------------------------------------------------------

    def save_message(self, msg: Message) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO messages"
            " (message_id, run_id, sender, recipient, type, status,"
            "  payload, artifact_path, task_id, context_id, created_at, delivered_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (msg.message_id, msg.run_id, msg.sender, msg.recipient,
             msg.type.value, msg.status.value, msg.payload, msg.artifact_path,
             msg.task_id, msg.context_id,
             _ts(msg.created_at),
             _ts(msg.delivered_at) if msg.delivered_at else None),
        )
        self._conn.commit()

    def get_messages(self, run_id: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE run_id = ? ORDER BY created_at", (run_id,),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def get_pending_messages(self, run_id: str, recipient: str) -> list[Message]:
        rows = self._conn.execute(
            "SELECT * FROM messages WHERE run_id = ? AND recipient = ? AND status = 'PENDING'"
            " ORDER BY created_at",
            (run_id, recipient),
        ).fetchall()
        return [self._row_to_message(r) for r in rows]

    def count_messages(self, run_id: str) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) as cnt FROM messages WHERE run_id = ? GROUP BY status",
            (run_id,),
        ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        return Message(
            message_id=row["message_id"],
            run_id=row["run_id"],
            sender=row["sender"],
            recipient=row["recipient"],
            type=MessageType(row["type"]),
            status=MessageStatus(row["status"]),
            payload=row["payload"],
            artifact_path=row["artifact_path"],
            task_id=row["task_id"],
            context_id=row["context_id"],
            created_at=_parse_ts(row["created_at"]),
            delivered_at=_parse_ts(row["delivered_at"]) if row["delivered_at"] else None,
        )

    # -- Task ---------------------------------------------------------------

    def save_task(self, task: Task) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tasks"
            " (task_id, context_id, run_id, state, history_message_ids,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task.task_id, task.context_id, task.run_id, task.state.value,
             json.dumps(task.history_message_ids),
             _ts(task.created_at), _ts(task.updated_at)),
        )
        self._conn.commit()

    def get_task(self, task_id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,),
        ).fetchone()
        return self._row_to_task(row) if row else None

    def get_tasks(self, run_id: str) -> list[Task]:
        rows = self._conn.execute(
            "SELECT * FROM tasks WHERE run_id = ? ORDER BY created_at", (run_id,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_active_task(self, run_id: str, context_id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE run_id = ? AND context_id = ?"
            " AND state IN ('SUBMITTED', 'WORKING')"
            " ORDER BY created_at DESC LIMIT 1",
            (run_id, context_id),
        ).fetchone()
        return self._row_to_task(row) if row else None

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        return Task(
            task_id=row["task_id"],
            context_id=row["context_id"],
            run_id=row["run_id"],
            state=TaskState(row["state"]),
            history_message_ids=json.loads(row["history_message_ids"]),
            created_at=_parse_ts(row["created_at"]),
            updated_at=_parse_ts(row["updated_at"]),
        )

    # -- Artifact -----------------------------------------------------------

    def save_artifact(self, artifact: Artifact) -> None:
        parts_json = json.dumps(
            [{"kind": p.kind, "text": p.text, "data": p.data, "media_type": p.media_type}
             for p in artifact.parts]
        )
        self._conn.execute(
            "INSERT OR REPLACE INTO artifacts"
            " (artifact_id, task_id, parts, created_at)"
            " VALUES (?, ?, ?, ?)",
            (artifact.artifact_id, artifact.task_id, parts_json,
             _ts(artifact.created_at)),
        )
        self._conn.commit()

    def get_artifacts(self, task_id: str) -> list[Artifact]:
        rows = self._conn.execute(
            "SELECT * FROM artifacts WHERE task_id = ? ORDER BY created_at",
            (task_id,),
        ).fetchall()
        return [self._row_to_artifact(r) for r in rows]

    @staticmethod
    def _row_to_artifact(row: sqlite3.Row) -> Artifact:
        parts_data = json.loads(row["parts"])
        parts = [
            Part(
                kind=p.get("kind", "text"),
                text=p.get("text"),
                data=p.get("data"),
                media_type=p.get("media_type", "text/plain"),
            )
            for p in parts_data
        ]
        return Artifact(
            artifact_id=row["artifact_id"],
            task_id=row["task_id"],
            parts=parts,
            created_at=_parse_ts(row["created_at"]),
        )
