"""도메인 모델 테스트."""

import pytest

from cmux_agent.domain.models import (
    Agent,
    AgentRole,
    Message,
    MessageStatus,
    MessageType,
    Run,
    RunStatus,
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
