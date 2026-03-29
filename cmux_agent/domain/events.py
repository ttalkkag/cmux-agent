"""도메인 이벤트 정의."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class DomainEvent:
    event: str
    run_id: str
    data: dict[str, Any] = field(default_factory=dict)
    ts: datetime = field(default_factory=_now)


# Run 이벤트
def run_created(run_id: str, workspace_id: str | None = None) -> DomainEvent:
    return DomainEvent("run.created", run_id, {"workspace_id": workspace_id})


def run_status_changed(run_id: str, old: str, new: str) -> DomainEvent:
    return DomainEvent("run.status_changed", run_id, {"old": old, "new": new})


# Agent 이벤트
def agent_registered(run_id: str, name: str, role: str) -> DomainEvent:
    return DomainEvent("agent.registered", run_id, {"name": name, "role": role})


# Artifact / Message 이벤트
def artifact_detected(run_id: str, path: str, sender: str) -> DomainEvent:
    return DomainEvent("artifact.detected", run_id, {"path": path, "sender": sender})


def artifact_validation_failed(run_id: str, path: str, reason: str) -> DomainEvent:
    return DomainEvent(
        "artifact.validation_failed", run_id, {"path": path, "reason": reason}
    )


def message_delivered(
    run_id: str, message_id: str, recipient: str,
) -> DomainEvent:
    return DomainEvent(
        "message.delivered", run_id, {"message_id": message_id, "recipient": recipient}
    )


def message_failed(
    run_id: str, message_id: str, reason: str,
) -> DomainEvent:
    return DomainEvent(
        "message.failed", run_id, {"message_id": message_id, "reason": reason}
    )
