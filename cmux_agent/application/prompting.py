"""역할별 prompt / delivery 메시지 생성."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
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
    """delivery 메시지, 주입 프롬프트를 생성한다."""

    def __init__(
        self,
        outbox_path: str,
        inbox_base: str,
        prompts_dir: str | None = None,
    ) -> None:
        self._outbox = outbox_path
        self._inbox_base = inbox_base
        self._prompts_dir = Path(prompts_dir) if prompts_dir else None

    # -- 프롬프트 파일 읽기 ----------------------------------------------------

    def read_prompt(self, filename: str) -> str | None:
        """prompts 디렉토리에서 프롬프트 파일을 읽는다. 없으면 None."""
        if not self._prompts_dir:
            return None
        path = self._prompts_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None

    # -- Inbox delivery (JSON 파일) ----------------------------------------

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
            "message_id": None,
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

    # -- 터미널 주입 프롬프트 (send_text용) ------------------------------------

    def build_injection_prompt(
        self,
        *,
        sender: str,
        recipient: str,
        msg_type: MessageType,
        payload: dict,
    ) -> str:
        message = payload.get("message", "")

        if msg_type == MessageType.DISPATCH:
            worker_prompt = (
                self.read_prompt(f"{recipient}.md")
                or self.read_prompt("worker.md")
            )
            if not worker_prompt:
                raise FileNotFoundError(
                    f"프롬프트 파일이 없습니다: "
                    f"{recipient}.md 또는 worker.md"
                )
            dispatch_prompt = self.read_prompt("dispatch.md") or ""
            parts = [worker_prompt, "---"]
            if dispatch_prompt:
                parts.append(dispatch_prompt.format(
                    sender=sender, recipient=recipient, message=message,
                ))
            return "\n\n".join(parts)

        result_prompt = self.read_prompt("result.md")
        if not result_prompt:
            raise FileNotFoundError("프롬프트 파일이 없습니다: result.md")
        return result_prompt.format(
            sender=sender, recipient=recipient, message=message,
        )
