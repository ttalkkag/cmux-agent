"""메시지 브로커 — artifact를 파싱하고 수신자 inbox에 전달한다."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from cmux_agent.application.prompting import PromptBuilder
from cmux_agent.domain.events import (
    artifact_created,
    artifact_detected,
    artifact_validation_failed,
    message_delivered,
    message_failed,
    task_created,
    task_state_changed,
)
from cmux_agent.domain.models import (
    Artifact,
    Message,
    MessageStatus,
    MessageType,
    Part,
    Task,
    TaskState,
)
from cmux_agent.infrastructure.cmux import CmuxAdapter
from cmux_agent.infrastructure.event_log import EventLog
from cmux_agent.infrastructure.filesystem import AgentFileSystem
from cmux_agent.infrastructure.storage import StateStore

logger = logging.getLogger(__name__)

MAX_RETRIES = 3


class MessageBroker:
    """artifact를 수신하여 라우팅하고 inbox에 전달하는 메시지 브로커."""

    def __init__(
        self,
        store: StateStore,
        event_log: EventLog,
        fs: AgentFileSystem,
        cmux: CmuxAdapter,
        prompt_builder: PromptBuilder,
        run_id: str,
        workspace_id: str | None = None,
    ) -> None:
        self._store = store
        self._event_log = event_log
        self._fs = fs
        self._cmux = cmux
        self._prompt = prompt_builder
        self._run_id = run_id
        self._workspace_id = workspace_id

    # -- ArtifactConsumer 프로토콜 구현 ------------------------------------

    def handle_artifact(self, artifact_path: Path, data: dict) -> None:
        """watcher가 감지한 artifact를 처리한다."""
        # 검증 실패 artifact 처리
        if "_error" in data:
            self._event_log.append(
                artifact_validation_failed(self._run_id, str(artifact_path), data["_error"])
            )
            self._fs.move_to_failed(artifact_path)
            return

        sender = data["sender"]
        recipient = data["recipient"]
        msg_type_str = data["type"]

        if msg_type_str == "dispatch":
            print(f"  → 라우팅: {sender} → {recipient} (dispatch)", flush=True)
        else:
            print(f"  → 라우팅: {recipient} ← {sender} (result)", flush=True)

        self._event_log.append(
            artifact_detected(self._run_id, str(artifact_path), sender)
        )

        # sender 확인
        if not self._store.get_agent_by_name(self._run_id, sender):
            logger.warning("미등록 송신자: %s", sender)
            self._event_log.append(
                artifact_validation_failed(
                    self._run_id, str(artifact_path), f"미등록 sender: {sender}"
                )
            )
            self._fs.move_to_failed(artifact_path)
            return

        # recipient 확인
        recipient_agent = self._store.get_agent_by_name(self._run_id, recipient)
        if not recipient_agent:
            logger.warning("미등록 수신자: %s", recipient)
            self._event_log.append(
                artifact_validation_failed(
                    self._run_id, str(artifact_path), f"미등록 recipient: {recipient}"
                )
            )
            self._fs.move_to_failed(artifact_path)
            return

        # recipient surface 생존 확인
        if recipient_agent.surface_id and not self._cmux.is_surface_alive(recipient_agent.surface_id):
            print(f"  ✗ 비활성 수신자: {recipient} (탭 닫힘)", flush=True)
            self._event_log.append(
                artifact_validation_failed(
                    self._run_id, str(artifact_path), f"비활성 recipient: {recipient}"
                )
            )
            self._fs.move_to_failed(artifact_path)
            return

        self._route_message(
            sender=sender,
            recipient=recipient,
            msg_type=MessageType(msg_type_str.upper()),
            payload=data,
            artifact_path=artifact_path,
        )

    # -- 내부 라우팅 --------------------------------------------------------

    def _route_message(
        self,
        *,
        sender: str,
        recipient: str,
        msg_type: MessageType,
        payload: dict,
        artifact_path: Path,
    ) -> None:
        # Task 생성/조회 및 Message correlation (실패해도 라우팅은 계속)
        try:
            task = self._resolve_task(sender, recipient, msg_type, payload)
        except Exception:
            logger.exception(
                "Task 처리 실패 (메시지 라우팅은 계속됨): sender=%s, recipient=%s",
                sender, recipient,
            )
            task = None
        task_id = payload.get("task_id")
        context_id = payload.get("context_id")
        if task:
            task_id = task.task_id
            context_id = task.context_id

        msg = Message(
            run_id=self._run_id,
            sender=sender,
            recipient=recipient,
            type=msg_type,
            payload=json.dumps(payload, ensure_ascii=False),
            artifact_path=str(artifact_path),
            task_id=task_id,
            context_id=context_id,
        )
        self._store.save_message(msg)

        # Task에 message 기록
        if task:
            task.add_message(msg.message_id)
            self._store.save_task(task)

        # delivery 메시지 구성
        delivery = self._prompt.build_delivery(
            sender=sender,
            recipient=recipient,
            msg_type=msg_type,
            payload=payload,
            message_id=msg.message_id,
            task_id=task_id,
            context_id=context_id,
        )

        # inbox에 전달 (재시도 포함)
        delivered = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                self._fs.write_to_inbox(recipient, msg.message_id, delivery)
                delivered = True
                break
            except OSError:
                logger.warning(
                    "inbox 전달 실패 (시도 %d/%d): %s", attempt, MAX_RETRIES, recipient
                )

        if delivered:
            msg.mark_delivered()
            self._store.save_message(msg)
            self._event_log.append(
                message_delivered(self._run_id, msg.message_id, recipient)
            )
            if msg_type == MessageType.DISPATCH:
                print(f"  ✓ 전달 완료: {sender} → {recipient}", flush=True)
            else:
                print(f"  ✓ 전달 완료: {recipient} ← {sender}", flush=True)
            self._inject_and_notify(recipient, sender, msg_type, payload)
        else:
            msg.mark_failed()
            self._store.save_message(msg)
            self._event_log.append(
                message_failed(self._run_id, msg.message_id, "inbox 전달 실패")
            )
            if msg_type == MessageType.DISPATCH:
                print(f"  ✗ 전달 실패: {sender} → {recipient}", flush=True)
            else:
                print(f"  ✗ 전달 실패: {recipient} ← {sender}", flush=True)

        # 처리 완료된 artifact 이동
        try:
            self._fs.move_to_processed(artifact_path)
        except OSError:
            logger.warning("artifact 이동 실패: %s", artifact_path)

    def _inject_and_notify(
        self,
        recipient: str,
        sender: str,
        msg_type: MessageType,
        payload: dict,
    ) -> None:
        """AI CLI 터미널에 메시지를 자동 주입하고 cmux 알림을 보낸다."""
        agent = self._store.get_agent_by_name(self._run_id, recipient)
        if not agent:
            return

        label = "작업 위임" if msg_type == MessageType.DISPATCH else "결과 반환"
        summary = f"[{sender}] → [{recipient}] {label}"

        # AI CLI 터미널에 주입 프롬프트 전달
        if agent.surface_id:
            injection = self._prompt.build_injection_prompt(
                sender=sender,
                recipient=recipient,
                msg_type=msg_type,
                payload=payload,
            )
            self._cmux.send_text(
                injection,
                surface_id=agent.surface_id,
                workspace_id=self._workspace_id,
            )
            self._cmux.send_key(
                "enter",
                surface_id=agent.surface_id,
                workspace_id=self._workspace_id,
            )
            self._cmux.trigger_flash(surface_id=agent.surface_id)

        self._cmux.notify(title="cmux-agent", body=summary)
        self._cmux.log(summary, level="info", source="cmux-agent")

    # -- Task 관리 ----------------------------------------------------------

    def _resolve_task(
        self,
        sender: str,
        recipient: str,
        msg_type: MessageType,
        payload: dict,
    ) -> Task | None:
        """dispatch → Task 생성(WORKING), result → 기존 Task 완료 + Artifact 생성."""
        if msg_type == MessageType.DISPATCH:
            context_id = payload.get("context_id") or str(uuid.uuid4())
            task = Task(run_id=self._run_id, context_id=context_id)
            task.transition_to(TaskState.WORKING)
            # save는 _route_message에서 add_message 후 한 번만 수행
            self._event_log.append(
                task_created(self._run_id, task.task_id, task.context_id)
            )
            return task

        if msg_type == MessageType.RESULT:
            task_id = payload.get("task_id")

            if not task_id:
                logger.debug("result에 task_id 없음 (legacy): sender=%s", sender)
                return None

            task = self._store.get_task(task_id)

            if task is None:
                logger.warning(
                    "result의 task_id가 DB에 없음: task_id=%s, sender=%s",
                    task_id, sender,
                )
                return None

            if task.state != TaskState.WORKING:
                logger.warning(
                    "result 수신했으나 task 상태가 WORKING이 아님: "
                    "task_id=%s, state=%s, sender=%s",
                    task_id, task.state.value, sender,
                )
                return task

            old_state = task.state.value
            task.transition_to(TaskState.COMPLETED)
            self._store.save_task(task)
            self._event_log.append(
                task_state_changed(
                    self._run_id, task.task_id, old_state, task.state.value
                )
            )
            message_text = payload.get("message", "")
            art = Artifact(
                task_id=task.task_id,
                parts=[Part(kind="text", text=message_text)],
            )
            self._store.save_artifact(art)
            self._event_log.append(
                artifact_created(self._run_id, task.task_id, art.artifact_id)
            )
            return task

        return None
