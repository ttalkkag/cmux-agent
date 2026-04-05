"""도메인 엔티티와 값 객체."""

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


# ---------------------------------------------------------------------------
# Value Objects (열거형)
# ---------------------------------------------------------------------------

class RunStatus(str, enum.Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AgentRole(str, enum.Enum):
    CONTROLLER = "CONTROLLER"
    ORCHESTRATOR = "ORCHESTRATOR"
    WORKER = "WORKER"


class MessageType(str, enum.Enum):
    DISPATCH = "DISPATCH"
    RESULT = "RESULT"


class MessageStatus(str, enum.Enum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"


class TaskState(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


@dataclass
class Run:
    run_id: str = field(default_factory=_uuid)
    status: RunStatus = RunStatus.CREATED
    workspace_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    _TRANSITIONS: dict[RunStatus, set[RunStatus]] = field(
        init=False,
        repr=False,
        default_factory=lambda: {
            RunStatus.CREATED: {RunStatus.RUNNING},
            RunStatus.RUNNING: {RunStatus.COMPLETED, RunStatus.FAILED},
        },
    )

    def transition_to(self, new_status: RunStatus) -> None:
        allowed = self._TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            msg = f"{self.status.value} → {new_status.value} 전이 불가"
            raise ValueError(msg)
        self.status = new_status
        self.updated_at = _now()


@dataclass
class Agent:
    agent_id: str = field(default_factory=_uuid)
    run_id: str = ""
    role: AgentRole = AgentRole.WORKER
    name: str = ""
    surface_id: str | None = None
    created_at: datetime = field(default_factory=_now)


@dataclass
class Message:
    message_id: str = field(default_factory=_uuid)
    run_id: str = ""
    sender: str = ""
    recipient: str = ""
    type: MessageType = MessageType.DISPATCH
    status: MessageStatus = MessageStatus.PENDING
    payload: str = ""
    artifact_path: str | None = None
    task_id: str | None = None
    context_id: str | None = None
    created_at: datetime = field(default_factory=_now)
    delivered_at: datetime | None = None

    def mark_delivered(self) -> None:
        self.status = MessageStatus.DELIVERED
        self.delivered_at = _now()

    def mark_failed(self) -> None:
        self.status = MessageStatus.FAILED


@dataclass
class Part:
    kind: str = "text"
    text: str | None = None
    data: dict | None = None
    media_type: str = "text/plain"


@dataclass
class Artifact:
    artifact_id: str = field(default_factory=_uuid)
    task_id: str = ""
    parts: list[Part] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)


@dataclass
class Task:
    task_id: str = field(default_factory=_uuid)
    context_id: str = field(default_factory=_uuid)
    run_id: str = ""
    state: TaskState = TaskState.SUBMITTED
    history_message_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    _TRANSITIONS: dict[TaskState, set[TaskState]] = field(
        init=False,
        repr=False,
        default_factory=lambda: {
            TaskState.SUBMITTED: {TaskState.WORKING, TaskState.FAILED},
            TaskState.WORKING: {TaskState.COMPLETED, TaskState.FAILED},
        },
    )

    def transition_to(self, new_state: TaskState) -> None:
        allowed = self._TRANSITIONS.get(self.state, set())
        if new_state not in allowed:
            msg = f"Task {self.state.value} → {new_state.value} 전이 불가"
            raise ValueError(msg)
        self.state = new_state
        self.updated_at = _now()

    def add_message(self, message_id: str) -> None:
        self.history_message_ids.append(message_id)
