"""StateStore 테스트."""

import tempfile
from pathlib import Path

import pytest

from cmux_agent.domain.models import (
    Agent,
    AgentRole,
    Message,
    MessageType,
    Run,
    RunStatus,
)
from cmux_agent.infrastructure.storage import StateStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    s = StateStore(db_path)
    yield s
    s.close()


class TestRunCRUD:
    def test_save_and_get(self, store):
        run = Run(run_id="run-1")
        store.save_run(run)
        result = store.get_run("run-1")
        assert result is not None
        assert result.run_id == "run-1"
        assert result.status == RunStatus.CREATED

    def test_get_latest(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_run(Run(run_id="run-2"))
        latest = store.get_latest_run()
        assert latest is not None
        assert latest.run_id == "run-2"

    def test_get_active(self, store):
        store.save_run(Run(run_id="run-1", status=RunStatus.COMPLETED))
        store.save_run(Run(run_id="run-2", status=RunStatus.RUNNING))
        active = store.get_active_run()
        assert active is not None
        assert active.run_id == "run-2"

    def test_update_status(self, store):
        store.save_run(Run(run_id="run-1"))
        store.update_run_status("run-1", RunStatus.RUNNING)
        run = store.get_run("run-1")
        assert run.status == RunStatus.RUNNING

    def test_get_nonexistent(self, store):
        assert store.get_run("nonexistent") is None


class TestAgentCRUD:
    def test_save_and_list(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_agent(Agent(run_id="run-1", role=AgentRole.ORCHESTRATOR, name="orch"))
        store.save_agent(Agent(run_id="run-1", role=AgentRole.WORKER, name="w1"))

        agents = store.get_agents("run-1")
        assert len(agents) == 2
        assert agents[0].name == "orch"
        assert agents[1].name == "w1"

    def test_get_by_name(self, store):
        store.save_run(Run(run_id="run-1"))
        store.save_agent(Agent(run_id="run-1", role=AgentRole.WORKER, name="w1"))

        agent = store.get_agent_by_name("run-1", "w1")
        assert agent is not None
        assert agent.role == AgentRole.WORKER

    def test_get_by_name_not_found(self, store):
        store.save_run(Run(run_id="run-1"))
        assert store.get_agent_by_name("run-1", "nope") is None


class TestMessageCRUD:
    def test_save_and_list(self, store):
        store.save_run(Run(run_id="run-1"))
        msg = Message(
            run_id="run-1", sender="orch", recipient="w1",
            type=MessageType.DISPATCH, payload='{"test": true}',
        )
        store.save_message(msg)

        messages = store.get_messages("run-1")
        assert len(messages) == 1
        assert messages[0].sender == "orch"

    def test_pending_messages(self, store):
        store.save_run(Run(run_id="run-1"))
        msg = Message(
            run_id="run-1", sender="orch", recipient="w1",
            type=MessageType.DISPATCH, payload="{}",
        )
        store.save_message(msg)

        pending = store.get_pending_messages("run-1", "w1")
        assert len(pending) == 1

    def test_count_messages(self, store):
        store.save_run(Run(run_id="run-1"))
        m1 = Message(run_id="run-1", sender="a", recipient="b", payload="{}")
        m2 = Message(run_id="run-1", sender="b", recipient="a", payload="{}")
        m2.mark_delivered()
        store.save_message(m1)
        store.save_message(m2)

        counts = store.count_messages("run-1")
        assert counts.get("PENDING") == 1
        assert counts.get("DELIVERED") == 1
