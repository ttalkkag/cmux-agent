"""도메인 모델 테스트."""

import pytest

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


class TestRun:
    def test_create_default(self):
        run = Run()
        assert run.status == RunStatus.CREATED
        assert run.run_id
        assert run.workspace_id is None

    def test_transition_created_to_running(self):
        run = Run()
        run.transition_to(RunStatus.RUNNING)
        assert run.status == RunStatus.RUNNING

    def test_transition_running_to_completed(self):
        run = Run(status=RunStatus.RUNNING)
        run.transition_to(RunStatus.COMPLETED)
        assert run.status == RunStatus.COMPLETED

    def test_transition_running_to_failed(self):
        run = Run(status=RunStatus.RUNNING)
        run.transition_to(RunStatus.FAILED)
        assert run.status == RunStatus.FAILED

    def test_invalid_transition(self):
        run = Run()
        with pytest.raises(ValueError, match="전이 불가"):
            run.transition_to(RunStatus.COMPLETED)

    def test_transition_updates_timestamp(self):
        run = Run()
        old_ts = run.updated_at
        run.transition_to(RunStatus.RUNNING)
        assert run.updated_at >= old_ts


class TestAgent:
    def test_create_default(self):
        agent = Agent(run_id="run-1", role=AgentRole.WORKER, name="worker-1")
        assert agent.role == AgentRole.WORKER
        assert agent.name == "worker-1"
        assert agent.surface_id is None


class TestMessage:
    def test_mark_delivered(self):
        msg = Message(run_id="run-1", sender="a", recipient="b")
        msg.mark_delivered()
        assert msg.status == MessageStatus.DELIVERED
        assert msg.delivered_at is not None

    def test_mark_failed(self):
        msg = Message(run_id="run-1", sender="a", recipient="b")
        msg.mark_failed()
        assert msg.status == MessageStatus.FAILED

    def test_task_correlation_fields(self):
        msg = Message(
            run_id="run-1", sender="a", recipient="b",
            task_id="task-1", context_id="ctx-1",
        )
        assert msg.task_id == "task-1"
        assert msg.context_id == "ctx-1"

    def test_task_correlation_defaults_none(self):
        msg = Message(run_id="run-1", sender="a", recipient="b")
        assert msg.task_id is None
        assert msg.context_id is None


class TestPart:
    def test_create_text_part(self):
        p = Part(kind="text", text="hello")
        assert p.kind == "text"
        assert p.text == "hello"
        assert p.media_type == "text/plain"

    def test_create_data_part(self):
        p = Part(kind="data", data={"key": "value"}, media_type="application/json")
        assert p.kind == "data"
        assert p.data == {"key": "value"}
        assert p.text is None


class TestArtifact:
    def test_create_default(self):
        art = Artifact(task_id="task-1")
        assert art.artifact_id
        assert art.task_id == "task-1"
        assert art.parts == []

    def test_with_parts(self):
        parts = [Part(kind="text", text="result")]
        art = Artifact(task_id="task-1", parts=parts)
        assert len(art.parts) == 1
        assert art.parts[0].text == "result"


class TestTask:
    def test_create_default(self):
        task = Task(run_id="run-1")
        assert task.state == TaskState.SUBMITTED
        assert task.task_id
        assert task.context_id
        assert task.history_message_ids == []

    def test_transition_submitted_to_working(self):
        task = Task(run_id="run-1")
        task.transition_to(TaskState.WORKING)
        assert task.state == TaskState.WORKING

    def test_transition_working_to_completed(self):
        task = Task(run_id="run-1", state=TaskState.WORKING)
        task.transition_to(TaskState.COMPLETED)
        assert task.state == TaskState.COMPLETED

    def test_transition_working_to_failed(self):
        task = Task(run_id="run-1", state=TaskState.WORKING)
        task.transition_to(TaskState.FAILED)
        assert task.state == TaskState.FAILED

    def test_transition_submitted_to_failed(self):
        task = Task(run_id="run-1")
        task.transition_to(TaskState.FAILED)
        assert task.state == TaskState.FAILED

    def test_invalid_transition_submitted_to_completed(self):
        task = Task(run_id="run-1")
        with pytest.raises(ValueError, match="전이 불가"):
            task.transition_to(TaskState.COMPLETED)

    def test_invalid_transition_from_completed(self):
        task = Task(run_id="run-1", state=TaskState.WORKING)
        task.transition_to(TaskState.COMPLETED)
        with pytest.raises(ValueError, match="전이 불가"):
            task.transition_to(TaskState.WORKING)

    def test_invalid_transition_from_failed(self):
        task = Task(run_id="run-1")
        task.transition_to(TaskState.FAILED)
        with pytest.raises(ValueError, match="전이 불가"):
            task.transition_to(TaskState.WORKING)

    def test_transition_updates_timestamp(self):
        task = Task(run_id="run-1")
        old_ts = task.updated_at
        task.transition_to(TaskState.WORKING)
        assert task.updated_at >= old_ts

    def test_add_message(self):
        task = Task(run_id="run-1")
        task.add_message("msg-1")
        task.add_message("msg-2")
        assert task.history_message_ids == ["msg-1", "msg-2"]

