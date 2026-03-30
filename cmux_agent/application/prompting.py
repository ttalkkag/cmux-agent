"""역할별 prompt / delivery 메시지 생성."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from string import Template
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

_TEMPLATE_FILENAMES = ("orchestrator.md", "worker.md", "dispatch.md", "result.md")


class PromptBuilder:
    """delivery 메시지, 주입 프롬프트, 프로토콜 파일을 생성한다."""

    def __init__(
        self,
        outbox_path: str,
        inbox_base: str,
        prompts_dir: str | None = None,
    ) -> None:
        self._outbox = outbox_path
        self._inbox_base = inbox_base
        self._prompts_dir = Path(prompts_dir) if prompts_dir else None

    # -- 템플릿 관리 -----------------------------------------------------------

    def check_prompts(self) -> list[str]:
        """prompts 디렉토리의 템플릿 파일 존재 여부를 확인한다. 누락 파일명 목록 반환."""
        if not self._prompts_dir:
            return list(_TEMPLATE_FILENAMES)
        return [n for n in _TEMPLATE_FILENAMES if not (self._prompts_dir / n).exists()]

    def _load_template(self, filename: str) -> str:
        """prompts 디렉토리에서 템플릿을 읽는다."""
        if not self._prompts_dir:
            raise FileNotFoundError(f"prompts_dir이 설정되지 않았습니다: {filename}")
        path = self._prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(
                f"프롬프트 템플릿을 찾을 수 없습니다: {path}\n"
                f"'.cmux/prompts/' 디렉토리에 템플릿 파일을 생성하세요."
            )
        return path.read_text(encoding="utf-8")

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
            tmpl = self._load_template("dispatch.md")
            return Template(tmpl).safe_substitute(
                sender=sender,
                recipient=recipient,
                message=message,
                outbox=self._outbox,
            )

        tmpl = self._load_template("result.md")
        return Template(tmpl).safe_substitute(
            sender=sender,
            recipient=recipient,
            message=message,
            outbox=self._outbox,
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
        """프롬프트 템플릿을 렌더링하여 프로토콜 파일을 .cmux/ 에 생성한다."""
        base = Path(base_dir)

        worker_names = [w.name for w in workers if w.role == AgentRole.WORKER]
        worker_list_str = "\n".join(f"- {n}" for n in worker_names)

        # orchestrator 프로토콜
        orch_tmpl = self._load_template("orchestrator.md")
        orch_content = Template(orch_tmpl).safe_substitute(
            outbox=self._outbox,
            worker_list=worker_list_str,
            artifact_format=json.dumps(
                ARTIFACT_FORMAT_DISPATCH, ensure_ascii=False, indent=2,
            ),
        )
        (base / "ORCHESTRATOR.md").write_text(orch_content, encoding="utf-8")

        # worker 프로토콜
        worker_tmpl = self._load_template("worker.md")
        for name in worker_names:
            fmt = {**ARTIFACT_FORMAT_RESULT, "sender": name}
            worker_content = Template(worker_tmpl).safe_substitute(
                outbox=self._outbox,
                worker_name=name,
                artifact_format=json.dumps(fmt, ensure_ascii=False, indent=2),
            )
            (base / f"{name.upper()}.md").write_text(worker_content, encoding="utf-8")
