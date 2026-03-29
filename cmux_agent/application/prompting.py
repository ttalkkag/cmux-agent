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
    """delivery 메시지, 주입 프롬프트, 프로토콜 파일을 생성한다."""

    def __init__(self, outbox_path: str, inbox_base: str) -> None:
        self._outbox = outbox_path
        self._inbox_base = inbox_base

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

    # -- 터미널 주입 프롬프트 (send_text용 자연어) ---------------------------

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
            return (
                f"[cmux-agent] {sender}로부터 작업이 도착했습니다.\n"
                f"\n"
                f"작업: {message}\n"
                f"\n"
                f"위 작업을 수행하세요.\n"
                f"완료 후 {self._outbox} 에 아래 형식의 JSON 파일을 생성하세요.\n"
                f'{{"type": "result", "sender": "{recipient}", '
                f'"recipient": "{sender}", "message": "<작업 결과 요약>"}}'
            )

        return (
            f"[cmux-agent] {sender}의 작업 결과입니다.\n"
            f"\n"
            f"결과: {message}\n"
            f"\n"
            f"추가 작업이 필요하면 {self._outbox} 에 dispatch artifact를 생성하세요.\n"
            f"모든 작업이 완료되었으면 최종 결과를 보고하세요."
        )

    # -- 초기 프롬프트 -------------------------------------------------------

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

    # -- 프로토콜 파일 생성 --------------------------------------------------

    def write_protocol_files(self, base_dir: str | Path, workers: list[Agent]) -> None:
        """AI CLI가 읽을 프로토콜 파일을 .agent/ 에 생성한다."""
        base = Path(base_dir)

        worker_names = [w.name for w in workers if w.role == AgentRole.WORKER]
        worker_list_str = "\n".join(f"- {n}" for n in worker_names)

        orch_content = (
            "# cmux-agent orchestrator 프로토콜\n"
            "\n"
            "당신은 orchestrator입니다.\n"
            "\n"
            "## 역할\n"
            "- 사용자의 요청을 분석하고 작업을 분해한다.\n"
            "- worker에게 작업을 위임한다.\n"
            "- 직접 파일을 수정하거나 명령을 실행하지 않는다.\n"
            "\n"
            "## 작업 위임 방법\n"
            f"{self._outbox} 디렉토리에 아래 형식의 JSON 파일을 생성한다.\n"
            "\n"
            "```json\n"
            + json.dumps(ARTIFACT_FORMAT_DISPATCH, ensure_ascii=False, indent=2)
            + "\n```\n"
            "\n"
            "## 사용 가능한 worker\n"
            f"{worker_list_str}\n"
            "\n"
            "## 결과 수신\n"
            "worker의 결과는 이 터미널에 자동으로 전달된다.\n"
            "추가 작업이 필요하면 새로운 dispatch를 생성한다.\n"
            "모든 작업이 완료되면 사용자에게 최종 결과를 보고한다.\n"
        )
        (base / "ORCHESTRATOR.md").write_text(orch_content, encoding="utf-8")

        for name in worker_names:
            fmt = {**ARTIFACT_FORMAT_RESULT, "sender": name}
            worker_content = (
                f"# cmux-agent {name} 프로토콜\n"
                f"\n"
                f"당신은 {name} worker입니다.\n"
                f"\n"
                f"## 역할\n"
                f"- orchestrator가 위임한 작업을 수행한다.\n"
                f"- 작업 완료 후 결과를 보고한다.\n"
                f"\n"
                f"## 작업 수신\n"
                f"이 터미널에 작업 지시가 자동으로 전달된다.\n"
                f"\n"
                f"## 결과 보고 방법\n"
                f"{self._outbox} 디렉토리에 아래 형식의 JSON 파일을 생성한다.\n"
                f"\n"
                f"```json\n"
                + json.dumps(fmt, ensure_ascii=False, indent=2)
                + "\n```\n"
            )
            (base / f"{name.upper()}.md").write_text(worker_content, encoding="utf-8")
