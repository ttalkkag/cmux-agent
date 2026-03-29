"""역할별 prompt / delivery 메시지 생성."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from cmux_agent.domain.models import AgentRole, MessageType

if TYPE_CHECKING:
    from cmux_agent.domain.models import Agent


ARTIFACT_FORMAT_DISPATCH = {
    "type": "dispatch",
    "sender": "orchestrator",
    "recipient": "<worker-name>",
    "message": "<구체적 작업 지시>",
}

ARTIFACT_FORMAT_RESULT = {
    "type": "result",
    "sender": "<worker-name>",
    "recipient": "orchestrator",
    "message": "<작업 결과 요약>",
}


class PromptBuilder:
    """delivery 메시지와 초기 prompt를 생성한다."""

    def __init__(self, outbox_path: str, inbox_base: str) -> None:
        self._outbox = outbox_path
        self._inbox_base = inbox_base

    def build_delivery(
        self,
        *,
        sender: str,
        recipient: str,
        msg_type: MessageType,
        payload: dict,
    ) -> dict:
        now = datetime.now(UTC).isoformat()

        if msg_type == MessageType.DISPATCH:
            return self._dispatch_delivery(sender, recipient, payload, now)
        return self._result_delivery(sender, recipient, payload, now)

    def _dispatch_delivery(
        self, sender: str, recipient: str, payload: dict, ts: str,
    ) -> dict:
        return {
            "message_id": None,  # broker가 채움
            "from": sender,
            "type": "dispatch",
            "task": payload.get("message", ""),
            "context": payload.get("context", {}),
            "instructions": (
                f"작업 완료 후 {self._outbox} 에 result artifact(JSON)를 생성하세요."
            ),
            "artifact_format": {
                "type": "result",
                "sender": recipient,
                "recipient": sender,
                "message": "<작업 결과 요약>",
            },
            "created_at": ts,
        }

    def _result_delivery(
        self, sender: str, recipient: str, payload: dict, ts: str,
    ) -> dict:
        return {
            "message_id": None,
            "from": sender,
            "type": "result",
            "result": payload.get("message", ""),
            "context": payload.get("context", {}),
            "instructions": (
                f"추가 작업이 필요하면 {self._outbox} 에 dispatch artifact를 생성하세요."
            ),
            "artifact_format": {
                "type": "dispatch",
                "sender": recipient,
                "recipient": "<worker-name>",
                "message": "<작업 지시>",
            },
            "created_at": ts,
        }

    def build_initial_orchestrator(self, workers: list[Agent]) -> dict:
        worker_list = [
            {"name": w.name, "role": w.role.value}
            for w in workers
            if w.role == AgentRole.WORKER
        ]
        return {
            "role": "orchestrator",
            "instructions": (
                "당신은 orchestrator입니다.\n"
                "분석, 계획, 작업 분해만 수행하세요.\n"
                "직접 파일을 수정하거나 명령을 실행하지 마세요.\n"
                f"worker에게 작업을 위임하려면 {self._outbox} 에 "
                "dispatch artifact(JSON)를 생성하세요."
            ),
            "workers": worker_list,
            "outbox_path": self._outbox,
            "inbox_path": f"{self._inbox_base}/orchestrator",
            "artifact_format": ARTIFACT_FORMAT_DISPATCH,
        }

    def build_initial_worker(self, name: str) -> dict:
        return {
            "role": "worker",
            "name": name,
            "instructions": (
                f"당신은 {name} worker입니다.\n"
                "할당된 작업을 수행하세요.\n"
                f"inbox({self._inbox_base}/{name})에서 작업을 확인하세요.\n"
                f"작업 완료 후 {self._outbox} 에 result artifact(JSON)를 생성하세요."
            ),
            "inbox_path": f"{self._inbox_base}/{name}",
            "outbox_path": self._outbox,
            "artifact_format": ARTIFACT_FORMAT_RESULT,
        }
