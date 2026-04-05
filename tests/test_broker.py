"""MessageBroker 테스트."""

import json
from pathlib import Path

import pytest

from cmux_agent.application.broker import MessageBroker
from cmux_agent.application.prompting import PromptBuilder
from cmux_agent.domain.models import (
    Agent, AgentRole, Message, MessageStatus, Run, TaskState,
)
from cmux_agent.infrastructure.cmux import CmuxAdapter, CmuxResult
from cmux_agent.infrastructure.event_log import EventLog
from cmux_agent.infrastructure.filesystem import AgentFileSystem
from cmux_agent.infrastructure.storage import StateStore


class FakeCmux(CmuxAdapter):
    """cmux 호출을 기록만 하는 fake."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def _run(self, *args, timeout=10):
        self.calls.append(("_run", {"args": args}))
        return CmuxResult(ok=True, stdout="", stderr="")

    def is_surface_alive(self, surface_id: str) -> bool:
        return True


@pytest.fixture
def setup(tmp_path):
    fs = AgentFileSystem(tmp_path / ".cmux")
    fs.init()
    store = StateStore(fs.db_path)
    event_log = EventLog(fs.event_log_path)
    cmux = FakeCmux()

    run = Run(run_id="run-1")
    store.save_run(run)

    store.save_agent(Agent(
        run_id="run-1", role=AgentRole.ORCHESTRATOR,
        name="orchestrator", surface_id="s:1",
    ))
    store.save_agent(Agent(
        run_id="run-1", role=AgentRole.WORKER,
        name="worker-1", surface_id="s:2",
    ))
    store.save_agent(Agent(
        run_id="run-1", role=AgentRole.CONTROLLER,
        name="controller",
    ))

    prompts_dir = str(
        (Path(__file__).resolve().parent.parent / ".cmux" / "prompts")
    )
    prompt_builder = PromptBuilder(str(fs.outbox), str(fs.inbox), prompts_dir)
    broker = MessageBroker(
        store=store, event_log=event_log, fs=fs,
        cmux=cmux, prompt_builder=prompt_builder, run_id="run-1",
    )
    return broker, store, fs, event_log, cmux


class TestBrokerRouting:
    def test_dispatch_routes_to_worker(self, setup):
        broker, store, fs, *_ = setup

        artifact_path = fs.outbox / "test.json"
        artifact_path.write_text("{}")

        data = {
            "type": "dispatch",
            "sender": "orchestrator",
            "recipient": "worker-1",
            "message": "do stuff",
        }
        broker.handle_artifact(artifact_path, data)

        # inbox에 파일 생성 확인
        inbox_files = list((fs.inbox / "worker-1").iterdir())
        assert len(inbox_files) == 1

        # message 기록 확인
        messages = store.get_messages("run-1")
        assert len(messages) == 1
        assert messages[0].status == MessageStatus.DELIVERED

    def test_result_routes_to_orchestrator(self, setup):
        broker, store, fs, *_ = setup

        artifact_path = fs.outbox / "result.json"
        artifact_path.write_text("{}")

        data = {
            "type": "result",
            "sender": "worker-1",
            "recipient": "orchestrator",
            "message": "done",
        }
        broker.handle_artifact(artifact_path, data)

        inbox_files = list((fs.inbox / "orchestrator").iterdir())
        assert len(inbox_files) == 1

    def test_unknown_sender_moves_to_failed(self, setup):
        broker, _, fs, *_ = setup

        artifact_path = fs.outbox / "bad.json"
        artifact_path.write_text("{}")

        data = {
            "type": "dispatch",
            "sender": "unknown",
            "recipient": "worker-1",
            "message": "x",
        }
        broker.handle_artifact(artifact_path, data)

        assert list(fs.failed.iterdir())

    def test_unknown_recipient_moves_to_failed(self, setup):
        broker, _, fs, *_ = setup

        artifact_path = fs.outbox / "bad2.json"
        artifact_path.write_text("{}")

        data = {
            "type": "dispatch",
            "sender": "orchestrator",
            "recipient": "no-one",
            "message": "x",
        }
        broker.handle_artifact(artifact_path, data)

        assert list(fs.failed.iterdir())

    def test_validation_error_moves_to_failed(self, setup):
        broker, _, fs, *_ = setup

        artifact_path = fs.outbox / "err.json"
        artifact_path.write_text("{}")

        data = {"_error": "bad format", "type": "dispatch"}
        broker.handle_artifact(artifact_path, data)

        assert list(fs.failed.iterdir())


class TestBrokerTaskIntegration:
    def test_dispatch_creates_task(self, setup):
        broker, store, fs, *_ = setup

        artifact_path = fs.outbox / "test.json"
        artifact_path.write_text("{}")

        data = {
            "type": "dispatch",
            "sender": "orchestrator",
            "recipient": "worker-1",
            "message": "implement auth",
        }
        broker.handle_artifact(artifact_path, data)

        # task가 생성되었는지 확인
        tasks = store.get_tasks("run-1")
        assert len(tasks) == 1
        assert tasks[0].state == TaskState.WORKING

        # message에 task_id가 기록되었는지 확인
        messages = store.get_messages("run-1")
        assert messages[0].task_id == tasks[0].task_id
        assert messages[0].context_id == tasks[0].context_id

        # task에 message가 기록되었는지 확인
        task = store.get_task(tasks[0].task_id)
        assert messages[0].message_id in task.history_message_ids

    def test_result_with_task_id_completes_task(self, setup):
        broker, store, fs, *_ = setup

        # 먼저 dispatch로 task 생성
        artifact1 = fs.outbox / "dispatch.json"
        artifact1.write_text("{}")
        broker.handle_artifact(artifact1, {
            "type": "dispatch",
            "sender": "orchestrator",
            "recipient": "worker-1",
            "message": "do stuff",
        })

        tasks = store.get_tasks("run-1")
        task_id = tasks[0].task_id

        # result로 task 완료
        artifact2 = fs.outbox / "result.json"
        artifact2.write_text("{}")
        broker.handle_artifact(artifact2, {
            "type": "result",
            "sender": "worker-1",
            "recipient": "orchestrator",
            "message": "stuff done",
            "task_id": task_id,
        })

        # task 상태 확인
        task = store.get_task(task_id)
        assert task.state == TaskState.COMPLETED

        # artifact가 생성되었는지 확인
        artifacts = store.get_artifacts(task_id)
        assert len(artifacts) == 1
        assert artifacts[0].parts[0].text == "stuff done"

    def test_result_without_task_id_no_task_change(self, setup):
        broker, store, fs, *_ = setup

        artifact_path = fs.outbox / "result.json"
        artifact_path.write_text("{}")

        data = {
            "type": "result",
            "sender": "worker-1",
            "recipient": "orchestrator",
            "message": "done",
        }
        broker.handle_artifact(artifact_path, data)

        # task가 생성되지 않음
        tasks = store.get_tasks("run-1")
        assert len(tasks) == 0

        # message는 정상 기록
        messages = store.get_messages("run-1")
        assert len(messages) == 1
        assert messages[0].task_id is None

    def test_duplicate_result_does_not_fail(self, setup):
        """이미 COMPLETED된 task에 중복 result가 오면 task 변경 없이 메시지만 전달."""
        broker, store, fs, *_ = setup

        # dispatch로 task 생성
        a1 = fs.outbox / "d1.json"
        a1.write_text("{}")
        broker.handle_artifact(a1, {
            "type": "dispatch",
            "sender": "orchestrator",
            "recipient": "worker-1",
            "message": "do stuff",
        })
        task_id = store.get_tasks("run-1")[0].task_id

        # 첫 번째 result → 완료
        a2 = fs.outbox / "r1.json"
        a2.write_text("{}")
        broker.handle_artifact(a2, {
            "type": "result",
            "sender": "worker-1",
            "recipient": "orchestrator",
            "message": "done",
            "task_id": task_id,
        })
        assert store.get_task(task_id).state == TaskState.COMPLETED

        # 두 번째 (중복) result → task는 여전히 COMPLETED, 메시지는 전달됨
        a3 = fs.outbox / "r2.json"
        a3.write_text("{}")
        broker.handle_artifact(a3, {
            "type": "result",
            "sender": "worker-1",
            "recipient": "orchestrator",
            "message": "done again",
            "task_id": task_id,
        })
        task = store.get_task(task_id)
        assert task.state == TaskState.COMPLETED
        messages = store.get_messages("run-1")
        assert len(messages) == 3  # dispatch + 2 results
        assert messages[2].task_id == task_id
        assert messages[2].context_id == task.context_id

        delivery = json.loads(sorted((fs.inbox / "orchestrator").iterdir())[-1].read_text())
        assert delivery["task_id"] == task_id
        assert delivery["context_id"] == task.context_id

    def test_result_with_nonexistent_task_id(self, setup):
        """존재하지 않는 task_id로 result가 와도 correlation 정보는 보존한다."""
        broker, store, fs, *_ = setup

        artifact_path = fs.outbox / "result.json"
        artifact_path.write_text("{}")
        broker.handle_artifact(artifact_path, {
            "type": "result",
            "sender": "worker-1",
            "recipient": "orchestrator",
            "message": "done",
            "task_id": "nonexistent-task-id",
            "context_id": "ctx-missing",
        })

        tasks = store.get_tasks("run-1")
        assert len(tasks) == 0

        messages = store.get_messages("run-1")
        assert len(messages) == 1
        assert messages[0].task_id == "nonexistent-task-id"
        assert messages[0].context_id == "ctx-missing"
        assert messages[0].status == MessageStatus.DELIVERED

        delivery = json.loads(next((fs.inbox / "orchestrator").iterdir()).read_text())
        assert delivery["task_id"] == "nonexistent-task-id"
        assert delivery["context_id"] == "ctx-missing"

    def test_delivery_includes_correlation(self, setup):
        broker, store, fs, *_ = setup

        artifact_path = fs.outbox / "test.json"
        artifact_path.write_text("{}")

        data = {
            "type": "dispatch",
            "sender": "orchestrator",
            "recipient": "worker-1",
            "message": "build API",
        }
        broker.handle_artifact(artifact_path, data)

        # inbox 파일에 correlation 정보가 있는지 확인
        inbox_files = list((fs.inbox / "worker-1").iterdir())
        assert len(inbox_files) == 1

        import json
        delivery = json.loads(inbox_files[0].read_text())
        assert delivery["message_id"] is not None
        assert delivery["task_id"] is not None
        assert delivery["parts"] is not None
        assert len(delivery["parts"]) == 1
        assert delivery["parts"][0]["kind"] == "text"
